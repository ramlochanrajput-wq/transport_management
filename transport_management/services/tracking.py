"""E4 public tracking data and the location ingest used by driver app and GPS devices."""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

from transport_management.services import geo
from transport_management.utils import age_minutes, get_settings, is_enabled, is_stale

TIMELINE_STATES = ["Planned", "Approved", "Started", "In Transit", "Arrived", "Completed"]
PUBLIC_CLOSED_STATES = ("Settled", "Cancelled")


def new_token() -> str:
	return frappe.generate_hash(length=24)


def public_view(token: str) -> dict | None:
	"""Read-only, minimal projection of a trip. Never exposes money, driver phone or documents."""
	if not token or not is_enabled("public_tracking"):
		return None
	name = frappe.db.get_value("Trip Plan", {"tracking_token": token, "tracking_enabled": 1})
	if not name:
		return None
	t = frappe.db.get_value(
		"Trip Plan",
		name,
		[
			"name", "workflow_state", "from_location", "to_location", "planned_start", "planned_end",
			"actual_start", "actual_end", "vehicle", "last_latitude", "last_longitude", "last_seen",
			"delay_minutes",
		],
		as_dict=True,
	)
	stops = frappe.get_all(
		"Trip Stop",
		filters={"parent": name, "parenttype": "Trip Plan"},
		fields=["sequence", "stop_type", "location", "status", "eta", "actual_arrival"],
		order_by="sequence asc, idx asc",
	)
	next_stop = next((s for s in stops if s.status in ("Pending", "Arrived")), None)
	eta = (next_stop or {}).get("eta") or t.planned_end
	closed = t.workflow_state in PUBLIC_CLOSED_STATES
	loc = None
	if t.last_latitude and t.last_longitude and not closed:
		loc = {
			"lat": t.last_latitude,
			"lng": t.last_longitude,
			"seen": t.last_seen,
			"age_minutes": age_minutes(t.last_seen),
			"stale": is_stale(t.last_seen),
		}
	timeline = []
	reached = TIMELINE_STATES.index(t.workflow_state) if t.workflow_state in TIMELINE_STATES else -1
	if t.workflow_state == "Settled":
		reached = len(TIMELINE_STATES) - 1
	for i, s in enumerate(TIMELINE_STATES):
		timeline.append({"state": s, "done": i <= reached, "current": i == reached})
	return {
		"trip": t.name,
		"status": t.workflow_state,
		"from": t.from_location,
		"to": t.to_location,
		"vehicle": t.vehicle,
		"eta": eta,
		"delay_minutes": t.delay_minutes,
		"timeline": timeline,
		"stops": stops,
		"location": loc,
		"closed": closed,
	}


def record_location(vehicle, lat, lng, speed=None, accuracy=None, trip_plan=None, driver=None,
                    timestamp=None, source="Mobile GPS"):
	"""Insert a Driver Location Log row (permission-checked by the caller)."""
	lat, lng = flt(lat), flt(lng)
	if not (-90 <= lat <= 90 and -180 <= lng <= 180):
		frappe.throw(_("Invalid coordinates"))
	log = frappe.get_doc(
		{
			"doctype": "Driver Location Log",
			"vehicle": vehicle,
			"driver": driver,
			"trip_plan": trip_plan,
			"latitude": lat,
			"longitude": lng,
			"speed_kmph": flt(speed),
			"accuracy_m": flt(accuracy),
			"timestamp": get_datetime(timestamp) if timestamp else now_datetime(),
			"source": source,
		}
	)
	log.insert(ignore_permissions=True)
	return log.name


def flag_out_of_zone(trip: str, lat, lng):
	"""E6: mark a trip when its position leaves the assigned service area."""
	if not is_enabled("service_areas"):
		return
	area = frappe.db.get_value("Trip Plan", trip, "service_area")
	if not area:
		return
	inside = geo.point_in_service_area(area, lat, lng)
	if inside is None:
		return
	frappe.db.set_value("Trip Plan", trip, "out_of_zone", 0 if inside else 1, update_modified=False)
