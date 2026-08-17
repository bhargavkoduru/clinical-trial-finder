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
