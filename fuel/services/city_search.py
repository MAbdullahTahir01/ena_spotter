import csv
from functools import lru_cache
from pathlib import Path

from django.conf import settings

MIN_QUERY_LENGTH = 2
MAX_RESULTS = 10

CITY_COORDS_CSV_PATH = Path(settings.BASE_DIR) / "fuel" / "data" / "us_city_coords.csv"


@lru_cache(maxsize=1)
def _load_cities() -> list[tuple[str, str]]:
    """Return deduplicated (city, state) pairs, loaded once per process."""
    seen: set[tuple[str, str]] = set()
    with open(CITY_COORDS_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seen.add((row["city"].strip(), row["state"].strip()))
    return sorted(seen)


@lru_cache(maxsize=1)
def _known_city_set() -> set[tuple[str, str]]:
    return {(city.upper(), state.upper()) for city, state in _load_cities()}


def is_known_city(query: str) -> bool:
    """True if query looks like a real "City, ST" from our city list.

    Used to reject junk input (e.g. "h", "u") before it ever reaches the
    geocoding API, which would otherwise return some fuzzy, meaningless
    match instead of a clean error.
    """
    city, _, state = query.strip().rpartition(",")
    if not city or not state:
        return False
    return (city.strip().upper(), state.strip().upper()) in _known_city_set()


def search_cities(query: str, limit: int = MAX_RESULTS) -> list[dict]:
    query = query.strip().lower()
    if len(query) < MIN_QUERY_LENGTH:
        return []

    prefix_matches = []
    substring_matches = []
    for city, state in _load_cities():
        city_lower = city.lower()
        if city_lower.startswith(query):
            prefix_matches.append((city, state))
        elif query in city_lower:
            substring_matches.append((city, state))

    # No population data to rank by, so show shorter names first
    # (prefer "Austin" over "Ausable Chasm").
    rank_key = lambda pair: (len(pair[0]), pair[0], pair[1])
    prefix_matches.sort(key=rank_key)
    substring_matches.sort(key=rank_key)

    results = (prefix_matches + substring_matches)[:limit]
    return [{"label": f"{city}, {state}", "city": city, "state": state} for city, state in results]
