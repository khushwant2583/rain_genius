from agent.profile import merge_profile, missing_fields, AREA_TO_M2

def test_preserve_district_across_turns():
    p,_=merge_profile({}, {"district":"Jalore"}); p,_=merge_profile(p,{"goal":"irrigation"})
    assert p["district"] == "Jalor" and p["goal"] == "irrigation"

def test_correction_goal_and_roof_removal():
    p,_=merge_profile({}, {"district":"Jalore","goal":"irrigation","catchment_type":"roof","catchment_area":1000,"catchment_area_unit":"sqft"})
    p,_=merge_profile(p,{"goal":"drinking_water"})
    p,_=merge_profile(p,{"catchment_type":"land","remove_roof":True})
    assert p["goal"] == "drinking_water" and p["catchment_type"] == "land" and "catchment_area_m2" not in p

def test_sqft_conversion():
    p,_=merge_profile({}, {"catchment_type":"roof","catchment_area":1000,"catchment_area_unit":"sqft"})
    assert abs(p["catchment_area_m2"] - 92.90304) < .001

def test_bigha_not_guessed(): assert "bigha" not in AREA_TO_M2

def test_goal_followup_not_repeat_district(): assert missing_fields({"district":"Jalor"}) == ["goal"]


def test_ambiguous_or_unknown_district_is_not_guessed():
    from agent.profile import match_district
    assert match_district("not a real district") is None
