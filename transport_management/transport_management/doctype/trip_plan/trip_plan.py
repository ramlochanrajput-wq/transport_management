import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, get_datetime, now_datetime, time_diff_in_seconds

from transport_management.services import availability, tracking
from transport_management.services.vehicle_status import refresh_vehicle_status
from transport_management.utils import get_settings, is_enabled

CLOSED_STATES = ("Completed", "Settled", "Cancelled")
OVERRIDE_ROLES = ("Transport Manager", "System Manager")


class TripPlan(Document):
	def before_insert(self):
		if is_enabled("public_tracking") and not self.tracking_token:
			self.tracking_token = tracking.new_token()

	def validate(self):
		self.validate_dates()
		self.sort_stops()
		self.validate_trip_type_rules()
		self.validate_assignment()
		self.validate_state_rules()

	def after_insert(self):
		self._after_assignment_change()

	def on_update(self):
		self._create_override_log()
		self._after_assignment_change()
		self._after_state_change()
		frappe.publish_realtime(
			"tm_trip_update",
			{"trip": self.name, "state": self.workflow_state, "vehicle": self.vehicle},
			after_commit=True,
		)

	def on_trash(self):
		vehicle = self.vehicle
		frappe.db.after_commit.add(lambda: refresh_vehicle_status(vehicle))

	# ------------------------------------------------------------ validation
	def validate_dates(self):
		if self.planned_start and self.planned_end and get_datetime(self.planned_end) <= get_datetime(
			self.planned_start
		):
			frappe.throw(_("Planned End must be after Planned Start"))

	def sort_stops(self):
		for i, s in enumerate(sorted(self.stops, key=lambda x: (cint(x.sequence) or 9999, x.idx)), 1):
			s.sequence = i
		self.stops.sort(key=lambda x: x.sequence)
		for i, s in enumerate(self.stops, 1):
			s.idx = i

	def _trip_type(self):
		return frappe.get_cached_doc("Trip Type", self.trip_type) if self.trip_type else None

	def validate_trip_type_rules(self):
		tt = self._trip_type()
		if tt and cint(tt.requires_stops) and len(self.stops) < 2:
			frappe.throw(_("Trip type {0} needs at least a pickup and a drop stop").format(tt.name))

	def _assignment_changed(self):
		if self.is_new():
			return True
		return any(
			self.has_value_changed(f)
			for f in ("vehicle", "driver", "planned_start", "planned_end", "load_kg")
		)

	def validate_assignment(self):
		if self.workflow_state in CLOSED_STATES:
			return
		if not self._assignment_changed() and not (
			self.has_value_changed("workflow_state") and self.workflow_state == "Started"
		):
			return
		start = self.planned_start
		if self.workflow_state == "Started":
			# trip start re-runs the same checks against the real window
			start = min(get_datetime(self.planned_start), now_datetime()) if self.planned_start else now_datetime()
		failures = availability.validate_assignment(
			self.vehicle, self.driver, start, self.planned_end, flt(self.load_kg) or None, self.name
		)
		self.flags.override_failures = None
		if not failures:
			return
		if not (self.override_reason or "").strip():
			frappe.throw(
				_("Assignment checks failed:") + availability.format_failures(failures)
				+ _("A Transport Manager can proceed by entering an Override Reason."),
				title=_("Cannot assign"),
			)
		if not set(frappe.get_roles()) & set(OVERRIDE_ROLES):
			frappe.throw(
				_("Only a Transport Manager may override failed assignment checks."),
				frappe.PermissionError,
			)
		self.flags.override_failures = failures
		self.override_done = 1

	def validate_state_rules(self):
		if not self.has_value_changed("workflow_state") or self.is_new():
			return
		state = self.workflow_state
		tt = self._trip_type()
		now = now_datetime()

		if state == "Started":
			if tt and cint(tt.requires_start_odometer) and not flt(self.start_odometer):
				frappe.throw(_("Start Odometer is required for trip type {0}").format(tt.name))
			if tt and cint(tt.requires_number_plate_photo) and not frappe.db.exists(
				"Vehicle Inspection Log",
				{"trip_plan": self.name, "inspection_type": ("in", ("Number Plate", "Pre-Trip Start"))},
			):
				frappe.throw(_("A number-plate / pre-trip photo is required before starting"))
			if not self.actual_start:
				self.actual_start = now
			late = time_diff_in_seconds(self.actual_start, self.planned_start) / 60 if self.planned_start else 0
			self.delay_minutes = max(int(late), 0)
		elif state in ("Arrived", "Completed"):
			if state == "Completed":
				self._validate_completion(tt, now)
		elif state == "On Hold" and not (self.hold_reason or "").strip():
			frappe.throw(_("Hold Reason is required"))
		elif state == "Cancelled" and not (self.cancel_reason or "").strip():
			frappe.throw(_("Cancel Reason is required"))

	def _validate_completion(self, tt, now):
		if tt and cint(tt.requires_end_odometer) and not flt(self.end_odometer):
			frappe.throw(_("End Odometer is required for trip type {0}").format(tt.name))
		if flt(self.end_odometer) and flt(self.start_odometer) and flt(self.end_odometer) < flt(self.start_odometer):
			frappe.throw(_("End Odometer cannot be less than Start Odometer"))
		if is_enabled("pod") and tt and cint(tt.requires_pod) and not self.proofs:
			frappe.throw(_("Proof of Delivery is required for trip type {0}").format(tt.name))
		open_stops = [s.location for s in self.stops if s.status in ("Pending", "Arrived")]
		if open_stops:
			frappe.throw(
				_("Complete or skip all stops first: {0}").format(", ".join(open_stops[:5]))
			)
		self.actual_end = self.actual_end or now
		self.distance_km = max(flt(self.end_odometer) - flt(self.start_odometer), 0)
		if self.planned_end:
			overrun = time_diff_in_seconds(self.actual_end, self.planned_end) / 60
			threshold = cint(get_settings().delay_threshold_minutes)
			if overrun > threshold:
				self.delay_minutes = max(cint(self.delay_minutes), int(overrun))
				if not (self.delay_reason or "").strip():
					frappe.throw(_("Delay Reason is required (trip finished {0} min late)").format(int(overrun)))

	# ---------------------------------------------------------- side effects
	def _create_override_log(self):
		failures = self.flags.get("override_failures")
		if not failures:
			return
		frappe.get_doc(
			{
				"doctype": "Override Log",
				"reference_doctype": "Trip Plan",
				"reference_name": self.name,
				"override_type": "Assignment",
				"failed_checks": "\n".join(f["message"] for f in failures),
				"reason": self.override_reason,
			}
		).insert(ignore_permissions=True)
		self.flags.override_failures = None

	def _after_assignment_change(self):
		before = self.get_doc_before_save()
		for v in {self.vehicle, getattr(before, "vehicle", None)}:
			refresh_vehicle_status(v)

	def _after_state_change(self):
		before = self.get_doc_before_save()
		if not before or before.workflow_state == self.workflow_state:
			return
		if self.workflow_state in ("Completed", "Settled") and flt(self.end_odometer) and self.vehicle:
			current = flt(frappe.db.get_value("Vehicle", self.vehicle, "last_odometer"))
			if flt(self.end_odometer) > current:
				frappe.db.set_value("Vehicle", self.vehicle, "last_odometer", self.end_odometer)
		if self.workflow_state == "Cancelled" and self.booking:
			frappe.db.set_value("Vehicle Booking Request", self.booking, "trip_plan", None)


# ------------------------------------------------------------------ helpers
def update_totals(trip: str):
	"""Recompute advance / expense / profit on a trip. Called from advance, expense and settlement."""
	if not trip or not frappe.db.exists("Trip Plan", trip):
		return
	adv = frappe.db.sql(
		"select ifnull(sum(amount),0) from `tabTrip Advance` where trip_plan=%s and docstatus=1", trip
	)[0][0]
	exp = frappe.db.sql(
		"select ifnull(sum(amount),0) from `tabTrip Expense` where trip_plan=%s and docstatus=1", trip
	)[0][0]
	allowance = frappe.db.sql(
		"select ifnull(sum(driver_allowance),0) from `tabTrip Settlement` where trip_plan=%s and docstatus=1",
		trip,
	)[0][0]
	freight = flt(frappe.db.get_value("Trip Plan", trip, "freight_amount"))
	frappe.db.set_value(
		"Trip Plan",
		trip,
		{
			"total_advance": adv,
			"total_expense": exp,
			"profit": freight - flt(exp) - flt(allowance),
		},
		update_modified=False,
	)


@frappe.whitelist()
def add_proof_of_delivery(trip, receiver_name, signature=None, photo=None, otp=None, remarks=None,
                          stop_sequence=None, receiver_phone=None):
	"""E5. Used by the driver app and the desk form."""
	from transport_management.utils import require_feature

	require_feature("pod")
	doc = frappe.get_doc("Trip Plan", trip)
	doc.check_permission("write")
	doc.append(
		"proofs",
		{
			"receiver_name": receiver_name,
			"receiver_phone": receiver_phone,
			"signature": signature,
			"photo": photo,
			"remarks": remarks,
			"stop_sequence": cint(stop_sequence),
			"delivered_on": now_datetime(),
			"otp_verified": 1 if otp and str(otp) == _delivery_otp(trip) else 0,
		},
	)
	doc.save()
	return doc.proofs[-1].name


def _delivery_otp(trip: str) -> str:
	"""Deterministic 4-digit OTP for a trip (shared with the receiver by the dispatcher)."""
	import hashlib

	secret = frappe.local.conf.get("encryption_key") or "tm"
	return str(int(hashlib.sha256(f"{secret}:{trip}".encode()).hexdigest(), 16) % 10000).zfill(4)


@frappe.whitelist()
def get_delivery_otp(trip):
	frappe.has_permission("Trip Plan", "write", trip, throw=True)
	return _delivery_otp(trip)
