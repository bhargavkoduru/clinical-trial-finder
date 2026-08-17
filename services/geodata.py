"""Static US ZIP-code centroid lookup and distance math. Offline only, no geocoding service."""
from __future__ import annotations

import csv
import math
import re
from functools import lru_cache
from pathlib import Path

_ZIP_RE = re.compile(r"^(\d{5})")
_DATA_PATH = Path(__file__).parent / "data" / "zip_centroids.csv"
_EARTH_RADIUS_MILES = 3958.8


@lru_cache(maxsize=1)
def _load_centroids() -> dict[str, tuple[float, float]]:
    """Load the bundled ZIP->(lat, lon) table once per process."""
    centroids: dict[str, tuple[float, float]] = {}
    with _DATA_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            centroids[row["zip"]] = (float(row["lat"]), float(row["lon"]))
    return centroids


def zip_to_latlon(location_text: str) -> tuple[float, float] | None:
    """Return (lat, lon) if location_text starts with a recognized 5-digit US ZIP, else None."""
    match = _ZIP_RE.match(location_text.strip())
    if not match:
        return None
    return _load_centroids().get(match.group(1))


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))
