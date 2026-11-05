app_name = "transport_management"
app_title = "Transport Management"
app_publisher = "agrify@klaimify.in"
app_description = "Vehicle and transport management: bookings, trips, advances, settlement, compliance"
app_email = "agrify@klaimify.in"
app_license = "mit"

required_apps = ["frappe/erpnext", "frappe/hrms"]

add_to_apps_screen = [
	{
		"name": "transport_management",
		"logo": "/assets/transport_management/images/transport.svg",
		"title": "Transport",
		"route": "/app/transport-management",
	}
]

# Extend (never edit) core doctypes' client behaviour
doctype_js = {
	"Vehicle": "public/js/vehicle.js",
}

after_install = "transport_management.setup.install.after_install"
after_migrate = "transport_management.setup.install.after_migrate"

# Public tracking page (E4): /track/<token>
website_route_rules = [
	{"from_route": "/track/<token>", "to_route": "track"},
]

doc_events = {
	"Vehicle": {
		"validate": "transport_management.events.validate_documents_table",
		"after_insert": "transport_management.events.vehicle_after_insert",
	},
	"Driver": {"validate": "transport_management.events.validate_documents_table"},
	"Trip Plan": {
		"after_insert": "transport_management.transport_management.doctype.vehicle_booking_request.vehicle_booking_request.mark_converted"
	},
}

permission_query_conditions = {
	"Trip Plan": "transport_management.permissions.trip_plan_query",
	"Trip Expense": "transport_management.permissions.trip_expense_query",
	"Trip Issue": "transport_management.permissions.trip_issue_query",
	"Fuel Log": "transport_management.permissions.fuel_log_query",
}

has_permission = {"Trip Plan": "transport_management.permissions.trip_plan_has_permission"}

scheduler_events = {
	"cron": {
		"*/15 * * * *": ["transport_management.scheduler.jobs.check_delays"],
	},
	"hourly": [
		"transport_management.scheduler.jobs.check_stale_locations",
		"transport_management.scheduler.jobs.check_geofence_and_idle",
		"transport_management.scheduler.jobs.refresh_vehicle_statuses",
	],
	"daily": [
		"transport_management.scheduler.jobs.send_document_reminders",
		"transport_management.scheduler.jobs.purge_old_locations",
	],
}

