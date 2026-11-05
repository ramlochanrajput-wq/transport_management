frappe.query_reports["Driver Attendance and Assignment"] = {
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
		"fieldname": "driver",
		"label": "Driver",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Driver"
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
