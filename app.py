"""Streamlit MVP: search ClinicalTrials.gov for studies matching a condition and location."""
from __future__ import annotations

import csv
import io

import streamlit as st

from services.clinicaltrials import ClinicalTrialsError, search_studies
from services.ranking import matching_locations, nearby_locations, score_study

PAGE_SIZE_OPTIONS = [10, 25, 50]
RADIUS_OPTIONS = [10, 25, 50, 100]

st.set_page_config(page_title="Nearby Clinical Trials", page_icon="🧬")

st.title("🧬 Nearby Clinical Trials")
st.write(
    "Find recruiting clinical studies near you. Informational only; this tool "
    "does not determine eligibility or provide medical advice."
)

params = st.query_params
default_condition = params.get("condition", "")
default_location = params.get("location", "")
default_recruiting = params.get("recruiting", "1") != "0"
try:
    default_page_size = int(params.get("results", "25"))
except ValueError:
    default_page_size = 25
if default_page_size not in PAGE_SIZE_OPTIONS:
    default_page_size = 25
try:
    default_radius = int(params.get("radius", "25"))
except ValueError:
    default_radius = 25
if default_radius not in RADIUS_OPTIONS:
    default_radius = 25

with st.form("search_form"):
    condition = st.text_input(
        "Disease or condition", value=default_condition, placeholder="e.g., rheumatoid arthritis"
    )
    st.caption('Tip: combine terms with OR, e.g. "diabetes OR prediabetes".')
    location = st.text_input("Location", value=default_location, placeholder="e.g., Boston, MA or 02115")
    recruiting_only = st.checkbox("Recruiting only", value=default_recruiting)
    page_size = st.selectbox(
        "Results", options=PAGE_SIZE_OPTIONS, index=PAGE_SIZE_OPTIONS.index(default_page_size)
    )
    radius_miles = st.selectbox(
        "Search radius (miles)",
        options=RADIUS_OPTIONS,
        index=RADIUS_OPTIONS.index(default_radius),
        help="Only used when location is a 5-digit ZIP code, for a true distance search. "
        "City/state entries use text matching instead.",
    )
    submitted = st.form_submit_button("Find trials")

if submitted:
    if not condition.strip() or not location.strip():
        st.error("Please enter both a disease/condition and a location.")
        st.session_state.pop("search", None)
    else:
        st.query_params["condition"] = condition.strip()
        st.query_params["location"] = location.strip()
        st.query_params["recruiting"] = "1" if recruiting_only else "0"
        st.query_params["results"] = str(page_size)
        st.query_params["radius"] = str(radius_miles)

        with st.spinner("Searching ClinicalTrials.gov..."):
            try:
                result = search_studies(
                    condition.strip(), location.strip(), recruiting_only, page_size, radius_miles=radius_miles
                )
            except ClinicalTrialsError as exc:
                st.session_state.pop("search", None)
                st.error(str(exc))
            else:
                st.session_state["search"] = {
                    "condition": condition.strip(),
                    "location": location.strip(),
                    "recruiting_only": recruiting_only,
                    "page_size": page_size,
                    "radius_miles": radius_miles,
                    "studies": result["studies"],
                    "total_count": result["total_count"],
                    "next_page_token": result["next_page_token"],
                    "broadened": result["broadened"],
                    "geo_center": result["geo_center"],
                }

search = st.session_state.get("search")

if search:
    geo_center = search["geo_center"]

    if search["broadened"]:
        st.info(
            "No exact matches on the condition field — showing a broader text "
            "search across study records instead."
        )

    if geo_center:
        st.info(f"Using real distance search: showing sites within {search['radius_miles']} miles of {search['location']}.")

    if not search["studies"]:
        st.info("No studies found matching your search. Try broadening your terms.")
    else:
        ranked = []
        for study in search["studies"]:
            if geo_center:
                lat, lon = geo_center
                sites, matched = nearby_locations(study["locations"], lat, lon, search["radius_miles"])
            else:
                plain_sites, matched = matching_locations(study["locations"], search["location"])
                sites = [(site, None) for site in plain_sites]
            score, reasons = score_study(
                study["overall_status"], matched, study["study_type"], study["phases"]
            )
            ranked.append((score, reasons, sites, study))
        ranked.sort(key=lambda item: item[0], reverse=True)

        total = search["total_count"]
        header = f"Showing {len(ranked)} of {total} matching studies" if total else f"Found {len(ranked)} studies"
        st.subheader(header)

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(
            ["NCT ID", "Title", "Status", "Phase", "Study Type", "Sponsor", "Score", "Nearest Site (mi)", "Link"]
        )

        for score, reasons, sites, study in ranked:
            nct_id = study["nct_id"] or "Unknown"
            title = study["brief_title"] or "Untitled study"
            link = f"https://clinicaltrials.gov/study/{nct_id}" if nct_id != "Unknown" else ""
            nearest_distance = sites[0][1] if sites and sites[0][1] is not None else ""
            writer.writerow(
                [
                    nct_id,
                    title,
                    study["overall_status"] or "",
                    ", ".join(study["phases"]),
                    study["study_type"] or "",
                    study["lead_sponsor"] or "",
                    score,
                    f"{nearest_distance:.1f}" if nearest_distance != "" else "",
                    link,
                ]
            )

            with st.container(border=True):
                st.markdown(f"### {title}")

                col_info, col_score = st.columns([3, 1])

                with col_info:
                    st.write(f"**NCT ID:** {nct_id}")
                    st.write(f"**Status:** {study['overall_status'] or 'Unknown'}")
                    if study["phases"]:
                        st.write(f"**Phase:** {', '.join(study['phases'])}")
                    st.write(f"**Study type:** {study['study_type'] or 'Unknown'}")
                    st.write(f"**Lead sponsor:** {study['lead_sponsor'] or 'Unknown'}")

                    eligibility = study["eligibility"]
                    eligibility_bits = []
                    if eligibility["sex"]:
                        eligibility_bits.append(eligibility["sex"])
                    if eligibility["minimum_age"] or eligibility["maximum_age"]:
                        min_age = eligibility["minimum_age"] or "N/A"
                        max_age = eligibility["maximum_age"] or "N/A"
                        eligibility_bits.append(f"{min_age} – {max_age}")
                    if eligibility_bits:
                        st.write(f"**Listed eligibility:** {' | '.join(eligibility_bits)}")

                with col_score:
                    st.metric("Match score", f"{score}/100")

                if study["brief_summary"]:
                    with st.expander("Brief summary"):
                        st.write(study["brief_summary"])

                if sites:
                    st.write("**Nearby listed sites:**")
                    for site, distance in sites:
                        site_parts = [
                            site.get("facility"),
                            site.get("city"),
                            site.get("state"),
                            site.get("country"),
                            site.get("zip"),
                        ]
                        site_text = ", ".join(str(p) for p in site_parts if p) or "No site details listed."
                        prefix = f"{distance:.1f} mi — " if distance is not None else ""
                        st.write(f"- {prefix}{site_text}")
                else:
                    st.write("**Nearby listed sites:** No site details listed.")

                if reasons:
                    st.caption("Why this score: " + "; ".join(reasons))

                if nct_id != "Unknown":
                    st.link_button("View official record", link)

        st.download_button(
            "Download results as CSV",
            data=csv_buffer.getvalue(),
            file_name="clinical_trials_results.csv",
            mime="text/csv",
        )

        if search["next_page_token"]:
            if st.button("Load more results"):
                with st.spinner("Loading more..."):
                    try:
                        more = search_studies(
                            search["condition"],
                            search["location"],
                            search["recruiting_only"],
                            search["page_size"],
                            page_token=search["next_page_token"],
                            use_term_search=search["broadened"],
                            radius_miles=search["radius_miles"],
                        )
                    except ClinicalTrialsError as exc:
                        st.error(str(exc))
                    else:
                        search["studies"] = search["studies"] + more["studies"]
                        search["next_page_token"] = more["next_page_token"]
                        st.session_state["search"] = search
                        st.rerun()

st.divider()
st.caption(
    "ClinicalTrials.gov listings may be incomplete or out of date. "
    "Contact the study site to confirm availability and eligibility."
)
