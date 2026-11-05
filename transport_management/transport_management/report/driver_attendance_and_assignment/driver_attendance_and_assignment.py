import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Driver",
  "fieldname": "driver",
  "fieldtype": "Link",
  "width": 130,
  "options": "Driver"
 },
 {
  "label": "Name",
  "fieldname": "name",
  "fieldtype": "Data",
  "width": 170
 },
 {
  "label": "Fleet",
  "fieldname": "fleet",
  "fieldtype": "Link",
  "width": 120,
  "options": "Transport Fleet"
 },
 {
  "label": "Date",
  "fieldname": "date",
  "fieldtype": "Date",
  "width": 100
 },
 {
  "label": "Attendance",
  "fieldname": "attendance",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Trips",
  "fieldname": "trips",
  "fieldtype": "Int",
  "width": 70
 },
 {
  "label": "Trip IDs",
  "fieldname": "trip_ids",
  "fieldtype": "Data",
  "width": 260
 },
 {
  "label": "Licence Expiry",
  "fieldname": "licence_expiry",
  "fieldtype": "Date",
  "width": 110
 }
]

SQL = """
select d.name as driver, d.full_name as name, d.tm_fleet as fleet, t.dt as date, d.employee, d.expiry_date as licence_expiry,
  t.cnt as trips, t.ids as trip_ids
from `tabDriver` d
join (select driver, date(planned_start) as dt, count(*) as cnt, group_concat(name) as ids
      from `tabTrip Plan` where workflow_state != 'Cancelled'
      and date(planned_start) between %(from_date)s and %(to_date)s group by driver, date(planned_start)) t
  on t.driver = d.name
where 1=1 {conds}
order by t.dt desc, d.name
"""

CONDS = {
 "driver": "d.name = %(driver)s",
 "fleet": "d.tm_fleet = %(fleet)s"
}


def _post(data, filters):

	has_att = frappe.db.exists("DocType", "Attendance")
	for r in data:
		r.attendance = "n/a"
		if has_att and r.employee:
			r.attendance = frappe.db.get_value(
				"Attendance", {"employee": r.employee, "attendance_date": r.date, "docstatus": 1}, "status"
			) or "No record"

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
