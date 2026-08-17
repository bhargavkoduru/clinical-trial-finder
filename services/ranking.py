"""Best-effort location matching and deterministic, explainable study scoring."""
from __future__ import annotations

import re
from typing import Any

from .geodata import haversine_miles

_BOOLEAN_OPERATORS = {"or", "and", "not"}


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
    """Return up to `limit` locations within radius_miles, sorted by real distance.

    Only considers locations with geoPoint data, and only those actually within
    radius_miles — a study can have sites far outside the search area too, and
    those are excluded rather than just sorted to the back. Returns (list of
    (location, distance_miles) tuples nearest first, within_radius) where
    within_radius is True if at least one site was within the radius.
    """
    scored = []
    for location in locations:
        geo = location.get("geoPoint") or {}
        lat, lon = geo.get("lat"), geo.get("lon")
        if lat is None or lon is None:
            continue
        distance = haversine_miles(center_lat, center_lon, lat, lon)
        if distance <= radius_miles:
            scored.append((location, distance))

    scored.sort(key=lambda item: item[1])
    within_radius = bool(scored)
    return scored[:limit], within_radius


def location_score(
    matched: bool, distance_miles: float | None, radius_miles: float | None, max_points: int = 30
) -> int:
    """Points for how well a site matches the searched location.

    When a real distance is known (ZIP-based radius search), points taper linearly from
    max_points at 0 miles to 0 at the edge of the search radius. Otherwise (text-matched
    city/state search, where no real distance exists) it's flat: max_points if matched, else 0.
    """
    if not matched:
        return 0
    if distance_miles is None or not radius_miles:
        return max_points
    ratio = min(distance_miles / radius_miles, 1.0)
    return round(max_points * (1 - ratio))


def condition_is_specific(study_conditions: list[str], condition_query: str) -> bool:
    """True if any term from the searched condition appears in the study's own listed conditions.

    This distinguishes a study where the searched condition is explicitly named (high
    specificity) from one that only matched via a broader free-text fallback search.
    """
    if not study_conditions or not condition_query:
        return False
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", condition_query.lower())
        if token and token not in _BOOLEAN_OPERATORS
    ]
    combined = " ".join(study_conditions).lower()
    return any(token in combined for token in tokens)


def score_breakdown(
    overall_status: str | None,
    study_type: str | None,
    phases: list[str],
    location_points: int,
    condition_specific: bool,
) -> list[tuple[str, int, int]]:
    """Return every scoring criterion as (label, points_earned, points_possible), in score order."""
    if overall_status == "RECRUITING":
        recruiting_points = 35
    elif overall_status == "NOT_YET_RECRUITING":
        recruiting_points = 15
    else:
        recruiting_points = 0

    return [
        (f"Recruitment status ({overall_status or 'Unknown'})", recruiting_points, 35),
        ("Location match to your search", location_points, 30),
        ("Study type is interventional", 10 if study_type == "INTERVENTIONAL" else 0, 10),
        ("Study phase is specified", 10 if phases else 0, 10),
        ("Your searched condition is explicitly listed for this study", 15 if condition_specific else 0, 15),
    ]


def score_study(
    overall_status: str | None,
    study_type: str | None,
    phases: list[str],
    location_points: int,
    condition_specific: bool,
) -> tuple[int, list[str]]:
    """Score a study 0-100 based on transparent, additive rules. Not a measure of eligibility."""
    criteria = score_breakdown(overall_status, study_type, phases, location_points, condition_specific)
    score = sum(earned for _, earned, _ in criteria)
    reasons = [f"{label} (+{earned})" for label, earned, _ in criteria if earned]
    return min(score, 100), reasons
