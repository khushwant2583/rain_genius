"""
make_monthly_nasa.py - builds data/processed/monthly_rainfall_by_district.csv

Why: the IMD daily file only covers about 8 weeks of one year, so it cannot give monthly averages.
NASA POWER gives satellite-and-model rainfall estimates for any coordinates, for many years, free.

Run from the project root (needs internet):
    python -m scripts.make_monthly_nasa
    python -m scripts.make_monthly_nasa --start 2015 --end 2024

Input : data/reference/district_coords.csv   (district, lat, lon)
Output: data/processed/monthly_rainfall_by_district.csv   (district, month, avg_rainfall_mm)

Then run:  python -m scripts.check_data

Say in your report: these are NASA POWER (PRECTOTCORR) estimates averaged over the years used.
They are not station measurements, so they can differ from IMD by some percent.
"""
import argparse
import calendar
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402
import requests  # noqa: E402

from agent import data  # noqa: E402

URL = "https://power.larc.nasa.gov/api/temporal/monthly/point"


def parse_monthly(response_json):
    """
    NASA gives mm PER DAY for each month, keyed like "201507" (and "201513" for the whole year).
    Returns 12 averages in mm PER MONTH (mm/day x days in that month, averaged over the years).
    """
    values = response_json["properties"]["parameter"]["PRECTOTCORR"]
    per_month = {m: [] for m in range(1, 13)}
    for key, mm_per_day in values.items():
        year, month = int(key[:4]), int(key[4:])
        if not 1 <= month <= 12:
            continue                                   # skip the yearly "13" entry
        if mm_per_day is None or mm_per_day < 0:
            continue                                   # NASA marks missing data as -999
        per_month[month].append(mm_per_day * calendar.monthrange(year, month)[1])
    if any(len(v) == 0 for v in per_month.values()):
        raise ValueError("some months have no data")
    return [round(sum(v) / len(v), 1) for v in per_month.values()]


def fetch(lat, lon, start, end, tries=3):
    params = {"parameters": "PRECTOTCORR", "community": "AG", "latitude": lat,
              "longitude": lon, "start": start, "end": end, "format": "JSON"}
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(URL, params=params, timeout=60)
            r.raise_for_status()
            return parse_monthly(r.json())
        except Exception as e:                         # network error, bad reply, missing months
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2015)
    ap.add_argument("--end", type=int, default=2024)
    args = ap.parse_args()

    coords = data.load_csv("reference", "district_coords.csv")
    if coords is None:
        sys.exit("data/reference/district_coords.csv not found")

    rows, failed = [], []
    for _, r in coords.iterrows():
        try:
            monthly = fetch(r["lat"], r["lon"], args.start, args.end)
        except Exception as e:
            failed.append(r["district"])
            print(f"  FAILED {r['district']}: {e}")
            continue
        rows += [(r["district"], m + 1, v) for m, v in enumerate(monthly)]
        print(f"  ok  {r['district']:14} yearly total {sum(monthly):7.0f} mm")

    if not rows:
        sys.exit("Nothing downloaded. Check your internet connection and try again.")
    out = data.DATA_DIR / "processed" / "monthly_rainfall_by_district.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=["district", "month", "avg_rainfall_mm"]).to_csv(out, index=False)
    print(f"\nSaved {out}  ({len(rows) // 12} districts, years {args.start}-{args.end})")
    if failed:
        print("Districts that failed, rerun to retry:", ", ".join(failed))
    print("Next: python -m scripts.check_data")


if __name__ == "__main__":
    main()
