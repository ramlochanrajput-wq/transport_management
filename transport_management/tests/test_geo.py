import unittest

from transport_management.services.geo import haversine_km, point_in_geojson

SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]}
HOLE = {"type": "Polygon", "coordinates": [SQUARE["coordinates"][0], [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]]}


class TestGeo(unittest.TestCase):
	def test_inside_outside(self):
		self.assertTrue(point_in_geojson(SQUARE, lat=5, lon=5))
		self.assertFalse(point_in_geojson(SQUARE, lat=15, lon=5))

	def test_hole(self):
		self.assertFalse(point_in_geojson(HOLE, lat=5, lon=5))
		self.assertTrue(point_in_geojson(HOLE, lat=2, lon=2))

	def test_haversine(self):
		self.assertAlmostEqual(haversine_km(0, 0, 0, 1), 111.19, delta=0.2)
