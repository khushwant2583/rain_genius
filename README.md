# Rain Genius

A beginner-friendly conversational decision-support prototype for Rajasthan households and farmers. It supports English and Roman Hinglish, uses LangGraph for conversation state and routing, Pandas for CSV datasets, RapidFuzz for district matching, and optional Ollama (`qwen2.5:3b`) for structured extraction. Calculations and profile validation are deterministic Python logic. It is **not affiliated with the Rajasthan government** and is not a certified engineering design.

## Current architecture

- `agent/graph.py`: actual LangGraph nodes and conditional routing, with `MemorySaver` per thread.
- `agent/extraction.py`: deterministic extraction plus optional Ollama structured extraction; model output is restricted to allowed categories.
- `agent/language.py`: English/Roman-Hinglish detection and final Devanagari output guard.
- `agent/profile.py`: explicit corrections, district aliases/fuzzy matching, area conversions and missing-field assessment.
- `agent/followups.py`: asks one deterministic next question.
- `agent/data.py`: Pandas CSV loading and completeness checks for monthly rainfall records.
- `agent/design.py`: deterministic rainwater collection calculation and cautious preliminary option.
- `agent/response.py`: template-based response; no LLM-generated numerical facts.
- `data/processed/monthly_rainfall_by_district.csv`: included local monthly rainfall table. Its source/version/coverage metadata still need verification; responses explicitly warn about that.
- `data/reference/subsidies.csv`: includes entries with statuses that require confirmation. The chatbot does not promise subsidy eligibility or amounts.

## Windows setup (PowerShell)

Open PowerShell in this project root (the folder containing `requirements.txt`). Check Python:

```powershell
py --version
py -m pip --version
```

Use Python 3.11 or 3.12. Create and activate a clean environment:

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If `py -3.12` is unavailable, use `py -3.11`. In Command Prompt instead of PowerShell, activate with `.venv\Scripts\activate.bat`.

## Run without Ollama first

This mode is recommended for first-run testing and works offline:

```powershell
$env:USE_MODEL="0"
python -m agent.chat_cli
```

## Enable Ollama

1. Install Ollama for Windows from the official Ollama website and start the Ollama app/service.
2. In a terminal, download the model:

```powershell
ollama pull qwen2.5:3b
ollama list
```

3. In the activated project environment:

```powershell
$env:USE_MODEL="1"
$env:RAIN_MODEL="qwen2.5:3b"
$env:OLLAMA_BASE_URL="http://localhost:11434"
python -m agent.chat_cli
```

If Ollama is offline, the configured model is missing, or structured extraction fails, deterministic rule extraction remains available. Set `USE_MODEL=0` for immediate rule-only behavior. The model never performs calculations or decides authoritative rainfall/subsidy values.

Optional Streamlit UI:

```powershell
python -m streamlit run app.py
```

## Tests

```powershell
python -m pytest -q
```

Tests do not require Ollama when `USE_MODEL=0` is set. To make this the default for a test terminal:

```powershell
$env:USE_MODEL="0"
python -m pytest -q
```

## Data and calculations

Formula:

`rainfall_mm × catchment_area_m2 × runoff_coefficient = theoretical runoff litres`

Estimated collectable volume applies a configurable collection-efficiency factor (`RAIN_COLLECTION_EFFICIENCY`, default `0.9`). The included runoff coefficients are planning assumptions, not universally valid engineering constants. Storage capacity, demand, first flush, conveyance loss, evaporation, overflow, seasonal distribution and site conditions can materially change usable yield.

Supported area units: square feet, square metres, square yards/gaj, acres and hectares. `bigha` is deliberately not converted because its size varies regionally; add a documented district-specific conversion only after verifying it. Expected rainfall CSV columns: `district,month,avg_rainfall_mm`, with exactly one valid row for each month 1–12. If missing/incomplete, the bot will not invent a rainfall figure.

For trusted rainfall data, record the source URL, download date, units, period, processing steps, and license in `data/processed/README.txt`. The current included table's provenance is not fully verified, so calculated output carries an explicit warning. Expected scheme CSV has a `status` column; entries marked `UNVERIFIED`, `NOT_CONFIRMED`, `EXCLUDED`, or similar must not be presented as approved benefits. Verify current-year terms with the official authority.

## Memory and privacy

LangGraph's in-memory checkpointer preserves a thread's profile while the Python process is running. It does **not** persist memory after the process exits. Each CLI run creates a new random thread ID. Use SQLite/Postgres checkpointer only if durable storage is intentionally added and documented.

## Common Windows troubleshooting

- **Wrong working directory:** run `cd` to the project root and verify `dir` shows `requirements.txt` and `agent`.
- **Stale venv path / pip launcher error:** delete only the project's `.venv` after confirming it is the environment folder, recreate it using the commands above, then install with `python -m pip`.
- **Pandas DLL/import error:** use a fresh venv, update pip, reinstall with `python -m pip install --no-cache-dir --force-reinstall pandas`; ensure Python architecture is consistent and do not mix packages from global Python and the venv.
- **Ollama model missing:** run `ollama list`, then `ollama pull qwen2.5:3b`; ensure `RAIN_MODEL` exactly matches a listed model.
- **Ollama connection refused:** open the Ollama desktop app or start its service; test `ollama run qwen2.5:3b` in a separate terminal. Rule-only mode remains available with `USE_MODEL=0`.
- **LangGraph import missing:** activate `.venv` and run `python -m pip install -r requirements.txt`.

## Limitations

The initial advisor is intentionally conservative. It does not estimate construction cost, guarantee water demand coverage, certify recharge suitability, or promise subsidy approval. Drinking water must be appropriately treated and tested before consumption. A qualified local engineer/authority should assess final construction decisions.
