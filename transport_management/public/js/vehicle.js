// Added to the standard ERPNext Vehicle form through hooks.doctype_js (no core file is edited).
frappe.ui.form.on("Vehicle", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("New Booking"), () => frappe.new_doc("Vehicle Booking Request", { preferred_vehicle: frm.doc.name }), __("Transport"));
		frm.add_custom_button(__("Maintenance Log"), () => frappe.new_doc("Vehicle Maintenance Log", { vehicle: frm.doc.name }), __("Transport"));
		frm.add_custom_button(__("Trips"), () => frappe.set_route("List", "Trip Plan", { vehicle: frm.doc.name }), __("Transport"));
		frm.add_custom_button(__("Ledger and Cost Sheet"), () => frappe.set_route("query-report", "Vehicle-wise Ledger and Cost Sheet", { vehicle: frm.doc.name, from_date: frappe.datetime.month_start(), to_date: frappe.datetime.get_today() }), __("Transport"));
		const expired = (frm.doc.tm_documents || []).filter((d) => d.is_mandatory && d.expiry_date && d.expiry_date < frappe.datetime.get_today());
		if (expired.length) frm.dashboard.set_headline(__("Expired mandatory documents: {0}. Assignment is blocked.", [expired.map((d) => d.document_type).join(", ")]), "red");
	},
});
