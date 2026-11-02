"""Streamlit dashboard for the Rajasthan Rainwater Harvesting & Water Advisor."""
from pathlib import Path
import uuid

import pandas as pd
import streamlit as st

from agent.graph import chat

ROOT = Path(__file__).resolve().parent
RAINFALL_PATH = ROOT / "data" / "processed" / "monthly_rainfall_by_district.csv"
SUBSIDY_PATH = ROOT / "data" / "reference" / "subsidies.csv"

st.set_page_config(
    page_title="Rajasthan Water Advisor",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .block-container {padding-top: 1.7rem; padding-bottom: 3rem; max-width: 1400px;}
  .hero {padding: 1.35rem 1.5rem; border-radius: 18px; margin-bottom: 1.1rem;
         background: linear-gradient(115deg, rgba(14,116,144,.25), rgba(30,64,175,.15));
         border: 1px solid rgba(100,160,190,.25);}
  .hero p {margin-bottom: .15rem; color: #aab8c7;}
  div[data-testid="stMetric"] {padding: 14px 16px; border: 1px solid rgba(128,128,128,.2);
         border-radius: 14px; background: rgba(128,128,128,.04);}
  .small-note {font-size: .84rem; color: #9ca3af;}
</style>
""", unsafe_allow_html=True)

@st.cache_data

def load_rainfall():
    if not RAINFALL_PATH.exists():
        return pd.DataFrame(columns=["district", "month", "avg_rainfall_mm"])
    df = pd.read_csv(RAINFALL_PATH)
    required = {"district", "month", "avg_rainfall_mm"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["district", "month", "avg_rainfall_mm"])
    df["district"] = df["district"].astype(str).str.strip()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["avg_rainfall_mm"] = pd.to_numeric(df["avg_rainfall_mm"], errors="coerce")
    return df.dropna(subset=["district", "month", "avg_rainfall_mm"])

@st.cache_data

def load_subsidies():
    if not SUBSIDY_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(SUBSIDY_PATH, encoding="utf-8-sig").fillna("")
    except (OSError, pd.errors.ParserError, UnicodeError):
        return pd.DataFrame()

rainfall_df = load_rainfall()
subsidy_df = load_subsidies()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.markdown("""
<div class="hero">
  <p>RAJASTHAN · WATER PLANNING ASSISTANT</p>
  <h1 style="margin:.25rem 0 .45rem 0;">Rainwater Harvesting &amp; Water Advisor</h1>
  <p>Explore rainfall patterns, estimate collection potential, and discover schemes to verify.</p>
</div>
""", unsafe_allow_html=True)
st.caption("Decision-support prototype; not affiliated with the Rajasthan government. Estimates depend on the supplied dataset and assumptions.")

# Shared district selection makes the charts and quick estimate data-driven.
if rainfall_df.empty:
    districts = ["Jalor"]
else:
    districts = sorted(rainfall_df["district"].dropna().unique().tolist())
default_district_index = next((i for i, d in enumerate(districts) if d.casefold() in {"jalor", "jalore"}), 0)

# Apply district and catchment details extracted from chat before creating widgets.
pending_district = st.session_state.pop("pending_dashboard_district", None)
if pending_district:
    match = next((d for d in districts if d.casefold() == str(pending_district).strip().casefold()), None)
    if match:
        st.session_state["district_selector"] = match

pending_estimate = st.session_state.pop("pending_dashboard_estimate", None)
if pending_estimate:
    if pending_estimate.get("area_m2") is not None:
        st.session_state["area_input"] = float(pending_estimate["area_m2"])
    if pending_estimate.get("catchment_type") in {"Roof", "Open land"}:
        st.session_state["catchment_type_input"] = pending_estimate["catchment_type"]
    if pending_estimate.get("efficiency_pct") is not None:
        st.session_state["efficiency_input"] = int(pending_estimate["efficiency_pct"])

with st.sidebar:
    st.header("Explore your location")
    district = st.selectbox(
        "District", districts, index=default_district_index, key="district_selector"
    )
    st.divider()
    st.subheader("Quick estimator")
    catchment_type = st.radio(
        "Catchment type", ["Roof", "Open land"], horizontal=True, key="catchment_type_input"
    )
    area = st.number_input(
        "Catchment area (m²)", min_value=1.0, max_value=1_000_000.0,
        value=111.48, step=10.0, key="area_input"
    )
    if catchment_type == "Roof":
        roof_type = st.selectbox("Roof surface", ["Concrete", "Metal", "Tiles", "Asbestos"])
        coeff = {"Concrete": 0.80, "Metal": 0.90, "Tiles": 0.75, "Asbestos": 0.75}[roof_type]
    else:
        coeff = 0.20
        st.caption("Open-land runoff varies substantially with soil, slope, and ground cover.")
    efficiency = st.slider(
        "Collection efficiency", min_value=50, max_value=100, value=90, step=5,
        key="efficiency_input"
    ) / 100
    st.caption("Uses average monthly rainfall in the included dataset. Its provenance may need verification.")

month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
selected = rainfall_df[rainfall_df["district"].str.casefold() == district.casefold()].copy() if not rainfall_df.empty else pd.DataFrame()
if not selected.empty:
    selected = selected.sort_values("month")
    annual_rainfall = float(selected["avg_rainfall_mm"].sum())
    valid_months = int(selected["month"].nunique())
    complete = valid_months == 12
else:
    annual_rainfall = None
    valid_months = 0
    complete = False

if annual_rainfall is not None:
    theoretical_l = annual_rainfall * area * coeff
    collectable_l = theoretical_l * efficiency
    collectable_kl = collectable_l / 1000
else:
    collectable_l = collectable_kl = None

# Tabs keep the dashboard and conversation together without crowding one page.
tab_overview, tab_chat, tab_schemes, tab_method = st.tabs(["📊 Overview", "💬 Water Advisor", "🌱 Schemes & Subsidies", "ℹ️ Method & Data"])

with tab_overview:
    st.subheader(f"Water snapshot · {district}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Annual rainfall", f"{annual_rainfall:,.1f} mm" if annual_rainfall is not None else "Unavailable")
    m2.metric("Estimated collection", f"{collectable_l:,.0f} L" if collectable_l is not None else "Unavailable")
    m3.metric("Catchment area", f"{area:,.2f} m²")
    m4.metric("Months available", f"{valid_months}/12")

    if not complete:
        st.warning("This district does not have 12 distinct monthly records in the current dataset. Treat the annual estimate and chart as incomplete.")

    left, right = st.columns([1.35, 1])
    with left:
        st.subheader("Monthly rainfall pattern")
        if not selected.empty:
            chart_df = selected.copy().sort_values("month")
            chart_df["Month"] = chart_df["month"].astype(int).map(lambda x: month_names[x - 1] if 1 <= x <= 12 else str(x))
            chart_df["Month"] = pd.Categorical(chart_df["Month"], categories=month_names, ordered=True)
            chart_df = chart_df.sort_values("Month")
            st.bar_chart(chart_df.set_index("Month")[["avg_rainfall_mm"]], y_label="Rainfall (mm)")
        else:
            st.info("No monthly rainfall records were found for this district.")
    with right:
        st.subheader("Estimated collection")
        if collectable_l is not None:
            compare_df = pd.DataFrame({"Component": ["Theoretical runoff", "Estimated collectable"], "Litres": [round(theoretical_l), round(collectable_l)]}).set_index("Component")
            st.bar_chart(compare_df, y_label="Litres")
            st.write(f"**Estimated volume:** {collectable_l:,.0f} L ({collectable_kl:.2f} kL)")
            st.caption(f"Assumptions: runoff coefficient {coeff:.2f}; collection efficiency {efficiency:.0%}.")
        else:
            st.info("Collection estimate will appear when rainfall data is available.")

    st.subheader("Planning notes")
    n1, n2, n3 = st.columns(3)
    n1.info("**Storage:** Size the tank against seasonal inflow and actual demand—not annual rainfall alone.")
    n2.info("**Water quality:** Include first-flush diversion and filtration. Treat and test water before drinking.")
    n3.info("**Data quality:** Confirm the rainfall source, period, and completeness before using this estimate for construction.")

with tab_chat:
    st.subheader("Ask the Water Advisor")
    st.caption("Describe your district, purpose, roof/land area, or ask about schemes. English and Roman Hinglish are supported.")
    chat_col, control_col = st.columns([5, 1])
    with control_col:
        if st.button("New chat", use_container_width=True):
            st.session_state.thread_id = str(uuid.uuid4())
            st.session_state.chat_history = []
            st.rerun()
    for role, content in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(content)
    prompt = st.chat_input("e.g. I am a farmer in Jalor and want to know about rainwater subsidies")
    if prompt:
        st.session_state.chat_history.append(("user", prompt))
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Checking your details and available data..."):
                try:
                    result = chat(prompt, thread_id=st.session_state.thread_id)
                    reply = result.get("reply", "I could not prepare a response.")
                    st.markdown(reply)
                    profile = result.get("profile") or {}
                    design = result.get("design") or {}

                    # Sync dashboard district, area, surface type, and efficiency with chat results.
                    chat_district = profile.get("district") or design.get("district")
                    if chat_district:
                        match = next(
                            (d for d in districts if d.casefold() == str(chat_district).strip().casefold()),
                            None,
                        )
                        if match:
                            st.session_state["pending_dashboard_district"] = match

                    if design and design.get("area_m2") is not None and design.get("estimated_collectable_l") is not None:
                        raw_type = str(profile.get("catchment_type", "")).casefold()
                        dashboard_type = "Open land" if raw_type in {"land", "open_land", "field"} else "Roof"
                        theoretical = float(design.get("theoretical_runoff_l") or 0)
                        estimated = float(design.get("estimated_collectable_l") or 0)
                        efficiency_pct = round(estimated / theoretical * 100) if theoretical > 0 else 90
                        st.session_state["pending_dashboard_estimate"] = {
                            "area_m2": float(design["area_m2"]),
                            "catchment_type": dashboard_type,
                            "efficiency_pct": max(50, min(100, int(efficiency_pct))),
                        }
                    if profile:
                        with st.expander("Details collected"):
                            st.json(profile)
                except Exception as exc:
                    reply = f"The workflow failed ({type(exc).__name__}). Check the terminal traceback."
                    st.error(reply)
        st.session_state.chat_history.append(("assistant", reply))
        st.rerun()

with tab_schemes:
    st.subheader("Scheme explorer")
    st.write("Use this section to explore candidate schemes. Listing a scheme does not confirm eligibility or current-year availability.")
    if subsidy_df.empty:
        st.warning("The subsidy dataset is missing or could not be read. Check data/reference/subsidies.csv.")
    else:
        scheme_type_options = sorted([x for x in subsidy_df.get("scheme_type", pd.Series(dtype=str)).astype(str).unique() if x])
        chosen_type = st.selectbox("Filter by category", ["All categories"] + scheme_type_options)
        filtered = subsidy_df.copy()
        if chosen_type != "All categories":
            filtered = filtered[filtered["scheme_type"].astype(str) == chosen_type]
        status_col = "status" if "status" in filtered.columns else None
        if status_col:
            filtered["Verification"] = filtered[status_col].replace({"SOURCE_CHECKED_CONFIRM_CURRENT_YEAR": "Source checked; current year needs confirmation", "UNVERIFIED": "Unverified", "EXCLUDED": "Excluded from rainwater subsidy"})
        display_cols = [c for c in ["scheme_name", "scheme_type", "applies_to", "subsidy_percent", "subsidy_cap_inr", "eligibility", "Verification"] if c in filtered.columns]
        if display_cols:
            st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)
        st.markdown("**Official/source links**")
        for _, row in filtered.iterrows():
            name = str(row.get("scheme_name", "Scheme"))
            url = str(row.get("source_url", "")).strip()
            status = str(row.get("status", "UNVERIFIED"))
            with st.expander(f"{name} · {status}"):
                st.write(str(row.get("eligibility", "Eligibility details not supplied.")))
                if row.get("notes"):
                    st.caption(str(row.get("notes")))
                if url.startswith("https://"):
                    st.link_button("Open source / verify current terms", url)
                if row.get("last_verified"):
                    st.caption(f"Last dataset review: {row.get('last_verified')}")
        st.warning("Do not treat unverified rates, caps, or scheme entries as an approved benefit. Confirm current rules with the official department before applying.")

with tab_method:
    st.subheader("How the estimate is calculated")
    st.latex(r"\text{Theoretical runoff (L)} = \text{Rainfall (mm)} \times \text{Area (m}^2\text{)} \times \text{Runoff coefficient}")
    st.latex(r"\text{Estimated collection (L)} = \text{Theoretical runoff} \times \text{Collection efficiency}")
    st.write("The estimator uses the monthly rainfall values supplied in the project dataset, the selected catchment area, a surface-specific runoff coefficient, and a configurable collection-efficiency assumption.")
    st.write("This is a planning estimate, not a guarantee of usable water. Actual yield depends on rainfall distribution, surface condition, first-flush diversion, leaks, evaporation, overflow, storage limits, and water demand.")
    st.write(f"**Dataset status for {district}:** {valid_months} distinct monthly records found.")
    if not selected.empty:
        st.write("**Rainfall data preview**")
        st.dataframe(selected.rename(columns={"district": "District", "month": "Month number", "avg_rainfall_mm": "Average rainfall (mm)"}), use_container_width=True, hide_index=True)
    st.caption("Prototype data may have unverified provenance. Check source, coverage, and current official scheme rules before making financial or construction decisions.")
