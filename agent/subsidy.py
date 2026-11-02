"""Conservative subsidy lookup: only explicitly VERIFIED rows can be presented as verified."""
from agent.data import load_csv

def subsidy_status():
    df = load_csv("reference", "subsidies.csv")
    if df is None: return {"status":"missing_dataset", "message":"No subsidy dataset is available."}
    if "status" not in df.columns: return {"status":"invalid_dataset", "message":"Subsidy dataset has no status column."}
    verified = df[df["status"].astype(str).str.upper().eq("VERIFIED")]
    return {"status":"available" if not verified.empty else "no_verified_entries", "verified_count":len(verified), "source":"data/reference/subsidies.csv"}
