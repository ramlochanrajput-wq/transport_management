"""Scheduled jobs (hooks.scheduler_events)."""

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, date_diff, flt, get_datetime, getdate, now_datetime, nowdate

from transport_management.services import geo, vehicle_status
from transport_management.transport_management.doctype.trip_issue.trip_issue import create_issue
from transport_management.utils import (
	get_settings,
	is_enabled,
	notify_roles,
	notify_users,
	users_with_roles,
)


# --------------------------------------------------------- daily: documents
def send_document_reminders():
	"""BRD 5.13: remind at configured days, escalate when close or expired."""
	settings = get_settings()
	days = settings.get_reminder_days()
	escalation = settings.document_escalation_role or "Transport Manager"
	today = getdate(nowdate())
	rows = frappe.db.sql(
		"""
		select d.name, d.parent, d.parenttype, d.document_type, d.expiry_date, d.last_reminder_on
		from `tabVehicle Document` d
		where d.expiry_date is not null and d.parenttype in ('Vehicle', 'Driver')
		""",
		as_dict=True,
	)
	fired = 0
	for r in rows:
		left = date_diff(r.expiry_date, today)
		expired = left < 0
		if not (expired or left in days):
			continue
		if r.last_reminder_on and getdate(r.last_reminder_on) == today:
			continue
		label = f"{r.parenttype} {r.parent}"
		if expired:
			subject = _("EXPIRED: {0} of {1} expired {2} day(s) ago").format(r.document_type, label, -left)
		else:
			subject = _("{0} of {1} expires in {2} day(s) on {3}").format(r.document_type, label, left, r.expiry_date)
		recipients = users_with_roles(["Transport Coordinator"])
		fleet = frappe.db.get_value(r.parenttype, r.parent, "tm_fleet") if frappe.get_meta(r.parenttype).has_field("tm_fleet") else None
		if fleet:
			manager = frappe.db.get_value("Transport Fleet", fleet, "fleet_manager")
			if manager:
				recipients.append(manager)
		if expired or left <= 7:  # escalate close-to-expiry and expired documents
			recipients += users_with_roles(escalation)
		notify_users(recipients, subject, subject, r.parenttype, r.parent)
		frappe.db.set_value("Vehicle Document", r.name, "last_reminder_on", today, update_modified=False)
		fired += 1

	# driver licence itself (ERPNext Driver.expiry_date)
	for d in frappe.get_all("Driver", filters={"expiry_date": ("is", "set"), "status": "Active"}, fields=["name", "expiry_date", "full_name"]):
		left = date_diff(d.expiry_date, today)
		if left < 0 or left in days:
			subject = _("Driving licence of {0} {1}").format(d.full_name or d.name, _("expired") if left < 0 else _("expires in {0} day(s)").format(left))
			notify_roles([escalation, "Transport Coordinator"], subject, subject, "Driver", d.name)
			fired += 1
	return fired


def purge_old_locations():
	days = cint(get_settings().location_retention_days)
	if days <= 0:
		return
	cutoff = add_to_date(now_datetime(), days=-days)
	frappe.db.delete("Driver Location Log", {"timestamp": ("<", cutoff)})


def refresh_vehicle_statuses():
	vehicle_status.refresh_all()


# ---------------------------------------------------------------- hourly
def check_stale_locations():
	"""Trips that are running but silent: raise a Missing GPS issue once."""
	if not is_enabled("issue_reporting"):
		return
	limit = max(cint(get_settings().stale_location_minutes), 1) * 4  # 4x the stale window before escalating
	cutoff = add_to_date(now_datetime(), minutes=-limit)
	for t in frappe.get_all(
		"Trip Plan",
		filters={"workflow_state": ("in", ("Started", "In Transit")), "actual_start": ("<", cutoff)},
		fields=["name", "last_seen", "vehicle"],
	):
		if not t.last_seen or get_datetime(t.last_seen) < cutoff:
			create_issue(t.name, "Missing GPS", _("No location received for {0} minutes").format(limit))


def check_geofence_and_idle():
	"""E17: leaving the assigned service area, or standing still too long."""
	if not is_enabled("geofence"):
		return
	idle_min = cint(get_settings().idle_alert_minutes)
	for t in frappe.get_all(
		"Trip Plan",
		filters={"workflow_state": ("in", ("Started", "In Transit"))},
		fields=["name", "vehicle", "service_area", "out_of_zone", "last_latitude", "last_longitude"],
	):
		if t.service_area and cint(t.out_of_zone):
			create_issue(t.name, "Geofence", _("Vehicle {0} is outside service area {1}").format(t.vehicle, t.service_area), latitude=t.last_latitude, longitude=t.last_longitude)
		if idle_min:
			since = add_to_date(now_datetime(), minutes=-idle_min)
			pts = frappe.get_all(
				"Driver Location Log",
				filters={"vehicle": t.vehicle, "timestamp": (">=", since)},
				fields=["latitude", "longitude"],
				limit=200,
			)
			if len(pts) >= 3:
				base = pts[0]
				if all(geo.haversine_km(flt(base.latitude), flt(base.longitude), flt(p.latitude), flt(p.longitude)) < 0.1 for p in pts):
					create_issue(t.name, "Idle", _("Vehicle {0} has not moved for {1} minutes").format(t.vehicle, idle_min), latitude=base.latitude, longitude=base.longitude)


# ------------------------------------------------------------- every 15 min
def check_delays():
	"""Running trips past their planned end, and approved trips that never started."""
	threshold = cint(get_settings().delay_threshold_minutes)
	limit = add_to_date(now_datetime(), minutes=-threshold)
	late = frappe.get_all(
		"Trip Plan",
		filters={"workflow_state": ("in", ("Started", "In Transit", "Arrived")), "planned_end": ("<", limit)},
		fields=["name", "planned_end"],
	)
	not_started = frappe.get_all(
		"Trip Plan",
		filters={"workflow_state": "Approved", "planned_start": ("<", limit)},
		fields=["name", "planned_start"],
	)
	for t in late:
		minutes = int((now_datetime() - get_datetime(t.planned_end)).total_seconds() / 60)
		frappe.db.set_value("Trip Plan", t.name, "delay_minutes", minutes, update_modified=False)
		create_issue(t.name, "Delay", _("Trip is {0} minutes past planned end").format(minutes))
	for t in not_started:
		create_issue(t.name, "Delay", _("Trip has not started; planned start was {0}").format(t.planned_start))
