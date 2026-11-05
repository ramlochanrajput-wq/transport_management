frappe.query_reports["Booking Register"] = {
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
		"fieldname": "customer",
		"label": "Customer",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Customer"
	},
	{
		"fieldname": "workflow_state",
		"label": "Status",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "\nDraft\nSubmitted\nApproved\nRejected\nCancelled\nConverted"
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
