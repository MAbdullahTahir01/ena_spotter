from django.test import TestCase

from fuel.models import FuelStation


class FuelStationModelTest(TestCase):
    def test_create_and_retrieve(self):
        FuelStation.objects.create(
            truckstop_id=7,
            name="WOODSHED OF BIG CABIN",
            address="I-44, EXIT 283 & US-69",
            city="Big Cabin",
            state="OK",
            latitude=36.5343,
            longitude=-95.2144,
            price=3.00733333,
        )
        station = FuelStation.objects.get(truckstop_id=7)
        self.assertEqual(station.city, "Big Cabin")
        self.assertAlmostEqual(station.price, 3.00733333)
