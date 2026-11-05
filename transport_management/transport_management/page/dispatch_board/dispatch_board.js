frappe.pages["dispatch-board"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Dispatch Board"), single_column: true });
	new tm.DispatchBoard(page);
};

window.tm = window.tm || {};

tm.BOARD_COLUMNS = [
	{ key: "booking:Submitted", title: "Booking: Awaiting Approval", kind: "booking" },
	{ key: "booking:Approved", title: "Booking: Approved", kind: "booking" },
	{ key: "trip:Planned", title: "Trip: Planned", kind: "trip" },
	{ key: "trip:Approved", title: "Trip: Ready", kind: "trip" },
	{ key: "trip:Started", title: "Trip: Started", kind: "trip" },
	{ key: "trip:In Transit", title: "Trip: In Transit", kind: "trip" },
	{ key: "trip:Arrived", title: "Trip: Arrived", kind: "trip" },
	{ key: "trip:On Hold", title: "Trip: On Hold", kind: "trip" },
];

tm.DispatchBoard = class {
	constructor(page) {
		this.page = page;
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.main.html(`<div class="tm-board" style="display:flex;gap:10px;overflow-x:auto;padding-bottom:10px"></div>
			<div class="text-muted small">${__("Drag a booking onto a vehicle suggestion, or open a card. Assignments always pass the normal availability checks.")}</div>`);
		this.refresh();
		frappe.realtime.on("tm_trip_update", () => this.refresh());
	}

	refresh() {
		frappe.call({ method: "transport_management.api.dispatch_board", callback: (r) => this.render(r.message || {}) });
	}

	render(data) {
		const e = frappe.utils.escape_html;
		const cols = tm.BOARD_COLUMNS.map((c) => {
			const [kind, state] = c.key.split(":");
			const items = (kind === "booking" ? data.bookings : data.trips || []).filter((x) => x.workflow_state === state);
			const cards = items.map((x) => kind === "booking"
				? `<div class="tm-card" data-kind="booking" data-name="${e(x.name)}" style="${this.card_style()}">
					<a href="/app/vehicle-booking-request/${encodeURIComponent(x.name)}"><b>${e(x.name)}</b></a>
					<div>${e(x.customer || "")}</div><div class="text-muted small">${e(x.pickup_location)} &rarr; ${e(x.drop_location)}</div>
					<div class="text-muted small">${frappe.datetime.str_to_user(x.from_datetime)}</div>
					${state === "Approved" ? `<button class="btn btn-xs btn-default tm-suggest" style="margin-top:4px">${__("Suggest vehicle")}</button>` : ""}
				</div>`
				: `<div class="tm-card" data-kind="trip" data-name="${e(x.name)}" style="${this.card_style()}">
					<a href="/app/trip-plan/${encodeURIComponent(x.name)}"><b>${e(x.name)}</b></a>
					<div>${e(x.vehicle || __("No vehicle"))} · ${e(x.driver_name || "")}</div>
					<div class="text-muted small">${e(x.from_location)} &rarr; ${e(x.to_location)}</div>
				</div>`).join("");
			return `<div style="flex:0 0 250px"><div class="text-muted" style="font-weight:600;margin-bottom:6px">${__(c.title)} <span class="badge">${items.length}</span></div>${cards || `<div class="text-muted small">${__("Empty")}</div>`}</div>`;
		}).join("");
		const board = this.page.main.find(".tm-board").html(cols);
		board.find(".tm-suggest").on("click", (ev) => this.suggest($(ev.currentTarget).closest(".tm-card").data("name")));
	}

	card_style() {
		return "border:1px solid var(--border-color);border-radius:8px;padding:8px;margin-bottom:8px;background:var(--card-bg)";
	}

	suggest(booking) {
		frappe.call({
			method: "transport_management.api.suggest",
			args: { booking },
			freeze: true,
			callback: (r) => {
				const rows = r.message || [];
				if (!rows.length) return frappe.msgprint(__("No eligible vehicle and driver found for this window."));
				const d = new frappe.ui.Dialog({
					title: __("Suggestions for {0}", [booking]),
					fields: [{ fieldtype: "HTML", fieldname: "list" }],
				});
				const e = frappe.utils.escape_html;
				d.fields_dict.list.$wrapper.html(rows.map((s, i) =>
					`<div style="padding:6px 0;border-bottom:1px solid var(--border-color)"><b>#${i + 1} ${e(s.vehicle)}</b> + ${e(s.driver)}
					<span class="text-muted">(${__("score")} ${s.score})</span><br><span class="small text-muted">${s.reasons.map(e).join(" · ")}</span>
					<button class="btn btn-xs btn-primary pull-right tm-use" data-v="${e(s.vehicle)}" data-d="${e(s.driver)}">${__("Use")}</button></div>`).join(""));
				d.fields_dict.list.$wrapper.find(".tm-use").on("click", (ev) => {
					const v = $(ev.currentTarget).data("v"), dr = $(ev.currentTarget).data("d");
					d.hide();
					frappe.call({
						method: "transport_management.transport_management.doctype.vehicle_booking_request.vehicle_booking_request.make_trip_plan",
						args: { booking },
						callback: (res) => {
							// open an unsaved Trip Plan pre-filled; the dispatcher confirms (suggestions never auto-assign)
							const m = res.message;
							frappe.model.with_doctype("Trip Plan", () => {
								const doc = frappe.model.get_new_doc("Trip Plan");
								["booking", "customer", "fleet", "trip_type", "planned_start", "planned_end", "load_kg", "from_location", "to_location", "freight_amount"].forEach((k) => (doc[k] = m[k]));
								doc.vehicle = v;
								doc.driver = dr;
								(m.stops || []).forEach((st) => {
									const c = frappe.model.add_child(doc, "stops");
									Object.assign(c, { sequence: st.sequence, stop_type: st.stop_type, location: st.location, eta: st.eta });
								});
								frappe.set_route("Form", "Trip Plan", doc.name);
							});
						},
					});
				});
				d.show();
			},
		});
	}
};
