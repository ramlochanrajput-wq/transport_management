frappe.query_reports["Zone Trips"] = {
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
		"fieldname": "service_area",
		"label": "Service Area",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Service Area"
	}
],
};
