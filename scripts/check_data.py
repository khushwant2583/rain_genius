"""
check_data.py - checks every data file the project uses and prints PASS / WARN / FAIL.

Run from the project root:   python -m scripts.check_data
Exit code is 1 if anything FAILS, so you can also use it before a demo.

Files checked (a missing optional file is reported as SKIP, not an error):
  data/processed/rainfall_daily.csv                 IMD daily rainfall (cleaned)
  data/processed/monthly_rainfall_by_district.csv   12 monthly values per district (the advisor needs this)
  data/processed/district_soil.csv                  optional
  data/processed/district_groundwater.csv           optional
  data/reference/runoff_coefficients.csv, costs.csv, subsidies.csv, district_coords.csv
"""
import calendar
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from agent import data  # noqa: E402
from agent.profile import FALLBACK_DISTRICTS  # noqa: E402

results = []


def report(status, name, detail=""):
    results.append(status)
    print(f"  [{status:4}] {name}" + (f": {detail}" if detail else ""))


def section(title):
    print(f"\n== {title} ==")


def names(df, col="district"):
    return set(df[col].astype(str).str.strip().str.title())


# ---------------------------------------------------------------- 1. IMD daily file
def check_daily():
    section("1. IMD daily rainfall  (data/processed/rainfall_daily.csv)")
    df = data.load_csv("processed", "rainfall_daily.csv")
    if df is None:
        return report("SKIP", "file not found")
    need = {"date", "district", "rainfall_mm"}
    if need - set(df.columns):
        return report("FAIL", "columns", f"missing {sorted(need - set(df.columns))}")
    report("PASS", "columns present")

    iso = df["date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}").all()      # 2026-08-19 vs 19-08-2026
    df["date"] = pd.to_datetime(df["date"], errors="coerce", dayfirst=not iso)
    df["rainfall_mm"] = pd.to_numeric(df["rainfall_mm"], errors="coerce")
    bad = int(df[["date", "district", "rainfall_mm"]].isna().any(axis=1).sum())
    report("PASS" if bad == 0 else "WARN", "missing or unreadable values", f"{bad} rows")
    df = df.dropna(subset=["date", "district", "rainfall_mm"])
    df["district"] = df["district"].astype(str).str.strip().str.title()

    neg = int((df["rainfall_mm"] < 0).sum())
    report("PASS" if neg == 0 else "FAIL", "no negative rainfall", f"{neg} negative values")
    top = df["rainfall_mm"].max()
    report("PASS" if top <= 500 else "WARN", "largest single-day value is believable (<= 500 mm)", f"max {top:.1f} mm")

    dup = int(df.duplicated(["district", "date"]).sum())
    report("PASS" if dup == 0 else "WARN", "one row per district per day", f"{dup} duplicates")

    per = df.groupby("district")["date"].nunique()
    same = per.nunique() == 1
    report("PASS" if same else "WARN", "every district has the same number of days",
           f"{per.min()} to {per.max()} days per district")
    report("PASS" if df["district"].nunique() >= 30 else "WARN", "number of districts", str(df["district"].nunique()))

    first, last = df["date"].min(), df["date"].max()
    span = (last - first).days + 1
    years = df["date"].dt.year.nunique()
    months = sorted(int(m) for m in df["date"].dt.month.unique())
    print(f"        range {first.date()} to {last.date()}  ({span} days, {years} year(s), months {months})")
    if span < 365 or len(months) < 12:
        report("FAIL", "enough history for MONTHLY AVERAGES",
               f"only {span} days / {len(months)} of 12 months. Use it for validation, "
               f"and build the monthly table from NASA POWER or IMD normals instead")
    elif years < 5:
        report("WARN", "enough history for monthly averages", f"{years} year(s); 5+ is better")
    else:
        report("PASS", "enough history for monthly averages", f"{years} years")


# ---------------------------------------------------------------- 2. monthly table
def check_monthly():
    section("2. Monthly rainfall  (data/processed/monthly_rainfall_by_district.csv)")
    df = data.load_csv("processed", "monthly_rainfall_by_district.csv")
    if df is None:
        return report("FAIL", "file not found", "the advisor cannot design anything without it; "
                                               "run: python -m scripts.make_monthly_nasa")
    need = {"district", "month", "avg_rainfall_mm"}
    if need - set(df.columns):
        return report("FAIL", "columns", f"missing {sorted(need - set(df.columns))}")
    report("PASS", "columns present")

    nan = int(df["avg_rainfall_mm"].isna().sum())
    report("PASS" if nan == 0 else "FAIL", "no missing values", f"{nan} empty")
    neg = int((df["avg_rainfall_mm"] < 0).sum())
    report("PASS" if neg == 0 else "FAIL", "no negative values", f"{neg} negative")

    df["district"] = df["district"].astype(str).str.strip().str.title()
    counts = df.groupby("district")["month"].apply(lambda s: sorted(s.tolist()))
    broken = [d for d, m in counts.items() if m != list(range(1, 13))]
    report("PASS" if not broken else "FAIL", "each district has months 1 to 12 exactly once",
           ", ".join(broken[:6]) if broken else f"{len(counts)} districts")

    annual = df.groupby("district")["avg_rainfall_mm"].sum()
    unit_bad = annual[(annual < 5) | (annual > 5000)]
    report("PASS" if unit_bad.empty else "FAIL", "yearly totals are not off by a unit (5 to 5000 mm)",
           ", ".join(f"{d}={v:.1f}" for d, v in unit_bad.head(5).items()))
    odd = annual[((annual < 50) | (annual > 1500)) & ~annual.index.isin(unit_bad.index)]
    report("PASS" if odd.empty else "WARN", "yearly totals look realistic for Rajasthan (50 to 1500 mm)",
           ", ".join(f"{d}={v:.0f}" for d, v in odd.head(5).items()))
    print(f"        yearly totals: min {annual.min():.0f}, median {annual.median():.0f}, max {annual.max():.0f} mm")

    # pivot_table averages duplicates instead of crashing; the check above already reports them
    wide = (df.pivot_table(index="district", columns="month", values="avg_rainfall_mm", aggfunc="mean")
              .reindex(columns=range(1, 13)).fillna(0))
    share = wide[[7, 8, 9]].sum(axis=1) / wide.sum(axis=1).replace(0, float("nan"))
    low = share[share < 0.55]
    report("PASS" if low.empty else "WARN", "July to September carry most of the rain (>= 55%)",
           ", ".join(f"{d}={v:.0%}" for d, v in low.head(5).items()))
    peak = wide.idxmax(axis=1)
    off = peak[~peak.isin([6, 7, 8, 9])]
    report("PASS" if off.empty else "WARN", "the wettest month is June to September",
           ", ".join(f"{d}=month {m}" for d, m in off.head(5).items()))
    dry = wide[[11, 12, 1, 2, 3]].sum(axis=1) / wide.sum(axis=1).replace(0, float("nan"))
    wet = dry[dry > 0.2]
    report("PASS" if wet.empty else "WARN", "November to March are mostly dry (< 20% of the year)",
           ", ".join(f"{d}={v:.0%}" for d, v in wet.head(5).items()))

    # NASA gives one value per ~50 km grid cell. Districts that fall in the same cell get identical numbers.
    twins = wide.round(1).apply(tuple, axis=1)
    groups = [sorted(g) for g in twins.groupby(twins).groups.values() if len(g) > 1]
    detail = "; ".join("+".join(g[:4]) + (f" (+{len(g) - 4} more)" if len(g) > 4 else "") for g in groups[:4])
    report("PASS" if not groups else "WARN",
           "no two districts have identical monthly values (identical = same NASA grid cell)",
           f"{sum(len(g) for g in groups)} districts in {len(groups)} shared group(s): {detail}" if groups else "")

    unknown = names(df) - set(FALLBACK_DISTRICTS)
    report("PASS" if not unknown else "WARN", "district names match the spellings used in the project",
           ", ".join(sorted(unknown)[:6]))


# ---------------------------------------------------------------- 3. reference tables
def check_reference():
    section("3. Reference tables  (data/reference/)")
    rc = data.load_csv("reference", "runoff_coefficients.csv")
    if rc is None:
        report("FAIL", "runoff_coefficients.csv not found")
    else:
        ok = rc["coefficient"].between(0, 1, inclusive="right").all()
        report("PASS" if ok else "FAIL", "runoff coefficients are between 0 and 1")
        need = {"concrete", "tiles", "metal", "asbestos", "ground"}
        miss = need - set(rc["surface"])
        report("PASS" if not miss else "FAIL", "all surfaces present", ", ".join(sorted(miss)))
        ph = int(rc["source"].astype(str).str.contains("PLACEHOLDER").sum())
        report("PASS" if ph == 0 else "WARN", "coefficients come from a government document", f"{ph} still placeholders")

    co = data.load_csv("reference", "costs.csv")
    if co is None:
        report("FAIL", "costs.csv not found")
    else:
        report("PASS" if (co["low_inr"] <= co["high_inr"]).all() and (co["low_inr"] > 0).all() else "FAIL",
               "every cost has 0 < low <= high")
        units = {"per_1000L", "per_m3", "each", "lump"}
        bad = co[~co["unit"].isin(units)]
        report("PASS" if bad.empty else "FAIL", "cost units are clear", ", ".join(bad["item"].tolist()))
        need = {"storage_tank", "recharge_pit", "filter_firstflush", "plumbing", "farm_pond", "farm_pond_lined"}
        miss = need - set(co["item"])
        report("PASS" if not miss else "FAIL", "all cost items present", ", ".join(sorted(miss)))
        ph = int(co["source"].astype(str).str.contains("PLACEHOLDER").sum())
        report("PASS" if ph == 0 else "WARN", "costs come from a schedule of rates or quotes", f"{ph} still placeholders")

    su = data.load_csv("reference", "subsidies.csv")
    if su is None:
        report("FAIL", "subsidies.csv not found")
    else:
        report("PASS" if su["subsidy_percent"].between(0, 100).all() and (su["subsidy_cap_inr"] >= 0).all()
               else "FAIL", "subsidy percent is 0 to 100 and caps are not negative")
        paid = su[su["subsidy_percent"] > 0]
        nosrc = paid[paid["source_url"].isna()]
        report("PASS" if nosrc.empty else "FAIL", "every subsidy row has a source link",
               ", ".join(nosrc["scheme_id"].tolist()))
        stale = su[su["last_verified"].astype(str).str.contains("YYYY")]
        report("PASS" if stale.empty else "WARN", "every row has a real last_verified date",
               f"{len(stale)} rows still say YYYY-MM-DD")

    co_ = data.load_csv("reference", "district_coords.csv")
    if co_ is None:
        report("SKIP", "district_coords.csv not found")
    else:
        inside = co_["lat"].between(23.0, 30.3) & co_["lon"].between(69.4, 78.4)
        report("PASS" if inside.all() else "FAIL", "coordinates fall inside Rajasthan's bounding box",
               ", ".join(co_.loc[~inside, "district"].tolist()))
        unknown = names(co_) - set(FALLBACK_DISTRICTS)
        report("PASS" if not unknown else "WARN", "coordinate names match the project spellings",
               ", ".join(sorted(unknown)[:6]))


# ---------------------------------------------------------------- 4. optional lookup tables
def check_lookup(file, column, allowed, label):
    df = data.load_csv("processed", file)
    if df is None:
        return report("SKIP", f"{file} not found (optional)")
    if not {"district", column} <= set(df.columns):
        return report("FAIL", f"{file} columns", f"needs district and {column}")
    bad = df[~df[column].isin(allowed)]
    report("PASS" if bad.empty else "FAIL", f"{label} values are one of {sorted(allowed)}",
           ", ".join(bad[column].astype(str).unique()[:5]))
    unknown = names(df) - set(FALLBACK_DISTRICTS)
    report("PASS" if not unknown else "WARN", f"{file}: district names match the project spellings",
           ", ".join(sorted(unknown)[:6]))
    report("PASS" if df[column].notna().all() else "FAIL", f"{file}: no blanks")


def check_optional():
    section("4. Optional lookup tables  (data/processed/)")
    check_lookup("district_soil.csv", "soil_type", {"sandy", "loamy", "clay"}, "soil")
    check_lookup("district_groundwater.csv", "category",
                 {"safe", "semi-critical", "critical", "over-exploited"}, "groundwater category")


# ---------------------------------------------------------------- 5. names agree across files
def check_agreement():
    section("5. District names agree across files")
    sets = {}
    for label, parts in (("monthly rainfall", ("processed", "monthly_rainfall_by_district.csv")),
                         ("daily IMD", ("processed", "rainfall_daily.csv")),
                         ("coordinates", ("reference", "district_coords.csv"))):
        df = data.load_csv(*parts)
        if df is not None and "district" in df.columns:
            sets[label] = names(df)
    if len(sets) < 2:
        return report("SKIP", "need at least two of the files above")
    base_label, base = next(iter(sets.items()))
    for label, s in list(sets.items())[1:]:
        diff = sorted(base ^ s)
        report("PASS" if not diff else "WARN", f"{base_label} vs {label}", ", ".join(diff[:8]))


if __name__ == "__main__":
    print(f"Checking data in: {data.DATA_DIR}")
    check_daily()
    check_monthly()
    check_reference()
    check_optional()
    check_agreement()
    print(f"\nSummary: {results.count('PASS')} pass, {results.count('WARN')} warn, "
          f"{results.count('FAIL')} fail, {results.count('SKIP')} skipped")
    sys.exit(1 if "FAIL" in results else 0)
