"""Deterministic rainwater estimates and preliminary option recommendations."""
import os
import math
import pandas as pd
from agent.data import annual_rainfall_mm, load_csv

COEFFICIENTS = {"concrete": 0.80, "metal": 0.90, "tiles": 0.75, "asbestos": 0.75, "land": 0.20}

def calculate_harvestable_water(rainfall_mm: float, area_m2: float, runoff_coefficient: float, efficiency: float = 0.9) -> dict:
    for name, value in (("rainfall_mm", rainfall_mm), ("area_m2", area_m2), ("runoff_coefficient", runoff_coefficient), ("efficiency", efficiency)):
        if value < 0: raise ValueError(f"{name} cannot be negative")
    if area_m2 <= 0: raise ValueError("area_m2 must be greater than zero")
    if not 0 <= runoff_coefficient <= 1 or not 0 <= efficiency <= 1: raise ValueError("coefficients must be between 0 and 1")
    theoretical = rainfall_mm * area_m2 * runoff_coefficient
    collectable = theoretical * efficiency
    return {"rainfall_mm": rainfall_mm, "area_m2": area_m2, "runoff_coefficient": runoff_coefficient, "collection_efficiency": efficiency, "theoretical_runoff_l": round(theoretical), "estimated_collectable_l": round(collectable), "estimated_collectable_kl": round(collectable / 1000, 2)}

def design_system(profile: dict) -> dict:
    district = profile["district"]
    rain = annual_rainfall_mm(district)
    if rain["status"] != "available": return {"status":"rainfall_unavailable", "rainfall_status":rain["status"], "district":district}
    catchment = profile.get("catchment_type")
    area = profile.get("catchment_area_m2") if catchment == "roof" else profile.get("land_area_m2")
    surface = profile.get("roof_type") if catchment == "roof" else "land"
    coefficient = COEFFICIENTS.get(surface, COEFFICIENTS["land"])
    efficiency = float(os.getenv("RAIN_COLLECTION_EFFICIENCY", "0.9"))
    result = calculate_harvestable_water(rain["rainfall_mm"], area, coefficient, efficiency)
    goal = profile["goal"]
    if goal == "groundwater_recharge": option = "A filtered recharge trench or pit may be explored after a site and groundwater-quality assessment."
    elif goal == "irrigation" and catchment == "roof": option = "A covered tank can capture roof runoff for non-potable irrigation; compare the seasonal collection estimate with crop demand before sizing storage."
    elif goal == "irrigation": option = "Compare a lined/unlined farm pond only after checking catchment, soil, land rights, evaporation, and irrigation demand."
    elif goal == "drinking_water": option = "A covered storage tank with first-flush diversion and filtration may be considered; treat and test water before drinking."
    elif goal == "livestock": option = "A covered storage tank or trough supplied from a filtered collection system may be considered."
    else: option = "A covered storage tank with roof gutters, leaf screen, first-flush diversion, and filtration may be considered."
    result.update({"status":"estimate_available", "district":district, "goal":goal, "recommendation":option, "rainfall_period":rain.get("period"), "rainfall_source":rain.get("source"), "rainfall_provenance_verified":rain.get("provenance_verified",False), "notes":["This is a planning estimate, not a guarantee of usable water.", "The local rainfall table's source/version is not verified; confirm its provenance before relying on the number.", "Actual yield is reduced by first-flush diversion, leaks, evaporation, overflow, and storage limits."]})
    # Cost ranges are read from the project's costs.csv, not hard-coded in the response.
    costs = load_csv("reference", "costs.csv")
    if costs is not None and not costs.empty:
        costs.columns = [str(c).strip().lower() for c in costs.columns]
        def cost_range(item, quantity):
            rows = costs[costs["item"].astype(str).str.lower().eq(item)]
            if rows.empty or quantity <= 0: return None
            row = rows.iloc[0]
            return {"item": item, "quantity": round(quantity, 2), "unit": str(row["unit"]),
                    "low_inr": round(float(row["low_inr"]) * quantity),
                    "high_inr": round(float(row["high_inr"]) * quantity),
                    "source": str(row.get("source", ""))}
        if catchment == "roof":
            # Annual collected volume is a preliminary storage sizing proxy, not a final tank design.
            tank_units = max(1, math.ceil(result["estimated_collectable_l"] / 1000))
            result["cost_estimates"] = [cost_range("storage_tank", tank_units), cost_range("filter_firstflush", 1), cost_range("plumbing", 1)]
            result["cost_estimates"] = [x for x in result["cost_estimates"] if x]
        elif goal == "irrigation":
            pond_m3 = max(0, result["estimated_collectable_l"] / 1000)
            length = profile.get("pond_length_m")
            width = profile.get("pond_width_m")
            depth = profile.get("pond_depth_m")
            explicit_dimensions = all(isinstance(v, (int, float)) and v > 0 for v in (length, width, depth))
            if explicit_dimensions:
                pond_m3 = float(length) * float(width) * float(depth)
            item = "farm_pond_lined" if profile.get("pond_type") == "lined" else "farm_pond"
            result["estimated_pond_volume_m3"] = round(pond_m3, 2)
            rate = profile.get("construction_rate_per_m3")
            if explicit_dimensions and isinstance(rate, (int, float)) and rate > 0:
                result["cost_estimates"] = [{"item": item, "quantity": round(pond_m3, 2), "unit": "per_m3 (user-provided rate)", "low_inr": round(pond_m3 * rate), "high_inr": round(pond_m3 * rate), "source": "User-provided construction rate"}]
            else:
                result["cost_estimates"] = [cost_range(item, pond_m3)] if pond_m3 > 0 else []
            result["cost_estimates"] = [x for x in result["cost_estimates"] if x]
            # Subsidy is only estimated for farm ponds; eligibility remains conditional.
            if pond_m3 >= 400 and profile.get("land_area_m2", 0) >= 3000:
                cap = 90000 if item == "farm_pond_lined" else 63000
                if result.get("cost_estimates"):
                    estimate = result["cost_estimates"][0]
                    result["subsidy_estimate"] = {"percent": 60, "cap_inr": cap,
                        "low_subsidy_inr": min(estimate["low_inr"] * .60, cap),
                        "high_subsidy_inr": min(estimate["high_inr"] * .60, cap),
                        "low_remaining_inr": max(0, estimate["low_inr"] - min(estimate["low_inr"] * .60, cap)),
                        "high_remaining_inr": max(0, estimate["high_inr"] - min(estimate["high_inr"] * .60, cap)),
                        "eligibility_note": "Preliminary only; confirm landholding, eligible-cost rules, current funding and approval before construction."}
            elif goal == "irrigation":
                result["subsidy_estimate"] = {"status":"eligibility_not_established", "message":"A subsidy estimate is not shown because the preliminary pond capacity or landholding threshold is not met/known."}
    if goal == "drinking_water": result["notes"].append("Do not drink harvested water until it has been appropriately treated and laboratory-tested.")
    return result
