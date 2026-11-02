"""Compatibility facade for older scripts; the primary workflow lives in agent.graph."""
from agent.extraction import extract_details, rule_extract
from agent.language import detect_language
from agent.profile import merge_profile, missing_fields
from agent.design import design_system
from agent.response import make_response

def chat_turn(user_text, messages, profile, store):
    """Backward-compatible one-turn helper. New integrations should call agent.graph.chat."""
    details = extract_details(user_text)
    language = detect_language(user_text, store.get("language"))
    store["language"] = language
    updated, problems = merge_profile(profile, details)
    profile.clear(); profile.update(updated)
    gaps = missing_fields(profile)
    design = {}
    if not problems and not gaps:
        design = design_system(profile)
        store["design"] = design
    reply = make_response(language, profile, gaps, problems, design)
    messages.extend([{"role":"user", "content":user_text}, {"role":"assistant", "content":reply}])
    return reply
