frappe.ui.form.on("Vehicle Booking Request", {
	refresh(frm) {
		if (frm.is_new()) return;
		const state = frm.doc.workflow_state;
		if (["Draft", "Submitted", "Approved"].includes(state)) {
			frm.add_custom_button(__("Get Freight Quote"), () =>
				frappe.call({ method: "transport_management.api.quote", args: { booking: frm.doc.name }, callback: () => frm.reload_doc() }), __("Quote"));
			frm.add_custom_button(__("Create Sales Order"), () =>
				frappe.call({ method: "transport_management.api.sales_order_from_quote", args: { booking: frm.doc.name }, callback: (r) => frappe.set_route("Form", "Sales Order", r.message) }), __("Quote"));
		}
		if (state === "Approved" && !frm.doc.trip_plan) {
			frm.add_custom_button(__("Suggest Vehicle and Driver"), () => tm_suggest(frm), __("Dispatch"));
			frm.add_custom_button(__("Create Trip Plan"), () =>
				frappe.model.open_mapped_doc ? tm_make_trip(frm) : tm_make_trip(frm), __("Dispatch"));
		}
		if (frm.doc.trip_plan) frm.add_custom_button(__("Open Trip Plan"), () => frappe.set_route("Form", "Trip Plan", frm.doc.trip_plan));
	},
});

function tm_make_trip(frm, vehicle, driver) {
	frappe.call({
		method: "transport_management.transport_management.doctype.vehicle_booking_request.vehicle_booking_request.make_trip_plan",
		args: { booking: frm.doc.name },
		callback: (r) => {
			const m = r.message;
			frappe.model.with_doctype("Trip Plan", () => {
				const doc = frappe.model.get_new_doc("Trip Plan");
				["booking", "customer", "fleet", "trip_type", "vehicle", "driver", "planned_start", "planned_end", "load_kg", "from_location", "to_location", "freight_amount"].forEach((k) => (doc[k] = m[k]));
				if (vehicle) doc.vehicle = vehicle;
				if (driver) doc.driver = driver;
				(m.stops || []).forEach((st) => {
					const c = frappe.model.add_child(doc, "stops");
					Object.assign(c, { sequence: st.sequence, stop_type: st.stop_type, location: st.location, eta: st.eta });
				});
				frappe.set_route("Form", "Trip Plan", doc.name);
			});
		},
	});
}

function tm_suggest(frm) {
	frappe.call({
		method: "transport_management.api.suggest",
		args: { booking: frm.doc.name },
		freeze: true,
		callback: (r) => {
			const rows = r.message || [];
			if (!rows.length) return frappe.msgprint(__("No eligible vehicle and driver found for this window."));
			const e = frappe.utils.escape_html;
			const d = new frappe.ui.Dialog({ title: __("Ranked suggestions (advisory)"), fields: [{ fieldtype: "HTML", fieldname: "list" }] });
			d.fields_dict.list.$wrapper.html(rows.map((s, i) =>
				`<div style="padding:6px 0;border-bottom:1px solid var(--border-color)"><b>#${i + 1} ${e(s.vehicle)}</b> + ${e(s.driver)} <span class="text-muted">(${__("score")} ${s.score})</span>
				<br><span class="small text-muted">${s.reasons.map(e).join(" · ")}</span>
				<button class="btn btn-xs btn-primary pull-right tm-use" data-v="${e(s.vehicle)}" data-d="${e(s.driver)}">${__("Use")}</button></div>`).join(""));
			d.fields_dict.list.$wrapper.find(".tm-use").on("click", (ev) => { d.hide(); tm_make_trip(frm, $(ev.currentTarget).data("v"), $(ev.currentTarget).data("d")); });
			d.show();
		},
	});
}
