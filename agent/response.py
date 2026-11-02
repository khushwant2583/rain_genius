
"""Safe, template-based response generation; LLM text never controls factual output."""

import pandas as pd

from agent.language import safe_output
from agent.followups import next_question
from agent.data import load_csv


def get_number(profile, *keys):
    """Return the first valid, non-negative numeric value."""
    for key in keys:
        value = profile.get(key)

        if value is None or str(value).strip() == "":
            continue

        try:
            number = float(value)
            if pd.notna(number) and number >= 0:
                return number
        except (TypeError, ValueError):
            continue

    return None


def calculate_farm_pond_cost(profile, scheme_row):
    """
    Estimate pond volume, construction cost, subsidy and remaining cost.

    Accepted profile keys:
      pond_length_m, pond_width_m, pond_depth_m,
      construction_rate_per_m3, construction_cost_inr
    """
    length = get_number(profile, "pond_length_m", "length_m")
    width = get_number(profile, "pond_width_m", "width_m")
    depth = get_number(profile, "pond_depth_m", "depth_m")

    rate = get_number(
        profile,
        "construction_rate_per_m3",
        "cost_per_m3",
    )

    provided_cost = get_number(
        profile,
        "construction_cost_inr",
        "estimated_construction_cost_inr",
        "project_cost_inr",
    )

    volume_m3 = None

    if all(
        value is not None and value > 0
        for value in (length, width, depth)
    ):
        volume_m3 = length * width * depth

    if provided_cost is not None and provided_cost > 0:
        total_cost = provided_cost
    elif (
        volume_m3 is not None
        and rate is not None
        and rate > 0
    ):
        total_cost = volume_m3 * rate
    else:
        return {
            "needs_details": True,
            "volume_m3": volume_m3,
        }

    try:
        percent = float(scheme_row["subsidy_percent"])
        cap = float(scheme_row["subsidy_cap_inr"])
    except (TypeError, ValueError, KeyError):
        return {
            "needs_details": True,
            "volume_m3": volume_m3,
        }

    if (
        pd.isna(percent)
        or pd.isna(cap)
        or percent <= 0
        or cap <= 0
    ):
        return {
            "needs_details": True,
            "volume_m3": volume_m3,
        }

    # Indicative calculation only; actual eligible cost is scheme-dependent.
    subsidy = min(total_cost * percent / 100.0, cap)

    return {
        "needs_details": False,
        "volume_m3": volume_m3,
        "total_cost": total_cost,
        "subsidy": subsidy,
        "remaining_cost": max(0, total_cost - subsidy),
        "percent": percent,
        "cap": cap,
    }


def _format_number(value):
    return f"{float(value):,.0f}"


def _is_number(value):
    try:
        number = float(value)
        return pd.notna(number) and number >= 0
    except (TypeError, ValueError):
        return False


def _subsidy_response(lang, profile):
    """Generate a concise subsidy response using the CSV dataset."""

    df = load_csv("reference", "subsidies.csv")

    if df is None or df.empty:
        return (
            "Subsidy ka data available nahi hai. RajKisan ya district agriculture office se confirm karein."
            if lang == "hinglish"
            else "Subsidy data is unavailable. Please check RajKisan or your district agriculture office."
        )

    # Normalize CSV headers.
    df.columns = [
        str(column).strip().lower().lstrip("*").replace(" ", "_")
        for column in df.columns
    ]

    required = {
        "scheme_id",
        "scheme_name",
        "scheme_type",
        "subsidy_percent",
        "subsidy_cap_inr",
        "status",
    }

    if not required.issubset(df.columns):
        return (
            "Subsidy CSV ke column names check karein."
            if lang == "hinglish"
            else "The subsidy CSV has an unexpected schema."
        )

    # Only the two farm-pond subsidy schemes are handled here.
    verified = df[
        df["scheme_type"].astype(str).str.strip().str.lower().eq("subsidy")
        & df["status"].astype(str).str.strip().str.upper().eq("VERIFIED")
        & df["scheme_id"].astype(str).str.strip().str.upper().isin(
            {"KT-RAW", "KT-LINED"}
        )
    ].copy()

    if verified.empty:
        return (
            "CSV mein matching VERIFIED khet-talab subsidy nahi mili. Scheme IDs aur status check karein."
            if lang == "hinglish"
            else "No matching VERIFIED farm-pond subsidy was found in the dataset."
        )

    # Filter by pond type if explicitly supplied.
    pond_type = str(
        profile.get("pond_type", profile.get("structure", ""))
    ).strip().lower()

    if any(word in pond_type for word in ("lined", "plastic", "lining")):
        verified = verified[
            verified["scheme_id"].astype(str).str.upper().eq("KT-LINED")
        ]
    elif any(
        word in pond_type
        for word in ("raw", "unlined", "without lining")
    ):
        verified = verified[
            verified["scheme_id"].astype(str).str.upper().eq("KT-RAW")
        ]

    if verified.empty:
        return (
            "Aapke pond type ke liye matching scheme nahi mili. Pond type check karein."
            if lang == "hinglish"
            else "No matching scheme was found for the specified pond type."
        )

    lines = [
        "Khet-talab subsidy estimate:"
        if lang == "hinglish"
        else "Farm pond subsidy estimate:"
    ]

    # Check user-provided landholding, if available.
    landholding = get_number(
        profile,
        "landholding_ha",
        "land_area_ha",
        "cultivable_land_ha",
    )

    for _, row in verified.iterrows():
        name = str(row.get("scheme_name", "Khet Talai")).strip()

        try:
            percent = float(row["subsidy_percent"])
            cap = float(row["subsidy_cap_inr"])
        except (TypeError, ValueError):
            continue

        if pd.isna(percent) or pd.isna(cap) or percent <= 0 or cap <= 0:
            continue

        lines.append(f"\n{name}")
        lines.append(
            f"Subsidy rate: {percent:g}%, maximum Rs {_format_number(cap)}."
            if lang == "english"
            else f"Subsidy rate: eligible cost ka {percent:g}%, maximum Rs {_format_number(cap)}."
        )

        minimum_capacity = get_number(
            {"value": row.get("min_capacity_m3")},
            "value",
        )
        minimum_land = get_number(
            {"value": row.get("min_landholding_ha")},
            "value",
        )

        # Calculate construction cost and indicative subsidy.
        estimate = calculate_farm_pond_cost(profile, row)

        if not estimate["needs_details"]:
            volume = estimate["volume_m3"]

            if volume is not None:
                lines.append(
                    f"Estimated pond capacity: {volume:.2f} m3."
                    if lang == "english"
                    else f"Talab ki estimated capacity: {volume:.2f} m3."
                )

                if (
                    minimum_capacity is not None
                    and minimum_capacity > 0
                    and volume < minimum_capacity
                ):
                    lines.append(
                        f"Warning: Minimum required capacity {minimum_capacity:g} m3 hai; "
                        "aapka pond isse chhota hai. Eligibility confirm karein."
                        if lang == "hinglish"
                        else f"Warning: Minimum required capacity is {minimum_capacity:g} m3; "
                             "your pond is smaller. Confirm eligibility."
                    )

            lines.append(
                f"Estimated construction cost: Rs {_format_number(estimate['total_cost'])}."
                if lang == "english"
                else f"Estimated construction cost: Rs {_format_number(estimate['total_cost'])}."
            )

            lines.append(
                f"Estimated subsidy: Rs {_format_number(estimate['subsidy'])}."
                if lang == "english"
                else f"Estimated subsidy: Rs {_format_number(estimate['subsidy'])}."
            )

            lines.append(
                f"Remaining estimated cost: Rs {_format_number(estimate['remaining_cost'])}."
                if lang == "english"
                else f"Subsidy ke baad estimated cost: Rs {_format_number(estimate['remaining_cost'])}."
            )
        else:
            lines.append(
                "Cost aur subsidy calculate karne ke liye pond ki length, width aur depth (metres) "
                "aur construction rate (Rs/m3) batayein. Total construction cost bhi de sakte hain."
                if lang == "hinglish"
                else "To calculate cost and subsidy, provide pond length, width and depth in metres "
                     "and the construction rate (Rs/m3), or provide the total construction cost."
            )

        if minimum_land is not None and minimum_land > 0:
            if landholding is None:
                lines.append(
                    f"Minimum landholding: {minimum_land:g} hectare. Aapki landholding kitni hectare hai?"
                    if lang == "hinglish"
                    else f"Minimum landholding: {minimum_land:g} hectare. Please provide your landholding."
                )
            elif landholding < minimum_land:
                lines.append(
                    f"Warning: Is scheme ke liye minimum landholding {minimum_land:g} hectare hai. "
                    "Aapki di hui landholding isse kam hai."
                    if lang == "hinglish"
                    else f"Warning: This scheme requires at least {minimum_land:g} hectare; "
                         "your stated landholding is below that threshold."
                )

        eligibility = str(row.get("eligibility", "")).strip()
        if eligibility and eligibility.lower() != "nan":
            lines.append(
                f"Eligibility: {eligibility}"
                if lang == "english"
                else f"Zaroori eligibility: {eligibility}"
            )

        source = str(row.get("source_url", "")).strip()
        if source.startswith(("https://", "http://")):
            lines.append(f"Official link: {source}")

    lines.append(
        "Note: CSV ka VERIFIED status approval ya current funding ki guarantee nahi hai. Construction se pehle RajKisan se confirm karein."
        if lang == "hinglish"
        else "Note: VERIFIED in the CSV does not guarantee current funding or approval. Confirm with RajKisan before construction."
    )

    return "\n".join(lines)


def _cost_lines(design, lang):
    lines = []
    estimates = design.get("cost_estimates") or []
    if estimates:
        lines.append("Indicative cost range (CSV rates):" if lang == "english" else "CSV rates ke hisaab se estimated cost:")
        for item in estimates:
            lines.append(f"- {item['item']}: Rs {_format_number(item['low_inr'])}–Rs {_format_number(item['high_inr'])}")
    subsidy = design.get("subsidy_estimate") or {}
    if subsidy.get("percent"):
        lines.append(f"Potential subsidy estimate (60%, capped at Rs {_format_number(subsidy['cap_inr'])}): Rs {_format_number(subsidy['low_subsidy_inr'])}–Rs {_format_number(subsidy['high_subsidy_inr'])}.")
        lines.append(f"Estimated remaining cost: Rs {_format_number(subsidy['low_remaining_inr'])}–Rs {_format_number(subsidy['high_remaining_inr'])}.")
        lines.append(subsidy.get("eligibility_note", "Eligibility and funding must be confirmed."))
    elif subsidy.get("message"):
        lines.append(subsidy["message"])
    if estimates:
        lines.append("Rates are placeholders/indicative, not verified quotations; final tank size/pond design needs site assessment.")
    return "\n".join(lines) + ("\n" if lines else "")


def make_response(language, profile, gaps, problems, design):
    lang = "hinglish" if language == "hinglish" else "english"
    profile = profile or {}
    design = design or {}

    # Validation problems.
    if problems:
        text = str(problems[0])
        fallback = (
            "Is detail ko validate nahi kar paya. Please dobara check karke batayein."
            if lang == "hinglish"
            else "I could not validate that detail. Please check it and try again."
        )
        return safe_output(text, fallback)

    # Ask for missing rainfall information.
    if gaps:
        intro = (
            "Samajh gaya. "
            if lang == "hinglish" and profile
            else ("Got it. " if profile else "")
        )
        question = next_question(lang, gaps)
        return safe_output(intro + question, question)

    # Missing rainfall data.
    if design.get("status") == "rainfall_unavailable":
        status = design.get("rainfall_status", "missing_dataset")

        hinglish_reasons = {
            "missing_dataset": "rainfall CSV missing hai ya uska schema galat hai",
            "district_not_found": "is district ka rainfall record nahi mila",
            "incomplete_data": "12 valid monthly rainfall values available nahi hain",
        }
        english_reasons = {
            "missing_dataset": "the rainfall CSV is missing or has an unexpected schema",
            "district_not_found": "no matching rainfall record was found",
            "incomplete_data": "12 valid monthly rainfall values are unavailable",
        }

        reasons = hinglish_reasons if lang == "hinglish" else english_reasons
        prefix = (
            "Rainfall estimate calculate nahi ho saka: "
            if lang == "hinglish"
            else "Rainfall estimate could not be calculated: "
        )
        text = prefix + reasons.get(status, "rainfall data unavailable") + "."

        return safe_output(text, text)

    if not design:
        text = (
            "Rainfall estimate ke liye district aur area details batayein."
            if lang == "hinglish"
            else "Please provide the district and catchment area for the rainfall estimate."
        )
        return safe_output(text, text)

    # Concise rainfall estimate.
    district = design.get("district", profile.get("district", "your district"))
    area = float(design.get("area_m2", 0))
    collectable_l = float(design.get("estimated_collectable_l", 0))
    collectable_kl = float(
        design.get("estimated_collectable_kl", collectable_l / 1000)
    )
    recommendation = str(
        design.get("recommendation", "Suitable rainwater storage system")
    )

    if lang == "hinglish":
        text = (
            f"Rainwater Estimate — {district}\n"
            f"Estimated collection: {collectable_l:,.0f} L ({collectable_kl:.2f} kL)\n"
            f"Catchment area: {area:.2f} m²\n"
            f"Recommended system: {recommendation}\n"
            + _cost_lines(design, lang)
            + "Note: Yeh planning estimate hai. Peene se pehle paani treat aur laboratory-test karein."
        )
    else:
        text = (
            f"Rainwater Estimate — {district}\n"
            f"Estimated collection: {collectable_l:,.0f} L ({collectable_kl:.2f} kL)\n"
            f"Catchment area: {area:.2f} m²\n"
            f"Recommended system: {recommendation}\n"
            + _cost_lines(design, lang)
            + "Note: This is a planning estimate. Treat and laboratory-test water before drinking."
        )

    fallback = (
        "Calculation output language validation failed; please check the project templates."
        if lang == "english"
        else "Response validation mein issue aaya; project templates check karein."
    )

    return safe_output(text, fallback)
