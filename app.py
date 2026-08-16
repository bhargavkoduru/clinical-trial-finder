"""Streamlit MVP: search ClinicalTrials.gov for studies matching a condition and location."""
from __future__ import annotations

import streamlit as st

from services.clinicaltrials import ClinicalTrialsError, search_studies
from services.ranking import best_matching_location, score_study

st.set_page_config(page_title="Nearby Clinical Trials", page_icon="🧬")

st.title("🧬 Nearby Clinical Trials")
st.write(
    "Find recruiting clinical studies near you. Informational only; this tool "
    "does not determine eligibility or provide medical advice."
)

with st.form("search_form"):
    condition = st.text_input("Disease or condition", placeholder="e.g., rheumatoid arthritis")
    location = st.text_input("Location", placeholder="e.g., Boston, MA or 02115")
    recruiting_only = st.checkbox("Recruiting only", value=True)
    page_size = st.selectbox("Results", options=[10, 25, 50], index=1)
    submitted = st.form_submit_button("Find trials")

if submitted:
    if not condition.strip() or not location.strip():
        st.error("Please enter both a disease/condition and a location.")
    else:
        with st.spinner("Searching ClinicalTrials.gov..."):
            try:
                studies = search_studies(condition.strip(), location.strip(), recruiting_only, page_size)
            except ClinicalTrialsError as exc:
                studies = None
                st.error(str(exc))

        if studies is not None:
            if not studies:
                st.info("No studies found matching your search. Try broadening your terms.")
            else:
                ranked = []
                for study in studies:
                    site, matched = best_matching_location(study["locations"], location)
                    score, reasons = score_study(
                        study["overall_status"], matched, study["study_type"], study["phases"]
                    )
                    ranked.append((score, reasons, site, study))

                ranked.sort(key=lambda item: item[0], reverse=True)

                st.subheader(f"Found {len(ranked)} studies")

                for score, reasons, site, study in ranked:
                    with st.container(border=True):
                        title = study["brief_title"] or "Untitled study"
                        nct_id = study["nct_id"] or "Unknown"
                        st.markdown(f"### {title}")

                        col_info, col_score = st.columns([3, 1])

                        with col_info:
                            st.write(f"**NCT ID:** {nct_id}")
                            st.write(f"**Status:** {study['overall_status'] or 'Unknown'}")
                            if study["phases"]:
                                st.write(f"**Phase:** {', '.join(study['phases'])}")
                            st.write(f"**Study type:** {study['study_type'] or 'Unknown'}")
                            st.write(f"**Lead sponsor:** {study['lead_sponsor'] or 'Unknown'}")

                        with col_score:
                            st.metric("Match score", f"{score}/100")

                        if study["brief_summary"]:
                            st.write(study["brief_summary"])

                        if site:
                            site_parts = [
                                site.get("facility"),
                                site.get("city"),
                                site.get("state"),
                                site.get("country"),
                                site.get("zip"),
                            ]
                            site_text = ", ".join(str(p) for p in site_parts if p)
                            st.write(f"**Nearest listed site:** {site_text or 'No site details listed.'}")
                        else:
                            st.write("**Nearest listed site:** No site details listed.")

                        if reasons:
                            st.caption("Why this score: " + "; ".join(reasons))

                        if nct_id and nct_id != "Unknown":
                            st.link_button(
                                "View official record",
                                f"https://clinicaltrials.gov/study/{nct_id}",
                            )

st.divider()
st.caption(
    "ClinicalTrials.gov listings may be incomplete or out of date. "
    "Contact the study site to confirm availability and eligibility."
)
