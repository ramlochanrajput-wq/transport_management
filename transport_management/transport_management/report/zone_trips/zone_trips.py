import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Service Area",
  "fieldname": "service_area",
  "fieldtype": "Link",
  "width": 160,
  "options": "Service Area"
 },
 {
  "label": "Trips",
  "fieldname": "trips",
  "fieldtype": "Int",
  "width": 70
 },
 {
  "label": "Out of Zone",
  "fieldname": "out_of_zone",
  "fieldtype": "Int",
  "width": 100
 },
 {
  "label": "Distance (km)",
  "fieldname": "distance_km",
  "fieldtype": "Float",
  "width": 110
 }
]

SQL = """
select ifnull(service_area, 'Unassigned') as service_area, count(*) as trips, sum(out_of_zone) as out_of_zone,
  sum(distance_km) as distance_km
from `tabTrip Plan`
where workflow_state != 'Cancelled' and date(planned_start) between %(from_date)s and %(to_date)s {conds}
group by service_area order by trips desc
"""

CONDS = {
 "service_area": "service_area = %(service_area)s"
}


def _post(data, filters):
	pass
	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
