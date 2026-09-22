from django.test import SimpleTestCase, override_settings

from fuel.services.planner import NoFeasibleRouteError, plan_fuel_stops
from fuel.services.stations import StationCandidate


def make_candidate(station_id, distance, price, distance_off_route=0.0):
    return StationCandidate(
        station_id=station_id,
        name=f"Station {station_id}",
        address="",
        city="",
        state="",
        latitude=0.0,
        longitude=0.0,
        price=price,
        distance_along_route_miles=distance,
        distance_off_route_miles=distance_off_route,
    )


class PlanFuelStopsTest(SimpleTestCase):
    @override_settings(FUEL_DEFAULT_PRICE_PER_GALLON=3.50)
    def test_no_stop_needed_within_range_falls_back_to_default_price(self):
        # No candidates at all near this route -> no real price data, so
        # total_cost falls back to the configured default rather than $0.
        plan = plan_fuel_stops([], total_distance_miles=300, max_range_miles=500, mpg=10)

        self.assertEqual(plan.stops, [])
        self.assertAlmostEqual(plan.total_gallons, 30.0)
        self.assertAlmostEqual(plan.total_cost, 30.0 * 3.50)

    def test_no_stop_needed_within_range_uses_cheapest_reachable_price(self):
        # Route fits in one tank, but there's a station within reach -- the
        # vehicle still has to fuel up for the trip, so it's priced at the
        # cheapest station reachable within the first tank's range.
        candidates = [make_candidate(1, 200, 3.10)]

        plan = plan_fuel_stops(candidates, total_distance_miles=300, max_range_miles=500, mpg=10)

        self.assertEqual(plan.stops, [])
        self.assertAlmostEqual(plan.total_gallons, 30.0)
        self.assertAlmostEqual(plan.total_cost, 30.0 * 3.10)

    def test_single_stop_chosen_when_route_exceeds_range(self):
        candidates = [make_candidate(1, 400, 3.00)]

        plan = plan_fuel_stops(candidates, total_distance_miles=700, max_range_miles=500, mpg=10)

        self.assertEqual(len(plan.stops), 1)
        self.assertEqual(plan.stops[0].candidate.station_id, 1)
        # 700 miles / 10 mpg = 70 gallons total. Station 1 ($3.00) is the
        # only -- and so cheapest reachable -- station, so it prices both
        # the initial leg (0->400) and the leg it actually sells (400->700).
        self.assertAlmostEqual(plan.total_gallons, 70.0)
        self.assertAlmostEqual(plan.total_cost, 70.0 * 3.00)

    def test_prefers_cheaper_distant_station_over_nearer_expensive_one(self):
        # Both are reachable for the first leg (<=500mi). Buying at the
        # cheaper station for the whole first leg is optimal even though
        # it's farther from the start, because price applies to the
        # entire leg consumed after buying.
        candidates = [
            make_candidate(1, 100, 4.00),  # near, expensive
            make_candidate(2, 450, 2.50),  # far, cheap, still in range
        ]

        plan = plan_fuel_stops(candidates, total_distance_miles=800, max_range_miles=500, mpg=10)

        stop_ids = [s.candidate.station_id for s in plan.stops]
        self.assertEqual(stop_ids, [2])
        # leg1: 0->450 priced at the cheapest reachable station ($2.50,
        # station 2 itself); leg2: 450->800 (350mi) bought at station 2.
        self.assertAlmostEqual(plan.total_gallons, 80.0)
        self.assertAlmostEqual(plan.total_cost, 80.0 * 2.50)

    def test_raises_when_leg_exceeds_range_with_no_reachable_station(self):
        candidates = [make_candidate(1, 600, 3.00)]  # first leg to it is 600 > 500

        with self.assertRaises(NoFeasibleRouteError):
            plan_fuel_stops(candidates, total_distance_miles=900, max_range_miles=500, mpg=10)

    def test_detour_off_route_adds_round_trip_miles_to_gallons_and_cost(self):
        # Station is 10mi off the route -- the vehicle has to drive there
        # and back (20mi round trip) on top of the route distance itself.
        candidates = [make_candidate(1, 400, 3.00, distance_off_route=10)]

        plan = plan_fuel_stops(candidates, total_distance_miles=700, max_range_miles=500, mpg=10)

        self.assertEqual(len(plan.stops), 1)
        # leg1: 0->400 route miles + 20mi detour = 420mi -> 42 gal @ $3.00 = $126
        # leg2 (final, no detour): 700-400 = 300mi -> 30 gal @ $3.00 = $90
        self.assertAlmostEqual(plan.total_gallons, 72.0)  # (700 + 20) / 10
        self.assertAlmostEqual(plan.total_cost, 216.0)  # 126 + 90

    def test_detour_off_route_counts_against_max_range(self):
        # Route-only distance (495mi) fits in a 500mi tank, but the 20mi
        # round trip to actually reach the station pushes the real leg to
        # 515mi -- over range, so this station must be rejected as unreachable.
        candidates = [make_candidate(1, 495, 3.00, distance_off_route=10)]

        with self.assertRaises(NoFeasibleRouteError):
            plan_fuel_stops(candidates, total_distance_miles=900, max_range_miles=500, mpg=10)

    def test_multi_stop_route_minimizes_total_cost(self):
        candidates = [
            make_candidate(1, 480, 3.50),
            make_candidate(2, 500, 2.80),
            make_candidate(3, 950, 3.00),
        ]

        plan = plan_fuel_stops(candidates, total_distance_miles=1400, max_range_miles=500, mpg=10)

        stop_ids = [s.candidate.station_id for s in plan.stops]
        # Station 2 (500mi, cheapest reachable) also prices the initial
        # leg; from there station 3 (950mi, 450mi leg) is in range; final
        # leg 950->1400 (450mi) is bought at station 3.
        self.assertEqual(stop_ids, [2, 3])
        self.assertAlmostEqual(plan.total_gallons, 140.0)
        expected_cost = (500 / 10) * 2.80 + (450 / 10) * 2.80 + (450 / 10) * 3.00
        self.assertAlmostEqual(plan.total_cost, expected_cost)
