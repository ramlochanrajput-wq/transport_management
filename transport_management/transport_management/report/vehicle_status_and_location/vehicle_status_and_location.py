import frappe
from frappe.utils import cint
from transport_management.utils import age_minutes, is_stale
from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Vehicle",
  "fieldname": "vehicle",
  "fieldtype": "Link",
  "width": 140,
  "options": "Vehicle"
 },
 {
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
  "width": 130
 },
 {
  "label": "Latitude",
  "fieldname": "latitude",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Longitude",
  "fieldname": "longitude",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Last Seen",
  "fieldname": "last_seen",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Age (min)",
  "fieldname": "age_min",
  "fieldtype": "Float",
  "width": 90
 },
 {
  "label": "Freshness",
  "fieldname": "freshness",
  "fieldtype": "Data",
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
  "fieldtype": "Data",
  "width": 160
 }
]

SQL = """
select v.name as vehicle, v.tm_status as status, v.tm_last_latitude as latitude,
  v.tm_last_longitude as longitude, v.tm_last_seen as last_seen, t.name as trip, t.driver_name as driver
from `tabVehicle` v
left join `tabTrip Plan` t on t.vehicle = v.name and t.workflow_state in ('Started','In Transit','Arrived')
where 1=1 {conds} order by v.name
"""

CONDS = {
 "fleet": "v.tm_fleet = %(fleet)s",
 "status": "v.tm_status = %(status)s"
}


def _post(data, filters):

	for r in data:
		r.age_min = age_minutes(r.last_seen)
		r.freshness = ("Stale" if is_stale(r.last_seen) else "Recent") if r.last_seen else "No GPS"

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
