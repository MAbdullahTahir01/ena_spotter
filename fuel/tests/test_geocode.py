from unittest import mock

import requests
from django.test import SimpleTestCase

from fuel.services import geocode


class GeocodeAddressTest(SimpleTestCase):
    def setUp(self):
        geocode._CACHE.clear()

    @mock.patch("fuel.services.geocode.requests.get")
    def test_returns_lat_lon_from_first_result(self, mock_get):
        mock_get.return_value = mock.Mock(
            status_code=200,
            json=lambda: [{"lat": "41.8781", "lon": "-87.6298"}],
        )
        mock_get.return_value.raise_for_status = mock.Mock()

        lat, lon = geocode.geocode_address("Chicago, IL")

        self.assertAlmostEqual(lat, 41.8781)
        self.assertAlmostEqual(lon, -87.6298)
        mock_get.assert_called_once()

    @mock.patch("fuel.services.geocode.requests.get")
    def test_raises_on_no_results(self, mock_get):
        mock_get.return_value = mock.Mock(status_code=200, json=lambda: [])
        mock_get.return_value.raise_for_status = mock.Mock()

        with self.assertRaises(geocode.GeocodeError):
            geocode.geocode_address("Nowhereville, ZZ")

    @mock.patch("fuel.services.geocode.requests.get")
    def test_raises_on_request_exception(self, mock_get):
        mock_get.side_effect = requests.Timeout("timed out")

        with self.assertRaises(geocode.GeocodeError):
            geocode.geocode_address("Chicago, IL")

    @mock.patch("fuel.services.geocode.requests.get")
    def test_second_call_with_same_query_is_cached(self, mock_get):
        mock_get.return_value = mock.Mock(
            status_code=200,
            json=lambda: [{"lat": "41.8781", "lon": "-87.6298"}],
        )
        mock_get.return_value.raise_for_status = mock.Mock()

        geocode.geocode_address("Chicago, IL")
        geocode.geocode_address("chicago, il")  # same, different case/whitespace

        mock_get.assert_called_once()
