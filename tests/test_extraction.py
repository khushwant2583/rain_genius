from agent.extraction import rule_extract

def test_jalore_does_not_infer_goal():
    x = rule_extract("jalore se hu water harvesting krna hai")
    assert x["district"] == "Jalor" and "goal" not in x

def test_sinchai(): assert rule_extract("sinchai k liye")["goal"] == "irrigation"
def test_roof_area():
    x = rule_extract("mere ghar ki chhat 1200 square feet hai")
    assert x["catchment_type"] == "roof" and x["catchment_area"] == 1200 and x["catchment_area_unit"] == "sqft"
def test_drinking_correction(): assert rule_extract("actually drinking water ke liye chahiye")["goal"] == "drinking_water"
def test_domain_word_not_name(): assert "name" not in rule_extract("ghar ki chhat 1000 sqft hai")
def test_multiple_details():
    x=rule_extract("Jodhpur me kheti hai, sinchai ke liye 2 acres land")
    assert x["district"] == "Jodhpur" and x["goal"] == "irrigation" and x["land_area"] == 2


def test_bigha_is_recognized_but_not_converted():
    x = rule_extract("mere khet ka area 2 bigha hai")
    assert x.get("land_area") == 2 and x.get("land_area_unit") == "bigha"
