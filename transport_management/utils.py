"""Shared helpers: settings access, feature switches and notifications."""

import frappe
from frappe.utils import cint, get_datetime, now_datetime, time_diff_in_seconds

FEATURE_FLAGS = {
	"live_map": "enable_live_map",
	"dispatch_board": "enable_dispatch_board",
	"suggestions": "enable_suggestions",
	"public_tracking": "enable_public_tracking",
	"pod": "enable_pod",
	"service_areas": "enable_service_areas",
	"rate_cards": "enable_rate_cards",
	"issue_reporting": "enable_issue_reporting",
	"fuel_logs": "enable_fuel_logs",
	"geofence": "enable_geofence_alerts",
	"ratings": "enable_driver_ratings",
}

TM_ROLES = (
	"Transport Manager",
	"Transport Coordinator",
	"Transport Dispatcher",
	"Transport Driver",
	"Transport Integrator",
)


def get_settings():
	return frappe.get_cached_doc("Transport Settings")


def is_enabled(feature: str) -> bool:
	"""True when an optional (Fleetbase extra) feature is switched on in Transport Settings."""
	field = FEATURE_FLAGS.get(feature, feature)
	return bool(cint(get_settings().get(field)))


def require_feature(feature: str):
	if not is_enabled(feature):
		frappe.throw(frappe._("This feature is switched off in Transport Settings."), frappe.PermissionError)


def users_with_roles(roles) -> list[str]:
	if isinstance(roles, str):
		roles = [roles]
	users = frappe.get_all(
		"Has Role", filters={"role": ("in", roles), "parenttype": "User"}, pluck="parent", distinct=True
	)
	if not users:
		return []
	return frappe.get_all(
		"User", filters={"name": ("in", users), "enabled": 1, "user_type": "System User"}, pluck="name"
	)


def notify_users(users, subject, message, doctype=None, name=None, email=True):
	"""In-app Notification Log for every user; email as well when enabled in settings."""
	users = [u for u in set(users or []) if u and u not in ("Administrator", "Guest")]
	if not users:
		return
	for user in users:
		try:
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"subject": subject,
					"email_content": message,
					"document_type": doctype,
					"document_name": name,
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title="Transport notification failed")
	settings = get_settings()
	if email and cint(settings.notify_email):
		try:
			frappe.sendmail(recipients=users, subject=subject, message=message, delayed=True)
		except Exception:
			frappe.log_error(title="Transport email failed")
	if cint(settings.notify_sms):
		_send_sms(users, subject)


def notify_roles(roles, subject, message, doctype=None, name=None):
	notify_users(users_with_roles(roles), subject, message, doctype, name)


def _send_sms(users, text):
	try:
		from frappe.core.doctype.sms_settings.sms_settings import send_sms

		numbers = [n for n in frappe.get_all("User", filters={"name": ("in", users)}, pluck="mobile_no") if n]
		if numbers:
			send_sms(numbers, text[:160])
	except Exception:
		frappe.log_error(title="Transport SMS failed")


def age_minutes(ts) -> float | None:
	if not ts:
		return None
	return round(time_diff_in_seconds(now_datetime(), get_datetime(ts)) / 60.0, 1)


def is_stale(ts) -> bool:
	age = age_minutes(ts)
	return age is None or age > cint(get_settings().stale_location_minutes or 15)
