import time

from django.conf import settings
from django.test import TestCase

from fuel.models import FuelStation
from fuel.services.geo import haversine_miles
from fuel.services.stations import find_candidate_stops


class FindCandidateStopsTest(TestCase):
    def setUp(self):
        # A straight route along latitude 40.0, from lon -90 to lon -85.
        self.route = [
            (40.0, -90.0, 0.0),
            (40.0, -87.5, 130.0),
            (40.0, -85.0, 260.0),
        ]

    def test_keeps_station_near_route_and_computes_projected_distance(self):
        FuelStation.objects.create(
            truckstop_id=1, name="On Route", address="", city="X", state="IL",
            latitude=40.0, longitude=-87.5, price=3.50,
        )

        candidates = find_candidate_stops(self.route, corridor_miles=5.0)

        self.assertEqual(len(candidates), 1)
        self.assertAlmostEqual(candidates[0].distance_along_route_miles, 130.0, delta=1)
        self.assertEqual(candidates[0].price, 3.50)

    def test_excludes_station_far_from_route(self):
        FuelStation.objects.create(
            truckstop_id=2, name="Far Away", address="", city="Y", state="TX",
            latitude=29.0, longitude=-95.0, price=3.10,
        )

        candidates = find_candidate_stops(self.route, corridor_miles=5.0)

        self.assertEqual(candidates, [])

    def test_results_sorted_by_distance_along_route(self):
        station_near_end = FuelStation.objects.create(
            truckstop_id=3, name="Near End", address="", city="Z", state="IN",
            latitude=40.0, longitude=-85.09, price=3.20,
        )
        station_near_start = FuelStation.objects.create(
            truckstop_id=4, name="Near Start", address="", city="W", state="IL",
            latitude=40.0, longitude=-89.91, price=3.80,
        )

        candidates = find_candidate_stops(self.route, corridor_miles=5.0)

        # Results should be sorted by distance_along_route_miles ascending:
        # station_near_start (lon -89.91) is near route start -> distance ~0
        # station_near_end (lon -85.09) is near route end -> distance ~260
        self.assertEqual([c.station_id for c in candidates], [station_near_start.id, station_near_end.id])


class FindCandidateStopsEdgeBandTest(TestCase):
    def test_returns_station_between_corridor_miles_and_acceptance_threshold(self):
        # Straight route along latitude 40.0, matching FindCandidateStopsTest.setUp.
        route = [
            (40.0, -90.0, 0.0),
            (40.0, -87.5, 130.0),
            (40.0, -85.0, 260.0),
        ]
        corridor_miles = 5.0
        acceptance_threshold = corridor_miles + settings.FUEL_SAMPLE_SPACING_MILES  # 6.0

        # Place a station directly "north" of the middle route point, at a true
        # distance from the route that falls strictly inside the
        # corridor_miles..acceptance_threshold edge band (roughly 5.0-6.0 mi).
        # This band is exactly what the widened acceptance threshold exists to
        # catch, and exactly what a margin sized to corridor_miles (instead of
        # acceptance_threshold) would incorrectly exclude -- both at the SQL
        # bounding-box query and at the inner per-point latitude pre-check.
        lat_offset = 5.5 / settings.FUEL_MILES_PER_DEGREE_LAT
        station_lat = 40.0 + lat_offset
        station_lon = -87.5

        true_distance = haversine_miles(station_lat, station_lon, 40.0, -87.5)
        self.assertGreater(true_distance, corridor_miles)
        self.assertLess(true_distance, acceptance_threshold)

        station = FuelStation.objects.create(
            truckstop_id=5, name="Edge Band", address="", city="X", state="IL",
            latitude=station_lat, longitude=station_lon, price=3.60,
        )

        candidates = find_candidate_stops(route, corridor_miles=corridor_miles)

        self.assertEqual([c.station_id for c in candidates], [station.id])


class FindCandidateStopsPerformanceTest(TestCase):
    def test_completes_quickly_on_large_coast_to_coast_style_route(self):
        # Simulate an OSRM overview=full geometry for a long (~3000 mile) route:
        # tens of thousands of cumulative-distance points, same order of magnitude
        # as a real LA -> NYC route (33,715 points). Without decimation, the
        # nearest-point scan is O(stations * points) and this regresses to ~45s.
        n_points = 33_715
        total_miles = 2800.0
        lon_start, lon_end = -118.24, -73.99
        cumulative_table = []
        for i in range(n_points):
            frac = i / (n_points - 1)
            lat = 34.05 + frac * (40.71 - 34.05)
            lon = lon_start + frac * (lon_end - lon_start)
            cumulative = frac * total_miles
            cumulative_table.append((lat, lon, cumulative))

        # A handful of stations scattered near/along the route so the inner
        # nearest-point scan actually runs against real queryset rows.
        for i in range(25):
            frac = i / 24
            lat = 34.05 + frac * (40.71 - 34.05)
            lon = lon_start + frac * (lon_end - lon_start)
            FuelStation.objects.create(
                truckstop_id=1000 + i,
                name=f"Station {i}",
                address="",
                city="City",
                state="CA",
                latitude=lat + 0.01,
                longitude=lon + 0.01,
                price=3.50,
            )

        start = time.monotonic()
        candidates = find_candidate_stops(cumulative_table, corridor_miles=5.0)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 5.0, f"find_candidate_stops took {elapsed:.2f}s, expected well under 5s")
        self.assertEqual(len(candidates), 25)
