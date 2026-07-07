"""
interpolate_v3.py
=================
Fixed version addressing:
  1. Non-unique prec_id across counties → use composite key (county_nam + prec_id)
  2. Spatial coverage mismatch diagnosis → check if BGs and precincts actually overlap
  3. Correct merge so no row duplication

Run from project root:
    python data/processed/interpolate_v3.py
"""

import geopandas as gpd
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ── Paths ─────────────────────────────────────────────────────────────────────
# Use the cleaned precinct file from the previous step
PRECINCT_PATH = Path("data/processed/nc_precinct_turnout_CLEAN.geojson")
BG_PATH       = Path("data/processed/nc_blockgroup_demographics.geojson")
OUTPUT_PATH   = Path("data/processed/nc_precinct_with_population.geojson")

AREA_CRS    = "EPSG:6542"
VAP_FACTOR  = 0.85

POP_COLUMNS = [
    "total_pop", "male_pop", "female_pop",
    "white_pop", "black_pop", "native_pop", "asian_pop",
    "pacific_pop", "other_pop", "multiracial_pop", "hispanic_pop",
    "under_18", "age_18_24", "age_25_34",
    "age_35_44", "age_45_64", "age_65_plus",
]


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 0 — LOAD & VALIDATE
# ═══════════════════════════════════════════════════════════════════════════════

def load_and_validate():
    print("Loading cleaned precinct file...")
    precincts = gpd.read_file(PRECINCT_PATH)
    print(f"  → {len(precincts):,} precincts, CRS: {precincts.crs}")

    print("Loading block group file...")
    bg = gpd.read_file(BG_PATH)
    print(f"  → {len(bg):,} block groups, CRS: {bg.crs}")

    # ── Build composite key on precincts ──────────────────────────────────────
    # prec_id alone is NOT unique statewide — "206" appears in multiple counties.
    # We need county_nam + prec_id as the true unique identifier.
    precincts["_composite_key"] = (
        precincts["county_nam"].astype(str).str.strip().str.upper()
        + "__"
        + precincts["prec_id"].astype(str).str.strip().str.upper()
    )

    n_unique = precincts["_composite_key"].nunique()
    n_total  = len(precincts)
    print(f"\n  Unique composite keys (county+prec_id): {n_unique:,} / {n_total:,} rows")

    if n_unique < n_total:
        # Still some duplicates — keep the one with the largest geometry
        print(f"  ⚠ {n_total - n_unique} rows still duplicated on composite key")
        print(f"    Keeping largest geometry per composite key...")
        precincts["_area"] = precincts.geometry.area
        precincts = (
            precincts
            .sort_values("_area", ascending=False)
            .drop_duplicates(subset=["_composite_key"], keep="first")
            .drop(columns=["_area"])
            .reset_index(drop=True)
        )
        print(f"    → {len(precincts):,} precincts after final dedup")

    return bg, precincts


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — SPATIAL COVERAGE DIAGNOSTIC
# ═══════════════════════════════════════════════════════════════════════════════

def diagnose_spatial_coverage(bg: gpd.GeoDataFrame, precincts: gpd.GeoDataFrame):
    """
    Check whether the two layers actually spatially overlap.

    If block groups cover all of NC but precincts only cover certain counties,
    most block groups will find zero intersection → massive undercounting.
    """
    print("\n" + "─" * 60)
    print("SPATIAL COVERAGE DIAGNOSTIC")
    print("─" * 60)

    bg_proj   = bg.to_crs(AREA_CRS)
    prec_proj = precincts.to_crs(AREA_CRS)

    bg_bounds   = bg_proj.total_bounds    # [minx, miny, maxx, maxy]
    prec_bounds = prec_proj.total_bounds

    print(f"\nBlock group extent (m, EPSG:6542):")
    print(f"  X: {bg_bounds[0]:>12,.0f} → {bg_bounds[2]:>12,.0f}")
    print(f"  Y: {bg_bounds[1]:>12,.0f} → {bg_bounds[3]:>12,.0f}")

    print(f"\nPrecinct extent (m, EPSG:6542):")
    print(f"  X: {prec_bounds[0]:>12,.0f} → {prec_bounds[2]:>12,.0f}")
    print(f"  Y: {prec_bounds[1]:>12,.0f} → {prec_bounds[3]:>12,.0f}")

    # Check bounding box overlap
    x_overlap = (bg_bounds[0] < prec_bounds[2]) and (bg_bounds[2] > prec_bounds[0])
    y_overlap = (bg_bounds[1] < prec_bounds[3]) and (bg_bounds[3] > prec_bounds[1])

    if not (x_overlap and y_overlap):
        print("\n  ⛔ CRITICAL: The two layers do NOT overlap at all!")
        print("     Check that both files cover the same geographic area.")
        print("     Possible causes:")
        print("       - Precincts are from a different region than the block groups")
        print("       - One layer uses a different datum and wasn't reprojected correctly")
        return False

    # Count how many precincts each BG centroid falls within
    # (quick proxy for coverage without running the full overlay)
    bg_centroids = bg_proj.copy()
    bg_centroids.geometry = bg_proj.geometry.centroid
    joined = gpd.sjoin(bg_centroids, prec_proj[["_composite_key", "geometry"]],
                       how="left", predicate="within")
    n_matched = joined["_composite_key"].notna().sum()
    n_total   = len(bg_proj)

    print(f"\n  BG centroids that fall within a precinct: {n_matched:,} / {n_total:,}")
    pct = n_matched / n_total * 100
    print(f"  Coverage: {pct:.1f}%")

    if pct < 50:
        print(f"\n  ⚠ WARNING: Only {pct:.0f}% of block groups overlap the precinct layer.")
        print(f"     This means your precinct file does NOT cover all of NC.")
        print(f"     Counties covered by precincts:")
        if "county_nam" in precincts.columns:
            counties = sorted(precincts["county_nam"].dropna().unique())
            print(f"     {counties}")
        print(f"\n     Your block groups cover all of NC ({len(bg):,} BGs).")
        print(f"     The interpolation will only produce estimates for the")
        print(f"     counties/precincts present in your precinct file.")
        print(f"     This is expected if you're working with a subset of NC.")
    elif pct >= 80:
        print(f"\n  ✓ Good spatial overlap — proceeding with interpolation.")

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — INTERPOLATION
# ═══════════════════════════════════════════════════════════════════════════════

def run_interpolation(bg: gpd.GeoDataFrame, precincts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    print("\n" + "─" * 60)
    print("RUNNING AREAL WEIGHTED INTERPOLATION")
    print("─" * 60)

    # Reproject
    bg_proj   = bg.to_crs(AREA_CRS).copy()
    prec_proj = precincts.to_crs(AREA_CRS).copy()

    # Fix geometries
    bg_proj.geometry   = bg_proj.geometry.buffer(0)
    prec_proj.geometry = prec_proj.geometry.buffer(0)

    # Block group areas
    bg_proj["bg_area_m2"] = bg_proj.geometry.area
    bg_proj = bg_proj[bg_proj["bg_area_m2"] > 0]

    # ── Spatial intersection ──────────────────────────────────────────────────
    print(f"\nIntersecting {len(bg_proj):,} BGs × {len(prec_proj):,} precincts...")
    print("  (may take 1–3 minutes for all of NC)")

    inter = gpd.overlay(bg_proj, prec_proj, how="intersection", keep_geom_type=True)
    print(f"  → {len(inter):,} intersection slices")

    if len(inter) == 0:
        raise RuntimeError("No intersections found — the two layers don't overlap.")

    # ── Post-intersection diagnostic ──────────────────────────────────────────
    if len(inter) < len(bg_proj) * 2:
        print(f"\n  ⚠ LOW SLICE COUNT — diagnosing precinct geometry coverage...")
        total_prec_area_km2 = prec_proj.geometry.area.sum() / 1e6
        total_nc_area_km2   = 139_391  # NC land area km²
        coverage_pct        = total_prec_area_km2 / total_nc_area_km2 * 100
        print(f"    Total precinct polygon area: {total_prec_area_km2:,.0f} km²")
        print(f"    NC total land area:          {total_nc_area_km2:,} km²")
        print(f"    Precinct coverage of NC:     {coverage_pct:.1f}%")
        if coverage_pct < 50:
            print(f"\n    ROOT CAUSE: Precinct polygons cover only {coverage_pct:.0f}% of NC's")
            print(f"    land area, so most block groups don't intersect any precinct.")
            print(f"    This means either:")
            print(f"      (a) The precinct file uses point/centroid geometries, not polygons")
            print(f"      (b) The precinct polygons are tiny representative blocks,")
            print(f"          not full precinct boundaries")
            print(f"      (c) The file was built from census blocks, not precinct boundaries")
            print(f"\n    RECOMMENDATION: Check your precinct source. You may need the")
            print(f"    official NC SBE precinct boundary shapefile instead.")
            print(f"    Source: https://www.ncsbe.gov/results-data/precinct-maps")
        else:
            print(f"    Coverage looks reasonable — gaps are likely water/boundary areas.")

    # ── Areal weights ─────────────────────────────────────────────────────────
    inter["slice_area_m2"] = inter.geometry.area
    inter["weight"]        = (inter["slice_area_m2"] / inter["bg_area_m2"]).clip(0, 1)

    print(f"\n  Weight stats:")
    print(f"    Mean weight per slice: {inter['weight'].mean():.4f}")
    print(f"    Max weight:            {inter['weight'].max():.4f}")
    print(f"    Slices with w > 0.5:   {(inter['weight'] > 0.5).sum():,}")

    # ── Identify composite key column after overlay ───────────────────────────
    # geopandas overlay adds _1 / _2 suffixes on name collisions
    key_col = "_composite_key"
    if key_col not in inter.columns:
        candidates = [c for c in inter.columns if "_composite_key" in c]
        if candidates:
            key_col = candidates[0]
            print(f"  Using '{key_col}' as the precinct composite key after overlay")
        else:
            print(f"  ⚠ Could not find composite key in overlay output.")
            print(f"    Available columns: {list(inter.columns)}")
            raise KeyError("composite key column missing from intersection")

    # ── Allocate population ───────────────────────────────────────────────────
    alloc_cols = []
    for col in POP_COLUMNS:
        if col in inter.columns:
            inter[f"alloc_{col}"] = inter[col] * inter["weight"]
            alloc_cols.append(f"alloc_{col}")
        else:
            print(f"  ⚠ Column '{col}' missing from block groups — skipping")

    inter["alloc_slice_area"] = inter["slice_area_m2"]

    # ── Aggregate by composite key ────────────────────────────────────────────
    grouped = inter.groupby(key_col)[alloc_cols + ["alloc_slice_area"]].sum()
    grouped.columns = [
        "est_covered_area_m2" if c == "alloc_slice_area" else c.replace("alloc_", "est_")
        for c in grouped.columns
    ]

    print(f"\n  Population estimates computed for {len(grouped):,} precincts")

    # ── Sanity check: compare estimated vs NC known total ────────────────────
    if "est_total_pop" in grouped.columns:
        est_state = grouped["est_total_pop"].sum()
        print(f"\n  Estimated state total population: {est_state:,.0f}")
        print(f"  (NC 2020 Census actual: ~10,439,388)")
        if est_state > 15_000_000:
            print(f"  ⚠ Estimate is too high — likely indicates duplicate merging downstream")
        elif est_state < 5_000_000:
            coverage_pct = est_state / 10_439_388 * 100
            print(f"  ℹ This is {coverage_pct:.0f}% of NC's population,")
            print(f"    consistent with a partial-state precinct file.")

    # ── Derive Youth VAP ──────────────────────────────────────────────────────
    if "est_total_pop" in grouped.columns:
        grouped["est_total_vap"]  = grouped["est_total_pop"] * VAP_FACTOR

    if "est_age_18_24" in grouped.columns:
        grouped["est_youth_vap"]  = grouped["est_age_18_24"]

    if "est_age_18_24" in grouped.columns and "est_age_25_34" in grouped.columns:
        grouped["est_youth_broad_vap"] = grouped["est_age_18_24"] + grouped["est_age_25_34"]

    if "est_youth_vap" in grouped.columns and "est_total_vap" in grouped.columns:
        grouped["est_youth_vap_pct"] = (
            grouped["est_youth_vap"] / grouped["est_total_vap"].replace(0, np.nan)
        )

    if "est_age_18_24" in grouped.columns and "est_total_pop" in grouped.columns:
        grouped["est_pct_youth"] = (
            grouped["est_age_18_24"] / grouped["est_total_pop"].replace(0, np.nan)
        )

    # ── Coverage quality ──────────────────────────────────────────────────────
    prec_areas = prec_proj.set_index("_composite_key")["geometry"].area
    grouped["bg_coverage"] = (
        grouped["est_covered_area_m2"] / prec_areas.reindex(grouped.index)
    ).clip(0, 1)
    grouped = grouped.drop(columns=["est_covered_area_m2"], errors="ignore")

    low_cov = (grouped["bg_coverage"] < 0.8).sum()
    if low_cov:
        print(f"\n  ⚠ {low_cov} precincts have BG coverage < 80%")

    # ── Merge back onto precinct GeoDataFrame ────────────────────────────────
    # Use the composite key for a clean 1-to-1 join — no row explosion
    print(f"\nMerging estimates back onto precinct layer...")
    grouped_reset = grouped.reset_index().rename(columns={key_col: "_composite_key"})

    result = precincts.merge(grouped_reset, on="_composite_key", how="left")

    # Verify no row explosion
    assert len(result) == len(precincts), (
        f"Row count changed after merge: {len(precincts):,} → {len(result):,}. "
        f"Composite key is not unique."
    )

    matched = result["est_total_pop"].notna().sum()
    print(f"  {matched:,} / {len(result):,} precincts matched with population data")
    if matched < len(result):
        unmatched = result[result["est_total_pop"].isna()]["_composite_key"].tolist()
        print(f"  Unmatched: {unmatched[:10]}")

    # ── Youth registration gap ────────────────────────────────────────────────
    if "youth_registered" in result.columns and "est_youth_vap" in result.columns:
        result["youth_reg_gap"]    = (
            result["est_youth_vap"] - result["youth_registered"].fillna(0)
        )
        result["youth_reg_rate"]   = (
            result["youth_registered"].fillna(0)
            / result["est_youth_vap"].replace(0, np.nan)
        )
        result["youth_unreg_rate"] = 1 - result["youth_reg_rate"]

        # Negative gaps mean more registered than estimated VAP — flag them
        n_neg = (result["youth_reg_gap"] < -5).sum()
        if n_neg > 0:
            print(f"\n  ℹ {n_neg} precincts where youth_registered > est_youth_vap by >5")
            print(f"    This is estimation error — the areal interpolation slightly")
            print(f"    underestimates VAP in some precincts. Treat youth_reg_gap < 0")
            print(f"    as approximately zero (fully registered) for those precincts.")

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

def print_summary(gdf: gpd.GeoDataFrame):
    print("\n" + "=" * 60)
    print("FINAL RESULTS SUMMARY")
    print("=" * 60)

    for col, label in [
        ("est_total_pop",   "Est. total population"),
        ("est_youth_vap",   "Est. youth VAP (18–24)"),
        ("est_total_vap",   "Est. total VAP (85% rule)"),
    ]:
        if col in gdf.columns:
            print(f"\n{label}:")
            print(f"  State total:       {gdf[col].sum():>12,.0f}")
            print(f"  Per-precinct mean: {gdf[col].mean():>12,.1f}")
            print(f"  Per-precinct max:  {gdf[col].max():>12,.1f}")

    if "youth_registered" in gdf.columns and "est_youth_vap" in gdf.columns:
        yr   = gdf["youth_registered"].fillna(0).sum()
        yvap = gdf["est_youth_vap"].fillna(0).sum()
        if yvap > 0:
            print(f"\nYouth registration summary:")
            print(f"  Youth registered:        {yr:>10,.0f}")
            print(f"  Youth VAP estimated:     {yvap:>10,.0f}")
            print(f"  Registration rate:       {yr/yvap*100:>9.1f}%")
            print(f"  Unregistered (gap):      {yvap - yr:>10,.0f}")

    if "bg_coverage" in gdf.columns:
        print(f"\nBlock group coverage:")
        print(f"  Mean:   {gdf['bg_coverage'].mean()*100:.1f}%")
        print(f"  ≥ 99%:  {(gdf['bg_coverage'] >= 0.99).sum():,} precincts")
        print(f"  ≥ 80%:  {(gdf['bg_coverage'] >= 0.80).sum():,} precincts")
        print(f"  < 80%:  {(gdf['bg_coverage'] < 0.80).sum():,} precincts")

    if "youth_reg_gap" in gdf.columns:
        show = [c for c in ["county_nam", "enr_desc", "prec_id",
                             "est_youth_vap", "youth_registered",
                             "youth_reg_gap", "youth_unreg_rate", "bg_coverage"]
                if c in gdf.columns]
        top10 = (
            gdf[show].dropna(subset=["youth_reg_gap"])
            .nlargest(10, "youth_reg_gap")
        )
        print(f"\nTop 10 precincts by unregistered youth (highest-opportunity):")
        print(top10.to_string(index=False))

    print("\n" + "=" * 60)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("BLOCK GROUP → PRECINCT INTERPOLATION  (v3)")
    print("=" * 60 + "\n")

    bg, precincts = load_and_validate()

    # Spatial coverage check — won't abort, just informs you
    diagnose_spatial_coverage(bg, precincts)

    result = run_interpolation(bg, precincts)

    # Save — reproject to WGS84 for GeoJSON
    print(f"\nSaving to {OUTPUT_PATH} ...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_out = result.to_crs("EPSG:4326")
    result_out.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"  ✓ GeoJSON: {OUTPUT_PATH}  ({len(result_out):,} features)")

    csv_path = OUTPUT_PATH.with_suffix(".csv")
    result_out.drop(columns="geometry").to_csv(csv_path, index=False)
    print(f"  ✓ CSV:     {csv_path}")

    print_summary(result)

    return result


if __name__ == "__main__":
    result = main()