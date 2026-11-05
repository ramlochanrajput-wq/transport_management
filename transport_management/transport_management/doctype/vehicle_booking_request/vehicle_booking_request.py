import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime

from transport_management.services import availability, rates
from transport_management.utils import is_enabled

DEAD_STATES = ("Rejected", "Cancelled", "Converted")


class VehicleBookingRequest(Document):
	def validate(self):
		if get_datetime(self.to_datetime) <= get_datetime(self.from_datetime):
			frappe.throw(_("To Date/Time must be after From Date/Time"))
		self.check_overlap()
		if self.workflow_state == "Rejected" and not (self.rejection_reason or "").strip():
			frappe.throw(_("Rejection Reason is required"))
		self.try_auto_quote()

	def check_overlap(self):
		"""Soft overlap check on the requested vehicle (BRD 5.3). Full checks run at assignment."""
		if not self.preferred_vehicle or self.workflow_state in DEAD_STATES:
			return
		clashes = [
			f"Trip {t.name}"
			for t in availability.overlapping_trips(
				"vehicle", self.preferred_vehicle, self.from_datetime, self.to_datetime
			)
		] + [
			f"Booking {b.name}"
			for b in availability.overlapping_bookings(
				self.preferred_vehicle, self.from_datetime, self.to_datetime, exclude=self.name
			)
		]
		if clashes:
			frappe.throw(
				_("Vehicle {0} is already committed in this window: {1}").format(
					self.preferred_vehicle, ", ".join(clashes)
				)
			)

	def try_auto_quote(self):
		if not is_enabled("rate_cards") or self.quoted_rate:
			return
		rate = rates.find_rate(
			self.pickup_location, self.drop_location, self.vehicle_type, self.customer, self.from_datetime
		)
		if rate:
			self.freight_rate = rate.name
			self.quoted_rate = rates.compute_quote(rate, self.distance_km, self.required_capacity_kg)
			self.quote_details = f"{rate.rate_basis} @ {rate.rate}"


@frappe.whitelist()
def make_trip_plan(booking: str):
	"""Convert an approved booking into a Trip Plan (not saved: user reviews the assignment)."""
	b = frappe.get_doc("Vehicle Booking Request", booking)
	b.check_permission("read")
	if b.workflow_state != "Approved":
		frappe.throw(_("Only an Approved booking can be converted"))
	if b.trip_plan:
		frappe.throw(_("Already converted to {0}").format(b.trip_plan))
	frappe.has_permission("Trip Plan", "create", throw=True)

	trip = frappe.new_doc("Trip Plan")
	trip.update(
		{
			"booking": b.name,
			"customer": b.customer,
			"fleet": b.fleet,
			"trip_type": b.trip_type,
			"vehicle": b.preferred_vehicle,
			"driver": b.preferred_driver,
			"planned_start": b.from_datetime,
			"planned_end": b.to_datetime,
			"load_kg": b.required_capacity_kg,
			"from_location": b.pickup_location,
			"to_location": b.drop_location,
			"freight_amount": b.quoted_rate,
		}
	)
	trip.append("stops", {"sequence": 1, "stop_type": "Pickup", "location": b.pickup_location, "eta": b.from_datetime})
	trip.append("stops", {"sequence": 2, "stop_type": "Drop", "location": b.drop_location, "eta": b.to_datetime})
	return trip.as_dict()


def mark_converted(doc, method=None):
	"""Trip Plan after_insert: link back to the booking and close it as Converted."""
	if doc.booking:
		frappe.db.set_value(
			"Vehicle Booking Request",
			doc.booking,
			{"trip_plan": doc.name, "workflow_state": "Converted"},
			update_modified=True,
		)
