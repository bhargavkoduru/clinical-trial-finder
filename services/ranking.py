"""Best-effort location matching and deterministic, explainable study scoring."""
from __future__ import annotations

from typing import Any


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


def best_matching_location(locations: list[dict[str, Any]], location_query: str) -> tuple[dict[str, Any] | None, bool]:
    """Pick the location whose fields best match the query text.

    Returns (location, matched) where matched is True only if the query text
    was actually found in the selected location's fields.
    """
    if not locations:
        return None, False

    query_tokens = [token for token in location_query.lower().replace(",", " ").split() if token]
    if query_tokens:
        for location in locations:
            text = _location_text(location)
            if all(token in text for token in query_tokens):
                return location, True

    return locations[0], False


def score_study(
    overall_status: str | None,
    location_matched: bool,
    study_type: str | None,
    phases: list[str],
) -> tuple[int, list[str]]:
    """Score a study 0-100 based on transparent, additive rules. Not a measure of eligibility."""
    score = 0
    reasons: list[str] = []

    if overall_status == "RECRUITING":
        score += 40
        reasons.append("Study is currently recruiting (+40)")

    if location_matched:
        score += 30
        reasons.append("A study site matches your submitted location (+30)")

    if study_type == "INTERVENTIONAL":
        score += 10
        reasons.append("Study type is interventional (+10)")

    if phases:
        score += 10
        reasons.append("Study phase is specified (+10)")

    return min(score, 100), reasons
