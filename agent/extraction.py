"""Conservative rule extraction, optionally enriched by Ollama but never dependent on it."""
from __future__ import annotations
import json, os, re
from typing import Any
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from rapidfuzz import fuzz, process
from agent.language import detect_language

DISTRICTS = ["Ajmer", "Alwar", "Banswara", "Baran", "Barmer", "Bharatpur", "Bhilwara", "Bikaner", "Bundi", "Chittaurgarh", "Churu", "Dausa", "Dholpur", "Dungarpur", "Ganganagar", "Hanumangarh", "Jaipur", "Jaiselmer", "Jalor", "Jhalawar", "Jhunjhunun", "Karauli", "Kota", "Nagaur", "Pali", "Prataapgarh", "Rajsmand", "Sikar", "Sirohi", "Swaimadhopur", "Tonk", "Udaipur", "Jodhpur"]
ALIASES = {"jalore":"Jalor", "jalor":"Jalor", "jaisalmer":"Jaiselmer", "jaiselmer":"Jaiselmer", "jhunjhunu":"Jhunjhunun", "pratapgarh":"Prataapgarh", "rajsamand":"Rajsmand", "sawai madhopur":"Swaimadhopur", "sawaimadhopur":"Swaimadhopur", "chittorgarh":"Chittaurgarh", "sri ganganagar":"Ganganagar"}
GOALS = {"irrigation": ["irrigation", "sinchai", "sinchayi", "kheti ke liye paani", "water for crops"], "drinking_water": ["drinking water", "peene ka paani", "peene ke liye", "drink water"], "household_use": ["household use", "ghar ke use", "ghar ke liye", "domestic use"], "groundwater_recharge": ["groundwater recharge", "ground water recharge", "recharge", "borewell recharge", "bhujal recharge"], "storage": ["storage", "store rainwater", "tanki", "tank", "paani store", "water storage"], "livestock": ["livestock", "cattle", "pashu", "animals ke liye"]}
UNIT_PATTERNS = [("sqft", r"square\s*feet|square\s*foot|sq\.?\s*ft|sqft|ft²|feet"), ("sqm", r"square\s*met(?:er|re)s?|sq\.?\s*m(?:eter|etre)?|sqm|m²"), ("acre", r"acres?|acre"), ("hectare", r"hectares?|ha\b"), ("sqyd", r"square\s*yards?|sq\.?\s*yd|sqyd|gaj|gaz"), ("bigha", r"bighas?|बीघा")]


def _district(text: str):
    low = text.lower()
    for alias, canonical in sorted(ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", low): return canonical
    for name in DISTRICTS:
        if re.search(rf"(?<!\w){re.escape(name.lower())}(?!\w)", low): return name
    # fuzzy matching only on short location-like phrases; avoid matching arbitrary sentences
    m = re.search(r"(?:district\s+|from\s+|in\s+|se\s+)([a-z ]{3,24})", low)
    if m:
        candidate = re.sub(r"\b(i|live|want|water|harvesting|hu|hoon|se|mein|me)\b", "", m.group(1)).strip()
        match = process.extract(candidate, DISTRICTS, scorer=fuzz.WRatio, limit=2)
        if match and match[0][1] >= 88 and (len(match) == 1 or match[0][1] - match[1][1] >= 8):
            return match[0][0]
    return None


def rule_extract(text: str) -> dict[str, Any]:
    t = text.lower().replace(",", "")
    out: dict[str, Any] = {}
    district = _district(t)
    if district: out["district"] = district
    # Goal only when there is explicit evidence; "water harvesting karna hai" is not a goal.
    for goal, phrases in GOALS.items():
        if any(p in t for p in phrases):
            out["goal"] = goal
            break
    if re.search(r"\b(farm|farmer|farming|kheti|khet|kisan|agricultural land)\b", t):
        out["property_type"] = "farm"
    elif re.search(r"\b(ghar|house|home|household)\b", t): out["property_type"] = "household"
    elif re.search(r"\b(plot|landowner|zameen|jameen|land)\b", t): out["property_type"] = "land"
    # Property/catchment corrections should remove incompatible roof assumptions at merge time.
    if re.search(r"\b(chhat|chat|roof|rooftop|terrace)\b", t): out["catchment_type"] = "roof"
    elif re.search(r"\b(khet|kheti|farm|field|open land|zameen|plot)\b", t): out["catchment_type"] = "land"
    # Area with explicit unit; unitless area is kept pending for a follow-up.
    unit_regex = "|".join(f"(?:{p})" for _, p in UNIT_PATTERNS)
    area_match = re.search(rf"(\d+(?:\.\d+)?)\s*({unit_regex})", t)
    if area_match:
        unit_text = area_match.group(2)
        unit = next((u for u, p in UNIT_PATTERNS if re.fullmatch(p, unit_text)), None)
        before = t[max(0, area_match.start()-35):area_match.start()]
        key = "catchment_area" if re.search(r"chhat|chat|roof|rooftop|terrace", before) or out.get("catchment_type") == "roof" else "land_area"
        out[key] = float(area_match.group(1)); out[key + "_unit"] = unit
    else:
        unitless = re.search(r"(?:chhat|chat|roof|rooftop|terrace|area|zameen|land|plot)\D{0,12}(\d+(?:\.\d+)?)\b", t)
        if unitless:
            key = "catchment_area" if out.get("catchment_type") == "roof" else "land_area"
            out[key] = float(unitless.group(1))
    # Unit-only answer for a pending area question.
    if not re.search(r"\d", t) and len(t.split()) <= 5:
        for unit, pattern in UNIT_PATTERNS:
            if re.search(pattern, t): out["bare_area_unit"] = unit; break
    people = re.search(r"\b(\d{1,3})\s*(?:people|persons|members|log|family members)\b", t)
    if people: out["people"] = int(people.group(1))
    demand = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:litres?|liters?|l)\s*(?:per day|daily|/day|roz)\b", t)
    if demand: out["water_demand_l_day"] = float(demand.group(1))
    if re.search(r"\b(nahi|nahin|nhi|no)\b.{0,15}\b(ghar|roof|chhat)\b|\bnot\s+(?:a\s+)?(?:house|home|roof)\b", t):
        out["catchment_type"] = "land"; out["property_type"] = "farm" if re.search(r"khet|farm|kheti", t) else "land"
        out["remove_roof"] = True
    if re.search(r"\b(concrete|cement|rcc|slab|pakka)\b", t): out["roof_type"] = "concrete"
    elif re.search(r"\b(metal|tin|sheet)\b", t): out["roof_type"] = "metal"
    elif re.search(r"\b(tile|tiles|khapra)\b", t): out["roof_type"] = "tiles"
    # Natural-language pond dimensions/rates are optional; the advisor can estimate them from rainfall/land when absent.
    dimension_patterns = {
        "pond_length_m": r"(?:length|lambai|lamba)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:m|metre|meter|metres|meters)?",
        "pond_width_m": r"(?:width|chaudai|chauda)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:m|metre|meter|metres|meters)?",
        "pond_depth_m": r"(?:depth|gehrai|gahrayi)\s*(?:is|hai|of|=|:)?\s*(\d+(?:\.\d+)?)\s*(?:m|metre|meter|metres|meters)?",
    }
    for field, pattern in dimension_patterns.items():
        match = re.search(pattern, t)
        if match: out[field] = float(match.group(1))
    rate_match = re.search(r"(?:construction\s*)?(?:rate|cost|dar)\s*(?:is|hai|of|=|:)?\s*(?:rs\.?|inr|₹)?\s*(\d+(?:\.\d+)?)\s*(?:rupees?\s*)?(?:per\s*(?:cubic\s*met(?:er|re)|m3|m³)|/\s*m3|/\s*m³)", t)
    if rate_match: out["construction_rate_per_m3"] = float(rate_match.group(1))
    if re.search(r"\b(lined|plastic[- ]lined|lining)\b", t): out["pond_type"] = "lined"
    elif re.search(r"\b(unlined|raw pond|without lining)\b", t): out["pond_type"] = "unlined"
    if re.search(r"\b(subsidy|subsidies|scheme|yojana)\b", t): out["asks_subsidy"] = True
    return out


def extract_details(text: str) -> dict[str, Any]:
    """Deterministic extraction is the fallback and source of truth; Ollama is optional."""
    result = rule_extract(text)
    if os.getenv("USE_MODEL", "1") != "1": return result
    try:
        from langchain_ollama import ChatOllama
        from pydantic import BaseModel, Field
        class Extracted(BaseModel):
            goal: str | None = None
            property_type: str | None = None
            catchment_type: str | None = None
            roof_type: str | None = None
        llm = ChatOllama(model=os.getenv("RAIN_MODEL", "qwen2.5:3b"), base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"), temperature=0, timeout=12)
        structured = llm.with_structured_output(Extracted)
        model_data = structured.invoke("Extract only explicitly stated fields from this message. Allowed goal values: irrigation, drinking_water, household_use, groundwater_recharge, storage, livestock. Allowed property_type: household, farm, land. catchment_type: roof, land. roof_type: concrete, metal, tiles, asbestos. Never infer a goal from generic rainwater harvesting. Message: " + text)
        allowed = {"goal": {"irrigation","drinking_water","household_use","groundwater_recharge","storage","livestock"}, "property_type":{"household","farm","land"}, "catchment_type":{"roof","land"}, "roof_type":{"concrete","metal","tiles","asbestos"}}
        for key, value in model_data.model_dump(exclude_none=True).items():
            if value in allowed.get(key, set()) and (key in result or value in text.lower()): result[key] = value
    except Exception:
        pass
    return result
