"""Language detection and a hard guard against Devanagari output."""
import re

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
HINGLISH_MARKERS = {
    "hai", "hain", "hu", "hoon", "mein", "me", "mera", "meri", "mere", "aap", "kya",
    "chahiye", "karna", "krna", "ke", "liye", "sinchai", "kheti", "khet", "chhat",
    "ghar", "paani", "pani", "zameen", "nahi", "nahin", "kitna", "kitni", "batao",
    "se", "par", "ka", "ki", "ko", "aur", "abhi", "hu", "raha", "rhi", "krni",
}


def detect_language(text: str, previous: str | None = None) -> str:
    """Return 'hinglish' or 'english'; explicit Roman-Hinglish markers switch language."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & HINGLISH_MARKERS:
        return "hinglish"
    if words & {"english", "please", "answer", "switch", "speak", "respond", "need", "want", "the", "for", "with", "from", "my", "your", "is", "are", "can", "could", "what", "how", "which", "district", "roof", "farm", "water", "harvesting", "irrigation", "calculate", "estimate", "subsidy"}:
        return "english"
    # Short numeric/unit-only answers inherit the conversation language.
    if previous in {"english", "hinglish"} and (not words or words <= {"sqft", "sqm", "sqft", "sqyd", "acre", "acres", "hectare", "hectares", "feet", "metres", "meters"}):
        return previous
    return "english"


def safe_output(text: str, fallback: str) -> str:
    """Never display Devanagari; use deterministic fallback if any appears."""
    return fallback if DEVANAGARI_RE.search(text or "") else (text or fallback).strip()
