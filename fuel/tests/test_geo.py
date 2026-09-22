from django.test import SimpleTestCase

from fuel.services.geo import haversine_miles


class HaversineMilesTest(SimpleTestCase):
    def test_same_point_is_zero(self):
        self.assertAlmostEqual(haversine_miles(40.0, -90.0, 40.0, -90.0), 0.0)

    def test_known_distance_chicago_to_stlouis(self):
        # Chicago, IL (41.8781, -87.6298) to St. Louis, MO (38.6270, -90.1994)
        # Great-circle distance is ~262 miles.
        distance = haversine_miles(41.8781, -87.6298, 38.6270, -90.1994)
        self.assertAlmostEqual(distance, 262, delta=5)
