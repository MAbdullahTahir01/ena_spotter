import json
from unittest import mock

from django.test import Client, TestCase

from fuel.services.geocode import GeocodeError
from fuel.services.local_astar import LocalAStarUnavailable
from fuel.services.routing import RouteResult, RoutingError


class RouteViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    @mock.patch("fuel.views.plan_fuel_stops")
    @mock.patch("fuel.views.find_candidate_stops")
    @mock.patch("fuel.views.get_route")
    @mock.patch("fuel.views.geocode_address")
    def test_happy_path_returns_expected_shape(
        self, mock_geocode, mock_get_route, mock_find_candidates, mock_plan
    ):
        mock_geocode.side_effect = [(41.8781, -87.6298), (34.0522, -118.2437)]
        mock_get_route.return_value = RouteResult(
            geometry=[(41.8781, -87.6298), (34.0522, -118.2437)],
            distance_miles=1745.0,
        )
        mock_find_candidates.return_value = []

        from fuel.services.planner import FuelPlan

        mock_plan.return_value = FuelPlan(
            stops=[], total_gallons=174.5, total_cost=0.0, actual_distance_miles=1745.0
        )

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["status"])
        data = body["data"]
        self.assertAlmostEqual(data["distance_miles"], 1745.0)
        self.assertAlmostEqual(data["total_gallons"], 174.5)
        self.assertIn("route_geometry", data)
        self.assertIn("fuel_stops", data)

    def test_missing_fields_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_non_dict_json_body_returns_400_not_500(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps([1, 2, 3]),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_non_string_field_values_return_400_not_500(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": 123, "finish": "Denver, CO"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @mock.patch("fuel.views.geocode_address")
    def test_geocode_failure_returns_400(self, mock_geocode):
        mock_geocode.side_effect = GeocodeError("no result")

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "??", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @mock.patch("fuel.views.get_route")
    @mock.patch("fuel.views.geocode_address")
    def test_routing_failure_returns_502(self, mock_geocode, mock_get_route):
        mock_geocode.side_effect = [(41.8781, -87.6298), (34.0522, -118.2437)]
        mock_get_route.side_effect = RoutingError("osrm down")

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)

    @mock.patch("fuel.views.plan_fuel_stops")
    @mock.patch("fuel.views.find_candidate_stops")
    @mock.patch("fuel.views.get_route_local_astar")
    @mock.patch("fuel.views.geocode_address")
    def test_classic_a_star_engine_used_when_requested(
        self, mock_geocode, mock_get_route_local, mock_find_candidates, mock_plan
    ):
        mock_geocode.side_effect = [(41.8781, -87.6298), (41.8920, -87.6298)]
        mock_get_route_local.return_value = RouteResult(
            geometry=[(41.8781, -87.6298), (41.8920, -87.6298)],
            distance_miles=2.0,
        )
        mock_find_candidates.return_value = []

        from fuel.services.planner import FuelPlan

        mock_plan.return_value = FuelPlan(
            stops=[], total_gallons=0.2, total_cost=0.0, actual_distance_miles=2.0
        )

        response = self.client.post(
            "/api/route/",
            data=json.dumps(
                {"start": "Chicago, IL", "finish": "Evanston, IL", "engine": "classic_a_star"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["engine"], "classic_a_star")
        mock_get_route_local.assert_called_once()

    @mock.patch("fuel.views.get_route_local_astar")
    @mock.patch("fuel.views.geocode_address")
    def test_classic_a_star_unavailable_returns_400(self, mock_geocode, mock_get_route_local):
        mock_geocode.side_effect = [(41.8781, -87.6298), (34.0522, -118.2437)]
        mock_get_route_local.side_effect = LocalAStarUnavailable("too far")

        response = self.client.post(
            "/api/route/",
            data=json.dumps(
                {"start": "Chicago, IL", "finish": "Los Angeles, CA", "engine": "classic_a_star"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    @mock.patch("fuel.views.plan_fuel_stops")
    @mock.patch("fuel.views.find_candidate_stops")
    @mock.patch("fuel.views.get_route_local_astar")
    @mock.patch("fuel.views.geocode_address")
    def test_auto_engine_picks_classic_a_star_for_short_trip(
        self, mock_geocode, mock_get_route_local, mock_find_candidates, mock_plan
    ):
        mock_geocode.side_effect = [(41.8781, -87.6298), (41.8920, -87.6298)]  # ~1 mi apart
        mock_get_route_local.return_value = RouteResult(
            geometry=[(41.8781, -87.6298), (41.8920, -87.6298)],
            distance_miles=2.0,
        )
        mock_find_candidates.return_value = []

        from fuel.services.planner import FuelPlan

        mock_plan.return_value = FuelPlan(
            stops=[], total_gallons=0.2, total_cost=0.0, actual_distance_miles=2.0
        )

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "Evanston, IL"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["engine"], "classic_a_star")

    @mock.patch("fuel.views.plan_fuel_stops")
    @mock.patch("fuel.views.find_candidate_stops")
    @mock.patch("fuel.views.get_route")
    @mock.patch("fuel.views.geocode_address")
    def test_auto_engine_picks_osrm_for_long_trip(
        self, mock_geocode, mock_get_route, mock_find_candidates, mock_plan
    ):
        mock_geocode.side_effect = [(41.8781, -87.6298), (34.0522, -118.2437)]
        mock_get_route.return_value = RouteResult(
            geometry=[(41.8781, -87.6298), (34.0522, -118.2437)],
            distance_miles=1745.0,
        )
        mock_find_candidates.return_value = []

        from fuel.services.planner import FuelPlan

        mock_plan.return_value = FuelPlan(
            stops=[], total_gallons=174.5, total_cost=0.0, actual_distance_miles=1745.0
        )

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "Los Angeles, CA"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["engine"], "osrm")

    @mock.patch("fuel.views.plan_fuel_stops")
    @mock.patch("fuel.views.find_candidate_stops")
    @mock.patch("fuel.views.get_route")
    @mock.patch("fuel.views.get_route_local_astar")
    @mock.patch("fuel.views.geocode_address")
    def test_auto_engine_falls_back_to_osrm_silently(
        self, mock_geocode, mock_get_route_local, mock_get_route, mock_find_candidates, mock_plan
    ):
        mock_geocode.side_effect = [(41.8781, -87.6298), (41.8920, -87.6298)]
        mock_get_route_local.side_effect = LocalAStarUnavailable("no local graph path")
        mock_get_route.return_value = RouteResult(
            geometry=[(41.8781, -87.6298), (41.8920, -87.6298)],
            distance_miles=2.0,
        )
        mock_find_candidates.return_value = []

        from fuel.services.planner import FuelPlan

        mock_plan.return_value = FuelPlan(
            stops=[], total_gallons=0.2, total_cost=0.0, actual_distance_miles=2.0
        )

        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "Evanston, IL"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["engine"], "osrm")

    def test_invalid_engine_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps(
                {"start": "Chicago, IL", "finish": "Evanston, IL", "engine": "hierarchical_geohash"}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_same_start_and_finish_returns_400(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "chicago, il"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unrecognized_start_returns_400_without_geocoding(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "h", "finish": "Evanston, IL"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unrecognized_finish_returns_400_without_geocoding(self):
        response = self.client.post(
            "/api/route/",
            data=json.dumps({"start": "Chicago, IL", "finish": "u"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_city_search_returns_results(self):
        response = self.client.get("/api/cities/?q=Chicago")

        self.assertEqual(response.status_code, 200)
        results = response.json()["data"]["results"]
        self.assertTrue(any("Chicago" in r["label"] for r in results))

    def test_city_search_short_query_returns_empty(self):
        response = self.client.get("/api/cities/?q=c")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["results"], [])

    def test_get_not_allowed_on_route_endpoint(self):
        response = self.client.get("/api/route/")

        self.assertEqual(response.status_code, 405)

    def test_index_view_renders(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "index.html")

    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["status"])

    def test_health_endpoint_rejects_post(self):
        response = self.client.post("/api/health/")

        self.assertEqual(response.status_code, 405)
