import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from transport_management.transport_management.doctype.trip_plan.trip_plan import update_totals
from transport_management.utils import get_settings


class TripSettlement(Document):
	def validate(self):
		trip = frappe.db.get_value(
			"Trip Plan", self.trip_plan, ["workflow_state", "settlement"], as_dict=True
		)
		if trip.workflow_state != "Completed" and not (
			trip.workflow_state == "Settled" and trip.settlement == self.name
		):
			frappe.throw(_("Trip {0} must be Completed to settle (it is {1})").format(self.trip_plan, trip.workflow_state))
		pending = frappe.db.sql(
			"""select name from `tabTrip Expense` where trip_plan=%s and docstatus=0
			and ifnull(workflow_state,'')!='Rejected'""",
			self.trip_plan,
		)
		if pending:
			frappe.throw(
				_("Unapproved expenses remain: {0}. Approve or reject them first.").format(
					", ".join(p[0] for p in pending[:5])
				)
			)
		if not self.advances and not self.expenses:
			self.load_items()
		self.compute()

	def load_items(self):
		self.set("advances", [])
		self.set("expenses", [])
		for a in frappe.get_all(
			"Trip Advance",
			filters={"trip_plan": self.trip_plan, "docstatus": 1, "settlement": ("in", ("", None, self.name))},
			fields=["name", "amount", "purpose"],
		):
			self.append("advances", {"reference_doctype": "Trip Advance", "reference_name": a.name, "amount": a.amount, "description": a.purpose})
		for e in frappe.get_all(
			"Trip Expense",
			filters={"trip_plan": self.trip_plan, "docstatus": 1, "settlement": ("in", ("", None, self.name))},
			fields=["name", "amount", "expense_category"],
		):
			self.append("expenses", {"reference_doctype": "Trip Expense", "reference_name": e.name, "amount": e.amount, "description": e.expense_category})

	def compute(self):
		self.total_advance = sum(flt(a.amount) for a in self.advances)
		self.total_expense = sum(flt(e.amount) for e in self.expenses)
		self.net_amount = flt(self.total_expense) + flt(self.driver_allowance) - flt(self.total_advance)
		self.settlement_type = (
			"Payable to Driver" if self.net_amount > 0 else "Recoverable from Driver" if self.net_amount < 0 else "Nil"
		)

	def on_submit(self):
		for row, dt in [(r, "Trip Advance") for r in self.advances] + [(r, "Trip Expense") for r in self.expenses]:
			frappe.db.set_value(dt, row.reference_name, "settlement", self.name, update_modified=False)
		je = self.create_journal_entry()
		if je:
			self.db_set("journal_entry", je)
		frappe.db.set_value(
			"Trip Plan", self.trip_plan, {"workflow_state": "Settled", "settlement": self.name}, update_modified=True
		)
		update_totals(self.trip_plan)
		from transport_management.services.vehicle_status import refresh_vehicle_status

		refresh_vehicle_status(self.vehicle)

	def on_cancel(self):
		if self.journal_entry and frappe.db.exists("Journal Entry", self.journal_entry):
			status = frappe.db.get_value("Journal Entry", self.journal_entry, "docstatus")
			if status == 1:
				frappe.throw(_("Cancel the posted Journal Entry {0} first").format(self.journal_entry))
			if status == 0:
				frappe.delete_doc("Journal Entry", self.journal_entry, ignore_permissions=True, force=True)
		for dt in ("Trip Advance", "Trip Expense"):
			frappe.db.sql(f"update `tab{dt}` set settlement=null where settlement=%s", self.name)
		frappe.db.set_value("Trip Plan", self.trip_plan, {"workflow_state": "Completed", "settlement": None})
		update_totals(self.trip_plan)

	def create_journal_entry(self):
		"""Draft JE: Dr expenses (+allowance), Cr advance account, balance to cash or driver payable."""
		s = get_settings()
		if not (s.company and s.advance_account and s.cash_account):
			frappe.msgprint(_("Accounting is not configured in Transport Settings; no draft entry created."), alert=True)
			return None
		cost_center = s.default_cost_center
		je = frappe.new_doc("Journal Entry")
		je.company = s.company
		je.voucher_type = "Journal Entry"
		je.posting_date = self.posting_date
		je.cheque_no = self.name
		je.cheque_date = self.posting_date
		je.user_remark = f"Trip settlement {self.name} for {self.trip_plan}"
		je.tm_trip_plan, je.tm_vehicle = self.trip_plan, self.vehicle

		by_account = {}
		for e in self.expenses:
			cat = frappe.db.get_value("Trip Expense", e.reference_name, "expense_category")
			acct = frappe.db.get_value("Expense Category", cat, "default_account")
			if not acct:
				frappe.throw(_("Expense Category {0} has no Default Account").format(cat))
			by_account[acct] = by_account.get(acct, 0) + flt(e.amount)
		if flt(self.driver_allowance):
			if not s.driver_payable_account:
				frappe.throw(_("Set a Driver Payable Account in Transport Settings to book the allowance"))
			by_account[s.driver_payable_account] = by_account.get(s.driver_payable_account, 0) + flt(self.driver_allowance)
		for acct, amt in by_account.items():
			je.append("accounts", {"account": acct, "debit_in_account_currency": amt, "cost_center": cost_center})

		debits = sum(by_account.values())
		advance = flt(self.total_advance)
		# credit the advance account for what was consumed, never more than the advance given
		consumed = min(advance, debits)
		if consumed:
			je.append("accounts", {"account": s.advance_account, "credit_in_account_currency": consumed, "cost_center": cost_center})
		if debits > consumed:  # employee is owed money
			je.append("accounts", {"account": s.driver_payable_account or s.cash_account, "credit_in_account_currency": debits - consumed, "cost_center": cost_center})
		if advance > consumed:  # unspent advance returns to cash
			je.append("accounts", {"account": s.cash_account, "debit_in_account_currency": advance - consumed, "cost_center": cost_center})
			je.append("accounts", {"account": s.advance_account, "credit_in_account_currency": advance - consumed, "cost_center": cost_center})
		if not je.accounts:
			return None
		je.flags.ignore_permissions = True
		je.insert()
		return je.name


@frappe.whitelist()
def get_items(trip_plan: str):
	"""Return unsettled approved advances and expenses for the form's Fetch button."""
	frappe.has_permission("Trip Settlement", "create", throw=True)
	doc = frappe.new_doc("Trip Settlement")
	doc.trip_plan = trip_plan
	doc.load_items()
	doc.compute()
	return {"advances": [r.as_dict() for r in doc.advances], "expenses": [r.as_dict() for r in doc.expenses]}
