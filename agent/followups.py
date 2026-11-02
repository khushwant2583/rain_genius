"""Deterministic one-question-at-a-time follow-up selection."""
QUESTIONS = {
 "english": {
  "district":"Which district in Rajasthan is the property located in?",
  "goal":"What is your main purpose: irrigation, household use, drinking water, groundwater recharge, or livestock?",
  "property_type":"Is this for a household, a farm, or another plot of land?",
  "catchment_type":"Do you have a roof catchment, open land/field, or both? Which one should we calculate first?",
  "catchment_area":"What is the approximate roof/catchment area? Please include the unit, such as square feet or square metres.",
  "land_area":"What is the approximate open land/field area? Please include the unit, such as acres or hectares.",
  "catchment_area_unit":"Bigha varies by region. Can you give the roof/catchment area in square feet, square metres, acres, or hectares?",
  "land_area_unit":"Bigha varies by region. Can you give the area in square feet, square metres, acres, or hectares?",
  "roof_type":"What is the roof material: concrete/RCC, metal sheet, or tiles?",
 },
 "hinglish": {
  "district":"Aapki property Rajasthan ke kis district mein hai?",
  "goal":"Rainwater harvesting kis purpose ke liye chahiye — sinchai, ghar ke use, drinking water, groundwater recharge, ya livestock?",
  "property_type":"Ye household ke liye hai, kheti ke liye, ya kisi aur plot ke liye?",
  "catchment_type":"Aapke paas chhat hai, khuli zameen/khet hai, ya dono? Pehle kis area ka estimate karein?",
  "catchment_area":"Chhat/catchment ka approximate area kitna hai? Unit bhi batayein, jaise square feet ya square metre.",
  "land_area":"Khet/khuli zameen ka approximate area kitna hai? Unit bhi batayein, jaise acre ya hectare.",
  "catchment_area_unit":"Bigha ka size region ke hisaab se badalta hai. Kya aap chhat ka area square feet, square metre, acre, ya hectare mein bata sakte ho?",
  "land_area_unit":"Bigha ka size region ke hisaab se badalta hai. Kya aap area square feet, square metre, acre, ya hectare mein bata sakte ho?",
  "roof_type":"Chhat kis material ki hai — concrete/RCC, metal sheet, ya tiles?",
 }
}

def next_question(language: str, gaps: list[str]) -> str:
    lang = "hinglish" if language == "hinglish" else "english"
    return QUESTIONS[lang].get(gaps[0], QUESTIONS[lang]["goal"]) if gaps else ""
