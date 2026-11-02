# Implementation notes

## Changes made

- Updated `agent/profile.py` so required fields depend on the selected goal rather than requiring household-size details for every household goal.
- Aligned household irrigation validation with the current design behavior: a supplied household roof area and roof type can be used for the irrigation catchment; otherwise land/open area is required.
- Added robust numeric parsing for area, people, and water-demand inputs so malformed values become validation messages instead of exceptions.
- Added rooftop-vs-farm storage-location extraction and validation for farmer/landowner storage.
- Fixed follow-up question mappings for `available_area`, `roof_area`, `people_or_water_demand`, `water_demand_l`, and `storage_location` so missing fields produce a question rather than no question.
- Added optional LLM phrasing for follow-up questions, constrained to the already validated missing-field list. Templates remain the fallback. Disable the second call with `RAIN_DYNAMIC_FOLLOWUP=0` if latency matters more than dynamic phrasing.
- Made cost table lookup fail with a clear error when a cost item is missing rather than raising an opaque `IndexError`.
- Changed Streamlit to call the same LangGraph workflow as the CLI and use a unique thread ID per Streamlit session.
- Cleared stale design output when a profile becomes incomplete or invalid.
- Added Streamlit to `requirements.txt`, offline profile tests, and a unified test runner.

## Validation performed here

- Python compile check: passed.
- Profile/unit tests: 7 passed.
- Direct extraction/profile reproduction of the reported sequence: `Jalore me ghar hai` -> `Sinchai ke liye` -> `concrete aur area 1200 sqft hai` reaches no missing fields after the final message.
- Direct calculation checks against the supplied local CSVs: household roof irrigation, household storage, farmer irrigation, and groundwater recharge returned recommendations.

## Validation not performed here

The execution environment did not have `langgraph`, `ollama`, or `streamlit` installed and network access prevented installing them. Therefore, the full graph/Streamlit runtime and a live Ollama response were not executed in this environment. Install `requirements.txt` locally and run `python -m scripts.run_tests` before replacing your backup.

## Data cautions

The supplied `costs.csv` explicitly marks the rates as placeholders. This implementation does not change those values or claim they are verified. Confirm costs, rainfall provenance, subsidy scheme details, and the engineering assumptions before using the recommendations for construction.
