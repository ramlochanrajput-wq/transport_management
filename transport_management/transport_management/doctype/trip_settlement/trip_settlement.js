frappe.ui.form.on("Trip Settlement", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.trip_plan) {
			frm.add_custom_button(__("Fetch Advances and Expenses"), () => tm_fetch(frm));
		}
	},
	trip_plan(frm) { if (frm.doc.trip_plan && frm.is_new()) tm_fetch(frm); },
	driver_allowance(frm) { tm_totals(frm); },
});

function tm_fetch(frm) {
	frappe.call({
		method: "transport_management.transport_management.doctype.trip_settlement.trip_settlement.get_items",
		args: { trip_plan: frm.doc.trip_plan },
		callback: (r) => {
			frm.clear_table("advances"); frm.clear_table("expenses");
			(r.message.advances || []).forEach((a) => Object.assign(frm.add_child("advances"), { reference_doctype: a.reference_doctype, reference_name: a.reference_name, amount: a.amount, description: a.description }));
			(r.message.expenses || []).forEach((a) => Object.assign(frm.add_child("expenses"), { reference_doctype: a.reference_doctype, reference_name: a.reference_name, amount: a.amount, description: a.description }));
			frm.refresh_fields(["advances", "expenses"]);
			tm_totals(frm);
		},
	});
}

function tm_totals(frm) {
	const sum = (rows) => (rows || []).reduce((t, r) => t + flt(r.amount), 0);
	const adv = sum(frm.doc.advances), exp = sum(frm.doc.expenses);
	const net = exp + flt(frm.doc.driver_allowance) - adv;
	frm.set_value({ total_advance: adv, total_expense: exp, net_amount: net, settlement_type: net > 0 ? "Payable to Driver" : net < 0 ? "Recoverable from Driver" : "Nil" });
}
