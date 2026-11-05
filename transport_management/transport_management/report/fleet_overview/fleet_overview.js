frappe.query_reports["Fleet Overview"] = {
	filters: [
	{
		"fieldname": "fleet",
		"label": "Fleet",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Transport Fleet"
	},
	{
		"fieldname": "status",
		"label": "Status",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "\nAvailable\nBooked\nOn Trip\nUnder Maintenance\nInactive"
	},
	{
		"fieldname": "vehicle_type",
		"label": "Vehicle Type",
		"fieldtype": "Data",
		"reqd": 0
	}
],
};
