import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, time_diff_in_hours

from transport_management.services.vehicle_status import refresh_vehicle_status


class VehicleMaintenanceLog(Document):
	def validate(self):
		if self.end_datetime and get_datetime(self.end_datetime) < get_datetime(self.start_datetime):
			frappe.throw(_("End must be after Start"))
		if self.status == "Completed":
			if not self.end_datetime:
				frappe.throw(_("End Date/Time is required to complete maintenance"))
			if not flt(self.odometer):
				frappe.throw(_("Odometer at Service is required to complete maintenance"))
		if self.end_datetime:
			self.downtime_hours = round(time_diff_in_hours(self.end_datetime, self.start_datetime), 2)

	def on_update(self):
		before = self.get_doc_before_save()
		if before and before.vehicle != self.vehicle:
			refresh_vehicle_status(before.vehicle)
		if self.status == "Completed":
			updates = {}
			if flt(self.odometer) > flt(frappe.db.get_value("Vehicle", self.vehicle, "last_odometer")):
				updates["last_odometer"] = self.odometer
			if self.next_due_date:
				updates["tm_next_service_date"] = self.next_due_date
			if flt(self.next_due_odometer):
				updates["tm_next_service_odometer"] = self.next_due_odometer
			if updates:
				frappe.db.set_value("Vehicle", self.vehicle, updates, update_modified=False)
		refresh_vehicle_status(self.vehicle)

	def on_trash(self):
		vehicle = self.vehicle
		frappe.db.after_commit.add(lambda: refresh_vehicle_status(vehicle))
