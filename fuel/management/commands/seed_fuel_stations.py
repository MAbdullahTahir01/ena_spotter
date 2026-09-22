import csv

from django.core.management.base import BaseCommand

from fuel.models import FuelStation
from fuel.services.city_coords import load_city_coords


class Command(BaseCommand):
    help = "Load fuel-prices CSV into FuelStation rows, resolving city/state to lat/lon."

    def add_arguments(self, parser):
        parser.add_argument("--prices", required=True, help="Path to the fuel prices CSV")
        parser.add_argument("--city-coords", required=True, help="Path to city,state,latitude,longitude CSV")
        parser.add_argument("--clear", action="store_true", help="Delete existing FuelStation rows first")

    def handle(self, *args, **options):
        if options["clear"]:
            FuelStation.objects.all().delete()

        coords = load_city_coords(options["city_coords"])

        # The source CSV lists the same physical truckstop (same OPIS Truckstop
        # ID) more than once for ~10% of stations, each copy with a different
        # price and no way to tell which is current. Keep only the lowest
        # price per truckstop_id, since a real trip would always choose it
        # over a pricier duplicate at the same location anyway.
        cheapest_by_truckstop_id: dict[int, FuelStation] = {}
        matched_rows = 0
        skipped = 0
        with open(options["prices"], newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["City"].strip().upper(), row["State"].strip().upper())
                latlon = coords.get(key)
                if latlon is None:
                    skipped += 1
                    continue
                lat, lon = latlon
                matched_rows += 1

                truckstop_id = int(row["OPIS Truckstop ID"])
                price = float(row["Retail Price"])
                existing = cheapest_by_truckstop_id.get(truckstop_id)
                if existing is not None and existing.price <= price:
                    continue

                cheapest_by_truckstop_id[truckstop_id] = FuelStation(
                    truckstop_id=truckstop_id,
                    name=row["Truckstop Name"],
                    address=row["Address"],
                    city=row["City"],
                    state=row["State"],
                    latitude=lat,
                    longitude=lon,
                    price=price,
                )

        matched = list(cheapest_by_truckstop_id.values())
        duplicates_collapsed = matched_rows - len(matched)

        FuelStation.objects.bulk_create(matched, batch_size=1000)
        self.stdout.write(
            f"Loaded {len(matched)} station(s); {skipped} row(s) skipped (no city/state match); "
            f"{duplicates_collapsed} duplicate row(s) collapsed to their lowest price."
        )
