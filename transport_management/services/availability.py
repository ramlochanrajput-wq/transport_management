"""Single source of truth for "can this vehicle / driver be used in this window?".

Used by Vehicle Booking Request (soft check), Trip Plan assignment (hard check with
authorised override) and trip start. Every function returns plain data; callers decide
whether a failure blocks or can be overridden.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime

from transport_management.utils import get_settings

# Trip states that no longer occupy a vehicle / driver
FREE_TRIP_STATES = ("Cancelled", "Settled")
BLOCKING_VEHICLE_STATUS = ("Under Maintenance", "Inactive")


def _fail(check, message):
	return {"check": check, "message": message}


def _trip_window_sql():
	# effective end = actual end when known, else planned end
	return "COALESCE(actual_end, planned_end)"


def overlapping_trips(field, value, start, end, exclude=None):
	"""Trip Plans using `value` (vehicle or driver) whose window overlaps [start, end]."""
	if not (value and start and end):
		return []
	assert field in ("vehicle", "driver")
	rows = frappe.db.sql(
		f"""
		select name, planned_start, {_trip_window_sql()} as window_end, workflow_state
		from `tabTrip Plan`
		where {field} = %(value)s
			and ifnull(workflow_state, '') not in %(free)s
			and name != %(exclude)s
			and planned_start < %(end)s
			and {_trip_window_sql()} > %(start)s
		""",
		{
			"value": value,
			"free": FREE_TRIP_STATES,
			"exclude": exclude or "",
			"start": get_datetime(start),
			"end": get_datetime(end),
		},
		as_dict=True,
	)
	return rows


def overlapping_bookings(vehicle, start, end, exclude=None):
	"""Approved bookings that asked for the same preferred vehicle in the window."""
	if not (vehicle and start and end):
		return []
	return frappe.db.sql(
		"""
		select name, from_datetime, to_datetime from `tabVehicle Booking Request`
		where preferred_vehicle = %(v)s and workflow_state = 'Approved'
			and name != %(exclude)s and from_datetime < %(end)s and to_datetime > %(start)s
		""",
		{"v": vehicle, "exclude": exclude or "", "start": get_datetime(start), "end": get_datetime(end)},
		as_dict=True,
	)


def expired_documents(doctype, name, on_date, mandatory_only=True):
	"""Documents on the Vehicle / Driver that are expired on `on_date`."""
	filters = {"parent": name, "parenttype": doctype, "expiry_date": ("<", getdate(on_date))}
	if mandatory_only:
		filters["is_mandatory"] = 1
	return frappe.get_all(
		"Vehicle Document",
		filters=filters,
		fields=["document_type", "document_number", "expiry_date", "verified"],
	)


def unverified_mandatory_documents(doctype, name):
	return frappe.get_all(
		"Vehicle Document",
		filters={"parent": name, "parenttype": doctype, "is_mandatory": 1, "verified": 0},
		pluck="document_type",
	)


def check_vehicle(vehicle, start, end, load_kg=None, exclude_trip=None):
	failures = []
	if not vehicle:
		return failures
	if not frappe.db.exists("Vehicle", vehicle):
		return [_fail("vehicle", _("Vehicle {0} does not exist").format(vehicle))]
	v = frappe.db.get_value(
		"Vehicle", vehicle, ["tm_status", "tm_capacity_kg", "tm_vehicle_type"], as_dict=True
	)
	if v.tm_status in BLOCKING_VEHICLE_STATUS:
		failures.append(_fail("vehicle_status", _("Vehicle {0} is {1}").format(vehicle, v.tm_status)))

	if start and end:
		for t in overlapping_trips("vehicle", vehicle, start, end, exclude_trip):
			failures.append(_fail("overlap", _("Vehicle {0} is already on trip {1}").format(vehicle, t.name)))
		maint = frappe.db.sql(
			"""
			select name from `tabVehicle Maintenance Log`
			where vehicle = %s and status != 'Completed' and start_datetime < %s
				and (end_datetime is null or end_datetime > %s)
			""",
			(vehicle, get_datetime(end), get_datetime(start)),
		)
		for (m,) in maint:
			failures.append(_fail("maintenance", _("Vehicle {0} is in maintenance ({1})").format(vehicle, m)))

	if load_kg and v.tm_capacity_kg and load_kg > v.tm_capacity_kg:
		failures.append(
			_fail(
				"capacity",
				_("Load {0} kg exceeds capacity {1} kg of {2}").format(load_kg, v.tm_capacity_kg, vehicle),
			)
		)

	if cint(get_settings().block_assignment_on_expired_documents):
		ref = getdate(start) if start else getdate()
		for d in expired_documents("Vehicle", vehicle, ref):
			failures.append(
				_fail(
					"documents",
					_("{0} of {1} expired on {2}").format(d.document_type, vehicle, d.expiry_date),
				)
			)
	return failures


def driver_attendance_ok(driver, on_date):
	"""None = not applicable / not checkable, True/False otherwise."""
	settings = get_settings()
	if not cint(settings.require_driver_attendance) or settings.attendance_source != "HRMS":
		return None
	if getdate(on_date) > getdate():
		return None  # future dates cannot have attendance yet
	employee = frappe.db.get_value("Driver", driver, "employee")
	if not employee:
		return False
	day = getdate(on_date)
	if frappe.db.exists("DocType", "Attendance") and frappe.db.exists(
		"Attendance",
		{"employee": employee, "attendance_date": day, "docstatus": 1, "status": ("in", ("Present", "Work From Home", "Half Day"))},
	):
		return True
	if frappe.db.exists("DocType", "Employee Checkin"):
		if frappe.db.sql(
			"select name from `tabEmployee Checkin` where employee=%s and date(time)=%s limit 1",
			(employee, day),
		):
			return True
	return False


def check_driver(driver, start, end, exclude_trip=None):
	failures = []
	if not driver:
		return failures
	d = frappe.db.get_value("Driver", driver, ["status", "expiry_date", "full_name"], as_dict=True)
	if not d:
		return [_fail("driver", _("Driver {0} does not exist").format(driver))]
	if d.status and d.status != "Active":
		failures.append(_fail("driver_status", _("Driver {0} is {1}").format(driver, d.status)))
	ref_end = getdate(end) if end else getdate()
	if d.expiry_date and getdate(d.expiry_date) < ref_end:
		failures.append(
			_fail("licence", _("Licence of {0} expires/expired on {1}").format(driver, d.expiry_date))
		)
	if cint(get_settings().block_assignment_on_expired_documents):
		ref = getdate(start) if start else getdate()
		for doc in expired_documents("Driver", driver, ref):
			failures.append(
				_fail("documents", _("{0} of driver {1} expired on {2}").format(doc.document_type, driver, doc.expiry_date))
			)
	if start and end:
		for t in overlapping_trips("driver", driver, start, end, exclude_trip):
			failures.append(_fail("overlap", _("Driver {0} is already on trip {1}").format(driver, t.name)))
	if start and driver_attendance_ok(driver, start) is False:
		failures.append(
			_fail("attendance", _("No attendance / check-in found for {0} on {1}").format(driver, getdate(start)))
		)
	return failures


def validate_assignment(vehicle, driver, start, end, load_kg=None, exclude_trip=None):
	"""Full assignment validation. Returns a list of {check, message}; empty list = OK."""
	return check_vehicle(vehicle, start, end, load_kg, exclude_trip) + check_driver(
		driver, start, end, exclude_trip
	)


def is_vehicle_free(vehicle, start, end, exclude_trip=None, load_kg=None):
	return not check_vehicle(vehicle, start, end, load_kg, exclude_trip)


def format_failures(failures):
	return "<ul>" + "".join(f"<li>{frappe.utils.escape_html(f['message'])}</li>" for f in failures) + "</ul>"


@frappe.whitelist()
def check_assignment(vehicle=None, driver=None, start=None, end=None, load_kg=None, trip=None):
	"""Client-side pre-check used by the Trip Plan form."""
	frappe.has_permission("Trip Plan", "read", throw=True)
	return validate_assignment(vehicle, driver, start, end, float(load_kg or 0) or None, trip)
