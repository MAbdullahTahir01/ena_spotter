import requests
from django.conf import settings


class GeocodeError(Exception):
    pass


_CACHE: dict[str, tuple[float, float]] = {}


def geocode_address(query: str) -> tuple[float, float]:
    key = query.strip().lower()
    if key in _CACHE:
        return _CACHE[key]

    try:
        response = requests.get(
            f"{settings.NOMINATIM_BASE_URL}/search",
            params={"q": query, "format": "json", "limit": 1},
            headers={"User-Agent": "ena_spotter-fuel-route-api/1.0"},
            timeout=settings.EXTERNAL_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        results = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise GeocodeError(f"Failed to geocode '{query}': {exc}") from exc

    if not results:
        raise GeocodeError(f"No geocoding result for '{query}'")

    try:
        lat = float(results[0]["lat"])
        lon = float(results[0]["lon"])
    except (KeyError, ValueError) as exc:
        raise GeocodeError(f"Failed to geocode '{query}': {exc}") from exc

    _CACHE[key] = (lat, lon)
    return lat, lon
