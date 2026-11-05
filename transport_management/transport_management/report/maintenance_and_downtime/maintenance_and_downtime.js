frappe.query_reports["Maintenance and Downtime"] = {
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
		"fieldname": "maintenance_type",
		"label": "Type",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "\nPreventive\nBreakdown\nRepair\nInspection\nAccident"
	}
],
};
