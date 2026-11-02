"""LangGraph controls the real extraction -> merge -> route -> design -> response workflow."""
from langgraph.graph import StateGraph, START, END
from agent.state import RainState
from agent.language import detect_language
from agent.extraction import extract_details
from agent.profile import merge_profile, missing_fields
from agent.design import design_system
from agent.response import make_response


def receive_user_message(state: RainState) -> dict:
    return {"user_text": str(state.get("user_text", "")).strip()}

def detect_and_extract(state: RainState) -> dict:
    store = dict(state.get("store") or {})
    language = detect_language(state.get("user_text", ""), store.get("language"))
    store["language"] = language
    details = extract_details(state.get("user_text", ""))
    # If a bare area follows an earlier roof/land declaration, bind it to that known catchment.
    profile = state.get("profile") or {}
    text_low = state.get("user_text", "").lower()
    has_roof_word = any(w in text_low for w in ("roof", "rooftop", "chhat", "chat", "terrace"))
    has_land_word = any(w in text_low for w in ("land", "field", "farm", "khet", "kheti", "zameen", "plot"))
    if not has_roof_word and not has_land_word and profile.get("catchment_type") == "roof" and "land_area" in details:
        details["catchment_area"] = details.pop("land_area")
        if "land_area_unit" in details: details["catchment_area_unit"] = details.pop("land_area_unit")
    elif not has_roof_word and not has_land_word and profile.get("catchment_type") == "land" and "catchment_area" in details:
        details["land_area"] = details.pop("catchment_area")
        if "catchment_area_unit" in details: details["land_area_unit"] = details.pop("catchment_area_unit")
    # Attach a unit-only response to the last unresolved area field.
    pending = store.get("pending_area")
    if details.get("bare_area_unit") and pending:
        details[pending] = store.pop("pending_value", None)
        details[pending + "_unit"] = details.pop("bare_area_unit")
        store.pop("pending_area", None)
        details = {k:v for k,v in details.items() if v is not None}
    for key in ("catchment_area", "land_area"):
        if key in details and details.get(key + "_unit") not in {"sqft", "sqm", "sqyd", "acre", "hectare"}:
            store["pending_area"] = key
            store["pending_value"] = details[key]
    return {"extracted": details, "language": language, "store": store}

def merge_and_assess(state: RainState) -> dict:
    profile, problems = merge_profile(dict(state.get("profile") or {}), dict(state.get("extracted") or {}))
    # Unitless values stay pending and are not silently converted.
    store = dict(state.get("store") or {})
    gaps = missing_fields(profile)
    if store.get("pending_area"):
        pending_gap = store["pending_area"] + "_unit"
        gaps = [pending_gap]
    return {"profile": profile, "problems": problems, "missing_fields": gaps, "design": {}}

def route_after_assessment(state: RainState) -> str:
    return "respond" if state.get("problems") or state.get("missing_fields") else "design"

def calculate_node(state: RainState) -> dict:
    try: design = design_system(state["profile"])
    except Exception as exc: design = {"status":"calculation_error", "message":type(exc).__name__}
    return {"design": design}

def respond_node(state: RainState) -> dict:
    reply = make_response(state.get("language", "english"), state.get("profile", {}), state.get("missing_fields", []), state.get("problems", []), state.get("design", {}))
    # Hard output guard: make_response also guards, but this is the final boundary.
    from agent.language import safe_output
    fallback = "Please tell me the missing detail in English or Roman Hinglish."
    reply = safe_output(reply, fallback)
    messages = list(state.get("messages") or [])
    messages.extend([{"role":"user", "content":state.get("user_text", "")}, {"role":"assistant", "content":reply}])
    store = dict(state.get("store") or {})
    store["last_question"] = state.get("missing_fields", [None])[0] if state.get("missing_fields") else None
    return {"reply":reply, "messages":messages, "store":store}

_builder = StateGraph(RainState)
_builder.add_node("receive_user_message", receive_user_message)
_builder.add_node("detect_language_and_extract", detect_and_extract)
_builder.add_node("merge_profile_and_assess", merge_and_assess)
_builder.add_node("calculate_harvesting_potential", calculate_node)
_builder.add_node("respond_to_user", respond_node)
_builder.add_edge(START, "receive_user_message")
_builder.add_edge("receive_user_message", "detect_language_and_extract")
_builder.add_edge("detect_language_and_extract", "merge_profile_and_assess")
_builder.add_conditional_edges("merge_profile_and_assess", route_after_assessment, {"respond":"respond_to_user", "design":"calculate_harvesting_potential"})
_builder.add_edge("calculate_harvesting_potential", "respond_to_user")
_builder.add_edge("respond_to_user", END)
try:
    from langgraph.checkpoint.memory import MemorySaver
    graph = _builder.compile(checkpointer=MemorySaver())
except ImportError:
    graph = _builder.compile()

def chat(user_text: str, thread_id: str = "local-user") -> dict:
    """One turn. MemorySaver retains state for thread_id while the process runs."""
    return graph.invoke({"user_text":user_text}, config={"configurable":{"thread_id":thread_id}})
