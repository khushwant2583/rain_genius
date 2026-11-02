"""Pandas-backed dataset access. Missing or malformed datasets are reported, never fabricated."""
import os
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("RAIN_DATA_DIR", ROOT / "data"))

def load_csv(*parts):
    # Resolve on each call so tests and separate deployments can change RAIN_DATA_DIR safely.
    data_dir = Path(os.environ.get("RAIN_DATA_DIR", ROOT / "data"))
    path = data_dir.joinpath(*parts)
    if not path.exists(): return None
    try: return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, UnicodeDecodeError): return None

def annual_rainfall_mm(district: str):
    """Return annualized monthly-average total only for a complete 12-month district record."""
    df = load_csv("processed", "monthly_rainfall_by_district.csv")
    if df is None or not {"district", "month", "avg_rainfall_mm"}.issubset(df.columns):
        return {"status":"missing_dataset", "rainfall_mm":None, "source":None}
    subset = df[df["district"].astype(str).str.strip().str.casefold() == district.casefold()].copy()
    if subset.empty: return {"status":"district_not_found", "rainfall_mm":None, "source":None}
    subset["month"] = pd.to_numeric(subset["month"], errors="coerce")
    subset["avg_rainfall_mm"] = pd.to_numeric(subset["avg_rainfall_mm"], errors="coerce")
    subset = subset.dropna(subset=["month", "avg_rainfall_mm"])
    subset = subset[(subset.month >= 1) & (subset.month <= 12) & (subset.avg_rainfall_mm >= 0)]
    if subset.month.nunique() != 12 or subset.month.duplicated().any():
        return {"status":"incomplete_data", "rainfall_mm":None, "source":None}
    # Values are monthly averages in the included local table; metadata/source provenance needs confirmation.
    return {"status":"available", "rainfall_mm":float(subset.avg_rainfall_mm.sum()), "source":"data/processed/monthly_rainfall_by_district.csv", "period":"sum of 12 monthly average values", "provenance_verified":False}
