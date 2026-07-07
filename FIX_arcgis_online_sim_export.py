"""
export_sim_arcgis.py
---------------------
Joins simulation results to congressional district geometry
and exports a zipped shapefile for ArcGIS Online.

Run AFTER simulate_youth_turnout.py.

Inputs:
  sim_district_results_{pct}pct.csv   -- from simulator
  sim_results_{pct}pct.csv            -- from simulator (precinct level)
  nc_2024_gen_cong_prec shapefile     -- geometry source

Outputs:
  sim_cong_arcgis_{pct}pct.zip        -- congressional districts for ArcGIS
  sim_prec_arcgis_{pct}pct.zip        -- precincts for ArcGIS

Columns in congressional district shapefile:
  cong_dist     : district number
  base_win      : baseline 2024 winner
  sim_win_raw   : simulated winner (precinct lean only)
  sim_win_bld   : simulated winner (blended exit poll)
  base_mar      : baseline margin %
  sim_mar_raw   : simulated margin % (raw)
  sim_mar_bld   : simulated margin % (blended)
  flp_raw       : flipped under raw lean (0/1)
  flp_bld       : flipped under blended lean (0/1)
  new_youth     : new youth voters added (precinct file only)

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
YOUTH_UPLIFT  = 0.10   # <-- match whatever you ran in the simulator
CONG_SHP      = r"data\raw\nc_2024_gen_prec\nc_2024_gen_cong_prec\nc_2024_gen_cong_prec.shp"
PCT_LABEL     = f"{int(YOUTH_UPLIFT * 100)}pct"
DIST_CSV      = f"sim_district_results_{PCT_LABEL}.csv"
PREC_CSV      = f"sim_results_{PCT_LABEL}.csv"
CONG_OUT_BASE = f"sim_cong_arcgis_{PCT_LABEL}"
PREC_OUT_BASE = f"sim_prec_arcgis_{PCT_LABEL}"
# ──────────────────────────────────────────────────────────────────────────────


def zip_shp(base: str) -> str:
    """Zip shapefile components and return zip path."""
    zip_path = base + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in [".shp", ".dbf", ".shx", ".prj", ".cpg"]:
            f = base + ext
            if os.path.exists(f):
                zf.write(f)
    return zip_path


def report_size(zip_path: str):
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"  Size: {size_mb:.1f} MB", end="")
    if size_mb <= 10:
        print(f" ✅ Ready for ArcGIS Online")
        print(f"  Upload: Content > Add Item > From your computer > {zip_path}")
    else:
        print(f" ⚠  Over 10MB — simplify geometry or use ArcGIS Pro")


def export_congressional(dist_csv: str, cong_shp: str, out_base: str):
    """
    Dissolve precinct geometries to congressional district level
    and join simulation results.
    """
    print("\nBuilding congressional district shapefile...")

    # Load and dissolve geometry to district level
    cong = gpd.read_file(cong_shp)
    cong["COUNTY"]   = cong["COUNTY"].str.strip().str.upper()
    cong["PRECINCT"] = cong["PRECINCT"].str.strip().str.upper()
    cong["cong_dist"] = pd.to_numeric(
        cong["UNIQUE_ID"].str.extract(r"CON-(\d+)", expand=False),
        errors="coerce"
    )
    cong = cong[cong["cong_dist"].notna()].copy()
    print(f"  Dissolving {len(cong):,} precinct rows to district polygons...")
    dist_geom = cong.dissolve(by="cong_dist").reset_index()[["cong_dist", "geometry"]]
    dist_geom = dist_geom.to_crs(epsg=4326)
    dist_geom = dist_geom[
        dist_geom.geometry.notna() &
        ~dist_geom.geometry.is_empty &
        dist_geom.geometry.is_valid
    ].copy()
    print(f"  {len(dist_geom):,} district polygons.")

    # Load simulation district results
    dist_df = pd.read_csv(dist_csv)
    cong_results = dist_df[dist_df["district_type"] == "cong_dist"].copy()
    cong_results["district"] = pd.to_numeric(cong_results["district"], errors="coerce")

    # Merge geometry + results
    merged = dist_geom.merge(
        cong_results[[
            "district", "base_winner", "sim_winner_raw", "sim_winner_blend",
            "base_margin", "sim_margin_raw", "sim_margin_blend",
            "flipped_raw", "flipped_blend",
            "base_trump", "base_harris",
        ]],
        left_on="cong_dist", right_on="district", how="left"
    )

    # Round margins
    for col in ["base_margin", "sim_margin_raw", "sim_margin_blend"]:
        merged[col] = pd.to_numeric(merged[col], errors="coerce").round(2)

    # Convert booleans to int for shapefile compatibility
    merged["flipped_raw"]   = merged["flipped_raw"].fillna(False).astype(int)
    merged["flipped_blend"] = merged["flipped_blend"].fillna(False).astype(int)

    # Rename to shapefile-safe 10-char names
    merged = merged.rename(columns={
        "cong_dist":        "cong_dist",
        "base_winner":      "base_win",
        "sim_winner_raw":   "sim_win_raw",
        "sim_winner_blend": "sim_win_bld",
        "base_margin":      "base_mar",
        "sim_margin_raw":   "sim_mar_raw",
        "sim_margin_blend": "sim_mar_bld",
        "flipped_raw":      "flp_raw",
        "flipped_blend":    "flp_bld",
        "base_trump":       "v_trump",
        "base_harris":      "v_harris",
    })

    # Drop redundant district col
    if "district" in merged.columns:
        merged = merged.drop(columns=["district"])

    merged.to_file(out_base + ".shp", driver="ESRI Shapefile")
    zip_path = zip_shp(out_base)
    print(f"  Saved: {zip_path}")
    report_size(zip_path)
    return merged


def export_precincts(prec_csv: str, cong_shp: str, out_base: str):
    """
    Join simulation precinct results to precinct geometry
    and export a slim shapefile.
    """
    print("\nBuilding precinct-level shapefile...")

    # Load precinct geometry (dissolve splits)
    cong = gpd.read_file(cong_shp)
    cong["COUNTY"]   = cong["COUNTY"].str.strip().str.upper()
    cong["PRECINCT"] = cong["PRECINCT"].str.strip().str.upper()
    cong["cong_dist"] = pd.to_numeric(
        cong["UNIQUE_ID"].str.extract(r"CON-(\d+)", expand=False),
        errors="coerce"
    )
    prec_geom = cong.dissolve(by=["COUNTY", "PRECINCT"]).reset_index()
    prec_geom = prec_geom[["COUNTY", "PRECINCT", "cong_dist", "geometry"]].copy()
    prec_geom = prec_geom.to_crs(epsg=4326)

    # Load simulation precinct results
    prec_df = pd.read_csv(prec_csv, dtype={
        "county_desc": str, "precinct_abbrv": str
    })
    prec_df["county_desc"]    = prec_df["county_desc"].str.strip().str.upper()
    prec_df["precinct_abbrv"] = prec_df["precinct_abbrv"].str.strip().str.upper()

    # Keep only key columns
    keep_cols = [
        "county_desc", "precinct_abbrv",
        "winner_2024", "sim_winner_raw", "sim_winner_blend",
        "precinct_margin", "sim_margin_raw", "sim_margin_blend",
        "flipped_raw", "flipped_blend",
        "new_youth_voters", "youth_nonvoters",
        "v_trump_2024", "v_harris_2024",
        "sim_trump_blend", "sim_harris_blend",
        "competitiveness", "age_18_24",
        "youth_turnout_2024", "overall_turnout_2024",
    ]
    keep_cols = [c for c in keep_cols if c in prec_df.columns]
    prec_df = prec_df[keep_cols]

    # Merge geometry
    merged = prec_geom.merge(
        prec_df,
        left_on=["COUNTY", "PRECINCT"],
        right_on=["county_desc", "precinct_abbrv"],
        how="left"
    )

    # Filter valid geometry
    merged = merged[
        merged.geometry.notna() &
        ~merged.geometry.is_empty &
        merged.geometry.is_valid
    ].copy()

    # Round floats
    for col in ["precinct_margin", "sim_margin_raw", "sim_margin_blend",
                "youth_turnout_2024", "overall_turnout_2024"]:
        if col in merged.columns:
            merged[col] = pd.to_numeric(merged[col], errors="coerce").round(4)

    # Bool to int
    for col in ["flipped_raw", "flipped_blend"]:
        if col in merged.columns:
            merged[col] = merged[col].fillna(False).astype(int)

    # Rename to 10-char safe names
    rename = {
        "COUNTY":            "county",
        "PRECINCT":          "precinct",
        "cong_dist":         "cong_dist",
        "winner_2024":       "base_win",
        "sim_winner_raw":    "sim_win_raw",
        "sim_winner_blend":  "sim_win_bld",
        "precinct_margin":   "base_mar",
        "sim_margin_raw":    "sim_mar_raw",
        "sim_margin_blend":  "sim_mar_bld",
        "flipped_raw":       "flp_raw",
        "flipped_blend":     "flp_bld",
        "new_youth_voters":  "new_youth",
        "youth_nonvoters":   "yth_nonvot",
        "v_trump_2024":      "v_trump",
        "v_harris_2024":     "v_harris",
        "sim_trump_blend":   "sim_trump",
        "sim_harris_blend":  "sim_harris",
        "competitiveness":   "competitiv",
        "age_18_24":         "reg_18_24",
        "youth_turnout_2024":"yth_turn",
        "overall_turnout_2024":"ovr_turn",
    }
    merged = merged.rename(columns={k: v for k, v in rename.items() if k in merged.columns})

    # Drop redundant cols
    for col in ["county_desc", "precinct_abbrv"]:
        if col in merged.columns:
            merged = merged.drop(columns=[col])

    # Simplify geometry to reduce file size
    print(f"  Simplifying geometry at 150ft tolerance...")
    merged = merged.to_crs(epsg=2264)
    merged["geometry"] = merged["geometry"].simplify(150, preserve_topology=True)
    merged = merged.to_crs(epsg=4326)
    merged = merged[~merged.geometry.is_empty & merged.geometry.notna()].copy()

    print(f"  {len(merged):,} precincts in output.")
    merged.to_file(out_base + ".shp", driver="ESRI Shapefile")
    zip_path = zip_shp(out_base)
    print(f"  Saved: {zip_path}")
    report_size(zip_path)
    return merged


def main():
    pct = int(YOUTH_UPLIFT * 100)
    print(f"Exporting simulation results for {pct}% youth uplift scenario...")

    # Check inputs exist
    for f in [DIST_CSV, PREC_CSV, CONG_SHP]:
        if not os.path.exists(f):
            print(f"❌ Missing: {f}")
            print("   Run simulate_youth_turnout.py first.")
            return

    # Export congressional districts
    cong_gdf = export_congressional(DIST_CSV, CONG_SHP, CONG_OUT_BASE)

    # Export precincts
    prec_gdf = export_precincts(PREC_CSV, CONG_SHP, PREC_OUT_BASE)

    print(f"\n{'='*55}")
    print(f"  Export complete for {pct}% youth uplift scenario")
    print(f"{'='*55}")
    print(f"\n  Congressional districts: {CONG_OUT_BASE}.zip")
    print(f"  Precincts:               {PREC_OUT_BASE}.zip")
    print(f"\n  In ArcGIS Online:")
    print(f"  1. Content > Add Item > From your computer")
    print(f"  2. Upload the zip file")
    print(f"  3. Style by 'sim_win_bld' for simulated winner")
    print(f"     or 'base_win' for 2024 baseline")
    print(f"  4. Use 'flp_bld' = 1 to highlight flipped districts")
    print(f"  5. Use 'sim_mar_bld' for margin graduated colors")
    print(f"\n  To export a different scenario:")
    print(f"  Change YOUTH_UPLIFT at top and rerun both scripts.")


if __name__ == "__main__":
    main()