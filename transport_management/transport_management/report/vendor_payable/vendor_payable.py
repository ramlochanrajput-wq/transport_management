import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Vendor",
  "fieldname": "vendor",
  "fieldtype": "Link",
  "width": 160,
  "options": "Supplier"
 },
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 120,
  "options": "Vehicle"
 },
 {
  "label": "Trip",
  "fieldname": "trip",
  "fieldtype": "Link",
  "width": 130,
  "options": "Trip Plan"
 },
 {
  "label": "Date",
  "fieldname": "date",
  "fieldtype": "Date",
  "width": 100
 },
 {
  "label": "Distance (km)",
  "fieldname": "distance_km",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Basis",
  "fieldname": "basis",
  "fieldtype": "Data",
  "width": 90
 },
 {
  "label": "Rate",
  "fieldname": "rate",
  "fieldtype": "Currency",
  "width": 100
 },
 {
  "label": "Payable",
  "fieldname": "payable",
  "fieldtype": "Currency",
  "width": 110
 }
]

SQL = """
select v.tm_vendor as vendor, v.name as vehicle, t.name as trip, date(t.planned_start) as date,
  t.distance_km, v.tm_rate_basis as basis, v.tm_contract_rate as rate
from `tabTrip Plan` t join `tabVehicle` v on v.name = t.vehicle
where v.tm_ownership != 'Company Owned' and t.workflow_state in ('Completed','Settled')
  and date(t.planned_start) between %(from_date)s and %(to_date)s {conds}
order by v.tm_vendor, t.planned_start
"""

CONDS = {
 "vendor": "v.tm_vendor = %(vendor)s"
}


def _post(data, filters):

	for r in data:
		rate = r.rate or 0
		if r.basis == "Per Km":
			r.payable = rate * (r.distance_km or 0)
		else:  # Per Trip / Per Day (one trip-day) / Monthly handled outside this report
			r.payable = rate

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
