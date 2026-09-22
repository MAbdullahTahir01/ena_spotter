import math
from typing import NamedTuple

from django.conf import settings

from fuel.models import FuelStation
from fuel.services.geo import haversine_miles


class StationCandidate(NamedTuple):
    station_id: int
    name: str
    address: str
    city: str
    state: str
    latitude: float
    longitude: float
    price: float
    distance_along_route_miles: float
    distance_off_route_miles: float = 0.0


def find_candidate_stops(
    cumulative_table: list[tuple[float, float, float]],
    corridor_miles: float | None = None,
) -> list[StationCandidate]:
    if corridor_miles is None:
        corridor_miles = settings.FUEL_CORRIDOR_MILES
    if not cumulative_table:
        return []

    # The nearest-point scan below accepts a station up to `acceptance_threshold` away
    # (corridor_miles widened by the decimation sample spacing, see below). Both the SQL
    # bounding-box pre-filter and the inner per-point latitude pre-check must be sized to
    # this same widened threshold, not the raw corridor_miles — otherwise they can exclude
    # a station (from the DB query, or from a given sampled point's distance comparison)
    # before the scan ever gets a chance to accept it, reintroducing the false-negative
    # the widened threshold exists to prevent.
    acceptance_threshold = corridor_miles + settings.FUEL_SAMPLE_SPACING_MILES

    lats = [lat for lat, _, _ in cumulative_table]
    lons = [lon for _, lon, _ in cumulative_table]
    lat_margin = acceptance_threshold / settings.FUEL_MILES_PER_DEGREE_LAT
    # Longitude degrees shrink toward the poles; use the widest (lowest-lat) margin to stay conservative.
    min_cos_lat = max(0.05, min(abs(math.cos(math.radians(lat))) for lat in lats))
    lon_margin = acceptance_threshold / (settings.FUEL_MILES_PER_DEGREE_LAT * min_cos_lat)

    queryset = FuelStation.objects.filter(
        latitude__gte=min(lats) - lat_margin,
        latitude__lte=max(lats) + lat_margin,
        longitude__gte=min(lons) - lon_margin,
        longitude__lte=max(lons) + lon_margin,
    )

    # Decimate the cumulative-distance table to ~FUEL_SAMPLE_SPACING_MILES spacing before
    # the nearest-point scan below: OSRM's overview=full geometry can carry tens of
    # thousands of points on long routes, and scanning every station against every point
    # is O(n*m) and slow. A station can be at most ~FUEL_SAMPLE_SPACING_MILES farther from
    # its nearest *sampled* point than from its nearest *true* point on the polyline, so we
    # widen the acceptance threshold by that same spacing to guarantee no false negatives.
    sampled_table = [cumulative_table[0]]
    for point in cumulative_table[1:]:
        if point[2] - sampled_table[-1][2] >= settings.FUEL_SAMPLE_SPACING_MILES:
            sampled_table.append(point)
    if sampled_table[-1] is not cumulative_table[-1]:
        sampled_table.append(cumulative_table[-1])

    candidates: list[StationCandidate] = []
    for station in queryset:
        best_distance_to_route = float("inf")
        best_cumulative = 0.0
        for lat, lon, cumulative in sampled_table:
            # Cheap pre-check: skip the trig-heavy haversine call when the point is
            # obviously outside the latitude margin already computed for the bounding box.
            if abs(station.latitude - lat) > lat_margin:
                continue
            d = haversine_miles(station.latitude, station.longitude, lat, lon)
            if d < best_distance_to_route:
                best_distance_to_route = d
                best_cumulative = cumulative
                if best_distance_to_route <= settings.FUEL_CLEARLY_ON_ROUTE_MILES:
                    break

        if best_distance_to_route <= acceptance_threshold:
            candidates.append(
                StationCandidate(
                    station_id=station.id,
                    name=station.name,
                    address=station.address,
                    city=station.city,
                    state=station.state,
                    latitude=station.latitude,
                    longitude=station.longitude,
                    price=station.price,
                    distance_along_route_miles=best_cumulative,
                    distance_off_route_miles=best_distance_to_route,
                )
            )

    candidates.sort(key=lambda c: c.distance_along_route_miles)
    return candidates
