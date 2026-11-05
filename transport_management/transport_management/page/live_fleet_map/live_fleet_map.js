frappe.pages["live-fleet-map"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Live Fleet Map"), single_column: true });
	new tm.LiveFleetMap(page, wrapper);
};

window.tm = window.tm || {};

// Status colours are fixed so a dispatcher learns them once.
tm.STATUS_COLORS = {
	Available: "#16a34a",
	Booked: "#2563eb",
	"On Trip": "#ea580c",
	"Under Maintenance": "#dc2626",
	Inactive: "#6b7280",
};

tm.LiveFleetMap = class {
	constructor(page, wrapper) {
		this.page = page;
		this.markers = {};
		this.rows = {};
		this.make_filters();
		this.make_layout();
		frappe.require(
			["/assets/transport_management/vendor/leaflet/leaflet.css", "/assets/transport_management/vendor/leaflet/leaflet.js"],
			() => {
				this.init_map();
				this.refresh();
				this.bind_realtime();
				// refresh age/stale labels even when no new pings arrive
				this.timer = setInterval(() => this.refresh(), 60 * 1000);
			}
		);
		$(wrapper).on("hide", () => this.timer && clearInterval(this.timer));
	}

	make_filters() {
		this.status = this.page.add_field({
			fieldname: "status", label: __("Status"), fieldtype: "Select",
			options: ["", "Available", "Booked", "On Trip", "Under Maintenance", "Inactive"].join("\n"),
			change: () => this.refresh(),
		});
		this.vtype = this.page.add_field({ fieldname: "vehicle_type", label: __("Vehicle Type"), fieldtype: "Data", change: () => this.refresh() });
		this.fleet = this.page.add_field({ fieldname: "fleet", label: __("Fleet"), fieldtype: "Link", options: "Transport Fleet", change: () => this.refresh() });
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
	}

	make_layout() {
		this.page.main.html(`
			<div class="tm-map-wrap" style="display:flex;gap:12px;flex-wrap:wrap">
				<div id="tm-map" style="flex:1 1 560px;height:70vh;min-height:420px;border-radius:8px;border:1px solid var(--border-color)"></div>
				<div style="flex:0 0 320px;max-width:100%">
					<div class="tm-legend" style="margin-bottom:8px"></div>
					<div class="tm-drawer text-muted" style="max-height:60vh;overflow:auto">${__("Click a vehicle on the map.")}</div>
				</div>
			</div>
			<div class="text-muted small" style="margin-top:6px">${__("Positions show the time they were last received. Anything older than the stale limit is greyed and labelled Stale; it is never shown as live.")}</div>`);
		const legend = Object.entries(tm.STATUS_COLORS)
			.map(([k, c]) => `<span style="margin-right:10px"><span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${c}"></span> ${__(k)}</span>`)
			.join("");
		this.page.main.find(".tm-legend").html(legend + `<span><span style="display:inline-block;width:10px;height:10px;border-radius:50%;border:2px dashed #6b7280"></span> ${__("Stale")}</span>`);
	}

	init_map() {
		this.map = L.map("tm-map").setView([20.5937, 78.9629], 5);
		L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
			maxZoom: 19, attribution: "&copy; OpenStreetMap contributors",
		}).addTo(this.map);
		setTimeout(() => this.map.invalidateSize(), 200);
	}

	refresh() {
		if (!this.map) return;
		frappe.call({
			method: "transport_management.api.fleet_positions",
			args: { status: this.status.get_value(), vehicle_type: this.vtype.get_value(), fleet: this.fleet.get_value() },
			callback: (r) => this.render(r.message || []),
		});
	}

	render(rows) {
		const seen = new Set();
		const bounds = [];
		let nopos = 0;
		rows.forEach((row) => {
			this.rows[row.vehicle] = row;
			if (!row.has_position) { nopos++; return; }
			seen.add(row.vehicle);
			this.upsert(row);
			bounds.push([row.lat, row.lng]);
		});
		Object.keys(this.markers).forEach((v) => {
			if (!seen.has(v)) { this.map.removeLayer(this.markers[v]); delete this.markers[v]; }
		});
		if (bounds.length && !this.fitted) { this.map.fitBounds(bounds, { padding: [30, 30] }); this.fitted = true; }
		this.page.set_indicator(__("{0} on map, {1} without GPS", [bounds.length, nopos]), "blue");
	}

	upsert(row) {
		const color = tm.STATUS_COLORS[row.status] || "#6b7280";
		const style = { radius: 8, color: row.stale ? "#6b7280" : color, weight: row.stale ? 3 : 2, fillColor: color, fillOpacity: row.stale ? 0.35 : 0.9, dashArray: row.stale ? "3 3" : null };
		let m = this.markers[row.vehicle];
		if (!m) {
			m = L.circleMarker([row.lat, row.lng], style).addTo(this.map);
			m.on("click", () => this.show_drawer(row.vehicle));
			this.markers[row.vehicle] = m;
		} else {
			m.setLatLng([row.lat, row.lng]);
			m.setStyle(style);
		}
		m.bindTooltip(`${frappe.utils.escape_html(row.plate || row.vehicle)} · ${__(row.status || "")}`);
	}

	age_label(row) {
		if (row.age_minutes == null) return __("No position received");
		const a = row.age_minutes;
		const txt = a < 1 ? __("just now") : a < 60 ? __("{0} min ago", [Math.round(a)]) : __("{0} h ago", [(a / 60).toFixed(1)]);
		return txt + (row.stale ? ` <span class="indicator-pill red">${__("Stale")}</span>` : "");
	}

	show_drawer(vehicle) {
		const row = this.rows[vehicle];
		if (!row) return;
		const e = frappe.utils.escape_html;
		const t = row.trip;
		const trip = t ? `<hr><div><b>${__("Trip")}</b>: <a href="/app/trip-plan/${encodeURIComponent(t.name)}">${e(t.name)}</a></div>
			<div>${e(t.from_location || "")} &rarr; ${e(t.to_location || "")}</div>
			<div>${__("Driver")}: ${e(t.driver_name || "-")}</div>
			<div>${__("Planned end")}: ${frappe.datetime.str_to_user(t.planned_end || "")}</div>` : `<hr><div class="text-muted">${__("No active trip")}</div>`;
		this.page.main.find(".tm-drawer").html(`
			<div class="h5"><a href="/app/vehicle/${encodeURIComponent(row.vehicle)}">${e(row.plate || row.vehicle)}</a></div>
			<div>${__("Status")}: <b>${__(row.status || "-")}</b> &middot; ${e(row.type || "")}</div>
			<div>${__("Last seen")}: ${this.age_label(row)}</div>${trip}`);
	}

	bind_realtime() {
		frappe.realtime.on("tm_location", (d) => {
			const row = this.rows[d.vehicle] || { vehicle: d.vehicle };
			Object.assign(row, { lat: d.lat, lng: d.lng, stale: d.stale, age_minutes: 0, has_position: true });
			this.rows[d.vehicle] = row;
			if (this.map && row.status !== undefined) this.upsert(row);
		});
		frappe.realtime.on("tm_vehicle_status", () => this.refresh());
		frappe.realtime.on("tm_trip_update", () => this.refresh());
	}
};
