"""Client for the ClinicalTrials.gov v2 studies API, plus response normalization."""
from __future__ import annotations

from typing import Any

import requests
import streamlit as st

from .geodata import zip_to_latlon

API_URL = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsError(Exception):
    """Raised when the ClinicalTrials.gov API cannot be reached or returns bad data."""


@st.cache_data(ttl=900, show_spinner=False)
def search_studies(
    condition: str,
    location: str,
    recruiting_only: bool,
    page_size: int,
    page_token: str = "",
    use_term_search: bool = False,
    radius_miles: int = 25,
) -> dict[str, Any]:
    """Query the ClinicalTrials.gov v2 API and return normalized studies plus paging info.

    If location is a recognized 5-digit US ZIP, this uses the API's filter.geo distance
    filter against a bundled offline ZIP centroid table for a real radius search. Otherwise
    it falls back to a text search (query.locn) against site facility/city/state/etc.

    On the first page, if a strict condition-field search (query.cond) returns nothing,
    this automatically retries with a broader free-text search (query.term) across the
    whole record so close wording or synonyms aren't missed. Pass use_term_search=True
    to keep using that broader mode on later pages (e.g. "Load more").
    """
    geo_center = zip_to_latlon(location)

    def run_query(term_mode: bool) -> dict[str, Any]:
        params: dict[str, Any] = {
            "pageSize": page_size,
            "format": "json",
            "countTotal": "true",
        }
        if geo_center:
            lat, lon = geo_center
            params["filter.geo"] = f"distance({lat},{lon},{radius_miles}mi)"
        else:
            params["query.locn"] = location
        params["query.term" if term_mode else "query.cond"] = condition
        if recruiting_only:
            params["filter.overallStatus"] = "RECRUITING"
        if page_token:
            params["pageToken"] = page_token
        return _fetch(params)

    payload = run_query(use_term_search)
    studies = payload.get("studies")
    broadened = use_term_search

    if not use_term_search and not page_token and not studies:
        payload = run_query(term_mode=True)
        studies = payload.get("studies")
        broadened = True

    if not isinstance(studies, list):
        studies = []

    return {
        "studies": [normalize_study(study) for study in studies if isinstance(study, dict)],
        "total_count": payload.get("totalCount"),
        "next_page_token": payload.get("nextPageToken"),
        "broadened": broadened,
        "geo_center": geo_center,
        "radius_miles": radius_miles if geo_center else None,
    }


def _fetch(params: dict[str, Any]) -> dict[str, Any]:
    """Call the API with the given params and return the parsed JSON payload."""
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

    if not isinstance(payload, dict):
        raise ClinicalTrialsError("ClinicalTrials.gov returned an unexpected response format.")

    return payload


def normalize_study(study: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields we care about from a raw study record, tolerating missing data."""
    protocol = study.get("protocolSection") or {}

    identification = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    description = protocol.get("descriptionModule") or {}
    sponsors = protocol.get("sponsorCollaboratorsModule") or {}
    contacts = protocol.get("contactsLocationsModule") or {}
    eligibility = protocol.get("eligibilityModule") or {}

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
        "eligibility": {
            "sex": eligibility.get("sex"),
            "minimum_age": eligibility.get("minimumAge"),
            "maximum_age": eligibility.get("maximumAge"),
        },
    }
