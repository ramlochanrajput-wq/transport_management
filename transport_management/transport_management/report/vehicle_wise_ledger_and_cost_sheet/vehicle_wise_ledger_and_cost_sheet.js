frappe.query_reports["Vehicle-wise Ledger and Cost Sheet"] = {
	filters: [
	{
		"fieldname": "from_date",
		"label": "From Date",
		"fieldtype": "Date",
		"reqd": 0,
		"default": frappe.datetime.month_start()
	},
	{
		"fieldname": "to_date",
		"label": "To Date",
		"fieldtype": "Date",
		"reqd": 0,
		"default": frappe.datetime.get_today()
	},
	{
		"fieldname": "vehicle",
		"label": "Vehicle",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Vehicle"
	},
	{
		"fieldname": "summary",
		"label": "Cost Sheet (summary per vehicle)",
		"fieldtype": "Check",
		"reqd": 0
	}
],
};
