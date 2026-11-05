"""Small geometry helpers: point-in-polygon on GeoJSON and haversine distance."""

import json
import math

import frappe


def haversine_km(lat1, lon1, lat2, lon2) -> float:
	r = 6371.0088
	p1, p2 = math.radians(lat1), math.radians(lat2)
	dphi = p2 - p1
	dl = math.radians(lon2 - lon1)
	a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
	return 2 * r * math.asin(math.sqrt(a))


def _ring_contains(ring, lon, lat) -> bool:
	inside = False
	n = len(ring)
	j = n - 1
	for i in range(n):
		xi, yi = ring[i][0], ring[i][1]
		xj, yj = ring[j][0], ring[j][1]
		if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
			inside = not inside
		j = i
	return inside


def _polygon_contains(polygon, lon, lat) -> bool:
	# polygon = [outer, hole1, hole2...]
	if not polygon or not _ring_contains(polygon[0], lon, lat):
		return False
	return not any(_ring_contains(h, lon, lat) for h in polygon[1:])


def _polygons(geo):
	t = geo.get("type")
	if t == "Polygon":
		return [geo["coordinates"]]
	if t == "MultiPolygon":
		return geo["coordinates"]
	if t == "Feature":
		return _polygons(geo["geometry"])
	if t == "FeatureCollection":
		out = []
		for f in geo.get("features", []):
			out += _polygons(f)
		return out
	return []


def point_in_geojson(geojson, lat, lon) -> bool:
	if isinstance(geojson, str):
		geojson = json.loads(geojson)
	return any(_polygon_contains(p, lon, lat) for p in _polygons(geojson or {}))


def point_in_service_area(area: str, lat, lon) -> bool | None:
	"""None when the area has no boundary (cannot decide)."""
	geojson = frappe.db.get_value("Service Area", area, "geojson")
	if not geojson:
		return None
	try:
		return point_in_geojson(geojson, float(lat), float(lon))
	except Exception:
		frappe.log_error(title=f"Bad GeoJSON in Service Area {area}")
		return None


def find_service_area(lat, lon) -> str | None:
	for a in frappe.get_all("Service Area", filters={"disabled": 0}, fields=["name", "geojson"]):
		if a.geojson and point_in_geojson(a.geojson, float(lat), float(lon)):
			return a.name
	return None
