"""
build_precinct_geojson.py
--------------------------
Brings together all four datasets into a single precinct-level GeoJSON:

  1. SBE_PRECINCTS_CENSUSBLOCKS shapefile  (blocks → precinct mapping + geometry)
  2. nc_census_blockgroups.csv             (ACS demographics at block group level)
  3. nc_voters_by_precinct.csv             (registration + turnout at precinct level)

Strategy:
  - Truncate block GEOID20 (15 digits) to 12 digits → matches block group GEOID
  - Join Census demographics onto each block via block group GEOID
  - Aggregate (sum) Census data from block → precinct
  - Dissolve block geometries → precinct polygons
  - Join voter registration + history data on county + precinct
  - Reproject to EPSG:4326 (WGS84) for GeoJSON output

Output:
  nc_precincts.geojson

Requirements:
  pip install geopandas pandas shapely pyogrio
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────
BLOCKS_SHP   = "data/raw/shapefiles/precincts/SBE_PRECINCTS_CENSUSBLOCKS_20251212.shp"
CENSUS_CSV   = "nc_census_blockgroups.csv"
VOTERS_CSV   = "nc_voters_by_precinct.csv"
OUTPUT_FILE  = "nc_precincts.geojson"
# ──────────────────────────────────────────────────────────────────────────────

# Census numeric columns we want to carry through
CENSUS_DEMO_COLS = [
    "pop_total", "pop_voting_age",
    "pop_under_18", "pop_18_24", "pop_25_34", "pop_35_44",
    "pop_45_54", "pop_55_64", "pop_65_74", "pop_75plus",
    "pop_white_alone", "pop_black_alone", "pop_asian_alone",
    "pop_aian_alone", "pop_nhpi_alone", "pop_other_alone",
    "pop_two_or_more", "pop_hispanic", "pop_not_hispanic",
    "pop_white_nonhispanic", "pop_nonwhite",
]


def main():

    # ── Step 1: Load blocks shapefile ─────────────────────────────────────────
    print("Loading blocks shapefile...")
    blocks = gpd.read_file(BLOCKS_SHP)
    print(f"  {len(blocks):,} blocks loaded. CRS: {blocks.crs}")

    # Normalize join keys
    blocks["county_nam"] = blocks["county_nam"].str.strip().str.upper()
    blocks["prec_id"]    = blocks["prec_id"].str.strip().str.upper()
    blocks["GEOID20"]    = blocks["GEOID20"].astype(str).str.strip().str.zfill(15)

    # Derive block group GEOID by truncating to 12 digits
    blocks["bg_GEOID"] = blocks["GEOID20"].str[:12]

    # ── Clean known shapefile issues ──────────────────────────────────────────────

    # 1. Drop blank/null rows (county_id == 0)
    blocks = blocks[blocks["county_id"] != 0].copy()

    # 2. Fix LEE county stored as county ID "53" instead of name "LEE"
    blocks["county_nam"] = blocks["county_nam"].replace({"53": "LEE"})

    # 3. Drop stale CLEVELAND S 4A precinct (retired, no voter file match)
    blocks = blocks[~(
        (blocks["county_nam"] == "CLEVELAND") & (blocks["prec_id"] == "S 4A")
    )].copy()

    print(f"  After cleaning: {len(blocks):,} blocks remaining.")

    # ── Step 2: Load Census CSV and join to blocks ────────────────────────────
    print("Loading Census block group data...")
    census = pd.read_csv(CENSUS_CSV, dtype={"GEOID": str})
    census["GEOID"] = census["GEOID"].str.strip().str.zfill(12)

    # Keep only the columns we need
    available_demo_cols = [c for c in CENSUS_DEMO_COLS if c in census.columns]
    census = census[["GEOID"] + available_demo_cols]

    # Convert to numeric
    for col in available_demo_cols:
        census[col] = pd.to_numeric(census[col], errors="coerce").fillna(0)

    print(f"  {len(census):,} block groups loaded.")
    print(f"  Joining blocks → block groups on GEOID...")

    blocks = blocks.merge(census, left_on="bg_GEOID", right_on="GEOID", how="left")

    matched   = blocks["pop_total"].notna().sum()
    unmatched = blocks["pop_total"].isna().sum()
    print(f"  Matched: {matched:,} blocks  |  Unmatched: {unmatched:,} blocks")

    # Fill any unmatched Census values with 0
    for col in available_demo_cols:
        blocks[col] = blocks[col].fillna(0)

    # ── Step 2b: Area-weighted apportionment ──────────────────────────────────
    # Problem: every block in a block group gets the full block group population,
    # causing massive double-counting when we sum to precinct level.
    # Fix: weight each block's share of the population by its share of the
    # block group's total area (Shape_Area). So if a block covers 30% of its
    # block group's area, it gets 30% of the block group's population.
    print("  Applying area-weighted apportionment to fix double-counting...")

    blocks["Shape_Area"] = pd.to_numeric(blocks["Shape_Area"], errors="coerce").fillna(0)

    # Compute each block group's total area (sum of all its blocks' areas)
    bg_total_area = (
        blocks.groupby("bg_GEOID")["Shape_Area"]
        .sum()
        .rename("bg_total_area")
    )
    blocks = blocks.join(bg_total_area, on="bg_GEOID")

    # Weight = this block's area / its block group's total area
    # If bg_total_area is 0 (edge case), assign equal weight to avoid div/0
    blocks["area_weight"] = np.where(
        blocks["bg_total_area"] > 0,
        blocks["Shape_Area"] / blocks["bg_total_area"],
        0,
    )

    # Multiply every Census count column by the area weight
    for col in available_demo_cols:
        blocks[col] = blocks[col] * blocks["area_weight"]

    print("  Apportionment complete.")

    # ── Step 3: Dissolve blocks → precinct polygons ───────────────────────────
    print("\nDissolving block geometries to precinct level...")
    GROUP = ["county_nam", "prec_id"]

    # Sum Census demographics per precinct
    census_agg = (
        blocks
        .groupby(GROUP)[available_demo_cols]
        .sum()
        .reset_index()
    )

    # Dissolve geometries (union all block polygons within each precinct)
    # Keep enr_desc (precinct name) by taking the first value per precinct
    meta_cols = GROUP + ["enr_desc"]
    precinct_meta = (
        blocks[meta_cols]
        .drop_duplicates(subset=GROUP)
    )

    print("  Unioning geometries (this may take a minute)...")
    precinct_geom = (
        blocks[GROUP + ["geometry"]]
        .dissolve(by=GROUP)
        .reset_index()
    )

    # Merge geometry + demographics + metadata
    precincts = precinct_geom.merge(census_agg, on=GROUP, how="left")
    precincts = precincts.merge(precinct_meta, on=GROUP, how="left")

    print(f"  {len(precincts):,} precincts after dissolve.")

    # ── Step 4: Join voter registration + history data ────────────────────────
    print("\nJoining voter registration and history data...")
    voters = pd.read_csv(VOTERS_CSV, dtype=str)
    voters["county_desc"]    = voters["county_desc"].str.strip().str.upper()
    voters["precinct_abbrv"] = voters["precinct_abbrv"].str.strip().str.upper()

    # Numeric columns in voter file
    voter_id_cols  = ["county_desc", "precinct_abbrv", "precinct_desc"]
    voter_num_cols = [c for c in voters.columns if c not in voter_id_cols]
    for col in voter_num_cols:
        voters[col] = pd.to_numeric(voters[col], errors="coerce").fillna(0)

    precincts = precincts.merge(
        voters,
        left_on=["county_nam", "prec_id"],
        right_on=["county_desc", "precinct_abbrv"],
        how="left",
    )

    matched_voters = precincts["reg_total"].notna().sum()
    print(f"  Matched voter data: {matched_voters:,} / {len(precincts):,} precincts")

    # ── Step 5: Add derived rate columns ─────────────────────────────────────
    print("\nComputing derived rate columns...")

    # ── Estimated VAP columns ─────────────────────────────────────────────────
    # est_vap_total  = 85% of total population (citizen voting-age estimate)
    # est_vap_youth  = 85% of 18-24 population (citizen youth VAP estimate)
    # These serve as a practical benchmark since not all VAP are citizens
    precincts["est_vap_total"] = (precincts["pop_total"] * 0.85).round(0)
    if "pop_18_24" in precincts.columns:
        precincts["est_vap_youth"] = (precincts["pop_18_24"] * 0.85).round(0)

    # Registration rate = active registered / estimated VAP
    # (using est_vap_total as denominator is more realistic than raw pop_voting_age)
    precincts["reg_rate"] = (
        precincts["reg_active"] / precincts["est_vap_total"].replace(0, np.nan)
    ).clip(upper=1.5).round(4)

    # Youth registration rate = active 18-24 registered / est_vap_youth
    if "age_18_24" in precincts.columns and "est_vap_youth" in precincts.columns:
        precincts["reg_rate_youth"] = (
            precincts["age_18_24"] / precincts["est_vap_youth"].replace(0, np.nan)
        ).clip(upper=1.5).round(4)

    # Racial composition rates (as share of total pop)
    race_rate_map = {
        "pct_white":        "pop_white_alone",
        "pct_black":        "pop_black_alone",
        "pct_hispanic":     "pop_hispanic",
        "pct_asian":        "pop_asian_alone",
        "pct_nonwhite":     "pop_nonwhite",
        "pct_white_nonhisp":"pop_white_nonhispanic",
    }
    for rate_col, raw_col in race_rate_map.items():
        if raw_col in precincts.columns:
            precincts[rate_col] = (
                precincts[raw_col] / precincts["pop_total"].replace(0, np.nan)
            ).clip(0, 1).round(4)

    # Age composition rates
    age_rate_map = {
        "pct_18_24":  "pop_18_24",
        "pct_25_34":  "pop_25_34",
        "pct_65plus": "pop_65_74",   # we'll add 75plus below
    }
    if "pop_65_74" in precincts.columns and "pop_75plus" in precincts.columns:
        precincts["pop_65plus"] = precincts["pop_65_74"] + precincts["pop_75plus"]
        precincts["pct_65plus"] = (
            precincts["pop_65plus"] / precincts["pop_total"].replace(0, np.nan)
        ).clip(0, 1).round(4)

    for rate_col, raw_col in age_rate_map.items():
        if raw_col in precincts.columns and rate_col not in precincts.columns:
            precincts[rate_col] = (
                precincts[raw_col] / precincts["pop_total"].replace(0, np.nan)
            ).clip(0, 1).round(4)

    # ── Step 6: Clean up duplicate columns from merge ─────────────────────────
    # Drop redundant county/precinct cols brought in from voter file
    drop_cols = ["county_desc", "precinct_abbrv", "precinct_desc", "GEOID", "bg_GEOID"]
    drop_cols = [c for c in drop_cols if c in precincts.columns]
    precincts = precincts.drop(columns=drop_cols)

    # Rename for clarity in final output
    precincts = precincts.rename(columns={
        "county_nam": "county",
        "prec_id":    "precinct_id",
        "enr_desc":   "precinct_name",
    })

    # ── Step 7: Reproject to WGS84 and export GeoJSON ─────────────────────────
    print(f"\nReprojecting from {precincts.crs} → EPSG:4326...")
    precincts = precincts.to_crs(epsg=4326)

    # Fill any remaining NaN values
    for col in precincts.columns:
        if col == "geometry":
            continue
        if precincts[col].dtype in [float, int] or pd.api.types.is_numeric_dtype(precincts[col]):
            precincts[col] = precincts[col].fillna(0)
        else:
            precincts[col] = precincts[col].fillna("")

    print(f"Exporting to {OUTPUT_FILE}...")
    precincts.to_file(OUTPUT_FILE, driver="GeoJSON")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n✅ Done! {len(precincts):,} precincts saved to: {OUTPUT_FILE}")
    print(f"   Total columns: {len(precincts.columns)}")
    print(f"\n   Statewide Census totals (area-apportioned):")
    for col in ["pop_total", "pop_voting_age", "pop_18_24", "est_vap_total", "est_vap_youth"]:
        if col in precincts.columns:
            print(f"   {col:<25}: {precincts[col].sum():>12,.0f}")
    print(f"\n   Statewide voter totals:")
    for col in ["reg_total", "reg_active"]:
        if col in precincts.columns:
            print(f"   {col:<25}: {precincts[col].sum():>12,.0f}")
    print(f"\n   Registration rates:")
    for col in ["reg_rate", "reg_rate_youth"]:
        if col in precincts.columns:
            print(f"   {col:<25}: avg {precincts[col].mean():.1%}")
    print(f"\n   Sample turnout columns:")
    turnout_cols = [c for c in precincts.columns if c.startswith("turnout_")][:3]
    for col in turnout_cols:
        print(f"   {col:<30}: avg {precincts[col].mean():.1%}")
    print(f"\n   Bounding box: {precincts.total_bounds.round(4)}")


if __name__ == "__main__":
    main()