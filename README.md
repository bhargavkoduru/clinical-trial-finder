# Nearby Clinical Trials

A Streamlit MVP for searching recruiting clinical studies on ClinicalTrials.gov by
condition and location.

## Setup

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows, activate the virtual environment with `.venv\Scripts\activate` instead.

## Data source

Queries the official ClinicalTrials.gov v2 API:

```
GET https://clinicaltrials.gov/api/v2/studies
```

## Location matching

- **ZIP code input** (e.g. `02115`) triggers a real distance search: the ZIP is
  resolved to coordinates using a bundled, offline centroid table
  (`services/data/zip_centroids.csv`, derived from the US Census Bureau's public
  domain 2023 ZCTA Gazetteer file), and the app queries the ClinicalTrials.gov
  `filter.geo` distance filter against each study site's real `geoPoint`
  coordinates. No live geocoding service is called.
- **City/state input** (e.g. `Boston, MA`) falls back to text matching against
  each site's facility, city, state, country, and ZIP fields — not geographic
  distance.
- Match scores are a deterministic, explainable ranking signal based on
  recruitment status, location match (text or radius), study type, and phase
  presence. They are **not** a measure of medical eligibility or suitability.

## What's shown per study

Beyond title, status, phase, sponsor, and eligibility summary, each result also
shows: enrollment count, study timeline (start/completion/last updated),
interventions being tested, the study's central contact and per-site contacts
(name/phone/email, as published by ClinicalTrials.gov), the full eligibility
criteria text, and a map of nearby site locations. All of this is public data
already on the study's ClinicalTrials.gov record — nothing here is inferred or
generated.

## Version history

- **v1 — Initial MVP**: core search (condition + location + recruiting-only +
  result count), deterministic 0–100 match scoring, text-based location
  matching, official ClinicalTrials.gov links.
- **v2 — Pagination, eligibility, multi-site, export**: "Load more" pagination
  using the API's `pageToken`/`totalCount`; listed eligibility (sex/age range);
  up to 3 nearby sites per study instead of just one; CSV export; shareable
  search URLs via query params; automatic fallback from a strict `query.cond`
  search to a broader `query.term` search when a condition returns no results.
- **v3 — Real distance search**: ZIP code input now triggers true radius search
  using the API's `filter.geo` distance filter against each site's real
  `geoPoint` coordinates, resolved through a bundled offline US ZIP centroid
  table (no live geocoding service). City/state input still uses text matching.
- **v4 — Site map, contacts, and study detail**: an `st.map` overview of nearby
  site locations; central and per-site study contacts (name/phone/email); study
  enrollment count; full timeline (start/primary completion/completion/last
  updated); interventions being tested; and full eligibility criteria text —
  all pulled from fields ClinicalTrials.gov already publishes per study.
- **v5 — Score transparency**: each result now has a "How this score was
  calculated" breakdown listing all four scoring criteria (recruiting status,
  location match, study type, phase) with points earned vs. possible for each —
  not just the criteria that scored. The scoring rules themselves are
  unchanged; this only makes the existing calculation visible.

## Disclaimer

This tool is informational only. It does not provide medical advice and does
not determine eligibility for any study. Always contact the study site
directly to confirm availability and eligibility. No personal health
information is collected or stored by this application.
