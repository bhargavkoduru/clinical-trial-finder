# Project Documentation — Nearby Clinical Trials

This document records why this project exists, what data it runs on, how it was
built through an iterative "vibe coding" workflow with an AI assistant, and what
was learned along the way. It's plain Markdown so it renders on GitHub, can be
edited in GitHub's web editor, and can be copy-pasted into a Google Doc (the
`#`/`-`/`**` characters will paste as plain text that Google Docs lets you
reformat, or render automatically if you use a markdown-import add-on).

---

## 1. Project Overview

### Problem statement

Someone looking for a clinical trial relevant to their condition and location
has to use ClinicalTrials.gov's own search UI, which surfaces a large number of
results with no simple way to see *why* one study might be more relevant than
another, no quick sense of which nearby sites are actually within a reasonable
distance, and no lightweight way to compare a shortlist of studies side by
side. At the same time, any tool built on top of this data has to be careful
not to cross the line into medical advice or eligibility determination — that
judgment belongs to the patient and the study's own clinical staff, not to
software.

**Goal:** build a small, self-contained Streamlit app that lets a user search
ClinicalTrials.gov by condition and location, ranks results with a transparent
and explainable (not medical) relevance score, and surfaces the practical
information someone would actually need — status, location, contacts,
eligibility criteria, enrollment, timeline — without ever implying a
recommendation, a match, or an eligibility outcome. The app had to run on
free/public data sources only: no paid APIs, no geocoding service, no LLM
calls, no database, no auth.

### Non-goals (explicit constraints)

- No medical advice or eligibility determination, at any point.
- No paid or external geocoding service — only ClinicalTrials.gov's own data
  plus static, offline public-domain datasets.
- No database, authentication, LLM calls, or embeddings.
- Standard library + `streamlit` + `requests` only.

---

## 2. Datasets used

| Dataset | Source | Purpose | License / access |
|---|---|---|---|
| ClinicalTrials.gov v2 Studies API | `https://clinicaltrials.gov/api/v2/studies` (live REST API, run by the U.S. National Library of Medicine) | Primary data source — study search, status, phase, sponsor, eligibility, contacts, enrollment, dates, interventions, and per-site `geoPoint` coordinates | Public, free, no API key required |
| US Census Bureau 2023 ZCTA Gazetteer | `www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_zcta_national.zip` | Reduced to a bundled offline `zip → (lat, lon)` lookup table (`services/data/zip_centroids.csv`, ~33.8K US ZIP codes) so a ZIP code search can be converted to coordinates **without calling a live geocoding service** | Public domain (US government work) |

The Census file was downloaded once, parsed down to just the three columns the
app needs (`zip,lat,lon`), and committed directly into the repo (~925 KB) —
there's no runtime dependency on the Census Bureau's servers.

---

## 3. Prompts used during vibe coding

Below is the actual chronological sequence of prompts that drove this
project's development in this session, kept close to verbatim (typos and all)
as an honest record of the process.

1. **Initial spec** — a long, fully detailed build spec: *"Build a
   production-minded Streamlit MVP called 'Nearby Clinical Trials'..."*
   specifying the exact API params (`query.cond`, `query.locn`,
   `filter.overallStatus`, `pageSize`, `format`), project file structure,
   normalization rules, scoring rubric, UI copy, safety/privacy constraints,
   and README requirements.
2. *"execute it for me. I don't know streamlit. Also, the eventual goal is to
   post the entire code base, README, etc as a project in my github and also,
   I should be able to access the streamlit app from my github."*
3. *"python is installed"* — after the environment initially lacked a working
   Python interpreter.
4. `https://github.com/bhargavkoduru/clinical-trial-finder` — the target repo
   to push to.
5. *"what are the additional updates that can be done using the existing
   clinicaltrials.gov API and limitations of streamlit but give a better
   experience to the user?"*
6. *"execute above and test. Also, see if the search of the disease or
   condition can be enhanced."*
7. *"yes, push the changes to Github"*
8. A Streamlit Cloud `ImportError` screenshot with: *"I'm getting following
   error in streamlit"*
9. *"how is the score calculated? explain in a few words with an example"*
10. *"explain similarly for location, condition matching"*
11. *"this location `https://clinicaltrials.gov/data-api/api` says that
    Locations and geopoint data are now pulling from a different database for
    geographic data. is that considered?"*
12. *"implement"*
13. *"is it pushed to Git? also update read me to show how the app has been
    slowly updated version after version and what those changes are."*
14. *"Enhance the existing app without changing its core behavior. Show how
    the matching score is calculated for each match, for transparency to the
    user"*
15. *"pushed to Git? read me updated to show this change in version
    history?"*
16. *"Should the overall score be updated based on how close the patient is
    to the site location? Also, what is the score difference to recruiting
    vs not yet recruiting? Also, should the score be optimized to show if
    the trial is very specific to the condition? should the score be
    updated based on the Phase? Maybe a later phase is close to maturity
    of the drug? Phase I/II usually include drug dosage optimization. Can
    any of these be implemented? Also, can the user select a few trials and
    compare the eligibility criteria, from the dropdown list?"*
17. *"go ahead with the four recommendations."*
18. *"add this url and details for the user in the app:
    `https://clinicaltrials.gov/find-studies/for-patients/how-to-join`"*
19. *"the options to download as csv, comparing eligibility criteria and the
    url to how to join a study are at the very bottom of the page. Can they
    be moved to the top of the app? can the app be enhanced in any other way
    from UI point to be more welcoming, and encouraging the user to learn
    about clinical trials."*
20. *"The map is not showing all the locations"*
21. *"show only the sites within the search radius"*
22. *"I need a 'Project Documentation' file created..."* (this document)

---

## 4. Iterations tried

| Version | What changed | Why |
|---|---|---|
| **v1 — Initial MVP** | Core search form (condition, location, recruiting-only, result count); deterministic 0–100 score (recruiting +40, location text match +30, interventional +10, phase specified +10); text-based location matching; official ClinicalTrials.gov links | Ship the spec as given |
| **v2 — Pagination & depth** | `pageToken`/`totalCount`-based "Load more"; listed eligibility (sex/age); up to 3 nearby sites instead of 1; CSV export; shareable search URLs via `st.query_params`; automatic fallback from strict `query.cond` to broader `query.term` when a condition search returns nothing | Users were capped at one page and one site, and exact condition-field mismatches silently returned zero results |
| **v3 — Real distance search** | ZIP code input resolved to lat/lon via the bundled Census centroid table, then used with the API's `filter.geo` distance filter for a true radius search; city/state input still text-matched | Discovered live that ClinicalTrials.gov now returns real per-site `geoPoint` data and a working `filter.geo` param — this closed the "textual guess" gap without needing a paid geocoding API |
| **v4 — Study detail & map** | `st.map` of nearby sites; central + per-site contacts (name/phone/email); enrollment count; study timeline; interventions; full eligibility criteria text | These fields already existed in the API but weren't surfaced; contacts in particular closed a real gap (the disclaimer said "contact the site" but gave no way to) |
| **v5 — Score transparency** | Per-result "How this score was calculated" expander showing every criterion, earned vs. possible, not just the ones that scored | Users had only a one-line "why" summary; refactored `score_study` to build off a shared `score_breakdown()` function, verified byte-for-byte identical output to the pre-refactor version before shipping |
| **v6 — Scoring rubric upgrade** | Recruitment status now gives partial credit to `NOT_YET_RECRUITING` (15 pts, was 0); location match graduated by real distance (0–30, tapering across the radius) instead of flat pass/fail; new +15 criterion for the searched condition being explicitly listed in the study's own `ConditionsModule`; added a "Compare eligibility criteria" multiselect | Requested rubric review surfaced that `NOT_YET_RECRUITING` scored identically to `TERMINATED`, and that location/condition matching were binary when better signal was available |
| **(deliberately not done)** | Weighting score by trial phase (e.g. favoring Phase 3/4 over Phase 1/2) | Explicitly rejected — this would embed an implicit "later phase = better trial for you" suitability judgment, which conflicts with the app's informational-only, no-medical-advice mandate. Phase stays visible but unscored. |
| **v7 — Patient guidance link** | Linked ClinicalTrials.gov's own official "How to Join a Study" guide | Give users a next step without the app itself giving process/eligibility guidance |
| **v8 — Onboarding & layout** | Moved CSV download and eligibility comparison above the results list; moved the "How to Join" link into a "New to clinical trials? Start here" expander near the top; added a data-source credibility caption and three one-click example searches | Original layout buried the most useful tools at the bottom of a long results page |
| **Bug fix — map coverage** | Map was plotting only the nearest site per study (`sites[:1]`) instead of all listed sites | Caught by comparing marker count against the actual number of sites shown in the text list |
| **Bug fix — radius leakage** | `nearby_locations` returned the 3 *nearest* sites regardless of whether they were within the search radius, so a multi-region trial could show/map a site far outside the requested distance | Caught by explicitly testing a Boston + NYC site pair against a 25-mile radius |

---

## 5. Learnings and observations

- **Verifying against the live API, not just synthetic test data, repeatedly
  caught real bugs.** Both the "map only shows 1 site" bug and the "sites
  outside the search radius still shown" bug were invisible in isolated unit
  tests and only became obvious when checked against real, multi-site trial
  records with `filter.geo` live.
- **The API itself evolved mid-project.** The original spec explicitly
  excluded geocoding/maps because ClinicalTrials.gov's location data used to
  be text-only. A later check of the API's own field metadata
  (`/api/v2/studies/metadata`) showed it now returns real per-site `geoPoint`
  coordinates and a working `filter.geo` distance filter — this enabled a
  genuine radius search using only a bundled, offline, public-domain ZIP
  centroid dataset, with no paid geocoding service and no scope violation.
- **Streamlit's `AppTest` framework was the main regression-testing tool** in
  a non-interactive/headless environment where a real browser wasn't
  available — it runs the actual script, drives real widget interactions
  (button clicks, form submits, multiselects), and surfaces exceptions,
  making it a fast substitute for manual UI testing.
- **Streamlit widget defaults have a gotcha:** a `text_input`'s `value=`
  parameter is only honored the *first* time a given `key` is rendered in a
  session; after that, `st.session_state` is the source of truth. This meant
  the one-click "example search" buttons had to set
  `st.session_state["condition_input"]` directly (not just change the query
  string) before triggering a rerun.
- **Streamlit Cloud's error banner deliberately redacts exception details**
  ("The original error message is redacted to prevent data leaks") — the
  real traceback is only visible in the app's own log pane via "Manage app,"
  which matters when diagnosing a deployed-but-not-local failure.
- **GitHub blocks pushes containing a real, privacy-protected email address**
  (`GH007`) — resolved by committing under a `users.noreply.github.com`
  address instead of a real one.
- **A small Windows/Bash-tool path-translation gotcha**: extracting the
  Census ZIP file and reading it back with a Windows-native Python
  interpreter needed the actual Windows path (`C:\Users\...`), not the
  POSIX-style `/tmp/...` path the shell tool reported, since MSYS/Git-Bash
  and Windows Python don't share a path namespace.
- **Explicitly deciding what *not* to build was as important as building
  features.** Phase-based score weighting was a reasonable-sounding request
  that was declined because it would have quietly turned a relevance score
  into an implied treatment recommendation — a reminder that "can we score
  this?" and "should we score this?" are different questions in a
  health-adjacent tool.
