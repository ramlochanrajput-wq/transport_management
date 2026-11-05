import frappe
from frappe.model.document import Document

from transport_management.services import tracking
from transport_management.utils import is_stale


class DriverLocationLog(Document):
	def after_insert(self):
		"""Keep the "last known" snapshot on Vehicle and Trip Plan and push it to live maps."""
		# ignore out-of-order pings: only move the snapshot forward in time
		last = frappe.db.get_value("Vehicle", self.vehicle, "tm_last_seen")
		if last and self.timestamp and frappe.utils.get_datetime(self.timestamp) < frappe.utils.get_datetime(last):
			return
		frappe.db.set_value(
			"Vehicle",
			self.vehicle,
			{
				"tm_last_latitude": self.latitude,
				"tm_last_longitude": self.longitude,
				"tm_last_seen": self.timestamp,
			},
			update_modified=False,
		)
		if self.trip_plan:
			frappe.db.set_value(
				"Trip Plan",
				self.trip_plan,
				{"last_latitude": self.latitude, "last_longitude": self.longitude, "last_seen": self.timestamp},
				update_modified=False,
			)
			tracking.flag_out_of_zone(self.trip_plan, self.latitude, self.longitude)
		frappe.publish_realtime(
			"tm_location",
			{
				"vehicle": self.vehicle,
				"trip_plan": self.trip_plan,
				"lat": self.latitude,
				"lng": self.longitude,
				"seen": str(self.timestamp),
				"speed": self.speed_kmph,
				"stale": is_stale(self.timestamp),
			},
			doctype="Vehicle",
			after_commit=True,
		)
