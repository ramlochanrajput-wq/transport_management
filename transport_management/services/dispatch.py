"""E3 smart assignment suggestions. Advisory only: nothing is assigned automatically."""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime, time_diff_in_hours

from transport_management.services import availability
from transport_management.services.geo import haversine_km
from transport_management.utils import require_feature


def _last_position(vehicle):
	row = frappe.db.get_value(
		"Vehicle", vehicle, ["tm_last_latitude", "tm_last_longitude", "tm_last_seen"], as_dict=True
	)
	if row and row.tm_last_latitude and row.tm_last_longitude:
		return row
	return None


def _idle_hours(vehicle):
	last_end = frappe.db.sql(
		"""select max(coalesce(actual_end, planned_end)) from `tabTrip Plan`
		where vehicle=%s and workflow_state not in ('Cancelled') and coalesce(actual_end, planned_end) <= %s""",
		(vehicle, now_datetime()),
	)[0][0]
	if not last_end:
		return 999.0
	return max(time_diff_in_hours(now_datetime(), last_end), 0)


def _eligible_driver(vehicle, start, end, exclude_trip, preferred=None):
	"""Best driver: preferred first, then the same fleet, with no failing checks."""
	fleet = frappe.db.get_value("Vehicle", vehicle, "tm_fleet")
	candidates = []
	if preferred:
		candidates.append(preferred)
	filters = {"status": "Active"}
	if fleet:
		filters["tm_fleet"] = fleet
	candidates += [d for d in frappe.get_all("Driver", filters=filters, pluck="name") if d != preferred]
	for d in candidates:
		if not availability.check_driver(d, start, end, exclude_trip):
			return d
	return None


@frappe.whitelist()
def suggest_for_booking(booking: str, limit: int = 5):
	"""Return a ranked list of {vehicle, driver, score, reasons} for a booking."""
	require_feature("suggestions")
	b = frappe.get_doc("Vehicle Booking Request", booking)
	b.check_permission("read")
	return rank(
		b.from_datetime,
		b.to_datetime,
		vehicle_type=b.vehicle_type,
		load_kg=b.required_capacity_kg,
		fleet=b.fleet,
		preferred_vehicle=b.preferred_vehicle,
		preferred_driver=b.preferred_driver,
		limit=cint(limit) or 5,
	)


def rank(start, end, vehicle_type=None, load_kg=None, fleet=None, preferred_vehicle=None,
         preferred_driver=None, limit=5, exclude_trip=None, ref_lat=None, ref_lon=None):
	filters = {"tm_status": ("not in", availability.BLOCKING_VEHICLE_STATUS)}
	if fleet:
		filters["tm_fleet"] = fleet
	if vehicle_type:
		filters["tm_vehicle_type"] = vehicle_type
	vehicles = frappe.get_all(
		"Vehicle", filters=filters, fields=["name", "tm_capacity_kg", "tm_vehicle_type", "tm_ownership"]
	)
	ranked = []
	for v in vehicles:
		if availability.check_vehicle(v.name, start, end, load_kg, exclude_trip):
			continue
		driver = _eligible_driver(v.name, start, end, exclude_trip, preferred_driver)
		if not driver:
			continue
		score, reasons = 50.0, []
		if v.name == preferred_vehicle:
			score += 25
			reasons.append(_("Requested vehicle"))
		# tightest capacity fit wins; wasted capacity lowers the score
		if load_kg and v.tm_capacity_kg:
			waste = max(v.tm_capacity_kg - load_kg, 0) / v.tm_capacity_kg
			score += round((1 - waste) * 15, 1)
			reasons.append(_("Capacity fit {0}%").format(round((1 - waste) * 100)))
		idle = _idle_hours(v.name)
		score += min(idle, 48) / 48 * 10  # longer idle -> fairer rotation
		reasons.append(_("Idle {0} h").format(round(min(idle, 999), 1)))
		pos = _last_position(v.name)
		if pos and ref_lat is not None and ref_lon is not None:
			dist = haversine_km(flt(pos.tm_last_latitude), flt(pos.tm_last_longitude), flt(ref_lat), flt(ref_lon))
			score += max(0, 20 - dist / 10)
			reasons.append(_("{0} km from pickup").format(round(dist, 1)))
		if v.tm_ownership == "Company Owned":
			score += 2
		ranked.append({"vehicle": v.name, "driver": driver, "score": round(score, 1), "reasons": reasons})
	ranked.sort(key=lambda r: -r["score"])
	return ranked[:limit]
