import frappe

from transport_management.services.tracking import public_view
from transport_management.utils import is_enabled

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.title = "Track your shipment"
	data = public_view(frappe.form_dict.get("token"))
	if not data:
		frappe.local.response["http_status_code"] = 404
		context.data = None
		return
	context.data = data
	context.token = frappe.form_dict.get("token")
	context.allow_feedback = is_enabled("ratings") and data["status"] in ("Completed", "Settled")
