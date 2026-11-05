"""Idempotent setup: roles, custom fields on ERPNext doctypes, workflows, defaults, notifications.

Runs after install and after every migrate. Nothing in ERPNext/Frappe/HRMS source is touched:
all additions are Custom Fields and ordinary records owned by this app.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from transport_management.setup.workflows import WORKFLOWS

ROLES = [
	"Transport Manager",
	"Transport Coordinator",
	"Transport Dispatcher",
	"Transport Driver",
	"Transport Integrator",
]

DOCUMENT_TYPES = [
	# (name, applies_to, mandatory)
	("Registration Certificate", "Vehicle", 1),
	("Insurance", "Vehicle", 1),
	("Fitness Certificate", "Vehicle", 1),
	("Pollution (PUC)", "Vehicle", 1),
	("Road Tax", "Vehicle", 0),
	("National Permit", "Vehicle", 0),
	("Driving Licence", "Driver", 1),
	("Medical Fitness", "Driver", 0),
]

TRIP_TYPES = [
	dict(trip_type_name="Local", requires_start_odometer=1, requires_end_odometer=1, requires_pod=0,
	     requires_stops=0, expense_limit=2000, approval_limit=1000),
	dict(trip_type_name="Outstation", requires_start_odometer=1, requires_end_odometer=1,
	     requires_number_plate_photo=1, requires_pod=1, requires_stops=1, advance_limit=20000,
	     expense_limit=25000, approval_limit=5000),
	dict(trip_type_name="Loading Only", requires_start_odometer=0, requires_end_odometer=0, requires_pod=0,
	     requires_stops=0, expense_limit=500, approval_limit=500),
]

EXPENSE_CATEGORIES = [
	dict(category_name="Fuel", is_fuel=1, receipt_required=1),
	dict(category_name="Toll", receipt_required=1),
	dict(category_name="Parking", receipt_required=0),
	dict(category_name="Driver Food", receipt_required=0, per_trip_limit=1500),
	dict(category_name="Loading / Unloading", receipt_required=0),
	dict(category_name="Minor Repair", receipt_required=1),
	dict(category_name="Police / RTO Fine", receipt_required=1),
]


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	create_roles()
	create_custom_field_set()
	create_defaults()
	create_workflows()
	create_notifications()
	frappe.db.commit()


# --------------------------------------------------------------------- roles
def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 0 if role in ("Transport Integrator",) else 1}).insert(ignore_permissions=True)


# ------------------------------------------------------------- custom fields
def _last_field(doctype):
	return frappe.get_meta(doctype).fields[-1].fieldname


def _chain(doctype, fields, start_after=None):
	prev = start_after or _last_field(doctype)
	for f in fields:
		f["insert_after"] = prev
		prev = f["fieldname"]
	return fields


def create_custom_field_set():
	vehicle = _chain(
		"Vehicle",
		[
			dict(fieldname="tm_section", fieldtype="Section Break", label="Transport Management", collapsible=0),
			dict(fieldname="tm_status", fieldtype="Select", label="Fleet Status", in_list_view=0, in_standard_filter=1,
			     options="Available\nBooked\nOn Trip\nUnder Maintenance\nInactive", default="Available",
			     allow_on_submit=1, description="Derived from trips and maintenance. Set Inactive manually to retire a vehicle."),
			dict(fieldname="tm_vehicle_type", fieldtype="Data", label="Vehicle Type", in_standard_filter=1, allow_on_submit=1),
			dict(fieldname="tm_capacity_kg", fieldtype="Float", label="Capacity (kg)", allow_on_submit=1),
			dict(fieldname="tm_fleet", fieldtype="Link", options="Transport Fleet", label="Fleet", in_standard_filter=1, allow_on_submit=1),
			dict(fieldname="tm_col1", fieldtype="Column Break"),
			dict(fieldname="tm_ownership", fieldtype="Select", label="Ownership", default="Company Owned",
			     options="Company Owned\nVendor Owned\nAttached", allow_on_submit=1),
			dict(fieldname="tm_vendor", fieldtype="Link", options="Supplier", label="Vendor",
			     depends_on="eval:doc.tm_ownership!='Company Owned'", allow_on_submit=1),
			dict(fieldname="tm_contract_rate", fieldtype="Currency", label="Vendor Contract Rate",
			     depends_on="eval:doc.tm_ownership!='Company Owned'", allow_on_submit=1),
			dict(fieldname="tm_rate_basis", fieldtype="Select", label="Contract Rate Basis",
			     options="\nPer Trip\nPer Km\nPer Day\nMonthly", depends_on="eval:doc.tm_ownership!='Company Owned'", allow_on_submit=1),
			dict(fieldname="tm_home_location", fieldtype="Data", label="Home Location", allow_on_submit=1),
			dict(fieldname="tm_section_loc", fieldtype="Section Break", label="Last known position and service"),
			dict(fieldname="tm_last_latitude", fieldtype="Float", label="Last Latitude", precision="6", read_only=1, allow_on_submit=1),
			dict(fieldname="tm_last_longitude", fieldtype="Float", label="Last Longitude", precision="6", read_only=1, allow_on_submit=1),
			dict(fieldname="tm_col2", fieldtype="Column Break"),
			dict(fieldname="tm_last_seen", fieldtype="Datetime", label="Last Seen", read_only=1, allow_on_submit=1),
			dict(fieldname="tm_next_service_date", fieldtype="Date", label="Next Service Date", allow_on_submit=1),
			dict(fieldname="tm_next_service_odometer", fieldtype="Float", label="Next Service Odometer", allow_on_submit=1),
			dict(fieldname="tm_section_docs", fieldtype="Section Break", label="Compliance Documents"),
			dict(fieldname="tm_documents", fieldtype="Table", options="Vehicle Document", label="Documents", allow_on_submit=1),
		],
	)
	driver = _chain(
		"Driver",
		[
			dict(fieldname="tm_section", fieldtype="Section Break", label="Transport Management"),
			dict(fieldname="tm_fleet", fieldtype="Link", options="Transport Fleet", label="Fleet", in_standard_filter=1),
			dict(fieldname="tm_section_docs", fieldtype="Section Break", label="Compliance Documents"),
			dict(fieldname="tm_documents", fieldtype="Table", options="Vehicle Document", label="Documents"),
		],
	)

	def link_pair(doctype, after):
		after = after if frappe.get_meta(doctype).has_field(after) else _last_field(doctype)
		return _chain(
			doctype,
			[
				dict(fieldname="tm_trip_plan", fieldtype="Link", options="Trip Plan", label="Trip Plan", allow_on_submit=1, search_index=1),
				dict(fieldname="tm_vehicle", fieldtype="Link", options="Vehicle", label="Vehicle", allow_on_submit=1, search_index=1),
			],
			after,
		)

	custom_fields = {
		"Vehicle": vehicle,
		"Driver": driver,
		"Payment Entry": link_pair("Payment Entry", "remarks"),
		"Journal Entry": link_pair("Journal Entry", "user_remark"),
		"Sales Invoice": link_pair("Sales Invoice", "remarks"),
	}
	# skip fields already present (re-runs on migrate) so layout customised by users is not reset
	for doctype, fields in custom_fields.items():
		fields[:] = [f for f in fields if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": f["fieldname"]})]
	custom_fields = {k: v for k, v in custom_fields.items() if v}
	if custom_fields:
		create_custom_fields(custom_fields, ignore_validate=True)


# ----------------------------------------------------------------- defaults
def _insert_if_missing(doctype, name, values):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def create_defaults():
	for name, applies, mandatory in DOCUMENT_TYPES:
		_insert_if_missing("Vehicle Document Type", name, dict(document_type=name, applies_to=applies, is_mandatory=mandatory))
	for tt in TRIP_TYPES:
		_insert_if_missing("Trip Type", tt["trip_type_name"], tt)
	for ec in EXPENSE_CATEGORIES:
		_insert_if_missing("Expense Category", ec["category_name"], ec)


# --------------------------------------------------------------- workflows
def create_workflows():
	for wf in WORKFLOWS:
		if frappe.db.exists("Workflow", wf["workflow_name"]):
			continue  # never overwrite a workflow the client has adapted
		for s in wf["states"]:
			_insert_if_missing("Workflow State", s["state"], dict(workflow_state_name=s["state"]))
		for t in wf["transitions"]:
			_insert_if_missing("Workflow Action Master", t["action"], dict(workflow_action_name=t["action"]))
		doc = frappe.get_doc(
			{
				"doctype": "Workflow",
				"workflow_name": wf["workflow_name"],
				"document_type": wf["document_type"],
				"workflow_state_field": "workflow_state",
				"is_active": 1,
				"send_email_alert": 0,
				"states": [
					{"state": s["state"], "doc_status": str(s.get("doc_status", 0)), "allow_edit": role,
					 "style": s.get("style")}
					for s in wf["states"]
					for role in ([s["allow_edit"]] if isinstance(s["allow_edit"], str) else s["allow_edit"])
				],
				"transitions": [
					{"state": t["state"], "action": t["action"], "next_state": t["next_state"],
					 "allowed": t["allowed"], "condition": t.get("condition"), "allow_self_approval": 1}
					for t in wf["transitions"]
				],
			}
		)
		doc.insert(ignore_permissions=True)


# ------------------------------------------------------------ notifications
NOTIFICATIONS = [
	dict(
		name="TM Booking Approved",
		subject="Booking {{ doc.name }} approved",
		document_type="Vehicle Booking Request",
		condition="doc.workflow_state == 'Approved'",
		message="<p>Your vehicle booking <b>{{ doc.name }}</b> ({{ doc.pickup_location }} to {{ doc.drop_location }}) was approved.</p>",
		recipients=[{"receiver_by_document_field": "owner"}],
	),
	dict(
		name="TM Booking Rejected",
		subject="Booking {{ doc.name }} rejected",
		document_type="Vehicle Booking Request",
		condition="doc.workflow_state == 'Rejected'",
		message="<p>Booking <b>{{ doc.name }}</b> was rejected.</p><p>Reason: {{ doc.rejection_reason }}</p>",
		recipients=[{"receiver_by_document_field": "owner"}],
	),
	dict(
		name="TM Booking Submitted",
		subject="Booking {{ doc.name }} awaits approval",
		document_type="Vehicle Booking Request",
		condition="doc.workflow_state == 'Submitted'",
		message="<p>Booking <b>{{ doc.name }}</b> from {{ doc.pickup_location }} to {{ doc.drop_location }} needs approval.</p>",
		recipients=[{"receiver_by_role": "Transport Manager"}],
	),
	dict(
		name="TM Trip Started",
		subject="Trip {{ doc.name }} started",
		document_type="Trip Plan",
		condition="doc.workflow_state == 'Started'",
		message="<p>Trip <b>{{ doc.name }}</b> ({{ doc.from_location }} to {{ doc.to_location }}) has started with {{ doc.vehicle }}.</p>",
		recipients=[{"receiver_by_role": "Transport Dispatcher"}],
	),
	dict(
		name="TM Expense Pending Approval",
		subject="Expense {{ doc.name }} needs approval",
		document_type="Trip Expense",
		condition="doc.workflow_state == 'Pending Approval'",
		message="<p>Expense <b>{{ doc.name }}</b> of {{ doc.amount }} on trip {{ doc.trip_plan }}. {{ doc.limit_remark or '' }}</p>",
		recipients=[{"receiver_by_role": "Transport Manager"}],
	),
]


def create_notifications():
	for n in NOTIFICATIONS:
		if frappe.db.exists("Notification", n["name"]):
			continue
		try:
			frappe.get_doc(
				{
					"doctype": "Notification",
					"name": n["name"],
					"subject": n["subject"],
					"document_type": n["document_type"],
					"event": "Value Change",
					"value_changed": "workflow_state",
					"channel": "System Notification",
					"condition": n["condition"],
					"message": n["message"],
					"message_type": "HTML",
					"enabled": 1,
					"recipients": n["recipients"],
				}
			).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Could not create Notification {n['name']}")
