import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Log",
  "fieldname": "log",
  "fieldtype": "Link",
  "width": 150,
  "options": "Vehicle Maintenance Log"
 },
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 120,
  "options": "Vehicle"
 },
 {
  "label": "Type",
  "fieldname": "type",
  "fieldtype": "Data",
  "width": 100
 },
 {
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
  "width": 100
 },
 {
  "label": "Start",
  "fieldname": "start",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "End",
  "fieldname": "end",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Downtime (h)",
  "fieldname": "downtime_h",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Cost",
  "fieldname": "cost",
  "fieldtype": "Currency",
  "width": 100
 },
 {
  "label": "Vendor",
  "fieldname": "vendor",
  "fieldtype": "Link",
  "width": 140,
  "options": "Supplier"
 },
 {
  "label": "Next Due",
  "fieldname": "next_due",
  "fieldtype": "Date",
  "width": 100
 }
]

SQL = """
select name as log, vehicle, maintenance_type as type, status, start_datetime as start, end_datetime as end,
  downtime_hours as downtime_h, cost, vendor, next_due_date as next_due
from `tabVehicle Maintenance Log`
where date(start_datetime) between %(from_date)s and %(to_date)s {conds}
order by start_datetime desc
"""

CONDS = {
 "vehicle": "vehicle = %(vehicle)s",
 "maintenance_type": "maintenance_type = %(maintenance_type)s"
}


def _post(data, filters):
	pass
	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
