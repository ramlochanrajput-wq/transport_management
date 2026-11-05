"""Derives Vehicle.tm_status from trips, maintenance and bookings (BRD 5.2)."""

import frappe
from frappe.utils import add_to_date, now_datetime

ACTIVE_RUN_STATES = ("Started", "In Transit", "Arrived")
BOOKED_STATES = ("Planned", "Approved")


def compute_status(vehicle: str) -> str:
	current = frappe.db.get_value("Vehicle", vehicle, "tm_status")
	if current == "Inactive":
		return "Inactive"  # manual state, never auto-overwritten

	if frappe.db.exists("Vehicle Maintenance Log", {"vehicle": vehicle, "status": ("!=", "Completed")}):
		return "Under Maintenance"

	if frappe.db.exists("Trip Plan", {"vehicle": vehicle, "workflow_state": ("in", ACTIVE_RUN_STATES)}):
		return "On Trip"

	horizon = add_to_date(now_datetime(), hours=24)
	if frappe.db.exists(
		"Trip Plan",
		{"vehicle": vehicle, "workflow_state": ("in", BOOKED_STATES), "planned_start": ("<=", horizon)},
	):
		return "Booked"
	return "Available"


def refresh_vehicle_status(vehicle: str | None):
	if not vehicle or not frappe.db.exists("Vehicle", vehicle):
		return
	new = compute_status(vehicle)
	if frappe.db.get_value("Vehicle", vehicle, "tm_status") != new:
		frappe.db.set_value("Vehicle", vehicle, "tm_status", new, update_modified=False)
		frappe.publish_realtime(
			"tm_vehicle_status", {"vehicle": vehicle, "status": new}, after_commit=True
		)


def refresh_all():
	"""Scheduler safety net: re-evaluate every vehicle (booked windows roll over with time)."""
	for v in frappe.get_all("Vehicle", pluck="name"):
		refresh_vehicle_status(v)
