import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Trip",
  "fieldname": "trip",
  "fieldtype": "Link",
  "width": 130,
  "options": "Trip Plan"
 },
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 120,
  "options": "Vehicle"
 },
 {
  "label": "Customer",
  "fieldname": "customer",
  "fieldtype": "Link",
  "width": 150,
  "options": "Customer"
 },
 {
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
  "width": 100
 },
 {
  "label": "Distance (km)",
  "fieldname": "distance_km",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Freight",
  "fieldname": "freight",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Expenses",
  "fieldname": "expenses",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Allowance",
  "fieldname": "allowance",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Profit",
  "fieldname": "profit",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Margin %",
  "fieldname": "margin",
  "fieldtype": "Percent",
  "width": 90
 },
 {
  "label": "Profit / km",
  "fieldname": "profit_km",
  "fieldtype": "Currency",
  "width": 100
 }
]

SQL = """
select t.name as trip, t.vehicle, t.customer, t.workflow_state as status, t.distance_km,
  t.freight_amount as freight, t.total_expense as expenses,
  (select ifnull(sum(s.driver_allowance),0) from `tabTrip Settlement` s where s.trip_plan=t.name and s.docstatus=1) as allowance
from `tabTrip Plan` t
where t.workflow_state in ('Completed','Settled') and date(t.planned_start) between %(from_date)s and %(to_date)s {conds}
order by t.planned_start desc
"""

CONDS = {
 "vehicle": "t.vehicle = %(vehicle)s",
 "customer": "t.customer = %(customer)s"
}


def _post(data, filters):

	for r in data:
		r.profit = (r.freight or 0) - (r.expenses or 0) - (r.allowance or 0)
		r.margin = (r.profit / r.freight * 100) if r.freight else 0
		r.profit_km = (r.profit / r.distance_km) if r.distance_km else 0

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
