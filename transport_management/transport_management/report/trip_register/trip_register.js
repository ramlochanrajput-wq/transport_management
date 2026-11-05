frappe.query_reports["Trip Register"] = {
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
		"fieldname": "workflow_state",
		"label": "Status",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "\nPlanned\nApproved\nStarted\nIn Transit\nArrived\nCompleted\nSettled\nOn Hold\nCancelled"
	},
	{
		"fieldname": "fleet",
		"label": "Fleet",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Transport Fleet"
	}
],
};
