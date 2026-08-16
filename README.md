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

## Limitations

- Location matching is text-based (facility, city, state, country, ZIP), not
  geographic distance. There is no geocoding or radius search in this MVP.
- Match scores are a deterministic, explainable ranking signal based on
  recruitment status, location text match, study type, and phase presence.
  They are **not** a measure of medical eligibility or suitability.

## Disclaimer

This tool is informational only. It does not provide medical advice and does
not determine eligibility for any study. Always contact the study site
directly to confirm availability and eligibility. No personal health
information is collected or stored by this application.
