import csv
import io
import zipfile
from pathlib import Path
from typing import Iterable, Iterator

import requests

POPULATED_PLACE_FEATURE_CLASS = "P"


def parse_geonames_lines(lines: Iterable[str]) -> Iterator[tuple[str, str, float, float]]:
    """Yield (city, state, lat, lon) for US populated-place rows."""
    for line in lines:
        if not line.strip():
            continue
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 11:
            continue
        name = cols[1]
        latitude = float(cols[4])
        longitude = float(cols[5])
        feature_class = cols[6]
        country_code = cols[8]
        state = cols[10]
        if country_code != "US" or feature_class != POPULATED_PLACE_FEATURE_CLASS:
            continue
        if not state:
            continue
        yield name, state, latitude, longitude


def download_and_build_city_coords_csv(
    out_path: str | Path,
    geonames_zip_url: str = "https://download.geonames.org/export/dump/US.zip",
) -> None:
    response = requests.get(geonames_zip_url, timeout=120)
    response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        with archive.open("US.txt") as raw:
            lines = io.TextIOWrapper(raw, encoding="utf-8")
            seen: dict[tuple[str, str], tuple[float, float]] = {}
            for city, state, lat, lon in parse_geonames_lines(lines):
                key = (city, state)
                if key not in seen:
                    seen[key] = (lat, lon)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "state", "latitude", "longitude"])
        for (city, state), (lat, lon) in seen.items():
            writer.writerow([city, state, lat, lon])


def load_city_coords(csv_path: str | Path) -> dict[tuple[str, str], tuple[float, float]]:
    lookup: dict[tuple[str, str], tuple[float, float]] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["city"].strip().upper(), row["state"].strip().upper())
            lookup[key] = (float(row["latitude"]), float(row["longitude"]))
    return lookup
