"""
build_precinct_layer.py
=======================
PURPOSE:
    Your current precinct GeoJSON has the right tabular data (registration,
    turnout, youth counts) but wrong geometries — it uses individual census
    blocks as polygon representatives instead of full precinct boundaries.
    This means only ~17% of NC's land is covered, so most block groups
    find nothing to intersect with.

    This script:
      1. Loads the official NC SBE precinct boundary shapefile
      2. Joins your tabular turnout data onto the real boundaries
      3. Runs the full areal interpolation with correct geometries
      4. Saves the enriched precinct GeoJSON

BEFORE RUNNING:
    Download the NC SBE precinct shapefile:
      https://www.ncsbe.gov/results-data/precinct-maps
      → "2024 Precinct Shapefiles" (or most recent year)
      → Download the statewide zip, extract it
      → Set SBE_SHAPEFILE_PATH below to the .shp file path

    The SBE shapefile will have columns like:
      county_nam (or COUNTY), prec_abbrv (or PREC_ID), geometry

    We join on county + precinct abbreviation to attach your turnout data.
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── CONFIGURE THESE PATHS ─────────────────────────────────────────────────────

# Path to the NC SBE precinct boundary shapefile (.shp)
# Download from: https://www.ncsbe.gov/results-data/precinct-maps
SBE_SHAPEFILE_PATH = Path("data/raw/shapefiles/SBE_PRECINCTS_20251212/SBE_PRECINCTS_20251212.shp")

# Your existing tabular precinct data (the CLEAN file with correct turnout numbers)
TURNOUT_PATH = Path("data/processed/nc_precinct_turnout_CLEAN.geojson")

# Block group demographics
BG_PATH = Path("data/processed/nc_blockgroup_demographics.geojson")

# Output
OUTPUT_PATH = Path("data/processed/nc_precinct_with_population.geojson")

AREA_CRS   = "EPSG:6542"
VAP_FACTOR = 0.85

POP_COLUMNS = [
    "total_pop", "male_pop", "female_pop",
    "white_pop", "black_pop", "native_pop", "asian_pop",
    "pacific_pop", "other_pop", "multiracial_pop", "hispanic_pop",
    "under_18", "age_18_24", "age_25_34",
    "age_35_44", "age_45_64", "age_65_plus",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — INSPECT SBE SHAPEFILE COLUMNS
# ═══════════════════════════════════════════════════════════════════════════════

def inspect_sbe(sbe_path: Path) -> gpd.GeoDataFrame:
    """Load and inspect the SBE precinct shapefile so we know its column names."""
    print("=" * 60)
    print("LOADING NC SBE PRECINCT BOUNDARY SHAPEFILE")
    print("=" * 60)

    sbe = gpd.read_file(sbe_path)
    print(f"\nRow count:  {len(sbe):,}")
    print(f"CRS:        {sbe.crs}")
    print(f"Columns:    {list(sbe.columns)}")
    print(f"\nFirst 3 rows:")
    print(sbe[[c for c in sbe.columns if c != "geometry"]].head(3).to_string())

    area_km2 = sbe.to_crs(AREA_CRS).geometry.area.sum() / 1e6
    print(f"\nTotal precinct area: {area_km2:,.0f} km²")
    print(f"NC land area:        139,391 km²")
    print(f"Coverage:            {area_km2/139391*100:.1f}%")
    print(f"(Should be ~95–100% for a complete statewide file)")

    return sbe


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — JOIN TURNOUT DATA ONTO SBE BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════════

def join_turnout_to_boundaries(sbe: gpd.GeoDataFrame, turnout_path: Path) -> gpd.GeoDataFrame:
    """
    Join tabular turnout/registration data onto the real precinct boundaries.

    The SBE shapefile has geometry + county/precinct identifiers.
    Your turnout file has registration counts + the same identifiers (no real geometry).
    We match them on normalized county name + precinct abbreviation.
    """
    print("\n" + "=" * 60)
    print("JOINING TURNOUT DATA ONTO SBE BOUNDARIES")
    print("=" * 60)

    turnout = gpd.read_file(turnout_path)
    print(f"\nTurnout data: {len(turnout):,} precincts")
    print(f"SBE bounds:   {len(sbe):,} precincts")

    # ── Normalize key columns for matching ────────────────────────────────────
    # Strip whitespace, uppercase, remove punctuation so "New Hanover" == "NEW HANOVER"
    def normalize(s):
        return s.astype(str).str.strip().str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)

    # Turnout side — already has county_nam and prec_id / precinct_abbrv
    turnout["_county_norm"] = normalize(turnout["county_nam"])
    turnout["_prec_norm"]   = normalize(turnout["precinct_abbrv"].fillna(turnout["prec_id"]))

    # SBE side — inspect which columns hold county and precinct info
    # Common SBE column names:
    sbe_county_candidates = ["county_nam", "COUNTY_NAM", "COUNTY", "county"]
    sbe_prec_candidates   = ["prec_abbrv", "PREC_ABBRV", "precinct_abbrv",
                              "PRECINCT", "prec_id", "PREC_ID"]

    sbe_county_col = next((c for c in sbe_county_candidates if c in sbe.columns), None)
    sbe_prec_col   = next((c for c in sbe_prec_candidates   if c in sbe.columns), None)

    if sbe_county_col is None or sbe_prec_col is None:
        print(f"\n⚠ Could not auto-detect SBE key columns!")
        print(f"  SBE columns: {list(sbe.columns)}")
        print(f"  Edit SBE_COUNTY_COL and SBE_PREC_COL below and re-run.")
        # ── MANUAL OVERRIDE — set these if auto-detect fails ──────────────────
        SBE_COUNTY_COL = "county_nam"   # ← change to actual column name
        SBE_PREC_COL   = "prec_abbrv"  # ← change to actual column name
        sbe_county_col = SBE_COUNTY_COL
        sbe_prec_col   = SBE_PREC_COL

    print(f"\nUsing SBE columns: county='{sbe_county_col}', precinct='{sbe_prec_col}'")

    sbe["_county_norm"] = normalize(sbe[sbe_county_col])
    sbe["_prec_norm"]   = normalize(sbe[sbe_prec_col])
    sbe["_join_key"]    = sbe["_county_norm"] + "__" + sbe["_prec_norm"]
    turnout["_join_key"]= turnout["_county_norm"] + "__" + turnout["_prec_norm"]

    # ── Check join key uniqueness ─────────────────────────────────────────────
    n_sbe_unique     = sbe["_join_key"].nunique()
    n_turnout_unique = turnout["_join_key"].nunique()
    print(f"\nUnique join keys — SBE: {n_sbe_unique:,}  |  Turnout: {n_turnout_unique:,}")

    # ── Perform the join ──────────────────────────────────────────────────────
    # Keep SBE geometry; attach turnout columns (drop turnout geometry).
    # Deduplicate turnout BEFORE merging, and rename its key column so pandas
    # doesn't complain about a duplicate "_join_key" column on both sides.
    turnout_cols = [c for c in turnout.columns
                    if c not in ["geometry", "_county_norm", "_prec_norm",
                                 "_composite_key", "county_nam"]
                    and not c.startswith("Shape_")]
    turnout_tab = (
        turnout[turnout_cols + ["_join_key"]]
        .drop_duplicates(subset=["_join_key"], keep="first")
        .rename(columns={"_join_key": "_t_join_key"})
        .copy()
    )

    merged = sbe.merge(
        turnout_tab,
        left_on="_join_key", right_on="_t_join_key",
        how="left", suffixes=("_sbe", "_turnout")
    )
    merged = merged.drop(columns=["_t_join_key"], errors="ignore")

    matched = merged["total_registered"].notna().sum()
    print(f"\nMatched: {matched:,} / {len(merged):,} SBE precincts got turnout data")

    unmatched_sbe = merged[merged["total_registered"].isna()]["_join_key"].tolist()
    if unmatched_sbe:
        print(f"\nSBE precincts with NO turnout data ({len(unmatched_sbe)}):")
        print(f"  {unmatched_sbe[:20]}")
        print(f"\n  Sample turnout keys for comparison:")
        sample = turnout["_join_key"].dropna().sample(min(5, len(turnout)), random_state=1).tolist()
        print(f"  {sample}")

    if len(merged) > len(sbe):
        print(f"\n⚠ Merge still inflated: {len(sbe):,} → {len(merged):,} rows")
        merged["_area"] = merged.geometry.area
        merged = (merged.sort_values("_area", ascending=False)
                        .drop_duplicates(subset=["_join_key"], keep="first")
                        .drop(columns=["_area"]).reset_index(drop=True))
        print(f"  → {len(merged):,} rows after dedup")

    # Clean up helper columns
    merged = merged.drop(columns=["_county_norm", "_prec_norm", "_join_key"], errors="ignore")

    # Add composite key for interpolation
    merged["_composite_key"] = (
        merged[sbe_county_col].astype(str).str.strip().str.upper()
        + "__"
        + merged[sbe_prec_col].astype(str).str.strip().str.upper()
    )

    print(f"\n✓ Merged layer: {len(merged):,} precincts with real boundaries + turnout data")

    return merged


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — FULL INTERPOLATION ON REAL BOUNDARIES
# ═══════════════════════════════════════════════════════════════════════════════

def run_interpolation(bg: gpd.GeoDataFrame, precincts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("\n" + "=" * 60)
    print("AREAL WEIGHTED INTERPOLATION")
    print("=" * 60)

    bg_proj   = bg.to_crs(AREA_CRS).copy()
    prec_proj = precincts.to_crs(AREA_CRS).copy()

    bg_proj.geometry   = bg_proj.geometry.buffer(0)
    prec_proj.geometry = prec_proj.geometry.buffer(0)
    bg_proj["bg_area_m2"] = bg_proj.geometry.area
    bg_proj = bg_proj[bg_proj["bg_area_m2"] > 0]

    # Coverage check
    prec_area_km2 = prec_proj.geometry.area.sum() / 1e6
    print(f"\nPrecinct coverage: {prec_area_km2:,.0f} km² "
          f"({prec_area_km2/139391*100:.1f}% of NC)")

    print(f"\nIntersecting {len(bg_proj):,} BGs × {len(prec_proj):,} precincts...")
    inter = gpd.overlay(bg_proj, prec_proj, how="intersection", keep_geom_type=True)
    print(f"  → {len(inter):,} intersection slices")

    inter["slice_area_m2"] = inter.geometry.area
    inter["weight"]        = (inter["slice_area_m2"] / inter["bg_area_m2"]).clip(0, 1)

    # Find composite key column (may have suffix after overlay)
    key_col = "_composite_key"
    if key_col not in inter.columns:
        candidates = [c for c in inter.columns if "_composite_key" in c]
        key_col = candidates[0] if candidates else None
        if key_col:
            print(f"  Using '{key_col}' as composite key after overlay")
        else:
            raise KeyError(f"_composite_key not found after overlay. Columns: {list(inter.columns)}")

    # Allocate
    alloc_cols = []
    for col in POP_COLUMNS:
        if col in inter.columns:
            inter[f"alloc_{col}"] = inter[col] * inter["weight"]
            alloc_cols.append(f"alloc_{col}")

    inter["alloc_slice_area"] = inter["slice_area_m2"]

    # Aggregate
    grouped = inter.groupby(key_col)[alloc_cols + ["alloc_slice_area"]].sum()
    grouped.columns = [
        "est_covered_area_m2" if c == "alloc_slice_area" else c.replace("alloc_", "est_")
        for c in grouped.columns
    ]

    # Derive Youth VAP
    grouped["est_total_vap"]       = grouped["est_total_pop"] * VAP_FACTOR
    grouped["est_youth_vap"]       = grouped["est_age_18_24"]
    grouped["est_youth_broad_vap"] = grouped["est_age_18_24"] + grouped["est_age_25_34"]
    grouped["est_youth_vap_pct"]   = (
        grouped["est_youth_vap"] / grouped["est_total_vap"].replace(0, np.nan)
    )
    grouped["est_pct_youth"]       = (
        grouped["est_age_18_24"] / grouped["est_total_pop"].replace(0, np.nan)
    )

    # Coverage quality
    prec_areas = prec_proj.set_index("_composite_key")["geometry"].area
    grouped["bg_coverage"] = (
        grouped["est_covered_area_m2"] / prec_areas.reindex(grouped.index)
    ).clip(0, 1)
    grouped = grouped.drop(columns=["est_covered_area_m2"], errors="ignore")

    # Sanity check
    est_total = grouped["est_total_pop"].sum()
    print(f"\n  Estimated total population: {est_total:,.0f}")
    print(f"  NC 2020 Census actual:      10,439,388")
    print(f"  Difference:                 {abs(est_total - 10_439_388)/10_439_388*100:.1f}%")

    # Merge back
    result = precincts.merge(
        grouped.reset_index().rename(columns={key_col: "_composite_key"}),
        on="_composite_key", how="left"
    )
    assert len(result) == len(precincts), \
        f"Row explosion: {len(precincts)} → {len(result)}"

    matched = result["est_total_pop"].notna().sum()
    print(f"  Matched: {matched:,} / {len(result):,} precincts")

    # Registration gap
    if "youth_registered" in result.columns:
        result["youth_reg_gap"]    = (
            result["est_youth_vap"] - result["youth_registered"].fillna(0)
        )
        result["youth_reg_rate"]   = (
            result["youth_registered"].fillna(0)
            / result["est_youth_vap"].replace(0, np.nan)
        )
        result["youth_unreg_rate"] = 1 - result["youth_reg_rate"]

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(gdf: gpd.GeoDataFrame):
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)

    for col, label in [
        ("est_total_pop", "Est. total population"),
        ("est_youth_vap", "Est. youth VAP (18–24)"),
        ("est_total_vap", "Est. total VAP (85% rule)"),
    ]:
        if col in gdf.columns:
            print(f"\n{label}:")
            print(f"  State total:       {gdf[col].sum():>12,.0f}")
            print(f"  Per-precinct mean: {gdf[col].mean():>12,.1f}")

    if "youth_registered" in gdf.columns and "est_youth_vap" in gdf.columns:
        yr   = gdf["youth_registered"].fillna(0).sum()
        yvap = gdf["est_youth_vap"].fillna(0).sum()
        if yvap > 0:
            print(f"\nYouth registration summary:")
            print(f"  Youth registered:    {yr:>10,.0f}")
            print(f"  Youth VAP estimated: {yvap:>10,.0f}")
            print(f"  Registration rate:   {yr/yvap*100:>9.1f}%  (should be 0–100%)")
            print(f"  Unregistered (gap):  {yvap - yr:>10,.0f}")

    if "youth_reg_gap" in gdf.columns:
        show = [c for c in ["county_nam", "enr_desc", "prec_id",
                             "est_youth_vap", "youth_registered",
                             "youth_reg_gap", "youth_unreg_rate", "bg_coverage"]
                if c in gdf.columns]
        top10 = gdf[show].dropna(subset=["youth_reg_gap"]).nlargest(10, "youth_reg_gap")
        print(f"\nTop 10 precincts by unregistered youth:")
        print(top10.to_string(index=False))

    print("\n" + "=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    # 1. Load and inspect SBE boundaries
    sbe = inspect_sbe(SBE_SHAPEFILE_PATH)

    # 2. Join turnout data onto real boundaries
    precincts = join_turnout_to_boundaries(sbe, TURNOUT_PATH)

    # Save the merged precinct layer (boundaries + turnout) for inspection
    merged_path = OUTPUT_PATH.parent / "nc_precincts_sbe_with_turnout.geojson"
    precincts.to_crs("EPSG:4326").to_file(merged_path, driver="GeoJSON")
    print(f"\n✓ Merged SBE+turnout layer saved: {merged_path}")

    # 3. Load block groups and run interpolation
    print(f"\nLoading block groups...")
    bg = gpd.read_file(BG_PATH)
    print(f"  → {len(bg):,} block groups")

    result = run_interpolation(bg, precincts)

    # 4. Save final output
    print(f"\nSaving to {OUTPUT_PATH} ...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_crs("EPSG:4326").to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"  ✓ GeoJSON: {OUTPUT_PATH}  ({len(result):,} features)")

    csv_path = OUTPUT_PATH.with_suffix(".csv")
    result.to_crs("EPSG:4326").drop(columns="geometry").to_csv(csv_path, index=False)
    print(f"  ✓ CSV: {csv_path}")

    print_summary(result)
    return result


if __name__ == "__main__":
    main()