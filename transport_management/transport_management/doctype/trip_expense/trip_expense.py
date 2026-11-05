import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from transport_management.transport_management.doctype.trip_plan.trip_plan import update_totals
from transport_management.utils import get_settings, is_enabled, notify_roles

CLOSED = ("Cancelled", "Settled")


class TripExpense(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		state = frappe.db.get_value("Trip Plan", self.trip_plan, "workflow_state")
		if state in CLOSED:
			frappe.throw(_("Trip {0} is {1}; no expense can be added").format(self.trip_plan, state))
		cat = frappe.get_cached_doc("Expense Category", self.expense_category)
		if cat.receipt_required and not self.receipt:
			frappe.throw(_("Receipt is required for category {0}").format(cat.name))
		if cat.is_fuel and not flt(self.litres):
			frappe.throw(_("Litres are required for a fuel expense"))
		self.set_receipt_hash()
		self.check_duplicate_receipt()
		self.check_limits(cat)

	def after_insert(self):
		if self.over_limit and is_enabled("issue_reporting"):
			issue = frappe.get_doc(
				{
					"doctype": "Trip Issue",
					"trip_plan": self.trip_plan,
					"issue_type": "Over-limit Expense",
					"description": f"{self.name}: {self.limit_remark}",
				}
			)
			issue.insert(ignore_permissions=True)

	def on_submit(self):
		update_totals(self.trip_plan)
		cat = frappe.get_cached_doc("Expense Category", self.expense_category)
		if cat.is_fuel and is_enabled("fuel_logs"):
			self.create_fuel_log()

	def on_cancel(self):
		update_totals(self.trip_plan)
		if self.fuel_log and frappe.db.exists("Fuel Log", self.fuel_log):
			frappe.delete_doc("Fuel Log", self.fuel_log, ignore_permissions=True, force=True)

	# ------------------------------------------------------------- helpers
	def set_receipt_hash(self):
		self.receipt_hash = None
		if not self.receipt:
			return
		try:
			file_doc = frappe.get_doc("File", {"file_url": self.receipt})
			self.receipt_hash = hashlib.sha256(file_doc.get_content() or b"").hexdigest()
		except Exception:
			frappe.log_error(title="Receipt hash failed")

	def check_duplicate_receipt(self):
		if not (self.receipt_hash and get_settings().check_duplicate_receipts):
			return
		dup = frappe.db.get_value(
			"Trip Expense",
			{
				"receipt_hash": self.receipt_hash,
				"name": ("!=", self.name or ""),
				"docstatus": ("<", 2),
				"workflow_state": ("!=", "Rejected"),
			},
		)
		if dup:
			frappe.throw(_("This receipt was already used on {0}").format(dup), title=_("Duplicate receipt"))

	def check_limits(self, cat):
		notes = []
		cat_used = frappe.db.sql(
			"""select ifnull(sum(amount),0) from `tabTrip Expense`
			where trip_plan=%s and expense_category=%s and docstatus<2 and name!=%s
			and ifnull(workflow_state,'')!='Rejected'""",
			(self.trip_plan, self.expense_category, self.name or ""),
		)[0][0]
		if flt(cat.per_trip_limit) and flt(cat_used) + flt(self.amount) > flt(cat.per_trip_limit):
			notes.append(
				_("{0} total {1} exceeds category limit {2}").format(cat.name, flt(cat_used) + flt(self.amount), cat.per_trip_limit)
			)
		trip_type = frappe.db.get_value("Trip Plan", self.trip_plan, "trip_type")
		tt = frappe.get_cached_doc("Trip Type", trip_type) if trip_type else None
		if tt and flt(tt.expense_limit):
			all_used = frappe.db.sql(
				"""select ifnull(sum(amount),0) from `tabTrip Expense`
				where trip_plan=%s and docstatus<2 and name!=%s and ifnull(workflow_state,'')!='Rejected'""",
				(self.trip_plan, self.name or ""),
			)[0][0]
			if flt(all_used) + flt(self.amount) > flt(tt.expense_limit):
				notes.append(
					_("Trip expenses {0} exceed trip-type limit {1}").format(flt(all_used) + flt(self.amount), tt.expense_limit)
				)
		self.over_limit = 1 if notes else 0
		self.limit_remark = "; ".join(notes)
		self.needs_manager = 1 if (notes or (tt and flt(tt.approval_limit) and flt(self.amount) > flt(tt.approval_limit))) else 0

	def create_fuel_log(self):
		trip = frappe.db.get_value("Trip Plan", self.trip_plan, ["vehicle", "driver"], as_dict=True)
		log = frappe.get_doc(
			{
				"doctype": "Fuel Log",
				"vehicle": trip.vehicle,
				"driver": trip.driver,
				"trip_plan": self.trip_plan,
				"trip_expense": self.name,
				"fill_date": self.expense_date,
				"litres": self.litres,
				"amount": self.amount,
				"rate": flt(self.amount) / flt(self.litres) if flt(self.litres) else 0,
				"odometer": self.odometer,
				"fuel_type": frappe.db.get_value("Vehicle", trip.vehicle, "fuel_type"),
			}
		)
		log.insert(ignore_permissions=True)
		self.db_set("fuel_log", log.name)
