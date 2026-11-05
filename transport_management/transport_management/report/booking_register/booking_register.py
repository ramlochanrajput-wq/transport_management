import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Booking",
  "fieldname": "booking",
  "fieldtype": "Link",
  "width": 150,
  "options": "Vehicle Booking Request"
 },
 {
  "label": "Status",
  "fieldname": "status",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Customer",
  "fieldname": "customer",
  "fieldtype": "Link",
  "width": 150,
  "options": "Customer"
 },
 {
  "label": "From",
  "fieldname": "from",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "To",
  "fieldname": "to",
  "fieldtype": "Datetime",
  "width": 150
 },
 {
  "label": "Pickup",
  "fieldname": "pickup",
  "fieldtype": "Data",
  "width": 140
 },
 {
  "label": "Drop",
  "fieldname": "drop",
  "fieldtype": "Data",
  "width": 140
 },
 {
  "label": "Trip Type",
  "fieldname": "trip_type",
  "fieldtype": "Link",
  "width": 110,
  "options": "Trip Type"
 },
 {
  "label": "Vehicle Type",
  "fieldname": "vehicle_type",
  "fieldtype": "Data",
  "width": 110
 },
 {
  "label": "Quote",
  "fieldname": "quote",
  "fieldtype": "Currency",
  "width": 100
 },
 {
  "label": "Requested By",
  "fieldname": "requested_by",
  "fieldtype": "Link",
  "width": 150,
  "options": "User"
 },
 {
  "label": "Trip",
  "fieldname": "trip",
  "fieldtype": "Link",
  "width": 130,
  "options": "Trip Plan"
 }
]

SQL = """
select name as booking, workflow_state as status, customer, from_datetime as `from`, to_datetime as `to`,
  pickup_location as pickup, drop_location as `drop`, trip_type, vehicle_type as vehicle_type_,
  quoted_rate as quote, requested_by, trip_plan as trip
from `tabVehicle Booking Request`
where date(from_datetime) between %(from_date)s and %(to_date)s {conds}
order by from_datetime desc
"""

CONDS = {
 "customer": "customer = %(customer)s",
 "workflow_state": "workflow_state = %(workflow_state)s",
 "fleet": "fleet = %(fleet)s"
}


def _post(data, filters):

	for r in data:
		r["vehicle_type"] = r.pop("vehicle_type_", None)

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
