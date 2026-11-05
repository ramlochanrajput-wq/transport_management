"""Row-level scoping: drivers see only their own records; everyone else is governed by
role permissions plus User Permissions on Transport Fleet."""

import frappe

STAFF_ROLES = {"Transport Manager", "Transport Coordinator", "Transport Dispatcher", "Accounts User", "System Manager"}


def _is_driver_only(user):
	if user == "Administrator":
		return False
	roles = set(frappe.get_roles(user))
	return "Transport Driver" in roles and not roles & STAFF_ROLES


def _driver_clause(table, user):
	drivers = frappe.get_all("Driver", filters={"user": user}, pluck="name")
	if not drivers:
		return "1=0"
	quoted = ", ".join(frappe.db.escape(d) for d in drivers)
	return f"`tab{table}`.`driver` in ({quoted})"


def trip_plan_query(user=None):
	user = user or frappe.session.user
	return _driver_clause("Trip Plan", user) if _is_driver_only(user) else ""


def trip_expense_query(user=None):
	user = user or frappe.session.user
	return _driver_clause("Trip Expense", user) if _is_driver_only(user) else ""


def trip_issue_query(user=None):
	user = user or frappe.session.user
	return _driver_clause("Trip Issue", user) if _is_driver_only(user) else ""


def fuel_log_query(user=None):
	user = user or frappe.session.user
	return _driver_clause("Fuel Log", user) if _is_driver_only(user) else ""


def trip_plan_has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if not _is_driver_only(user):
		return True
	drivers = frappe.get_all("Driver", filters={"user": user}, pluck="name")
	return doc.driver in drivers
