frappe.query_reports["Fuel Efficiency"] = {
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
		"fieldname": "driver",
		"label": "Driver",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Driver"
	},
	{
		"fieldname": "only_anomalies",
		"label": "Anomalies Only",
		"fieldtype": "Check",
		"reqd": 0
	}
],
};
