"""Client for the ClinicalTrials.gov v2 studies API, plus response normalization."""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

API_URL = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsError(Exception):
    """Raised when the ClinicalTrials.gov API cannot be reached or returns bad data."""


@st.cache_data(ttl=900, show_spinner=False)
def search_studies(
    condition: str,
    location: str,
    recruiting_only: bool,
    page_size: int,
) -> list[dict[str, Any]]:
    """Query the ClinicalTrials.gov v2 API and return normalized study dicts."""
    params: dict[str, Any] = {
        "query.cond": condition,
        "query.locn": location,
        "pageSize": page_size,
        "format": "json",
    }
    if recruiting_only:
        params["filter.overallStatus"] = "RECRUITING"

    try:
        response = requests.get(API_URL, params=params, timeout=20)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise ClinicalTrialsError("The request to ClinicalTrials.gov timed out. Please try again.") from exc
    except requests.exceptions.HTTPError as exc:
        raise ClinicalTrialsError(f"ClinicalTrials.gov returned an error: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise ClinicalTrialsError(f"Could not reach ClinicalTrials.gov: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ClinicalTrialsError("ClinicalTrials.gov returned a malformed response.") from exc

    studies = payload.get("studies")
    if not isinstance(studies, list):
        return []

    return [normalize_study(study) for study in studies if isinstance(study, dict)]


def normalize_study(study: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we care about from a raw study record, tolerating missing data."""
    protocol = study.get("protocolSection") or {}

    identification = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    description = protocol.get("descriptionModule") or {}
    sponsors = protocol.get("sponsorCollaboratorsModule") or {}
    contacts = protocol.get("contactsLocationsModule") or {}

    lead_sponsor = sponsors.get("leadSponsor") or {}
    locations = contacts.get("locations") or []
    if not isinstance(locations, list):
        locations = []

    return {
        "nct_id": identification.get("nctId"),
        "brief_title": identification.get("briefTitle"),
        "overall_status": status.get("overallStatus"),
        "phases": design.get("phases") or [],
        "study_type": design.get("studyType"),
        "brief_summary": description.get("briefSummary"),
        "lead_sponsor": lead_sponsor.get("name"),
        "locations": locations,
    }
