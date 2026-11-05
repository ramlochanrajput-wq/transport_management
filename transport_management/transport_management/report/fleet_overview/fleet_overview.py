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
  "label": "Plate",
  "fieldname": "plate",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Type",
  "fieldname": "type",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Fleet",
  "fieldname": "fleet",
  "fieldtype": "Link",
  "width": 130,
  "options": "Transport Fleet"
 },
 {
  "label": "Ownership",
  "fieldname": "ownership",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
  "width": 130
 },
 {
  "label": "Capacity (kg)",
  "fieldname": "capacity_kg",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Odometer",
  "fieldname": "odometer",
  "fieldtype": "Float",
  "width": 100
 },
 {
  "label": "Current Trip",
  "fieldname": "current_trip",
  "fieldtype": "Link",
  "width": 130,
  "options": "Trip Plan"
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
  "label": "Position",
  "fieldname": "position",
  "fieldtype": "Data",
  "width": 100
 }
]

SQL = """
select v.name as vehicle, v.license_plate as plate, v.tm_vehicle_type as type, v.tm_fleet as fleet,
  v.tm_ownership as ownership, v.tm_status as status, v.tm_capacity_kg as capacity_kg,
  v.last_odometer as odometer, t.name as current_trip, v.tm_last_seen as last_seen
from `tabVehicle` v
left join `tabTrip Plan` t on t.vehicle = v.name and t.workflow_state in ('Started','In Transit','Arrived')
where 1=1 {conds}
order by v.tm_status, v.name
"""

CONDS = {
 "fleet": "v.tm_fleet = %(fleet)s",
 "status": "v.tm_status = %(status)s",
 "vehicle_type": "v.tm_vehicle_type = %(vehicle_type)s"
}


def _post(data, filters):

	for r in data:
		age = age_minutes(r.last_seen)
		r.age_min = age
		r.position = ("Stale" if is_stale(r.last_seen) else "Recent") if r.last_seen else "No GPS"

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
