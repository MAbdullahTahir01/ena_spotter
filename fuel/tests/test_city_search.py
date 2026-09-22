from django.test import SimpleTestCase

from fuel.services import city_search


class SearchCitiesTest(SimpleTestCase):
    def test_short_query_returns_no_results(self):
        self.assertEqual(city_search.search_cities("c"), [])

    def test_prefix_match_finds_known_city(self):
        results = city_search.search_cities("Chicago")

        labels = [r["label"] for r in results]
        self.assertTrue(any(label.startswith("Chicago, IL") for label in labels))

    def test_results_capped_at_limit(self):
        results = city_search.search_cities("san", limit=3)

        self.assertLessEqual(len(results), 3)

    def test_result_shape(self):
        results = city_search.search_cities("Chicago", limit=1)

        self.assertTrue(results)
        result = results[0]
        self.assertIn("label", result)
        self.assertIn("city", result)
        self.assertIn("state", result)


class IsKnownCityTest(SimpleTestCase):
    def test_recognizes_real_city_state_pair(self):
        self.assertTrue(city_search.is_known_city("Chicago, IL"))
        self.assertTrue(city_search.is_known_city("chicago, il"))

    def test_rejects_junk_input(self):
        self.assertFalse(city_search.is_known_city("h"))
        self.assertFalse(city_search.is_known_city("u"))
        self.assertFalse(city_search.is_known_city("??"))

    def test_rejects_city_with_wrong_state(self):
        self.assertFalse(city_search.is_known_city("Chicago, ZZ"))
