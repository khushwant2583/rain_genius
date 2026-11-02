"""Validated profile merging, unit conversion, and required-field assessment."""
from __future__ import annotations
from typing import Any
from agent.extraction import DISTRICTS, ALIASES
from rapidfuzz import process, fuzz

# Explicit conversions; bigha is intentionally not included because its size varies by region.
AREA_TO_M2 = {"sqm": 1.0, "sqft": 0.09290304, "sqyd": 0.83612736, "acre": 4046.8564224, "hectare": 10000.0}
GOALS = {"irrigation", "drinking_water", "household_use", "groundwater_recharge", "storage", "livestock"}

def match_district(value: str) -> str | None:
    v = value.strip().lower()
    if v in ALIASES: return ALIASES[v]
    for district in DISTRICTS:
        if v == district.lower(): return district
    results = process.extract(v, DISTRICTS, scorer=fuzz.WRatio, limit=2)
    if not results or results[0][1] < 88: return None
    if len(results) > 1 and results[0][1] - results[1][1] < 8: return None
    return results[0][0]

def merge_profile(profile: dict[str, Any], details: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Update only fields present in details; explicit corrections replace previous values."""
    p = dict(profile); problems: list[str] = []
    if details.get("district"):
        matched = match_district(str(details["district"]))
        if matched: p["district"] = matched
        else: problems.append("I could not confidently match that district. Please type the district name again.")
    if details.get("goal") in GOALS: p["goal"] = details["goal"]
    if details.get("property_type") in {"household", "farm", "land"}: p["property_type"] = details["property_type"]
    if details.get("catchment_type") in {"roof", "land"}:
        p["catchment_type"] = details["catchment_type"]
        if details["catchment_type"] == "land" or details.get("remove_roof"):
            p.pop("catchment_area_m2", None); p.pop("catchment_area", None); p.pop("catchment_area_unit", None); p.pop("roof_type", None)
        elif details["catchment_type"] == "roof":
            p.pop("land_area_m2", None); p.pop("land_area", None); p.pop("land_area_unit", None)
    if details.get("remove_roof"):
        p.pop("catchment_area_m2", None); p.pop("roof_type", None)
    for key in ("catchment_area", "land_area"):
        if key not in details: continue
        try: value = float(details[key])
        except (TypeError, ValueError): problems.append("Area must be a number."); continue
        unit = details.get(key + "_unit")
        if not unit:
            p[key] = value; p[key + "_unit"] = None
            continue
        if unit not in AREA_TO_M2:
            p[key] = value; p[key + "_unit"] = unit
            continue
        if not 0 < value <= 1_000_000:
            problems.append("Area must be greater than zero and within a reasonable range."); continue
        p[key] = value; p[key + "_unit"] = unit; p[key + "_m2"] = value * AREA_TO_M2[unit]
    if details.get("bare_area_unit"):
        for key in ("catchment_area", "land_area"):
            if key in p and p.get(key + "_unit") is None:
                unit = details["bare_area_unit"]
                if unit in AREA_TO_M2:
                    p[key + "_unit"] = unit; p[key + "_m2"] = p[key] * AREA_TO_M2[unit]
                break
    if details.get("roof_type") in {"concrete", "metal", "tiles", "asbestos"}: p["roof_type"] = details["roof_type"]
    if "people" in details and 1 <= int(details["people"]) <= 100: p["people"] = int(details["people"])
    if "water_demand_l_day" in details and 0 < float(details["water_demand_l_day"]) <= 100000: p["water_demand_l_day"] = float(details["water_demand_l_day"])
    for key in ("pond_length_m", "pond_width_m", "pond_depth_m", "construction_rate_per_m3"):
        if key in details:
            try:
                value = float(details[key])
                if value > 0: p[key] = value
                else: problems.append(f"{key} must be greater than zero.")
            except (TypeError, ValueError):
                problems.append(f"{key} must be a number.")
    if details.get("pond_type") in {"lined", "unlined"}: p["pond_type"] = details["pond_type"]
    if details.get("asks_subsidy"): p["asks_subsidy"] = True
    return p, problems

def missing_fields(profile: dict[str, Any]) -> list[str]:
    if not profile.get("district"): return ["district"]
    if not profile.get("goal"):
        # Sensible first-pass default; user can override with an explicit purpose later.
        if profile.get("catchment_type") == "roof": profile["goal"] = "household_use"
        elif profile.get("catchment_type") == "land" and profile.get("property_type") == "farm": profile["goal"] = "irrigation"
        else: return ["goal"]
    # Catchment type is more actionable than asking household/farmer classification first.
    if not profile.get("catchment_type"): return ["catchment_type"]
    if profile.get("goal") == "irrigation" or profile.get("goal") == "groundwater_recharge":
        if profile.get("catchment_type") is None: return ["catchment_type"]
        key = "catchment_area_m2" if profile.get("catchment_type") == "roof" else "land_area_m2"
        raw = "catchment_area" if profile.get("catchment_type") == "roof" else "land_area"
        if profile.get(key) is None:
            if profile.get(raw) is not None and profile.get(raw + "_unit") is None: return [raw + "_unit"]
            if profile.get(raw + "_unit") not in (None, *AREA_TO_M2.keys()): return [raw + "_unit"]
            return [raw]
        if profile.get("catchment_type") == "roof" and not profile.get("roof_type"): return ["roof_type"]
    else:
        if profile.get("catchment_type") is None: return ["catchment_type"]
        key = "catchment_area_m2" if profile.get("catchment_type") == "roof" else "land_area_m2"
        raw = "catchment_area" if profile.get("catchment_type") == "roof" else "land_area"
        if profile.get(key) is None:
            if profile.get(raw) is not None and profile.get(raw + "_unit") is None: return [raw + "_unit"]
            if profile.get(raw + "_unit") not in (None, *AREA_TO_M2.keys()): return [raw + "_unit"]
            return [raw]
        if profile.get("catchment_type") == "roof" and not profile.get("roof_type"): return ["roof_type"]
    return []
