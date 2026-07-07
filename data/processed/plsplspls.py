"""
interpolate_final.py  —  NC Youth Power Map
============================================
Clean final version. Run from project root:
    python data/processed/interpolate_final.py
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── PATHS — edit these if needed ──────────────────────────────────────────────
SBE_PATH      = Path("data/raw/shapefiles/SBE_PRECINCTS_20251212/SBE_PRECINCTS_20251212.shp")
TURNOUT_PATH  = Path("data/processed/nc_precinct_turnout_CLEAN.geojson")
BG_PATH       = Path("data/processed/nc_blockgroup_demographics.geojson")
OUTPUT_PATH   = Path("data/processed/nc_precinct_with_population.geojson")

AREA_CRS   = "EPSG:6542"
VAP_FACTOR = 0.85

POP_COLUMNS = [
    "total_pop", "male_pop", "female_pop",
    "white_pop", "black_pop", "native_pop", "asian_pop",
    "pacific_pop", "other_pop", "multiracial_pop", "hispanic_pop",
    "under_18", "age_18_24", "age_25_34",
    "age_35_44", "age_45_64", "age_65_plus",
]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def norm(series):
    """Normalize strings: uppercase, strip, remove non-alphanumeric."""
    return series.astype(str).str.strip().str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. LOAD SBE BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════════

print("=" * 60)
print("NC YOUTH POWER MAP — Block Group → Precinct Interpolation")
print("=" * 60)

print(f"\n[1] Loading SBE precinct boundaries...")
sbe = gpd.read_file(SBE_PATH)
print(f"    {len(sbe):,} precincts | CRS: {sbe.crs}")
print(f"    Columns: {list(sbe.columns)}")
area_pct = sbe.to_crs(AREA_CRS).geometry.area.sum() / 1e6 / 139391 * 100
print(f"    Area coverage: {area_pct:.1f}% of NC  (should be ~100%)")

# Build normalized join key on SBE side
sbe["_key"] = norm(sbe["county_nam"]) + "__" + norm(sbe["prec_id"])
print(f"    Unique SBE keys: {sbe['_key'].nunique():,}")


# ═══════════════════════════════════════════════════════════════════════════════
# 2. LOAD TURNOUT DATA (attributes only — ignore its bad geometries)
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[2] Loading turnout/registration data...")
turnout_raw = gpd.read_file(TURNOUT_PATH)
print(f"    {len(turnout_raw):,} rows | Columns: {[c for c in turnout_raw.columns if c != 'geometry']}")

# Build normalized join key on turnout side
turnout_raw["_key"] = norm(turnout_raw["county_nam"]) + "__" + norm(turnout_raw["prec_id"])
print(f"    Unique turnout keys: {turnout_raw['_key'].nunique():,}")

# Keep only the attribute columns we care about (no geometry, no shape columns)
keep_cols = [
    "total_registered", "youth_registered", "avg_age",
    "avg_turnout", "avg_general_turnout_rate",
    "pct_voted_2024", "pct_voted_2022", "pct_voted_2020",
    "youth_share", "enr_desc", "_key"
]
keep_cols = [c for c in keep_cols if c in turnout_raw.columns]

# Deduplicate: if two turnout rows share the same key, keep the one with
# more registered voters (most complete record)
sort_col = "total_registered" if "total_registered" in turnout_raw.columns else keep_cols[0]
turnout_tab = (
    turnout_raw[keep_cols]
    .sort_values(sort_col, ascending=False, na_position="last")
    .drop_duplicates(subset=["_key"], keep="first")
    .reset_index(drop=True)
)
print(f"    After dedup: {len(turnout_tab):,} unique precincts")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. JOIN TURNOUT ONTO SBE BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[3] Joining turnout data onto SBE boundaries...")

# Rename turnout key to avoid pandas "duplicate column" error on merge
turnout_tab = turnout_tab.rename(columns={"_key": "_turnout_key"})

merged = sbe.merge(
    turnout_tab,
    left_on="_key",
    right_on="_turnout_key",
    how="left",
    suffixes=("", "_turnout"),
)
merged = merged.drop(columns=["_turnout_key"], errors="ignore")

assert len(merged) == len(sbe), \
    f"Merge inflated rows: {len(sbe)} SBE → {len(merged)} merged. Key not unique."

matched = merged["total_registered"].notna().sum()
print(f"    Matched: {matched:,} / {len(merged):,} precincts")

unmatched = merged[merged["total_registered"].isna()]["_key"].tolist()
if unmatched:
    print(f"    Unmatched SBE precincts ({len(unmatched)}): {unmatched[:15]}")
    # Show closest turnout keys for manual inspection
    print(f"    Sample turnout keys: {turnout_tab['_turnout_key'].sample(min(8,len(turnout_tab)), random_state=1).tolist()}")

# Build composite key for interpolation groupby
merged["_composite_key"] = merged["_key"]
merged = merged.drop(columns=["_key"], errors="ignore")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. LOAD BLOCK GROUPS
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[4] Loading block groups...")
bg = gpd.read_file(BG_PATH)
print(f"    {len(bg):,} block groups | CRS: {bg.crs}")

missing_pop = [c for c in POP_COLUMNS if c not in bg.columns]
if missing_pop:
    print(f"    ⚠ Missing BG columns: {missing_pop}")
    POP_COLUMNS_USE = [c for c in POP_COLUMNS if c in bg.columns]
else:
    POP_COLUMNS_USE = POP_COLUMNS
    print(f"    ✓ All {len(POP_COLUMNS)} population columns present")


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AREAL WEIGHTED INTERPOLATION
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[5] Running areal weighted interpolation...")

bg_proj   = bg.to_crs(AREA_CRS).copy()
prec_proj = merged.to_crs(AREA_CRS).copy()

# Fix any invalid geometries
bg_proj.geometry   = bg_proj.geometry.buffer(0)
prec_proj.geometry = prec_proj.geometry.buffer(0)

# Block group areas (computed BEFORE intersection so we always divide by full BG area)
bg_proj["bg_area_m2"] = bg_proj.geometry.area
bg_proj = bg_proj[bg_proj["bg_area_m2"] > 0].copy()

print(f"    Intersecting {len(bg_proj):,} BGs × {len(prec_proj):,} precincts...")
print(f"    (may take 1–3 minutes...)")

inter = gpd.overlay(bg_proj, prec_proj, how="intersection", keep_geom_type=True)
print(f"    → {len(inter):,} intersection slices")

# Find composite key after overlay (may get a suffix)
key_col = "_composite_key"
if key_col not in inter.columns:
    candidates = [c for c in inter.columns if "_composite_key" in c]
    if candidates:
        key_col = candidates[0]
        print(f"    Using '{key_col}' as composite key (got suffix after overlay)")
    else:
        raise KeyError(f"Could not find _composite_key after overlay. Columns: {list(inter.columns)}")

# Areal weights
inter["slice_area_m2"] = inter.geometry.area
inter["weight"] = (inter["slice_area_m2"] / inter["bg_area_m2"]).clip(0, 1)

# Allocate population
alloc_cols = []
for col in POP_COLUMNS_USE:
    inter[f"alloc_{col}"] = inter[col] * inter["weight"]
    alloc_cols.append(f"alloc_{col}")
inter["alloc_slice_area"] = inter["slice_area_m2"]

# Aggregate by precinct
grouped = inter.groupby(key_col)[alloc_cols + ["alloc_slice_area"]].sum()
grouped.columns = [
    "est_covered_area_m2" if c == "alloc_slice_area" else c.replace("alloc_", "est_")
    for c in grouped.columns
]
print(f"    Population estimated for {len(grouped):,} precincts")

# Sanity check
est_nc_total = grouped["est_total_pop"].sum()
print(f"\n    Est. NC total population: {est_nc_total:>12,.0f}")
print(f"    2020 Census actual:       10,439,388")
print(f"    Difference:               {abs(est_nc_total-10_439_388)/10_439_388*100:.1f}%  (areal interpolation error — expected)")


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DERIVE YOUTH VAP COLUMNS
# ═══════════════════════════════════════════════════════════════════════════════

grouped["est_total_vap"]       = grouped["est_total_pop"] * VAP_FACTOR
grouped["est_youth_vap"]       = grouped["est_age_18_24"]   # 18–24 IS youth VAP
grouped["est_youth_broad_vap"] = grouped["est_age_18_24"] + grouped["est_age_25_34"]
grouped["est_youth_vap_pct"]   = grouped["est_youth_vap"] / grouped["est_total_vap"].replace(0, np.nan)
grouped["est_pct_youth"]       = grouped["est_age_18_24"] / grouped["est_total_pop"].replace(0, np.nan)

# Coverage quality metric
# Use groupby mean to avoid duplicate-index issues from any remaining geometry dupes
prec_areas = (
    prec_proj[["_composite_key", "geometry"]]
    .assign(area=prec_proj.geometry.area)
    .groupby("_composite_key")["area"]
    .first()
)
grouped["bg_coverage"] = (
    grouped["est_covered_area_m2"] / prec_areas.reindex(grouped.index)
).clip(0, 1)
grouped = grouped.drop(columns=["est_covered_area_m2"])


# ═══════════════════════════════════════════════════════════════════════════════
# 7. MERGE BACK ONTO PRECINCT LAYER
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[6] Merging estimates back onto precinct layer...")
result = merged.merge(
    grouped.reset_index().rename(columns={key_col: "_composite_key"}),
    on="_composite_key",
    how="left",
)

assert len(result) == len(merged), \
    f"Merge inflated rows: {len(merged)} → {len(result)}"

pop_matched = result["est_total_pop"].notna().sum()
print(f"    {pop_matched:,} / {len(result):,} precincts have population estimates")


# ═══════════════════════════════════════════════════════════════════════════════
# 8. YOUTH REGISTRATION GAP
# ═══════════════════════════════════════════════════════════════════════════════

if "youth_registered" in result.columns and "est_youth_vap" in result.columns:
    result["youth_reg_gap"]    = result["est_youth_vap"] - result["youth_registered"].fillna(0)
    result["youth_reg_rate"]   = result["youth_registered"].fillna(0) / result["est_youth_vap"].replace(0, np.nan)
    result["youth_unreg_rate"] = 1 - result["youth_reg_rate"]


# ═══════════════════════════════════════════════════════════════════════════════
# 9. SAVE
# ═══════════════════════════════════════════════════════════════════════════════

print(f"\n[7] Saving outputs...")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
result_out = result.to_crs("EPSG:4326")
result_out.to_file(OUTPUT_PATH, driver="GeoJSON")
print(f"    ✓ GeoJSON: {OUTPUT_PATH}  ({len(result_out):,} features)")

csv_path = OUTPUT_PATH.with_suffix(".csv")
result_out.drop(columns="geometry").to_csv(csv_path, index=False)
print(f"    ✓ CSV:     {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════════
# 10. SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("RESULTS SUMMARY")
print("=" * 60)

for col, label in [
    ("est_total_pop", "Est. total population"),
    ("est_youth_vap", "Est. youth VAP (18–24)"),
    ("est_total_vap", "Est. total VAP (85% rule)"),
]:
    if col in result.columns:
        print(f"\n{label}:")
        print(f"  State total:       {result[col].sum():>12,.0f}")
        print(f"  Per-precinct mean: {result[col].mean():>12,.1f}")

if "youth_registered" in result.columns and "est_youth_vap" in result.columns:
    yr   = result["youth_registered"].fillna(0).sum()
    yvap = result["est_youth_vap"].fillna(0).sum()
    print(f"\nYouth registration:")
    print(f"  Registered:          {yr:>10,.0f}")
    print(f"  VAP estimated:       {yvap:>10,.0f}")
    print(f"  Registration rate:   {yr/yvap*100:>9.1f}%  ← should be 0–100%")
    print(f"  Unregistered (gap):  {yvap - yr:>10,.0f}")

if "youth_reg_gap" in result.columns:
    show = [c for c in ["county_nam","enr_desc","prec_id",
                         "est_youth_vap","youth_registered",
                         "youth_reg_gap","youth_unreg_rate","bg_coverage"]
            if c in result.columns]
    top10 = result[show].dropna(subset=["youth_reg_gap"]).nlargest(10, "youth_reg_gap")
    print(f"\nTop 10 precincts by unregistered youth:")
    print(top10.to_string(index=False))

if "bg_coverage" in result.columns:
    print(f"\nBlock group coverage:")
    print(f"  Mean:  {result['bg_coverage'].mean()*100:.1f}%")
    print(f"  ≥99%:  {(result['bg_coverage']>=0.99).sum():,} precincts")
    print(f"  <80%:  {(result['bg_coverage']<0.80).sum():,} precincts")

print("\n" + "=" * 60)
print("Done.")