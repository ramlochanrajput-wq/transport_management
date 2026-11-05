"""Workflow definitions (BRD 5.3, 5.6, 5.9, 5.10). Created once; admins may adapt them afterwards."""

MGR = "Transport Manager"
COORD = "Transport Coordinator"
DISP = "Transport Dispatcher"
DRV = "Transport Driver"
INTEG = "Transport Integrator"
ACC = "Accounts User"
ACC_MGR = "Accounts Manager"


def S(state, allow_edit, doc_status=0, style=None):
	return {"state": state, "allow_edit": allow_edit, "doc_status": doc_status, "style": style}


def T(state, action, next_state, allowed, condition=None):
	return {"state": state, "action": action, "next_state": next_state, "allowed": allowed, "condition": condition}


BOOKING = {
	"workflow_name": "Vehicle Booking Request Approval",
	"document_type": "Vehicle Booking Request",
	"states": [
		S("Draft", (COORD, DISP, INTEG)),
		S("Submitted", MGR, style="Warning"),
		S("Approved", MGR, style="Success"),
		S("Rejected", (COORD, DISP), style="Danger"),
		S("Cancelled", MGR, style="Danger"),
		S("Converted", MGR, style="Primary"),
	],
	"transitions": [
		T("Draft", "Submit Request", "Submitted", COORD),
		T("Draft", "Submit Request", "Submitted", DISP),
		T("Draft", "Submit Request", "Submitted", INTEG),
		T("Submitted", "Approve", "Approved", MGR),
		T("Submitted", "Reject", "Rejected", MGR),
		T("Rejected", "Reopen", "Draft", COORD),
		T("Draft", "Cancel Request", "Cancelled", COORD),
		T("Submitted", "Cancel Request", "Cancelled", MGR),
		T("Approved", "Cancel Request", "Cancelled", MGR),
	],
}

_MOVERS = (DRV, DISP, MGR)

TRIP = {
	"workflow_name": "Trip Plan Lifecycle",
	"document_type": "Trip Plan",
	"states": [
		S("Planned", (COORD, DISP, MGR)),
		S("Approved", _MOVERS, style="Primary"),
		S("Started", _MOVERS, style="Info"),
		S("In Transit", _MOVERS, style="Info"),
		S("Arrived", _MOVERS, style="Info"),
		S("Completed", (COORD, MGR), style="Success"),
		S("Settled", MGR, style="Success"),
		S("On Hold", MGR, style="Warning"),
		S("Cancelled", MGR, style="Danger"),
	],
	"transitions": [
		T("Planned", "Approve Trip", "Approved", MGR),
		*[T("Approved", "Start Trip", "Started", r) for r in _MOVERS],
		*[T("Started", "Mark In Transit", "In Transit", r) for r in _MOVERS],
		*[T("Started", "Arrive", "Arrived", r) for r in _MOVERS],
		*[T("In Transit", "Arrive", "Arrived", r) for r in _MOVERS],
		*[T("Arrived", "Complete Trip", "Completed", r) for r in _MOVERS],
		T("Approved", "Hold", "On Hold", MGR),
		T("Started", "Hold", "On Hold", MGR),
		T("In Transit", "Hold", "On Hold", MGR),
		T("On Hold", "Resume", "In Transit", MGR, "doc.actual_start"),
		T("On Hold", "Resume", "Approved", MGR, "not doc.actual_start"),
		T("Planned", "Cancel Trip", "Cancelled", MGR),
		T("Approved", "Cancel Trip", "Cancelled", MGR),
		T("On Hold", "Cancel Trip", "Cancelled", MGR),
	],
}

EXPENSE = {
	"workflow_name": "Trip Expense Approval",
	"document_type": "Trip Expense",
	"states": [
		S("Draft", (COORD, DRV)),
		S("Pending Approval", (MGR, COORD), style="Warning"),
		S("Approved", MGR, 1, style="Success"),
		S("Rejected", (COORD, DRV), style="Danger"),
		S("Cancelled", MGR, 2, style="Danger"),
	],
	"transitions": [
		T("Draft", "Send for Approval", "Pending Approval", COORD),
		T("Draft", "Send for Approval", "Pending Approval", DRV),
		T("Pending Approval", "Approve", "Approved", MGR),
		# coordinators may approve only within the monetary limits (needs_manager is computed on save)
		T("Pending Approval", "Approve", "Approved", COORD, "doc.needs_manager == 0"),
		T("Pending Approval", "Reject", "Rejected", MGR),
		T("Pending Approval", "Reject", "Rejected", COORD),
		T("Rejected", "Reopen", "Draft", COORD),
		T("Rejected", "Reopen", "Draft", DRV),
		T("Approved", "Cancel", "Cancelled", MGR),
	],
}

SETTLEMENT = {
	"workflow_name": "Trip Settlement Approval",
	"document_type": "Trip Settlement",
	"states": [
		S("Draft", (COORD, MGR, ACC)),
		S("Pending Accounts", ACC, style="Warning"),
		S("Settled", ACC, 1, style="Success"),
		S("Cancelled", ACC_MGR, 2, style="Danger"),
	],
	"transitions": [
		T("Draft", "Send to Accounts", "Pending Accounts", COORD),
		T("Draft", "Send to Accounts", "Pending Accounts", MGR),
		T("Pending Accounts", "Send Back", "Draft", ACC),
		T("Pending Accounts", "Post Settlement", "Settled", ACC),
		T("Settled", "Cancel", "Cancelled", ACC_MGR),
	],
}

WORKFLOWS = [BOOKING, TRIP, EXPENSE, SETTLEMENT]
