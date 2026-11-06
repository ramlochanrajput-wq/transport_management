"""Whitelisted endpoints for the driver PWA, GPS devices and external integrators (E14).

Driver endpoints only ever touch trips of the Driver linked to the calling user.
Integrators authenticate with a normal Frappe API key/secret (Authorization: token key:secret).
"""

import frappe
from frappe.rate_limiter import rate_limit
from frappe import _
from frappe.utils import cint, flt, get_datetime, now_datetime

from transport_management.services import availability, dispatch, rates, tracking
from transport_management.services.vehicle_status import refresh_vehicle_status
from transport_management.utils import age_minutes, is_enabled, is_stale, require_feature

DRIVER_TRANSITIONS = {
	"start": ("Approved", "Started"),
	"in_transit": ("Started", "In Transit"),
	"arrive": (("Started", "In Transit"), "Arrived"),
	"complete": ("Arrived", "Completed"),
}


# ----------------------------------------------------------------- helpers
def _my_drivers() -> list[str]:
	return frappe.get_all("Driver", filters={"user": frappe.session.user}, pluck="name")


def _own_trip(trip: str):
	doc = frappe.get_doc("Trip Plan", trip)
	if doc.driver not in _my_drivers() and not (set(frappe.get_roles()) & {"Transport Manager", "Transport Dispatcher", "System Manager"}):
		frappe.throw(_("This trip is not assigned to you"), frappe.PermissionError)
	return doc


# ------------------------------------------------------------ driver app
@frappe.whitelist()
def my_trips():
	drivers = _my_drivers()
	if not drivers:
		return []
	trips = frappe.get_all(
		"Trip Plan",
		filters={"driver": ("in", drivers), "workflow_state": ("in", ("Approved", "Started", "In Transit", "Arrived", "On Hold", "Planned"))},
		fields=["name", "workflow_state", "vehicle", "driver", "from_location", "to_location", "planned_start",
		        "planned_end", "trip_type", "start_odometer", "end_odometer"],
		order_by="planned_start asc",
	)
	for t in trips:
		t["stops"] = frappe.get_all(
			"Trip Stop", filters={"parent": t.name}, fields=["name", "sequence", "stop_type", "location", "status", "eta"], order_by="sequence asc"
		)
		tt = frappe.get_cached_doc("Trip Type", t.trip_type) if t.trip_type else None
		t["rules"] = {
			"start_odometer": bool(tt and tt.requires_start_odometer),
			"end_odometer": bool(tt and tt.requires_end_odometer),
			"plate_photo": bool(tt and tt.requires_number_plate_photo),
			"pod": bool(tt and tt.requires_pod) and is_enabled("pod"),
		}
	return trips


@frappe.whitelist()
def expense_categories():
	return frappe.get_all("Expense Category", fields=["name", "receipt_required", "is_fuel"])


@frappe.whitelist()
def trip_action(trip, action, odometer=None, lat=None, lng=None, delay_reason=None):
	if action not in DRIVER_TRANSITIONS:
		frappe.throw(_("Unknown action"))
	doc = _own_trip(trip)
	src, dst = DRIVER_TRANSITIONS[action]
	allowed = (src,) if isinstance(src, str) else src
	if doc.workflow_state not in allowed:
		frappe.throw(_("Trip is {0}; cannot {1}").format(doc.workflow_state, action))
	if action == "start":
		doc.start_odometer = flt(odometer) or doc.start_odometer
	elif action == "complete":
		doc.end_odometer = flt(odometer) or doc.end_odometer
		if delay_reason:
			doc.delay_reason = delay_reason
	doc.workflow_state = dst
	doc.flags.ignore_permissions = True
	doc.save()
	if lat and lng and doc.vehicle:
		tracking.record_location(doc.vehicle, lat, lng, trip_plan=doc.name, driver=doc.driver, source="Mobile GPS")
	return {"state": doc.workflow_state, "tracking_url": public_tracking_url(doc)}


@frappe.whitelist()
def update_stop(trip, stop, status, lat=None, lng=None, proof=None):
	if status not in ("Arrived", "Completed", "Skipped"):
		frappe.throw(_("Invalid stop status"))
	doc = _own_trip(trip)
	row = next((s for s in doc.stops if s.name == stop), None)
	if not row:
		frappe.throw(_("Stop not found"))
	row.status = status
	if status == "Arrived":
		row.actual_arrival = now_datetime()
	if status in ("Completed", "Skipped"):
		row.actual_departure = now_datetime()
	if lat and lng:
		row.latitude, row.longitude = flt(lat), flt(lng)
	if proof:
		row.proof = proof
	doc.flags.ignore_permissions = True
	doc.save()
	return True


@frappe.whitelist()
def post_location(vehicle=None, lat=None, lng=None, speed=None, accuracy=None, trip_plan=None,
                  timestamp=None, source="Mobile GPS"):
	"""Driver app or a GPS device pushes a position. A driver may only report for their own trip."""
	roles = set(frappe.get_roles())
	driver = None
	if "Transport Integrator" in roles or "Transport Manager" in roles or "System Manager" in roles:
		if not vehicle:
			frappe.throw(_("vehicle is required"))
	else:
		drivers = _my_drivers()
		if not drivers:
			frappe.throw(_("No driver is linked to your user"), frappe.PermissionError)
		driver = drivers[0]
		if trip_plan:
			t = frappe.db.get_value("Trip Plan", trip_plan, ["driver", "vehicle"], as_dict=True)
			if not t or t.driver not in drivers:
				frappe.throw(_("This trip is not assigned to you"), frappe.PermissionError)
			vehicle = t.vehicle
		else:
			active = frappe.db.get_value(
				"Trip Plan", {"driver": ("in", drivers), "workflow_state": ("in", ("Started", "In Transit", "Arrived"))}, ["name", "vehicle"], as_dict=True
			)
			if not active:
				frappe.throw(_("No active trip"))
			trip_plan, vehicle = active.name, active.vehicle
	return tracking.record_location(vehicle, lat, lng, speed, accuracy, trip_plan, driver, timestamp, source)


@frappe.whitelist()
def add_expense(trip, expense_category, amount, receipt=None, description=None, litres=None, odometer=None,
                expense_date=None):
	doc = _own_trip(trip)
	exp = frappe.get_doc(
		{
			"doctype": "Trip Expense",
			"trip_plan": doc.name,
			"expense_category": expense_category,
			"amount": flt(amount),
			"receipt": receipt,
			"description": description,
			"litres": flt(litres),
			"odometer": flt(odometer),
			"expense_date": expense_date or frappe.utils.today(),
			"workflow_state": "Draft",
		}
	)
	exp.flags.ignore_permissions = True
	exp.insert()
	return exp.name


@frappe.whitelist()
def add_inspection(trip, inspection_type, photo, odometer=None, lat=None, lng=None, remarks=None):
	doc = _own_trip(trip)
	log = frappe.get_doc(
		{
			"doctype": "Vehicle Inspection Log",
			"trip_plan": doc.name,
			"vehicle": doc.vehicle,
			"inspection_type": inspection_type,
			"photo": photo,
			"odometer": flt(odometer),
			"latitude": flt(lat),
			"longitude": flt(lng),
			"remarks": remarks,
		}
	)
	log.flags.ignore_permissions = True
	log.insert()
	return log.name


@frappe.whitelist()
def report_issue(trip, issue_type, description, photo=None, lat=None, lng=None):
	require_feature("issue_reporting")
	doc = _own_trip(trip)
	issue = frappe.get_doc(
		{
			"doctype": "Trip Issue",
			"trip_plan": doc.name,
			"issue_type": issue_type,
			"description": description,
			"photo": photo,
			"latitude": flt(lat),
			"longitude": flt(lng),
		}
	)
	issue.flags.ignore_permissions = True
	issue.insert()
	return issue.name


@frappe.whitelist()
def submit_pod(trip, receiver_name, signature=None, photo=None, otp=None, remarks=None, stop_sequence=None):
	from transport_management.transport_management.doctype.trip_plan.trip_plan import _delivery_otp

	require_feature("pod")
	doc = _own_trip(trip)
	doc.append(
		"proofs",
		{
			"receiver_name": receiver_name,
			"signature": signature,
			"photo": photo,
			"remarks": remarks,
			"stop_sequence": cint(stop_sequence),
			"delivered_on": now_datetime(),
			"otp_verified": 1 if otp and str(otp) == _delivery_otp(doc.name) else 0,
		},
	)
	doc.flags.ignore_permissions = True
	doc.save()
	return True


def public_tracking_url(doc):
	if doc.tracking_token and is_enabled("public_tracking") and doc.tracking_enabled:
		return frappe.utils.get_url(f"/track/{doc.tracking_token}")
	return None


# ------------------------------------------------------------ live map
@frappe.whitelist()
def fleet_positions(status=None, vehicle_type=None, fleet=None):
	"""E1: one row per vehicle with colour-ready status, age and stale flag. Never claims "live"."""
	require_feature("live_map")
	frappe.has_permission("Vehicle", "read", throw=True)
	filters = {}
	if status:
		filters["tm_status"] = status
	if vehicle_type:
		filters["tm_vehicle_type"] = vehicle_type
	if fleet:
		filters["tm_fleet"] = fleet
	rows = frappe.get_list(
		"Vehicle",
		filters=filters,
		fields=["name", "license_plate", "tm_status", "tm_vehicle_type", "tm_fleet", "tm_last_latitude", "tm_last_longitude", "tm_last_seen"],
		limit_page_length=0,
	)
	trips = {
		t.vehicle: t
		for t in frappe.get_all(
			"Trip Plan",
			filters={"workflow_state": ("in", ("Started", "In Transit", "Arrived"))},
			fields=["name", "vehicle", "driver_name", "from_location", "to_location", "workflow_state", "planned_end"],
		)
	}
	out = []
	for r in rows:
		t = trips.get(r.name)
		out.append(
			{
				"vehicle": r.name,
				"plate": r.license_plate,
				"status": r.tm_status,
				"type": r.tm_vehicle_type,
				"fleet": r.tm_fleet,
				"lat": r.tm_last_latitude,
				"lng": r.tm_last_longitude,
				"last_seen": r.tm_last_seen,
				"age_minutes": age_minutes(r.tm_last_seen),
				"stale": is_stale(r.tm_last_seen),
				"has_position": bool(r.tm_last_latitude and r.tm_last_longitude),
				"trip": t,
			}
		)
	return out


# --------------------------------------------------------- dispatch board
@frappe.whitelist()
def dispatch_board():
	"""E2: bookings and trips grouped by status for the board page."""
	require_feature("dispatch_board")
	frappe.has_permission("Trip Plan", "read", throw=True)
	bookings = frappe.get_list(
		"Vehicle Booking Request",
		filters={"workflow_state": ("in", ("Submitted", "Approved"))},
		fields=["name", "customer", "pickup_location", "drop_location", "from_datetime", "workflow_state", "trip_type"],
		order_by="from_datetime asc",
		limit_page_length=200,
	)
	trips = frappe.get_list(
		"Trip Plan",
		filters={"workflow_state": ("in", ("Planned", "Approved", "Started", "In Transit", "Arrived", "On Hold"))},
		fields=["name", "vehicle", "driver_name", "from_location", "to_location", "planned_start", "workflow_state"],
		order_by="planned_start asc",
		limit_page_length=300,
	)
	return {"bookings": bookings, "trips": trips}


@frappe.whitelist()
def assign_from_board(trip, vehicle=None, driver=None):
	"""Drag-to-assign: runs the normal Trip Plan validation (and its override rules)."""
	doc = frappe.get_doc("Trip Plan", trip)
	doc.check_permission("write")
	if vehicle:
		doc.vehicle = vehicle
	if driver:
		doc.driver = driver
	doc.save()
	return doc.name


@frappe.whitelist()
def suggest(booking):
	return dispatch.suggest_for_booking(booking)


@frappe.whitelist()
def quote(booking):
	return rates.get_quote(booking)


@frappe.whitelist()
def sales_order_from_quote(booking):
	return rates.make_sales_order(booking)


# ------------------------------------------------------- integrators (E14)
@frappe.whitelist()
def create_booking(pickup_location, drop_location, from_datetime, to_datetime, customer=None, trip_type=None,
                   vehicle_type=None, required_capacity_kg=None, purpose=None, contact_person=None,
                   contact_phone=None, submit=1):
	"""Create (and by default submit for approval) a booking. Requires role Transport Integrator."""
	if not set(frappe.get_roles()) & {"Transport Integrator", "Transport Manager", "Transport Coordinator", "System Manager"}:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if not trip_type:
		frappe.throw(_("trip_type is required"))
	doc = frappe.get_doc(
		{
			"doctype": "Vehicle Booking Request",
			"pickup_location": pickup_location,
			"drop_location": drop_location,
			"from_datetime": from_datetime,
			"to_datetime": to_datetime,
			"customer": customer,
			"trip_type": trip_type,
			"vehicle_type": vehicle_type,
			"required_capacity_kg": flt(required_capacity_kg),
			"purpose": purpose,
			"contact_person": contact_person,
			"contact_phone": contact_phone,
			"workflow_state": "Draft",
		}
	)
	doc.insert()
	if cint(submit):
		from frappe.model.workflow import apply_workflow

		doc = apply_workflow(doc, "Submit Request")
	return {"name": doc.name, "state": doc.workflow_state, "quoted_rate": doc.quoted_rate}


@frappe.whitelist()
def booking_status(name):
	doc = frappe.get_doc("Vehicle Booking Request", name)
	doc.check_permission("read")
	return {"name": doc.name, "state": doc.workflow_state, "trip_plan": doc.trip_plan}


@frappe.whitelist(allow_guest=True)
def submit_feedback(token, rating, comments=None):
	"""E19: the party rates a completed trip through the public tracking page."""
	require_feature("ratings")
	trip = frappe.db.get_value("Trip Plan", {"tracking_token": token, "tracking_enabled": 1}, ["name", "workflow_state"], as_dict=True)
	if not trip or trip.workflow_state not in ("Completed", "Settled"):
		frappe.throw(_("Feedback is open only for completed trips"))
	if frappe.db.exists("Trip Feedback", {"trip_plan": trip.name}):
		frappe.throw(_("Feedback was already submitted"))
	r = flt(rating)
	if not 0 <= r <= 1:
		frappe.throw(_("Rating must be between 0 and 1"))
	frappe.get_doc({"doctype": "Trip Feedback", "trip_plan": trip.name, "rating": r, "comments": (comments or "")[:500]}).insert(ignore_permissions=True)
	return True


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=120, seconds=60)
def public_tracking(token):
	"""JSON twin of /track/<token> used by the page's auto-refresh. Read-only, no login."""
	data = tracking.public_view(token)
	if not data:
		frappe.throw(_("Tracking link not found"), frappe.DoesNotExistError)
	return data
