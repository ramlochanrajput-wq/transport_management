import frappe
from frappe import _
from frappe.model.document import Document


class OverrideLog(Document):
	"""Append-only audit record of every authorised override."""

	def validate(self):
		if not (self.reason or "").strip():
			frappe.throw(_("Reason is required"))
		if not self.is_new():
			frappe.throw(_("Override Log entries cannot be changed"))

	def on_trash(self):
		if not frappe.flags.in_test and frappe.session.user != "Administrator":
			frappe.throw(_("Override Log entries cannot be deleted"))
