# Transport Management

Custom Frappe v16 app (ERPNext + HRMS) implementing the Vehicle & Transport BRD (5.1-5.16) plus the optional Fleetbase-style extras (E1-E20). Nothing in frappe, erpnext or hrms is modified: extensions are Custom Fields, doc events, and the app's own DocTypes.

## Install
    bench get-app /path/to/transport_management   # already in apps/
    bench --site <site> install-app transport_management
    bench --site <site> migrate && bench build --app transport_management

Then open **Transport Settings** (accounts, feature switches, limits). Give users the roles Transport Manager / Coordinator / Dispatcher / Driver / Integrator. Link each driver app user through `Driver.user`.

## Where things live
- `services/availability.py` single validation used by booking, assignment and trip start
- `services/dispatch.py` advisory suggestions (never auto-assigns), `services/rates.py` quotes, `services/tracking.py` public view + location ingest
- `setup/install.py`, `setup/workflows.py` roles, custom fields, workflows, notifications (idempotent, runs on migrate; existing workflows are never overwritten)
- `api.py` driver app, GPS device and integrator endpoints; `scheduler/jobs.py` reminders, delay/stale/geofence checks, retention
- `www/track.*` public link `/track/<token>`; `www/driver/` PWA at `/driver/app`
- Pages: Live Fleet Map, Dispatch Board. 15 Script Reports.

## Limits
Browser GPS only works while the PWA is open; continuous tracking needs a native wrapper or a GPS device posting to `transport_management.api.post_location`.
