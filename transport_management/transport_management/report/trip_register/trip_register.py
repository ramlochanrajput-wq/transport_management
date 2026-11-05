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
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
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
  "fieldtype": "Data",
  "width": 150
 },
 {
  "label": "Customer",
  "fieldname": "customer",
  "fieldtype": "Link",
  "width": 140,
  "options": "Customer"
 },
 {
  "label": "From",
  "fieldname": "from",
  "fieldtype": "Data",
  "width": 130
 },
 {
  "label": "To",
  "fieldname": "to",
  "fieldtype": "Data",
  "width": 130
 },
 {
  "label": "Planned Start",
  "fieldname": "planned_start",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Actual Start",
  "fieldname": "actual_start",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Actual End",
  "fieldname": "actual_end",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Distance (km)",
  "fieldname": "distance_km",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Delay (min)",
  "fieldname": "delay_min",
  "fieldtype": "Int",
  "width": 90
 },
 {
  "label": "Delay Reason",
  "fieldname": "delay_reason",
  "fieldtype": "Data",
  "width": 170
 },
 {
  "label": "Out of Zone",
  "fieldname": "out_of_zone",
  "fieldtype": "Check",
  "width": 80
 }
]

SQL = """
select name as trip, workflow_state as status, vehicle, driver_name as driver, customer,
  from_location as `from`, to_location as `to`, planned_start, actual_start, actual_end, distance_km,
  delay_minutes as delay_min, delay_reason, out_of_zone
from `tabTrip Plan`
where date(planned_start) between %(from_date)s and %(to_date)s {conds}
order by planned_start desc
"""

CONDS = {
 "vehicle": "vehicle = %(vehicle)s",
 "driver": "driver = %(driver)s",
 "workflow_state": "workflow_state = %(workflow_state)s",
 "fleet": "fleet = %(fleet)s"
}


def _post(data, filters):
	pass
	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
