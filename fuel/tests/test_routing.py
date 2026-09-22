from unittest import mock

import requests
from django.test import SimpleTestCase

from fuel.services import routing


class GetRouteTest(SimpleTestCase):
    @mock.patch("fuel.services.routing.requests.get")
    def test_returns_geometry_and_distance(self, mock_get):
        mock_get.return_value = mock.Mock(
            status_code=200,
            json=lambda: {
                "code": "Ok",
                "routes": [
                    {
                        "distance": 402336.0,  # meters == 250 miles
                        "geometry": {
                            "coordinates": [
                                [-87.6298, 41.8781],
                                [-90.1994, 38.6270],
                            ]
                        },
                    }
                ],
            },
        )
        mock_get.return_value.raise_for_status = mock.Mock()

        result = routing.get_route((41.8781, -87.6298), (38.6270, -90.1994))

        self.assertAlmostEqual(result.distance_miles, 250.0, delta=0.5)
        self.assertEqual(result.geometry[0], (41.8781, -87.6298))
        self.assertEqual(result.geometry[1], (38.6270, -90.1994))
        mock_get.assert_called_once()

    @mock.patch("fuel.services.routing.requests.get")
    def test_raises_when_no_route_found(self, mock_get):
        mock_get.return_value = mock.Mock(
            status_code=200, json=lambda: {"code": "NoRoute", "routes": []}
        )
        mock_get.return_value.raise_for_status = mock.Mock()

        with self.assertRaises(routing.RoutingError):
            routing.get_route((0.0, 0.0), (1.0, 1.0))

    @mock.patch("fuel.services.routing.requests.get")
    def test_raises_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.Timeout("timed out")

        with self.assertRaises(routing.RoutingError):
            routing.get_route((0.0, 0.0), (1.0, 1.0))


class CumulativeDistancesTest(SimpleTestCase):
    def test_first_point_is_zero_and_accumulates(self):
        geometry = [
            (41.8781, -87.6298),  # Chicago
            (38.6270, -90.1994),  # St. Louis, ~262 mi from Chicago (per Task 3 ruling)
        ]

        table = routing.cumulative_distances(geometry)

        self.assertEqual(len(table), 2)
        self.assertEqual(table[0], (41.8781, -87.6298, 0.0))
        lat, lon, cumulative = table[1]
        self.assertEqual((lat, lon), (38.6270, -90.1994))
        self.assertAlmostEqual(cumulative, 262, delta=5)
