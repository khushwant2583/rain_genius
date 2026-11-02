"""Typed state passed between LangGraph nodes."""
from typing import Any, TypedDict
class RainState(TypedDict, total=False):
    user_text: str
    profile: dict[str, Any]
    store: dict[str, Any]
    extracted: dict[str, Any]
    problems: list[str]
    missing_fields: list[str]
    design: dict[str, Any]
    language: str
    reply: str
    messages: list[dict[str, str]]
