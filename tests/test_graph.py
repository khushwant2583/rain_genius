import pytest
pytest.importorskip("langgraph")
from agent.graph import chat

def test_multiturn_regression():
    thread="test-regression-jalore"
    a=chat("jalore se hu water harvesting krna hai",thread)
    assert "sinchai" in a["reply"].lower() or "purpose" in a["reply"].lower()
    b=chat("sinchai k liye",thread)
    assert b["profile"]["district"] == "Jalor" and b["profile"]["goal"] == "irrigation"
    assert "district" not in (b.get("missing_fields") or []) and "goal" not in (b.get("missing_fields") or [])
    assert "chhat" in b["reply"].lower() or "roof" in b["reply"].lower() or "catchment" in b["reply"].lower()
    assert not any(0x0900 <= ord(c) <= 0x097F for c in b["reply"])

def test_roof_area_context():
    thread="test-roof-context"
    chat("Jalore se hu",thread); chat("sinchai ke liye",thread); chat("ghar ki chhat hai",thread)
    r=chat("1000 sqft",thread)
    assert r["profile"].get("catchment_area_m2") is not None
