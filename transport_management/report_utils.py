"""Tiny helper shared by the SQL-based Script Reports."""

import frappe


def run_report(filters, columns, sql, conds=None, post=None):
	"""Build WHERE fragments from the filters that were actually set and run `sql`.

	`sql` must contain a literal ``{conds}`` placeholder (each fragment starts with AND).
	`conds` maps filter name -> SQL fragment using ``%(name)s`` parameters.
	"""
	filters = frappe._dict(filters or {})
	fragments = [frag for key, frag in (conds or {}).items() if filters.get(key) not in (None, "", 0)]
	query = sql.replace("{conds}", "".join(f" AND {f}" for f in fragments))
	data = frappe.db.sql(query, filters, as_dict=True)
	if post:
		data = post(data, filters) or data
	return columns, data
