import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from transport_management.utils import get_settings


class FuelLog(Document):
	def validate(self):
		if flt(self.litres) <= 0:
			frappe.throw(_("Litres must be greater than zero"))
		if not flt(self.amount) and flt(self.rate):
			self.amount = flt(self.litres) * flt(self.rate)
		self.compute_mileage()

	def compute_mileage(self):
		prev = frappe.db.get_value(
			"Fuel Log",
			{"vehicle": self.vehicle, "name": ("!=", self.name or ""), "odometer": ("<", flt(self.odometer))},
			["odometer"],
			order_by="odometer desc",
		)
		self.previous_odometer = flt(prev)
		self.km_run = max(flt(self.odometer) - flt(prev), 0) if prev else 0
		self.kmpl = round(self.km_run / flt(self.litres), 2) if self.km_run and flt(self.litres) else 0
		self.anomaly, self.anomaly_note = 0, None
		if not self.kmpl:
			return
		recent = frappe.get_all(
			"Fuel Log",
			filters={"vehicle": self.vehicle, "name": ("!=", self.name or ""), "kmpl": (">", 0)},
			pluck="kmpl",
			order_by="odometer desc",
			limit=5,
		)
		if recent:
			avg = sum(recent) / len(recent)
			pct = abs(self.kmpl - avg) / avg * 100
			if pct > flt(get_settings().fuel_anomaly_percent or 25):
				self.anomaly = 1
				self.anomaly_note = _("{0} km/l vs recent average {1} km/l ({2}% off)").format(
					self.kmpl, round(avg, 2), round(pct)
				)
