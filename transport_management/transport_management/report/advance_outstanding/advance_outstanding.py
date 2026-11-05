import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Advance",
  "fieldname": "advance",
  "fieldtype": "Link",
  "width": 140,
  "options": "Trip Advance"
 },
 {
  "label": "Date",
  "fieldname": "date",
  "fieldtype": "Date",
  "width": 100
 },
 {
  "label": "Trip",
  "fieldname": "trip",
  "fieldtype": "Link",
  "width": 130,
  "options": "Trip Plan"
 },
 {
  "label": "Driver",
  "fieldname": "driver",
  "fieldtype": "Link",
  "width": 130,
  "options": "Driver"
 },
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 120,
  "options": "Vehicle"
 },
 {
  "label": "Amount",
  "fieldname": "amount",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Accounting Entry",
  "fieldname": "accounting_entry",
  "fieldtype": "Data",
  "width": 150
 },
 {
  "label": "Trip Status",
  "fieldname": "trip_status",
  "fieldtype": "Data",
  "width": 100
 },
 {
  "label": "Age (days)",
  "fieldname": "age_days",
  "fieldtype": "Int",
  "width": 90
 }
]

SQL = """
select a.name as advance, a.requested_on as date, a.trip_plan as trip, a.driver, a.vehicle, a.amount,
  ifnull(a.payment_entry, a.journal_entry) as accounting_entry, t.workflow_state as trip_status,
  datediff(curdate(), a.requested_on) as age_days
from `tabTrip Advance` a join `tabTrip Plan` t on t.name = a.trip_plan
where a.docstatus = 1 and ifnull(a.settlement, '') = '' and a.requested_on between %(from_date)s and %(to_date)s {conds}
order by a.requested_on
"""

CONDS = {
 "driver": "a.driver = %(driver)s",
 "vehicle": "a.vehicle = %(vehicle)s"
}


def _post(data, filters):
	pass
	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
