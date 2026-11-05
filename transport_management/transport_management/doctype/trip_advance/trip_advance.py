import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from transport_management.transport_management.doctype.trip_plan.trip_plan import update_totals
from transport_management.utils import get_settings

CLOSED = ("Cancelled", "Settled")


class TripAdvance(Document):
	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		state = frappe.db.get_value("Trip Plan", self.trip_plan, "workflow_state")
		if state in CLOSED:
			frappe.throw(_("Trip {0} is {1}; no advance can be given").format(self.trip_plan, state))
		self.check_limit()

	def check_limit(self):
		trip_type = frappe.db.get_value("Trip Plan", self.trip_plan, "trip_type")
		limit = flt(frappe.db.get_value("Trip Type", trip_type, "advance_limit")) if trip_type else 0
		if not limit:
			return
		given = frappe.db.sql(
			"select ifnull(sum(amount),0) from `tabTrip Advance` where trip_plan=%s and docstatus<2 and name!=%s",
			(self.trip_plan, self.name or ""),
		)[0][0]
		if flt(given) + flt(self.amount) > limit:
			roles = set(frappe.get_roles())
			if not roles & {"Transport Manager", "System Manager"}:
				frappe.throw(
					_("Total advances {0} would exceed the limit {1} for this trip type. Ask a Transport Manager.").format(
						flt(given) + flt(self.amount), limit
					)
				)
			self.flags.over_limit = (flt(given) + flt(self.amount), limit)

	def on_update(self):
		if self.flags.get("over_limit") and not self.flags.get("override_logged"):
			total, limit = self.flags.over_limit
			frappe.get_doc(
				{
					"doctype": "Override Log",
					"reference_doctype": "Trip Advance",
					"reference_name": self.name,
					"override_type": "Advance Limit",
					"failed_checks": _("Total advances {0} exceed limit {1}").format(total, limit),
					"reason": self.purpose or _("Approved by manager"),
				}
			).insert(ignore_permissions=True)
			self.flags.override_logged = True

	def on_submit(self):
		result = self.create_payment_document()
		if result:
			doctype, name = result
			self.db_set("payment_entry" if doctype == "Payment Entry" else "journal_entry", name)
		update_totals(self.trip_plan)

	def on_cancel(self):
		for doctype, name in (("Payment Entry", self.payment_entry), ("Journal Entry", self.journal_entry)):
			if name and frappe.db.exists(doctype, name):
				status = frappe.db.get_value(doctype, name, "docstatus")
				if status == 1:
					frappe.throw(_("Cancel the posted {0} {1} first").format(doctype, name))
				if status == 0:
					frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
		update_totals(self.trip_plan)

	def create_payment_document(self):
		"""Draft Payment Entry (driver has an Employee) or draft Journal Entry. Posting is for Accounts."""
		s = get_settings()
		if not (s.company and s.advance_account and s.cash_account):
			frappe.msgprint(
				_("Accounting is not configured in Transport Settings; no draft accounting entry was created."),
				alert=True,
			)
			return None
		vehicle = frappe.db.get_value("Trip Plan", self.trip_plan, "vehicle")
		employee = frappe.db.get_value("Driver", self.driver, "employee") if self.driver else None
		if employee:
			pe = frappe.new_doc("Payment Entry")
			pe.payment_type = "Pay"
			pe.company = s.company
			pe.posting_date = self.requested_on
			pe.mode_of_payment = self.mode_of_payment or s.advance_mode_of_payment
			pe.party_type = "Employee"
			pe.party = employee
			pe.paid_from = s.cash_account
			pe.paid_to = s.advance_account
			pe.paid_amount = pe.received_amount = flt(self.amount)
			pe.reference_no = self.name
			pe.reference_date = self.requested_on
			pe.remarks = f"Trip advance {self.name} for {self.trip_plan}"
			pe.tm_trip_plan, pe.tm_vehicle = self.trip_plan, vehicle
			pe.flags.ignore_permissions = True
			pe.insert()
			return ("Payment Entry", pe.name)
		je = frappe.new_doc("Journal Entry")
		je.company = s.company
		je.voucher_type = "Journal Entry"
		je.posting_date = self.requested_on
		je.cheque_no = self.name
		je.cheque_date = self.requested_on
		je.user_remark = f"Trip advance {self.name} for {self.trip_plan}"
		je.tm_trip_plan, je.tm_vehicle = self.trip_plan, vehicle
		je.append("accounts", {"account": s.advance_account, "debit_in_account_currency": flt(self.amount), "cost_center": s.default_cost_center})
		je.append("accounts", {"account": s.cash_account, "credit_in_account_currency": flt(self.amount), "cost_center": s.default_cost_center})
		je.flags.ignore_permissions = True
		je.insert()
		return ("Journal Entry", je.name)
