"""Doc-event handlers on ERPNext / HRMS documents. No core code is modified: Frappe calls these via hooks."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from transport_management.services.vehicle_status import refresh_vehicle_status


def validate_documents_table(doc, method=None):
	"""Vehicle / Driver: stamp verifier, forbid verifying by non-managers, sanity-check dates."""
	before = doc.get_doc_before_save()
	was_verified = {r.name: r.verified for r in (before.get("tm_documents") if before else []) or []}
	is_manager = bool(set(frappe.get_roles()) & {"Transport Manager", "System Manager"})
	for row in doc.get("tm_documents") or []:
		if row.issue_date and row.expiry_date and row.expiry_date < row.issue_date:
			frappe.throw(_("Row {0}: Expiry Date is before Issue Date").format(row.idx))
		changed = bool(row.verified) != bool(was_verified.get(row.name, 0))
		if row.verified and changed:
			if not is_manager:
				frappe.throw(_("Row {0}: only a Transport Manager can verify a document").format(row.idx))
			row.verified_by = frappe.session.user
		if not row.verified:
			row.verified_by = None
		# a renewed (changed) expiry date needs fresh verification
		old = (before.get("tm_documents") if before else None) or []
		prev = next((o for o in old if o.name == row.name), None)
		if prev and prev.expiry_date != row.expiry_date and row.verified and not changed and not is_manager:
			row.verified = 0
			row.verified_by = None


def vehicle_after_insert(doc, method=None):
	refresh_vehicle_status(doc.name)
