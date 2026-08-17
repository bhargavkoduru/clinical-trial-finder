"""Best-effort location matching and deterministic, explainable study scoring."""
from __future__ import annotations

from typing import Any

from .geodata import haversine_miles


def _location_text(location: dict[str, Any]) -> str:
    """Combine a location's facility, city, state, country, and ZIP into one lowercase string."""
    parts = [
        location.get("facility"),
        location.get("city"),
        location.get("state"),
        location.get("country"),
        location.get("zip"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def matching_locations(
    locations: list[dict[str, Any]], location_query: str, limit: int = 3
) -> tuple[list[dict[str, Any]], bool]:
    """Return up to `limit` locations, with any text matches on the query listed first.

    Returns (locations, any_matched) where any_matched is True only if at least one
    location's fields contained the submitted location text.
    """
    if not locations:
        return [], False

    query_tokens = [token for token in location_query.lower().replace(",", " ").split() if token]
    matched, unmatched = [], []
    for location in locations:
        text = _location_text(location)
        if query_tokens and all(token in text for token in query_tokens):
            matched.append(location)
        else:
            unmatched.append(location)

    return (matched + unmatched)[:limit], bool(matched)


def nearby_locations(
    locations: list[dict[str, Any]],
    center_lat: float,
    center_lon: float,
    radius_miles: float,
    limit: int = 3,
) -> tuple[list[tuple[dict[str, Any], float]], bool]:
    """Return up to `limit` locations sorted by real distance from (center_lat, center_lon).

    Only considers locations with geoPoint data. Returns (list of (location, distance_miles)
    tuples nearest first, within_radius) where within_radius is True if the nearest site is
    within radius_miles.
    """
    scored = []
    for location in locations:
        geo = location.get("geoPoint") or {}
        lat, lon = geo.get("lat"), geo.get("lon")
        if lat is None or lon is None:
            continue
        scored.append((location, haversine_miles(center_lat, center_lon, lat, lon)))

    scored.sort(key=lambda item: item[1])
    within_radius = bool(scored) and scored[0][1] <= radius_miles
    return scored[:limit], within_radius


def score_breakdown(
    overall_status: str | None,
    location_matched: bool,
    study_type: str | None,
    phases: list[str],
) -> list[tuple[str, int, bool]]:
    """Return every scoring criterion as (label, points, earned), in the order they're applied."""
    return [
        ("Study is currently recruiting", 40, overall_status == "RECRUITING"),
        ("A study site is near your submitted location", 30, location_matched),
        ("Study type is interventional", 10, study_type == "INTERVENTIONAL"),
        ("Study phase is specified", 10, bool(phases)),
    ]


def score_study(
    overall_status: str | None,
    location_matched: bool,
    study_type: str | None,
    phases: list[str],
) -> tuple[int, list[str]]:
    """Score a study 0-100 based on transparent, additive rules. Not a measure of eligibility."""
    criteria = score_breakdown(overall_status, location_matched, study_type, phases)
    score = sum(points for _, points, earned in criteria if earned)
    reasons = [f"{label} (+{points})" for label, points, earned in criteria if earned]
    return min(score, 100), reasons
