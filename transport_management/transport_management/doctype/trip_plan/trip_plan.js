frappe.ui.form.on("Trip Plan", {
	setup(frm) {
		frm.set_query("driver", () => ({ filters: { status: "Active" } }));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Check Assignment"), () => tm_check(frm));
		const live = ["Started", "In Transit", "Arrived", "Completed", "Approved"];
		if (frm.doc.tracking_token && frm.doc.tracking_enabled && live.includes(frm.doc.workflow_state)) {
			frm.add_custom_button(__("Copy Tracking Link"), () => {
				const url = `${window.location.origin}/track/${frm.doc.tracking_token}`;
				frappe.utils.copy_to_clipboard(url);
			}, __("Tracking"));
		}
		if (["Started", "In Transit", "Arrived"].includes(frm.doc.workflow_state)) {
			frm.add_custom_button(__("Show Delivery OTP"), () =>
				frappe.call({ method: "transport_management.transport_management.doctype.trip_plan.trip_plan.get_delivery_otp", args: { trip: frm.doc.name }, callback: (r) => frappe.msgprint({ title: __("Delivery OTP"), message: `<h2>${r.message}</h2>` }) }), __("Tracking"));
		}
		if (frm.doc.workflow_state === "Completed") {
			frm.add_custom_button(__("Create Settlement"), () => frappe.new_doc("Trip Settlement", { trip_plan: frm.doc.name }), __("Create"));
		}
		if (!["Cancelled", "Settled", "Completed"].includes(frm.doc.workflow_state)) {
			frm.add_custom_button(__("Trip Advance"), () => frappe.new_doc("Trip Advance", { trip_plan: frm.doc.name }), __("Create"));
			frm.add_custom_button(__("Trip Expense"), () => frappe.new_doc("Trip Expense", { trip_plan: frm.doc.name }), __("Create"));
			frm.add_custom_button(__("Trip Issue"), () => frappe.new_doc("Trip Issue", { trip_plan: frm.doc.name }), __("Create"));
		}
		frm.add_custom_button(__("Inspection Photo"), () => frappe.new_doc("Vehicle Inspection Log", { trip_plan: frm.doc.name, vehicle: frm.doc.vehicle }), __("Create"));
		if (frm.doc.last_latitude) {
			frm.dashboard.add_comment(
				__("Last position {0}, {1} at {2}", [frm.doc.last_latitude, frm.doc.last_longitude, frappe.datetime.str_to_user(frm.doc.last_seen)]) +
				` (<a target="_blank" href="https://www.openstreetmap.org/?mlat=${frm.doc.last_latitude}&mlon=${frm.doc.last_longitude}#map=14/${frm.doc.last_latitude}/${frm.doc.last_longitude}">${__("map")}</a>)`,
				"blue", true);
		}
	},
});

function tm_check(frm) {
	frappe.call({
		method: "transport_management.services.availability.check_assignment",
		args: { vehicle: frm.doc.vehicle, driver: frm.doc.driver, start: frm.doc.planned_start, end: frm.doc.planned_end, load_kg: frm.doc.load_kg, trip: frm.doc.name },
		callback: (r) => {
			const f = r.message || [];
			if (!f.length) return frappe.show_alert({ message: __("All assignment checks passed"), indicator: "green" });
			frappe.msgprint({ title: __("Assignment checks failed"), indicator: "red", message: "<ul>" + f.map((x) => `<li>${frappe.utils.escape_html(x.message)}</li>`).join("") + "</ul>" });
		},
	});
}
