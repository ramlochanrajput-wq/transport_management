import frappe
from frappe import _
from frappe.utils import flt

COLUMNS = [
	{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
	{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 120},
	{"label": _("Trip"), "fieldname": "trip", "fieldtype": "Link", "options": "Trip Plan", "width": 130},
	{"label": _("Source"), "fieldname": "source", "fieldtype": "Data", "width": 130},
	{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 160},
	{"label": _("Description"), "fieldname": "description", "fieldtype": "Data", "width": 220},
	{"label": _("Income"), "fieldname": "income", "fieldtype": "Currency", "width": 110},
	{"label": _("Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 110},
	{"label": _("Posting"), "fieldname": "posting", "fieldtype": "Data", "width": 100},
]
SUMMARY_COLUMNS = [
	{"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 140},
	{"label": _("Income (Posted)"), "fieldname": "income_posted", "fieldtype": "Currency", "width": 130},
	{"label": _("Cost (Posted)"), "fieldname": "cost_posted", "fieldtype": "Currency", "width": 130},
	{"label": _("Cost (Operational)"), "fieldname": "cost_operational", "fieldtype": "Currency", "width": 140},
	{"label": _("Income (Operational)"), "fieldname": "income_operational", "fieldtype": "Currency", "width": 150},
	{"label": _("Total Cost"), "fieldname": "cost", "fieldtype": "Currency", "width": 120},
	{"label": _("Total Income"), "fieldname": "income", "fieldtype": "Currency", "width": 120},
	{"label": _("Net"), "fieldname": "net", "fieldtype": "Currency", "width": 120},
]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not (filters.from_date and filters.to_date):
		frappe.throw(_("From Date and To Date are required"))
	rows = operational_rows(filters) + posted_rows(filters)
	rows.sort(key=lambda r: (str(r["date"]), r["vehicle"] or ""))
	if filters.summary:
		return SUMMARY_COLUMNS, summarise(rows)
	return COLUMNS, rows


def _veh_cond(filters, col):
	return f" and {col} = %(vehicle)s" if filters.vehicle else ""


def operational_rows(f):
	"""Documents that exist in the transport module but are not (or not yet) in the GL."""
	out = []
	for r in frappe.db.sql(
		f"""select a.requested_on as date, a.vehicle, a.trip_plan as trip, a.name, a.amount, a.purpose
		from `tabTrip Advance` a where a.docstatus=1 and a.requested_on between %(from_date)s and %(to_date)s
		{_veh_cond(f, 'a.vehicle')}""", f, as_dict=True):
		out.append(_row(r, "Trip Advance", "Trip Advance", r.purpose, cost=r.amount))
	for r in frappe.db.sql(
		f"""select e.expense_date as date, e.vehicle, e.trip_plan as trip, e.name, e.amount, e.expense_category as purpose
		from `tabTrip Expense` e where e.docstatus=1 and e.expense_date between %(from_date)s and %(to_date)s
		{_veh_cond(f, 'e.vehicle')}""", f, as_dict=True):
		out.append(_row(r, "Trip Expense", "Trip Expense", r.purpose, cost=r.amount))
	for r in frappe.db.sql(
		f"""select date(m.start_datetime) as date, m.vehicle, null as trip, m.name, m.cost as amount, m.maintenance_type as purpose
		from `tabVehicle Maintenance Log` m where m.cost > 0 and date(m.start_datetime) between %(from_date)s and %(to_date)s
		{_veh_cond(f, 'm.vehicle')}""", f, as_dict=True):
		out.append(_row(r, "Vehicle Maintenance Log", "Maintenance", r.purpose, cost=r.amount))
	for r in frappe.db.sql(
		f"""select date(t.planned_start) as date, t.vehicle, t.name as trip, t.name, t.freight_amount as amount, 'Freight' as purpose
		from `tabTrip Plan` t where t.freight_amount > 0 and t.workflow_state in ('Completed','Settled')
		and date(t.planned_start) between %(from_date)s and %(to_date)s {_veh_cond(f, 't.vehicle')}""", f, as_dict=True):
		out.append(_row(r, "Trip Plan", "Trip Freight", r.purpose, income=r.amount))
	return out


def posted_rows(f):
	"""GL Entry rows of vouchers tagged with a vehicle (Payment/Journal Entry, Sales Invoice)."""
	out = []
	for vtype, table in (("Payment Entry", "tabPayment Entry"), ("Journal Entry", "tabJournal Entry"), ("Sales Invoice", "tabSales Invoice")):
		vouchers = frappe.db.sql(
			f"""select name, tm_vehicle as vehicle, tm_trip_plan as trip from `{table}`
			where docstatus=1 and ifnull(tm_vehicle,'') != '' and posting_date between %(from_date)s and %(to_date)s
			{_veh_cond(f, 'tm_vehicle')}""", f, as_dict=True)
		if not vouchers:
			continue
		by_name = {v.name: v for v in vouchers}
		gl = frappe.db.sql(
			"""select voucher_no, posting_date, sum(debit) as debit, sum(credit) as credit, min(remarks) as remarks
			from `tabGL Entry` where voucher_type=%s and voucher_no in %s and is_cancelled=0
			group by voucher_no, posting_date""", (vtype, tuple(by_name)), as_dict=True)
		for g in gl:
			v = by_name[g.voucher_no]
			amount = flt(g.debit)  # a balanced voucher: total debit = total value moved
			row = {"date": g.posting_date, "vehicle": v.vehicle, "trip": v.trip, "source": vtype,
			       "source_doctype": vtype, "reference": g.voucher_no, "description": g.remarks, "income": 0, "cost": 0, "posting": "Posted"}
			if vtype == "Sales Invoice":
				row["income"] = amount
			else:
				row["cost"] = amount
			out.append(row)
	return out


def _row(r, doctype, source, description, cost=0, income=0):
	return {"date": r.date, "vehicle": r.vehicle, "trip": r.trip, "source": source, "source_doctype": doctype,
	        "reference": r.name, "description": description, "income": flt(income), "cost": flt(cost), "posting": "Operational"}


def summarise(rows):
	agg = {}
	for r in rows:
		a = agg.setdefault(r["vehicle"], dict(vehicle=r["vehicle"], income_posted=0, cost_posted=0, income_operational=0, cost_operational=0))
		suffix = "posted" if r["posting"] == "Posted" else "operational"
		a[f"income_{suffix}"] += flt(r["income"])
		a[f"cost_{suffix}"] += flt(r["cost"])
	for a in agg.values():
		a["income"] = a["income_posted"] + a["income_operational"]
		a["cost"] = a["cost_posted"] + a["cost_operational"]
		a["net"] = a["income"] - a["cost"]
	return sorted(agg.values(), key=lambda a: a["vehicle"] or "")
