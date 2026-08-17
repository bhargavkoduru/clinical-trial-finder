"""Streamlit MVP: search ClinicalTrials.gov for studies matching a condition and location."""
from __future__ import annotations

import csv
import io

import streamlit as st

from services.clinicaltrials import ClinicalTrialsError, search_studies
from services.ranking import (
    condition_is_specific,
    location_score,
    matching_locations,
    nearby_locations,
    score_breakdown,
    score_study,
)

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
                nearest_distance = sites[0][1] if sites else None
                loc_points = location_score(matched, nearest_distance, search["radius_miles"])
            else:
                plain_sites, matched = matching_locations(study["locations"], search["location"])
                sites = [(site, None) for site in plain_sites]
                loc_points = location_score(matched, None, None)

            specific = condition_is_specific(study["conditions"], search["condition"])
            score, reasons = score_study(
                study["overall_status"], study["study_type"], study["phases"], loc_points, specific
            )
            breakdown = score_breakdown(
                study["overall_status"], study["study_type"], study["phases"], loc_points, specific
            )
            ranked.append((score, reasons, breakdown, sites, study))
        ranked.sort(key=lambda item: item[0], reverse=True)

        total = search["total_count"]
        header = f"Showing {len(ranked)} of {total} matching studies" if total else f"Found {len(ranked)} studies"
        st.subheader(header)

        map_points = [
            {"lat": site.get("geoPoint", {}).get("lat"), "lon": site.get("geoPoint", {}).get("lon")}
            for _, _, _, sites, _ in ranked
            for site, _ in sites[:1]
            if site.get("geoPoint")
        ]
        if map_points:
            st.map(map_points, size=40)

        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(
            ["NCT ID", "Title", "Status", "Phase", "Study Type", "Sponsor", "Score", "Nearest Site (mi)", "Link"]
        )

        for score, reasons, breakdown, sites, study in ranked:
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

                    enrollment = study["enrollment"]
                    if enrollment["count"]:
                        type_bit = f" ({enrollment['type']})" if enrollment["type"] else ""
                        st.write(f"**Enrollment:** {enrollment['count']}{type_bit}")

                with col_score:
                    st.metric("Match score", f"{score}/100")

                if study["brief_summary"]:
                    with st.expander("Brief summary"):
                        st.write(study["brief_summary"])

                dates = study["dates"]
                if any(dates.values()):
                    with st.expander("Study timeline"):
                        if dates["start"]:
                            st.write(f"**Start date:** {dates['start']}")
                        if dates["primary_completion"]:
                            st.write(f"**Primary completion:** {dates['primary_completion']}")
                        if dates["completion"]:
                            st.write(f"**Completion:** {dates['completion']}")
                        if dates["last_update_posted"]:
                            st.write(f"**Last updated on ClinicalTrials.gov:** {dates['last_update_posted']}")

                if study["interventions"]:
                    with st.expander("Interventions"):
                        for interv in study["interventions"]:
                            label = interv["name"] or "Unnamed intervention"
                            type_bit = f" ({interv['type']})" if interv["type"] else ""
                            st.write(f"**{label}{type_bit}**")
                            if interv["description"]:
                                st.caption(interv["description"])

                if eligibility["criteria"]:
                    with st.expander("Full eligibility criteria (as listed by the study)"):
                        st.text(eligibility["criteria"])

                if study["central_contacts"]:
                    st.write("**Study contact:**")
                    for c in study["central_contacts"]:
                        bits = [b for b in [c["name"], c["phone"], c["email"]] if b]
                        st.write(f"- {' — '.join(bits)}" if bits else "- Contact listed, no details available.")

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

                        site_contacts = site.get("contacts") or []
                        for c in site_contacts:
                            if not isinstance(c, dict):
                                continue
                            bits = [b for b in [c.get("name"), c.get("phone"), c.get("email")] if b]
                            if bits:
                                st.caption(f"  Contact: {' — '.join(bits)}")
                else:
                    st.write("**Nearby listed sites:** No site details listed.")

                if reasons:
                    st.caption("Why this score: " + "; ".join(reasons))

                with st.expander(f"How this {score}/100 score was calculated"):
                    for label, earned, possible in breakdown:
                        icon = "✅" if earned == possible else ("➖" if earned else "◻️")
                        st.write(f"{icon} {label} — +{earned} of {possible} points")
                    st.caption(
                        "This score reflects recruitment status, location match (real distance "
                        "when searching by ZIP), study type, phase specificity, and whether your "
                        "searched condition is explicitly listed for the study — it is not a "
                        "measure of medical eligibility."
                    )

                if nct_id != "Unknown":
                    st.link_button("View official record", link)

        st.download_button(
            "Download results as CSV",
            data=csv_buffer.getvalue(),
            file_name="clinical_trials_results.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("Compare eligibility criteria")
        compare_options = {
            f"{study['brief_title'] or 'Untitled study'} ({study['nct_id'] or 'Unknown'})": study
            for _, _, _, _, study in ranked
        }
        selected_labels = st.multiselect(
            "Select trials from the results above to compare their eligibility side by side",
            options=list(compare_options.keys()),
        )
        if selected_labels:
            compare_cols = st.columns(len(selected_labels))
            for col, label in zip(compare_cols, selected_labels):
                compare_study = compare_options[label]
                with col:
                    st.markdown(f"**{compare_study['brief_title'] or 'Untitled study'}**")
                    st.caption(compare_study["nct_id"] or "Unknown")
                    st.write(f"**Status:** {compare_study['overall_status'] or 'Unknown'}")
                    if compare_study["phases"]:
                        st.write(f"**Phase:** {', '.join(compare_study['phases'])}")
                    elig = compare_study["eligibility"]
                    elig_bits = []
                    if elig["sex"]:
                        elig_bits.append(elig["sex"])
                    if elig["minimum_age"] or elig["maximum_age"]:
                        elig_bits.append(f"{elig['minimum_age'] or 'N/A'} – {elig['maximum_age'] or 'N/A'}")
                    if elig_bits:
                        st.write(f"**Listed eligibility:** {' | '.join(elig_bits)}")
                    st.markdown("**Full eligibility criteria:**")
                    st.text(elig["criteria"] or "Not listed.")

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
st.markdown(
    "New to clinical trials? Read ClinicalTrials.gov's official guide: "
    "[How to Join a Study](https://clinicaltrials.gov/find-studies/for-patients/how-to-join)."
)
