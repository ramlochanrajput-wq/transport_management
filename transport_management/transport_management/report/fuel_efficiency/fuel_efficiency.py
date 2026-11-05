import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Log",
  "fieldname": "log",
  "fieldtype": "Link",
  "width": 130,
  "options": "Fuel Log"
 },
 {
  "label": "Date",
  "fieldname": "date",
  "fieldtype": "Date",
  "width": 100
 },
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 120,
  "options": "Vehicle"
 },
 {
  "label": "Driver",
  "fieldname": "driver",
  "fieldtype": "Link",
  "width": 120,
  "options": "Driver"
 },
 {
  "label": "Litres",
  "fieldname": "litres",
  "fieldtype": "Float",
  "width": 80
 },
 {
  "label": "Amount",
  "fieldname": "amount",
  "fieldtype": "Currency",
  "width": 100
 },
 {
  "label": "Odometer",
  "fieldname": "odometer",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Km Run",
  "fieldname": "km_run",
  "fieldtype": "Float",
  "width": 90
 },
 {
  "label": "Km per Litre",
  "fieldname": "km_per_litre",
  "fieldtype": "Float",
  "width": 80
 },
 {
  "label": "Anomaly",
  "fieldname": "anomaly",
  "fieldtype": "Check",
  "width": 80
 },
 {
  "label": "Note",
  "fieldname": "note",
  "fieldtype": "Data",
  "width": 260
 }
]

SQL = """
select name as log, fill_date as date, vehicle, driver, litres, amount, odometer, km_run, kmpl as km_per_litre, anomaly, anomaly_note as note
from `tabFuel Log`
where fill_date between %(from_date)s and %(to_date)s {conds} order by fill_date desc
"""

CONDS = {
 "vehicle": "vehicle = %(vehicle)s",
 "driver": "driver = %(driver)s",
 "only_anomalies": "anomaly = 1"
}


def _post(data, filters):
	pass
	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
