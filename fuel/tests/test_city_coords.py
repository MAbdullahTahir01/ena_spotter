from pathlib import Path
from django.test import SimpleTestCase

from fuel.services.city_coords import load_city_coords, parse_geonames_lines

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class ParseGeonamesLinesTest(SimpleTestCase):
    def test_filters_to_populated_places_and_keeps_first(self):
        with open(FIXTURES_DIR / "sample_geonames_US.txt", encoding="utf-8") as f:
            lines = f.readlines()

        rows = list(parse_geonames_lines(lines))

        cities = {(city, state) for city, state, _, _ in rows}
        self.assertIn(("Chicago", "IL"), cities)
        self.assertIn(("Big Cabin", "OK"), cities)
        self.assertIn(("New York City", "NY"), cities)
        # Feature class S (military installation) excluded
        self.assertNotIn(
            ("Cape Canaveral Air Force Station", "FL"), cities
        )
        self.assertEqual(len(rows), 3)


class LoadCityCoordsTest(SimpleTestCase):
    def test_loads_csv_into_uppercased_lookup(self):
        # Deliberately not "sample_city_coords.csv" — that name is a
        # committed static fixture owned by fuel/tests/test_seed_command.py;
        # this test writes and deletes a scratch file, so it must not share
        # a path with a fixture another test reads from disk.
        csv_path = FIXTURES_DIR / "scratch_load_city_coords_test.csv"
        csv_path.write_text(
            "city,state,latitude,longitude\n"
            "Chicago,IL,41.85003,-87.65005\n"
            "Big Cabin,OK,36.53994,-95.21419\n",
            encoding="utf-8",
        )
        try:
            lookup = load_city_coords(csv_path)
            self.assertEqual(
                lookup[("CHICAGO", "IL")], (41.85003, -87.65005)
            )
            self.assertEqual(
                lookup[("BIG CABIN", "OK")], (36.53994, -95.21419)
            )
        finally:
            csv_path.unlink()
