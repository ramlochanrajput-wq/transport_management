import frappe
from frappe.utils import cint

from transport_management.report_utils import run_report

COLUMNS = [
 {
  "label": "Type",
  "fieldname": "type",
  "fieldtype": "Data",
  "width": 80
 },
 {
  "label": "Owner",
  "fieldname": "owner",
  "fieldtype": "Dynamic Link",
  "width": 150,
  "options": "Type"
 },
 {
  "label": "Document",
  "fieldname": "document",
  "fieldtype": "Link",
  "width": 170,
  "options": "Vehicle Document Type"
 },
 {
  "label": "Number",
  "fieldname": "number",
  "fieldtype": "Data",
  "width": 130
 },
 {
  "label": "Expiry",
  "fieldname": "expiry",
  "fieldtype": "Date",
  "width": 100
 },
 {
  "label": "Days Left",
  "fieldname": "days_left",
  "fieldtype": "Int",
  "width": 90
 },
 {
  "label": "Mandatory",
  "fieldname": "mandatory",
  "fieldtype": "Check",
  "width": 80
 },
 {
  "label": "Verified",
  "fieldname": "verified",
  "fieldtype": "Check",
  "width": 80
 },
 {
  "label": "Attachment",
  "fieldname": "attachment",
  "fieldtype": "Data",
  "width": 120
 }
]

SQL = """
select d.parenttype as type, d.parent as owner, d.document_type as document, d.document_number as number,
  d.expiry_date as expiry, datediff(d.expiry_date, curdate()) as days_left, d.is_mandatory as mandatory,
  d.verified, d.attachment
from `tabVehicle Document` d
where d.parenttype in ('Vehicle','Driver') and d.expiry_date is not null
  and datediff(d.expiry_date, curdate()) <= %(within_days)s {conds}
order by d.expiry_date
"""

CONDS = {
 "applies_to": "d.parenttype = %(applies_to)s",
 "only_mandatory": "d.is_mandatory = 1"
}


def _post(data, filters):

	if filters.get("fleet"):
		keep = []
		for r in data:
			meta = frappe.get_meta(r["type"])
			if meta.has_field("tm_fleet") and frappe.db.get_value(r["type"], r["owner"], "tm_fleet") == filters.fleet:
				keep.append(r)
		return keep

	return data


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return run_report(filters, COLUMNS, SQL, CONDS, _post)
