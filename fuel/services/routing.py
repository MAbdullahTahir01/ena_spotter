from typing import NamedTuple

import requests
from django.conf import settings

from fuel.services.geo import haversine_miles

METERS_PER_MILE = 1609.344


class RoutingError(Exception):
    pass


class RouteResult(NamedTuple):
    geometry: list[tuple[float, float]]
    distance_miles: float


def get_route(start: tuple[float, float], finish: tuple[float, float]) -> RouteResult:
    start_lat, start_lon = start
    finish_lat, finish_lon = finish
    url = (
        f"{settings.OSRM_BASE_URL}/route/v1/driving/"
        f"{start_lon},{start_lat};{finish_lon},{finish_lat}"
    )

    try:
        response = requests.get(
            url,
            params={"overview": "full", "geometries": "geojson"},
            timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RoutingError(f"Failed to fetch route: {exc}") from exc

    if data.get("code") != "Ok" or not data.get("routes"):
        raise RoutingError(f"No route found (OSRM code={data.get('code')})")

    route = data["routes"][0]
    coordinates = route["geometry"]["coordinates"]  # [lon, lat] pairs
    geometry = [(lat, lon) for lon, lat in coordinates]
    distance_miles = route["distance"] / METERS_PER_MILE

    return RouteResult(geometry=geometry, distance_miles=distance_miles)


def cumulative_distances(geometry: list[tuple[float, float]]) -> list[tuple[float, float, float]]:
    if not geometry:
        return []

    table = [(geometry[0][0], geometry[0][1], 0.0)]
    total = 0.0
    for (lat1, lon1), (lat2, lon2) in zip(geometry, geometry[1:]):
        total += haversine_miles(lat1, lon1, lat2, lon2)
        table.append((lat2, lon2, total))
    return table
