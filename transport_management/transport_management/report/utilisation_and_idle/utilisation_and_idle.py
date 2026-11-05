import frappe
from frappe.utils import cint
from frappe.utils import date_diff
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
  "label": "Fleet",
  "fieldname": "fleet",
  "fieldtype": "Link",
  "width": 120,
  "options": "Transport Fleet"
 },
 {
  "label": "Trips",
  "fieldname": "trips",
  "fieldtype": "Int",
  "width": 70
 },
 {
  "label": "Distance (km)",
  "fieldname": "distance_km",
  "fieldtype": "Float",
  "width": 110
 },
 {
  "label": "Busy (h)",
  "fieldname": "busy_h",
  "fieldtype": "Float",
  "width": 90
 },
 {
  "label": "Maintenance (h)",
  "fieldname": "maintenance_h",
  "fieldtype": "Float",
  "width": 110
 },
 {
  "label": "Available (h)",
  "fieldname": "available_h",
  "fieldtype": "Float",
  "width": 110
 },
 {
  "label": "Idle (h)",
  "fieldname": "idle_h",
  "fieldtype": "Float",
  "width": 90
 },
 {
  "label": "Utilisation %",
  "fieldname": "utilisation",
  "fieldtype": "Percent",
  "width": 110
 }
]

SQL = """
select v.name as vehicle, v.tm_fleet as fleet,
  (select count(*) from `tabTrip Plan` t where t.vehicle=v.name and t.workflow_state not in ('Cancelled','Planned')
     and date(t.planned_start) between %(from_date)s and %(to_date)s) as trips,
  (select ifnull(sum(t.distance_km),0) from `tabTrip Plan` t where t.vehicle=v.name and t.workflow_state in ('Completed','Settled')
     and date(t.planned_start) between %(from_date)s and %(to_date)s) as distance_km,
  (select ifnull(sum(timestampdiff(minute, coalesce(t.actual_start,t.planned_start), coalesce(t.actual_end,t.planned_end))),0)/60
     from `tabTrip Plan` t where t.vehicle=v.name and t.workflow_state not in ('Cancelled','Planned')
     and date(t.planned_start) between %(from_date)s and %(to_date)s) as busy,
  (select ifnull(sum(m.downtime_hours),0) from `tabVehicle Maintenance Log` m where m.vehicle=v.name
     and date(m.start_datetime) between %(from_date)s and %(to_date)s) as maintenance
from `tabVehicle` v where ifnull(v.tm_status,'') != 'Inactive' {conds}
order by v.name
"""

CONDS = {
 "fleet": "v.tm_fleet = %(fleet)s",
 "vehicle": "v.name = %(vehicle)s"
}


def _post(data, filters):

	days = date_diff(filters.to_date, filters.from_date) + 1
	period_h = max(days, 1) * 24
	for r in data:
		busy = round(r.pop("busy") or 0, 1)
		maint = r.pop("maintenance") or 0
		available = max(period_h - maint, 0)
		r.busy_h, r.maintenance_h, r.available_h = busy, maint, available
		r.idle_h = max(available - busy, 0)
		r.utilisation = round(busy / available * 100, 1) if available else 0

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
