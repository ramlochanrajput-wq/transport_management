frappe.query_reports["Expense Analysis"] = {
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
		"fieldname": "expense_category",
		"label": "Category",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Expense Category"
	},
	{
		"fieldname": "group_by",
		"label": "Group By",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "Category\nVehicle\nDriver\nTrip",
		"default": "Category"
	}
],
};
