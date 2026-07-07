"""
export_cong_tiger.py
---------------------
Joins simulation results to Census TIGER congressional district
boundaries (14 proper district polygons) and exports for ArcGIS Online.

Outputs:
  nc_cong_sim_{pct}pct.geojson   -- for ArcGIS Online
  nc_cong_sim_{pct}pct.zip       -- zipped shapefile alternative

Requirements:
  pip install geopandas pandas
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import zipfile
import os
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
YOUTH_UPLIFT = 0.10   # match your simulator run
TIGER_SHP    = r"data\raw\shapefiles\tl_2024_37_cd119\tl_2024_37_cd119.shp"
PCT_LABEL    = f"{int(YOUTH_UPLIFT * 100)}pct"
DIST_CSV     = f"sim_district_results_{PCT_LABEL}.csv"
GEOJSON_OUT  = f"nc_cong_sim_{PCT_LABEL}.geojson"
SHP_BASE     = f"nc_cong_sim_{PCT_LABEL}"
ZIP_OUT      = f"nc_cong_sim_{PCT_LABEL}.zip"
# ──────────────────────────────────────────────────────────────────────────────


def main():
    pct = int(YOUTH_UPLIFT * 100)
    print(f"Building congressional district map — {pct}% youth uplift\n")

    # ── Load TIGER district boundaries ────────────────────────────────────────
    print("Loading TIGER congressional district boundaries...")
    tiger = gpd.read_file(TIGER_SHP)
    tiger["cong_dist"] = pd.to_numeric(tiger["CD119FP"], errors="coerce")
    tiger = tiger[["cong_dist", "NAMELSAD", "geometry"]].copy()
    tiger = tiger.to_crs(epsg=4326)
    print(f"  {len(tiger):,} districts. CRS: EPSG:4326")
    print(f"  Districts: {sorted(tiger['cong_dist'].dropna().astype(int).tolist())}")
    print(f"  Bounds: {tiger.total_bounds.round(3)}")

    # ── Load simulation district results ──────────────────────────────────────
    print(f"\nLoading simulation results: {DIST_CSV}...")
    dist_df = pd.read_csv(DIST_CSV)
    cong    = dist_df[dist_df["district_type"] == "cong_dist"].copy()
    cong["district"] = pd.to_numeric(cong["district"], errors="coerce")
    print(f"  {len(cong)} congressional district result rows.")

    # Keep key columns
    keep = [
        "district",
        "base_winner", "sim_winner_raw", "sim_winner_blend",
        "base_margin", "sim_margin_raw", "sim_margin_blend",
        "flipped_raw", "flipped_blend",
        "base_trump", "base_harris",
        "sim_trump_blend", "sim_harris_blend",
    ]
    keep  = [c for c in keep if c in cong.columns]
    cong  = cong[keep].copy()

    for col in ["base_margin", "sim_margin_raw", "sim_margin_blend"]:
        if col in cong.columns:
            cong[col] = pd.to_numeric(cong[col], errors="coerce").round(2)

    for col in ["flipped_raw", "flipped_blend"]:
        if col in cong.columns:
            cong[col] = cong[col].fillna(False).astype(int)

    # ── Join ──────────────────────────────────────────────────────────────────
    print("\nJoining to TIGER boundaries...")
    merged = tiger.merge(cong, left_on="cong_dist", right_on="district", how="left")
    matched = merged["base_winner"].notna().sum()
    print(f"  {matched} / {len(merged)} districts matched to simulation results.")

    # Add friendly color columns for ArcGIS styling
    merged["color_sim"]  = merged["sim_winner_blend"].map(
        {"Trump": "Republican", "Harris": "Democrat"}
    ).fillna("No data")
    merged["color_base"] = merged["base_winner"].map(
        {"Trump": "Republican", "Harris": "Democrat"}
    ).fillna("No data")
    merged["flipped"]    = merged["flipped_blend"].fillna(0).astype(int)

    # Drop redundant col
    if "district" in merged.columns:
        merged = merged.drop(columns=["district"])

    # ── Print summary table ───────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  NC Congressional Districts — {pct}% Youth Turnout Uplift")
    print(f"{'='*65}")
    print(f"  {'CD':>4}  {'District Name':<35} {'2024':>8} {'Sim':>8} {'Margin':>8} {'':>6}")
    print(f"  {'-'*4}  {'-'*35} {'-'*8} {'-'*8} {'-'*8} {'-'*6}")
    for _, row in merged.sort_values("cong_dist").iterrows():
        dist    = int(row["cong_dist"]) if not pd.isna(row["cong_dist"]) else "?"
        name    = str(row.get("NAMELSAD", ""))[:35]
        base    = row.get("base_winner", "?")
        sim     = row.get("sim_winner_blend", "?")
        margin  = row.get("sim_margin_blend", np.nan)
        flipped = "⭐ FLIP" if row.get("flipped_blend", 0) == 1 else ""
        margin_s = f"{margin:+.1f}%" if not pd.isna(margin) else "?"
        print(f"  {dist:>4}  {name:<35} {str(base):>8} {str(sim):>8} {margin_s:>8} {flipped}")
    print(f"{'='*65}")

    # ── Export GeoJSON ────────────────────────────────────────────────────────
    print(f"\nSaving GeoJSON: {GEOJSON_OUT}...")
    merged.to_file(GEOJSON_OUT, driver="GeoJSON")
    size_mb = os.path.getsize(GEOJSON_OUT) / 1024 / 1024
    print(f"  Size: {size_mb:.1f} MB ✅")

    # ── Export zipped shapefile ───────────────────────────────────────────────
    print(f"Saving shapefile: {SHP_BASE}.shp...")
    shp = merged.rename(columns={
        "cong_dist":         "cong_dist",
        "NAMELSAD":          "dist_name",
        "base_winner":       "base_win",
        "sim_winner_raw":    "sim_win_raw",
        "sim_winner_blend":  "sim_win_bld",
        "base_margin":       "base_mar",
        "sim_margin_raw":    "sim_mar_raw",
        "sim_margin_blend":  "sim_mar_bld",
        "flipped_raw":       "flp_raw",
        "flipped_blend":     "flp_bld",
        "base_trump":        "v_trump",
        "base_harris":       "v_harris",
        "sim_trump_blend":   "sim_trump",
        "sim_harris_blend":  "sim_harris",
        "color_sim":         "color_sim",
        "color_base":        "color_base",
        "flipped":           "flipped",
    })
    shp.to_file(SHP_BASE + ".shp", driver="ESRI Shapefile")

    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".dbf", ".shx", ".prj", ".cpg"]:
            f = SHP_BASE + ext
            if os.path.exists(f):
                zf.write(f)
    zip_mb = os.path.getsize(ZIP_OUT) / 1024 / 1024
    print(f"  Zip size: {zip_mb:.1f} MB ✅")

    print(f"\n  Upload to ArcGIS Online:")
    print(f"  Content > Add Item > From your computer > {GEOJSON_OUT}")
    print(f"  Style by 'color_sim'  → red/blue by simulated winner")
    print(f"  Style by 'color_base' → red/blue by 2024 actual winner")
    print(f"  Style by 'sim_mar_bld' → graduated color by margin")
    print(f"  Filter 'flipped = 1'  → highlight flipped districts")


if __name__ == "__main__":
    main()