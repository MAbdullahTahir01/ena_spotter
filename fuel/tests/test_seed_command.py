from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from fuel.models import FuelStation

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class SeedFuelStationsCommandTest(TestCase):
    def test_loads_matched_rows_and_reports_unmatched(self):
        out = StringIO()
        call_command(
            "seed_fuel_stations",
            "--prices",
            str(FIXTURES_DIR / "sample_prices.csv"),
            "--city-coords",
            str(FIXTURES_DIR / "sample_city_coords.csv"),
            stdout=out,
        )

        self.assertEqual(FuelStation.objects.count(), 2)
        big_cabin = FuelStation.objects.get(truckstop_id=7)
        self.assertAlmostEqual(big_cabin.latitude, 36.53994)
        self.assertAlmostEqual(big_cabin.longitude, -95.21419)
        self.assertIn("1 row(s) skipped", out.getvalue())

    def test_duplicate_truckstop_id_keeps_lowest_price(self):
        out = StringIO()
        call_command(
            "seed_fuel_stations",
            "--prices",
            str(FIXTURES_DIR / "sample_prices.csv"),
            "--city-coords",
            str(FIXTURES_DIR / "sample_city_coords.csv"),
            stdout=out,
        )

        # truckstop_id 9 appears 3 times in the fixture (3.28733333, 3.199,
        # 3.455) -- only the lowest price should survive as a single row.
        self.assertEqual(FuelStation.objects.filter(truckstop_id=9).count(), 1)
        kwik_trip = FuelStation.objects.get(truckstop_id=9)
        self.assertAlmostEqual(kwik_trip.price, 3.199)
        self.assertIn("2 duplicate row(s) collapsed to their lowest price", out.getvalue())
