import frappe
from frappe import _
from frappe.model.document import Document


class TransportSettings(Document):
	def validate(self):
		days = self.get_reminder_days()
		if not days:
			frappe.throw(_("Reminder Days must be a comma separated list of numbers, e.g. 30,15,7,1"))
		self.reminder_days = ",".join(str(d) for d in days)
		self.auto_assign = 0  # suggestions are advisory; auto-assign is intentionally unsupported

	def get_reminder_days(self):
		try:
			return sorted({int(x) for x in (self.reminder_days or "").split(",") if x.strip()}, reverse=True)
		except ValueError:
			return []

	def on_update(self):
		frappe.clear_cache(doctype=self.doctype)
