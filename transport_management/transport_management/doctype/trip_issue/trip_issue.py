import frappe
from frappe import _
from frappe.model.document import Document

from transport_management.utils import get_settings, notify_roles, users_with_roles, notify_users


class TripIssue(Document):
	def validate(self):
		if self.status == "Resolved" and not (self.resolution or "").strip():
			frappe.throw(_("Resolution is required to resolve an issue"))

	def after_insert(self):
		if self.issue_type in ("Breakdown", "Accident") and self.vehicle:
			self.create_maintenance_log()
		self.notify()

	def create_maintenance_log(self):
		log = frappe.get_doc(
			{
				"doctype": "Vehicle Maintenance Log",
				"vehicle": self.vehicle,
				"maintenance_type": "Breakdown" if self.issue_type == "Breakdown" else "Accident",
				"status": "Open",
				"description": f"{self.issue_type} reported on trip {self.trip_plan}: {self.description}",
				"trip_issue": self.name,
			}
		)
		log.insert(ignore_permissions=True)
		self.db_set("maintenance_log", log.name)

	def notify(self):
		users = users_with_roles(["Transport Manager", "Transport Dispatcher"])
		extra = get_settings().dispatcher_email
		subject = _("{0} reported on trip {1}").format(self.issue_type, self.trip_plan or "-")
		notify_users(users, subject, f"{self.description}<br>{frappe.utils.get_url_to_form(self.doctype, self.name)}", self.doctype, self.name)
		if extra:
			try:
				frappe.sendmail(recipients=[extra], subject=subject, message=self.description or "", delayed=True)
			except Exception:
				frappe.log_error(title="Dispatcher email failed")


def create_issue(trip_plan, issue_type, description, dedupe=True, **extra):
	"""Create a system-raised Trip Issue; with dedupe it skips if an open one of the same type exists."""
	if dedupe and frappe.db.exists(
		"Trip Issue", {"trip_plan": trip_plan, "issue_type": issue_type, "status": ("!=", "Resolved")}
	):
		return None
	doc = frappe.get_doc(
		{"doctype": "Trip Issue", "trip_plan": trip_plan, "issue_type": issue_type, "description": description, **extra}
	)
	doc.insert(ignore_permissions=True)
	return doc.name
