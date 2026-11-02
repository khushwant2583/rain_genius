from agent.language import detect_language, safe_output

def test_english(): assert detect_language("I need rainwater harvesting for irrigation") == "english"
def test_hinglish(): assert detect_language("sinchai k liye") == "hinglish"
def test_mixed_english_hinglish(): assert detect_language("I need water for kheti") == "hinglish"
def test_unit_answer_remembers_language(): assert detect_language("1000 sqft", "hinglish") == "hinglish"
def test_language_switches_to_english(): assert detect_language("Please answer in English", "hinglish") == "english"
def test_devanagari_guard(): assert safe_output("आपका जवाब", "Fallback") == "Fallback"
