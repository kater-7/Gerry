"""
Areal Weighted Interpolation: Block Groups → Precincts
======================================================
Youth Power Map project — NC Gerrymandering Analysis

PURPOSE:
    Census population data (block groups) and voter registration data (precincts)
    use incompatible geographies. This script estimates block-group population
    figures at the precinct level using areal weighted interpolation.

METHOD — Areal Weighted Interpolation:
    For every (block_group × precinct) overlap pair:
        weight = area_of_intersection / area_of_block_group

    Then for each precinct:
        estimated_pop = SUM over all overlapping BGs of (bg_pop × weight)

    Assumption: population is uniformly distributed within each block group.
    This is a standard GIS technique and works well at the block-group level
    (block groups are designed to be ~600–3,000 people in roughly homogeneous areas).

KEY CHALLENGE RESOLVED HERE:
    Block groups  → EPSG:4269  (geographic, decimal degrees, NAD83)
    Precincts     → EPSG:2264  (NC State Plane, feet, NAD83)
    Both must be projected to a common equal-area CRS before computing areas.
    We use EPSG:6542 (NC State Plane meters) for accurate area calculations.

INPUTS:
    data/processed/nc_blockgroup_demographics.geojson
    data/processed/nc_precinct_turnout.geojson

OUTPUT:
    data/processed/nc_precinct_with_population.geojson  — precincts enriched with
        estimated population columns, youth VAP, and readiness for youth power mapping

COLUMNS ADDED TO PRECINCT OUTPUT:
    est_total_pop       — estimated total population
    est_under_18        — estimated population under 18
    est_age_18_24       — estimated 18–24 population
    est_age_25_34       — estimated 25–34 population
    est_youth_vap       — estimated youth voting-age population (18–24)
                          using the 85% VAP national average adjustment
    est_total_vap       — estimated total VAP (85% × total_pop)
    est_youth_vap_adj   — youth VAP as share of total VAP
    est_pct_youth       — pct of total pop that is youth (18–24)
    est_white_pop       — race/ethnicity columns for demographic analysis
    est_black_pop
    est_hispanic_pop
    est_other_pop
    bg_coverage         — fraction of precinct area covered by block groups (QC metric)
                          values < 0.8 mean the precinct had sparse BG coverage
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", message=".*CRS.*")

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

# Paths — adjust if your working directory differs
BG_PATH       = Path("data/processed/nc_blockgroup_demographics.geojson")
PRECINCT_PATH = Path("data/processed/nc_precinct_turnout.geojson")
OUTPUT_PATH   = Path("data/processed/nc_precinct_with_population.geojson")

# CRS for area calculations (NC State Plane, meters — equal-area, appropriate for NC)
# EPSG:6542 = NAD83(2011) / North Carolina (meters)
# Using 6542 instead of 2264 because 2264 is in feet and mixing units is error-prone
AREA_CRS = "EPSG:6542"

# VAP adjustment factor (national average: ~85% of total population is 18+)
VAP_FACTOR = 0.85

# Population columns from block group data to interpolate
# These are the raw count columns — percentages are re-derived after interpolation
POP_COLUMNS = [
    "total_pop",
    "male_pop",
    "female_pop",
    "white_pop",
    "black_pop",
    "native_pop",
    "asian_pop",
    "pacific_pop",
    "other_pop",
    "multiracial_pop",
    "hispanic_pop",
    "under_18",
    "age_18_24",
    "age_25_34",
    "age_35_44",
    "age_45_64",
    "age_65_plus",
]

# Precinct ID column (used for grouping results)
PRECINCT_ID_COL = "prec_id"


# ─────────────────────────────────────────────
# STEP 1 — LOAD DATA
# ─────────────────────────────────────────────

def load_data(bg_path: Path, precinct_path: Path):
    """Load both GeoJSON files and validate they loaded correctly."""
    print("Loading block group data...")
    bg = gpd.read_file(bg_path)
    print(f"  → {len(bg):,} block groups, CRS: {bg.crs}")

    print("Loading precinct data...")
    precincts = gpd.read_file(precinct_path)
    print(f"  → {len(precincts):,} precincts, CRS: {precincts.crs}")

    # Validate population columns exist
    missing = [c for c in POP_COLUMNS if c not in bg.columns]
    if missing:
        raise ValueError(f"Missing columns in block group data: {missing}")

    # Check for null geometries
    bg_null = bg.geometry.isna().sum()
    prec_null = precincts.geometry.isna().sum()
    if bg_null > 0:
        print(f"  ⚠ WARNING: {bg_null} block groups have null geometry — dropping them")
        bg = bg.dropna(subset=["geometry"])
    if prec_null > 0:
        print(f"  ⚠ WARNING: {prec_null} precincts have null geometry — dropping them")
        precincts = precincts.dropna(subset=["geometry"])

    return bg, precincts


# ─────────────────────────────────────────────
# STEP 2 — REPROJECT TO COMMON CRS
# ─────────────────────────────────────────────

def align_crs(bg: gpd.GeoDataFrame, precincts: gpd.GeoDataFrame, target_crs: str):
    """
    Reproject both layers to a common equal-area CRS for accurate area math.

    The block groups come in EPSG:4269 (geographic degrees) and precincts in
    EPSG:2264 (NC State Plane, feet). Neither is suitable for area calculations
    — degrees are not equal-area and feet introduce large numbers that are
    harder to reason about. We reproject both to EPSG:6542 (NC State Plane, meters).
    """
    print(f"\nReprojecting both layers to {target_crs} for area calculations...")
    bg = bg.to_crs(target_crs)
    precincts = precincts.to_crs(target_crs)
    print(f"  ✓ Block groups reprojected")
    print(f"  ✓ Precincts reprojected")
    return bg, precincts


# ─────────────────────────────────────────────
# STEP 3 — COMPUTE BLOCK GROUP AREAS
# ─────────────────────────────────────────────

def compute_bg_areas(bg: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute the area of each block group in the projected CRS (m²).

    We store this before any intersection so we always divide by the
    ORIGINAL block group area, not a clipped intersection area.
    """
    bg = bg.copy()
    bg["bg_area_m2"] = bg.geometry.area

    # Sanity check — warn if any block group has zero area
    zero_area = (bg["bg_area_m2"] == 0).sum()
    if zero_area > 0:
        print(f"  ⚠ WARNING: {zero_area} block groups have zero area — they will be dropped")
        bg = bg[bg["bg_area_m2"] > 0]

    print(f"  Block group areas computed (range: "
          f"{bg['bg_area_m2'].min()/1e6:.2f} – {bg['bg_area_m2'].max()/1e6:.2f} km²)")
    return bg


# ─────────────────────────────────────────────
# STEP 4 — SPATIAL INTERSECTION (OVERLAY)
# ─────────────────────────────────────────────

def compute_intersection(bg: gpd.GeoDataFrame, precincts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute the geometric intersection of every block group with every precinct.

    geopandas overlay(how='intersection') returns a new GeoDataFrame where each
    row is a (block_group × precinct) overlap polygon. Columns from both input
    layers are included (with suffixes _1 and _2 if names conflict).

    This is the most expensive step — O(n × m) potential pairs, though the
    spatial index makes it much faster in practice. For all of NC this may
    take 1–3 minutes.
    """
    print("\nComputing spatial intersection (block groups × precincts)...")
    print("  This may take 1–3 minutes for all of NC...")

    # Ensure both have valid geometries before overlay
    bg = bg[bg.geometry.is_valid]
    precincts = precincts[precincts.geometry.is_valid]

    # Fix any invalid geometries with a zero-width buffer
    n_invalid_bg = (~bg.geometry.is_valid).sum()
    n_invalid_pr = (~precincts.geometry.is_valid).sum()
    if n_invalid_bg > 0:
        print(f"  Fixing {n_invalid_bg} invalid block group geometries...")
        bg.geometry = bg.geometry.buffer(0)
    if n_invalid_pr > 0:
        print(f"  Fixing {n_invalid_pr} invalid precinct geometries...")
        precincts.geometry = precincts.geometry.buffer(0)

    intersection = gpd.overlay(bg, precincts, how="intersection", keep_geom_type=True)

    print(f"  → {len(intersection):,} intersection polygons created")
    print(f"     (each row = one block group slice within one precinct)")
    return intersection


# ─────────────────────────────────────────────
# STEP 5 — COMPUTE AREAL WEIGHTS & INTERPOLATE
# ─────────────────────────────────────────────

def interpolate_population(
    intersection: gpd.GeoDataFrame,
    precinct_id_col: str,
    pop_columns: list,
) -> pd.DataFrame:
    """
    Core interpolation logic.

    For each (block_group × precinct) intersection slice:
        weight = area_of_slice / area_of_block_group

    For each population column:
        allocated_pop = bg_population × weight

    Then aggregate by precinct by summing all allocated populations.

    Returns a DataFrame (not GeoDataFrame) indexed by precinct_id.
    """
    print("\nComputing areal weights and interpolating population...")

    inter = intersection.copy()

    # Area of each intersection slice
    inter["slice_area_m2"] = inter.geometry.area

    # Weight = slice area / total block group area
    # bg_area_m2 was carried through from the block group layer
    inter["weight"] = inter["slice_area_m2"] / inter["bg_area_m2"]

    # Sanity check weights
    max_weight = inter["weight"].max()
    if max_weight > 1.01:
        print(f"  ⚠ WARNING: Some weights exceed 1.0 (max={max_weight:.3f}) — "
              f"this can happen with projection edge effects. Values will be clipped.")
        inter["weight"] = inter["weight"].clip(0, 1)

    # Allocate each population column: allocated = pop × weight
    for col in pop_columns:
        if col in inter.columns:
            inter[f"alloc_{col}"] = inter[col] * inter["weight"]
        else:
            print(f"  ⚠ Column '{col}' not found in intersection — skipping")

    # The precinct ID column may have a suffix (_1 or _2) if there was a name
    # collision during the overlay. Detect it.
    if precinct_id_col not in inter.columns:
        candidates = [c for c in inter.columns if c.startswith(precinct_id_col)]
        if candidates:
            precinct_id_col = candidates[0]
            print(f"  Using '{precinct_id_col}' as the precinct ID column after overlay")
        else:
            raise ValueError(
                f"Could not find precinct ID column '{precinct_id_col}' in intersection. "
                f"Available columns: {list(inter.columns)}"
            )

    # Aggregate by precinct — sum all allocated values
    alloc_cols = [f"alloc_{col}" for col in pop_columns if f"alloc_{col}" in inter.columns]

    # Also compute the total block-group area that overlapped each precinct
    # (used for the quality-control coverage metric)
    inter["alloc_slice_area"] = inter["slice_area_m2"]

    grouped = inter.groupby(precinct_id_col)[alloc_cols + ["alloc_slice_area"]].sum()

    # Rename alloc_ prefix to est_ for clarity in output
    rename = {f"alloc_{col}": f"est_{col}" for col in pop_columns}
    rename["alloc_slice_area"] = "est_covered_area_m2"
    grouped = grouped.rename(columns=rename)

    print(f"  ✓ Interpolation complete")
    print(f"  → Results for {len(grouped):,} precincts")
    return grouped


# ─────────────────────────────────────────────
# STEP 6 — DERIVE YOUTH VAP COLUMNS
# ─────────────────────────────────────────────

def derive_youth_vap(pop_df: pd.DataFrame, vap_factor: float) -> pd.DataFrame:
    """
    Derive youth VAP estimates using the 85% national average adjustment.

    VAP (Voting Age Population) methodology:
        est_total_vap   = est_total_pop × 0.85
            (85% of total pop is estimated to be 18+ / eligible to vote)

        est_youth_vap   = est_age_18_24
            (The 18–24 cohort IS the youth VAP — no adjustment needed here
             because the census already counts this age group directly.
             The 85% factor was needed to *estimate* total VAP from total pop,
             but for the 18–24 cohort we have the actual count from the census.)

    Youth VAP rate:
        est_youth_vap_rate = est_youth_vap / est_total_vap
            (What fraction of the eligible electorate is youth?)

    Youth registration gap:
        This is computed AFTER merging with precinct registration data:
        youth_reg_gap = est_youth_vap - youth_registered
            (Estimated youth who are eligible but not registered)
    """
    df = pop_df.copy()

    # Total VAP: 85% of total estimated population
    if "est_total_pop" in df.columns:
        df["est_total_vap"] = df["est_total_pop"] * vap_factor

    # Youth VAP: the 18–24 cohort directly from census interpolation
    if "est_age_18_24" in df.columns:
        df["est_youth_vap"] = df["est_age_18_24"]

    # Youth VAP as share of total VAP
    if "est_youth_vap" in df.columns and "est_total_vap" in df.columns:
        df["est_youth_vap_pct"] = df["est_youth_vap"] / df["est_total_vap"].replace(0, np.nan)

    # Youth (18–24) as share of total population
    if "est_age_18_24" in df.columns and "est_total_pop" in df.columns:
        df["est_pct_youth"] = df["est_age_18_24"] / df["est_total_pop"].replace(0, np.nan)

    # Under-35 population (often useful for youth organizing)
    if all(c in df.columns for c in ["est_age_18_24", "est_age_25_34"]):
        df["est_age_18_34"] = df["est_age_18_24"] + df["est_age_25_34"]
        df["est_youth_broad_vap"] = df["est_age_18_34"]

    return df


# ─────────────────────────────────────────────
# STEP 7 — COMPUTE COVERAGE QUALITY METRIC
# ─────────────────────────────────────────────

def compute_coverage(
    pop_df: pd.DataFrame,
    precincts: gpd.GeoDataFrame,
    precinct_id_col: str,
) -> pd.DataFrame:
    """
    Compute bg_coverage: fraction of each precinct's area covered by block groups.

    A value of 1.0 means the entire precinct was covered by block groups.
    Values < 0.8 indicate that a significant part of the precinct had no
    matching block group — estimates for those precincts should be treated
    with caution.

    Common causes of low coverage:
    - Precincts extend into water bodies (no BGs over water)
    - State/county border edge effects
    - Block group data doesn't include every county
    """
    prec_areas = precincts.set_index(precinct_id_col)["geometry"].area.rename("precinct_area_m2")
    pop_df = pop_df.join(prec_areas, how="left")

    if "est_covered_area_m2" in pop_df.columns and "precinct_area_m2" in pop_df.columns:
        pop_df["bg_coverage"] = (
            pop_df["est_covered_area_m2"] / pop_df["precinct_area_m2"]
        ).clip(0, 1)

        low_coverage = (pop_df["bg_coverage"] < 0.8).sum()
        if low_coverage > 0:
            print(f"\n  ⚠ {low_coverage} precincts have BG coverage < 80%")
            print(f"     (population estimates for these precincts are less reliable)")
            print(f"     Consider masking these on the Youth Power Map or flagging them.")

    pop_df = pop_df.drop(columns=["est_covered_area_m2", "precinct_area_m2"], errors="ignore")
    return pop_df


# ─────────────────────────────────────────────
# STEP 8 — MERGE BACK WITH PRECINCT LAYER
# ─────────────────────────────────────────────

def merge_with_precincts(
    pop_df: pd.DataFrame,
    precincts: gpd.GeoDataFrame,
    precinct_id_col: str,
) -> gpd.GeoDataFrame:
    """
    Merge the interpolated population estimates back onto the precinct GeoDataFrame.

    The result is a GeoDataFrame with:
    - All original precinct columns (registration, turnout, geometry, etc.)
    - All interpolated population estimates (est_* columns)
    - Derived youth VAP columns
    - bg_coverage quality metric
    """
    print(f"\nMerging population estimates back onto precinct layer...")

    # Reset index so precinct_id_col becomes a regular column for the merge
    pop_df = pop_df.reset_index()

    result = precincts.merge(
        pop_df,
        on=precinct_id_col,
        how="left",
        suffixes=("", "_interp"),
    )

    # Report how many precincts got population data
    matched = result["est_total_pop"].notna().sum()
    print(f"  → {matched:,} of {len(result):,} precincts matched with population data")

    unmatched = len(result) - matched
    if unmatched > 0:
        print(f"  ⚠ {unmatched} precincts had no overlapping block groups")
        missing_ids = result.loc[result["est_total_pop"].isna(), precinct_id_col].tolist()
        print(f"     Unmatched precinct IDs: {missing_ids[:20]}")

    return result


# ─────────────────────────────────────────────
# STEP 9 — COMPUTE YOUTH REGISTRATION GAP
# ─────────────────────────────────────────────

def compute_registration_gap(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Compute the gap between estimated youth VAP and actual youth registered voters.

    This is the core "Youth Power Map" metric:
        youth_reg_gap      = est_youth_vap - youth_registered
            (number of eligible youth who are NOT registered)

        youth_reg_gap_rate = youth_reg_gap / est_youth_vap
            (fraction of eligible youth who are NOT registered)
            → High values = high opportunity precincts for registration drives

        youth_reg_rate     = youth_registered / est_youth_vap
            (fraction of eligible youth who ARE registered)
            → The inverse; useful for ranking

    NOTE: These gaps can be slightly negative if youth_registered slightly
    exceeds the estimated youth_vap due to estimation error. Flag these
    as data quality issues rather than treating them as real negatives.
    """
    if "est_youth_vap" in gdf.columns and "youth_registered" in gdf.columns:
        gdf["youth_reg_gap"] = gdf["est_youth_vap"] - gdf["youth_registered"].fillna(0)
        gdf["youth_reg_rate"] = (
            gdf["youth_registered"].fillna(0) / gdf["est_youth_vap"].replace(0, np.nan)
        )
        gdf["youth_unreg_rate"] = 1 - gdf["youth_reg_rate"]

        # Flag suspicious values (negative gap = more registered than estimated VAP)
        n_negative = (gdf["youth_reg_gap"] < 0).sum()
        if n_negative > 0:
            print(f"\n  ℹ {n_negative} precincts have youth_registered > est_youth_vap")
            print(f"     This is normal for estimation error; gaps set negative are valid.")
            print(f"     Consider treating |gap| < 10 as 'approximately zero'.")

    return gdf


# ─────────────────────────────────────────────
# STEP 10 — SUMMARY STATISTICS
# ─────────────────────────────────────────────

def print_summary(gdf: gpd.GeoDataFrame):
    """Print a summary of the interpolation results for QC."""
    print("\n" + "=" * 60)
    print("INTERPOLATION SUMMARY")
    print("=" * 60)

    if "est_total_pop" in gdf.columns:
        print(f"\nEstimated total population (all precincts):")
        print(f"  Sum:    {gdf['est_total_pop'].sum():>12,.0f}")
        print(f"  Mean:   {gdf['est_total_pop'].mean():>12,.0f} per precinct")
        print(f"  Median: {gdf['est_total_pop'].median():>12,.0f} per precinct")

    if "est_youth_vap" in gdf.columns:
        print(f"\nEstimated youth VAP (18–24) (all precincts):")
        print(f"  Sum:    {gdf['est_youth_vap'].sum():>12,.0f}")
        print(f"  Mean:   {gdf['est_youth_vap'].mean():>12,.0f} per precinct")

    if "youth_registered" in gdf.columns and "est_youth_vap" in gdf.columns:
        total_youth_reg = gdf["youth_registered"].sum()
        total_youth_vap = gdf["est_youth_vap"].sum()
        print(f"\nYouth registration overview:")
        print(f"  Total youth registered:    {total_youth_reg:>12,.0f}")
        print(f"  Total youth VAP estimated: {total_youth_vap:>12,.0f}")
        print(f"  Overall registration rate: {total_youth_reg/total_youth_vap*100:>11.1f}%")
        print(f"  Overall registration gap:  {total_youth_vap - total_youth_reg:>12,.0f} "
              f"(eligible but not registered)")

    if "bg_coverage" in gdf.columns:
        print(f"\nBlock group coverage quality:")
        print(f"  Mean coverage:   {gdf['bg_coverage'].mean()*100:.1f}%")
        print(f"  Full coverage (≥99%): {(gdf['bg_coverage'] >= 0.99).sum():>6,} precincts")
        print(f"  Good coverage (≥80%): {(gdf['bg_coverage'] >= 0.80).sum():>6,} precincts")
        print(f"  Low coverage  (<80%): {(gdf['bg_coverage'] < 0.80).sum():>6,} precincts")

    if "youth_reg_gap" in gdf.columns:
        print(f"\nTop 10 precincts by youth registration gap (highest opportunity):")
        top10 = (
            gdf[["prec_id", "county_nam", "est_youth_vap", "youth_registered", "youth_reg_gap"]]
            .dropna()
            .nlargest(10, "youth_reg_gap")
        )
        print(top10.to_string(index=False))

    print("\n" + "=" * 60)


# ─────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BLOCK GROUP → PRECINCT AREAL INTERPOLATION")
    print("NC Youth Power Map Project")
    print("=" * 60 + "\n")

    # ── 1. Load ──────────────────────────────
    bg, precincts = load_data(BG_PATH, PRECINCT_PATH)

    # ── 2. Reproject ─────────────────────────
    bg, precincts = align_crs(bg, precincts, AREA_CRS)

    # ── 3. Block group areas ─────────────────
    print("\nComputing block group areas...")
    bg = compute_bg_areas(bg)

    # ── 4. Spatial intersection ───────────────
    intersection = compute_intersection(bg, precincts)

    # ── 5. Interpolate population ─────────────
    pop_df = interpolate_population(intersection, PRECINCT_ID_COL, POP_COLUMNS)

    # ── 6. Derive youth VAP columns ───────────
    print("\nDeriving youth VAP estimates...")
    pop_df = derive_youth_vap(pop_df, VAP_FACTOR)

    # ── 7. Coverage quality metric ────────────
    print("\nComputing block group coverage quality metric...")
    pop_df = compute_coverage(pop_df, precincts, PRECINCT_ID_COL)

    # ── 8. Merge back with precincts ──────────
    result = merge_with_precincts(pop_df, precincts, PRECINCT_ID_COL)

    # ── 9. Youth registration gap ─────────────
    print("\nComputing youth registration gap...")
    result = compute_registration_gap(result)

    # ── 10. Write output ──────────────────────
    print(f"\nWriting output to {OUTPUT_PATH}...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Reproject back to WGS84 for GeoJSON compatibility (most mapping tools expect this)
    result = result.to_crs("EPSG:4326")
    result.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"  ✓ Saved {len(result):,} features to {OUTPUT_PATH}")

    # ── 11. Summary ───────────────────────────
    print_summary(result)

    # Also export a flat CSV for tabular analysis / joining
    csv_path = OUTPUT_PATH.with_suffix(".csv")
    result.drop(columns="geometry").to_csv(csv_path, index=False)
    print(f"  ✓ CSV (no geometry) saved to {csv_path}")

    return result


if __name__ == "__main__":
    result = main()