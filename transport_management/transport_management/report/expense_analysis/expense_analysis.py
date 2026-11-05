import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Group",
  "fieldname": "group",
  "fieldtype": "Data",
  "width": 200
 },
 {
  "label": "Expenses",
  "fieldname": "expenses",
  "fieldtype": "Int",
  "width": 90
 },
 {
  "label": "Total",
  "fieldname": "total",
  "fieldtype": "Currency",
  "width": 120
 },
 {
  "label": "Average",
  "fieldname": "average",
  "fieldtype": "Currency",
  "width": 110
 },
 {
  "label": "Over Limit",
  "fieldname": "over_limit",
  "fieldtype": "Int",
  "width": 90
 },
 {
  "label": "Share %",
  "fieldname": "share",
  "fieldtype": "Percent",
  "width": 90
 }
]

SQL = """
select
  case %(group_by)s when 'Vehicle' then e.vehicle when 'Driver' then e.driver when 'Trip' then e.trip_plan
       else e.expense_category end as grp,
  count(*) as expenses, sum(e.amount) as total, avg(e.amount) as average, sum(e.over_limit) as over_limit
from `tabTrip Expense` e
where e.docstatus = 1 and e.expense_date between %(from_date)s and %(to_date)s {conds}
group by grp order by total desc
"""

CONDS = {
 "vehicle": "e.vehicle = %(vehicle)s",
 "expense_category": "e.expense_category = %(expense_category)s"
}


def _post(data, filters):

	grand = sum(r.total or 0 for r in data) or 1
	for r in data:
		r["group"] = r.pop("grp")
		r.share = (r.total or 0) / grand * 100

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
