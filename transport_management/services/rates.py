"""E7 rate cards and quotes."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from transport_management.utils import get_settings, require_feature


def find_rate(from_location, to_location, vehicle_type=None, customer=None, on_date=None):
	on_date = getdate(on_date or nowdate())
	rows = frappe.get_all(
		"Freight Rate",
		filters={"disabled": 0, "from_location": from_location, "to_location": to_location},
		fields=["*"],
	)
	best, best_rank = None, -1
	for r in rows:
		if r.valid_from and getdate(r.valid_from) > on_date:
			continue
		if r.valid_upto and getdate(r.valid_upto) < on_date:
			continue
		if r.vehicle_type and vehicle_type and r.vehicle_type != vehicle_type:
			continue
		if r.customer and r.customer != customer:
			continue
		# a customer-specific, vehicle-specific rate is the most specific
		rank = (2 if r.customer else 0) + (1 if r.vehicle_type else 0)
		if rank > best_rank:
			best, best_rank = r, rank
	return best


def compute_quote(rate, distance_km=None, load_kg=None):
	if rate.rate_basis == "Per Km":
		amount = flt(rate.rate) * flt(distance_km or rate.distance_km)
	elif rate.rate_basis == "Per Tonne":
		amount = flt(rate.rate) * flt(load_kg) / 1000.0
	else:
		amount = flt(rate.rate)
	return max(amount, flt(rate.minimum_charge))


@frappe.whitelist()
def get_quote(booking: str):
	"""Fill quote fields on a booking from the best matching Freight Rate."""
	require_feature("rate_cards")
	b = frappe.get_doc("Vehicle Booking Request", booking)
	b.check_permission("write")
	rate = find_rate(b.pickup_location, b.drop_location, b.vehicle_type, b.customer, b.from_datetime)
	if not rate:
		frappe.throw(_("No active Freight Rate for {0} to {1}").format(b.pickup_location, b.drop_location))
	amount = compute_quote(rate, b.distance_km, b.required_capacity_kg)
	b.db_set(
		{
			"freight_rate": rate.name,
			"quoted_rate": amount,
			"quote_details": f"{rate.rate_basis} @ {rate.rate} (min {flt(rate.minimum_charge)})",
		}
	)
	return {"quoted_rate": amount, "freight_rate": rate.name}


@frappe.whitelist()
def make_sales_order(booking: str):
	"""Create a draft Sales Order whose line carries the quoted freight."""
	require_feature("rate_cards")
	b = frappe.get_doc("Vehicle Booking Request", booking)
	b.check_permission("read")
	frappe.has_permission("Sales Order", "create", throw=True)
	if not b.customer:
		frappe.throw(_("Customer is required to create a Sales Order"))
	if not flt(b.quoted_rate):
		frappe.throw(_("Get a quote first"))
	settings = get_settings()
	if not settings.freight_item:
		frappe.throw(_("Set a Freight Item in Transport Settings"))
	so = frappe.new_doc("Sales Order")
	so.customer = b.customer
	so.company = settings.company or frappe.defaults.get_user_default("Company")
	so.delivery_date = getdate(b.from_datetime)
	so.append(
		"items",
		{
			"item_code": settings.freight_item,
			"qty": 1,
			"rate": b.quoted_rate,
			"description": f"Freight {b.pickup_location} to {b.drop_location} ({b.name})",
		},
	)
	so.insert()
	return so.name
