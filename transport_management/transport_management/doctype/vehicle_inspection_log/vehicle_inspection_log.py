import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class VehicleInspectionLog(Document):
	def validate(self):
		if self.is_new():
			self.uploaded_by = frappe.session.user
			self.uploaded_on = now_datetime()
		if self.trip_plan and not self.vehicle:
			self.vehicle = frappe.db.get_value("Trip Plan", self.trip_plan, "vehicle")
		if self.trip_plan:
			trip_vehicle = frappe.db.get_value("Trip Plan", self.trip_plan, "vehicle")
			if trip_vehicle and trip_vehicle != self.vehicle:
				frappe.throw(_("Vehicle does not match trip {0}").format(self.trip_plan))
