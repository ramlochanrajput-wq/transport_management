frappe.query_reports["Document Expiry"] = {
	filters: [
	{
		"fieldname": "within_days",
		"label": "Expiring Within (days)",
		"fieldtype": "Int",
		"reqd": 0,
		"default": "60"
	},
	{
		"fieldname": "applies_to",
		"label": "Applies To",
		"fieldtype": "Select",
		"reqd": 0,
		"options": "\nVehicle\nDriver"
	},
	{
		"fieldname": "fleet",
		"label": "Fleet",
		"fieldtype": "Link",
		"reqd": 0,
		"options": "Transport Fleet"
	},
	{
		"fieldname": "only_mandatory",
		"label": "Mandatory Only",
		"fieldtype": "Check",
		"reqd": 0
	}
],
};
