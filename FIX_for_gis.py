"""
simplify_geometry.py
---------------------
Simplifies precinct polygon geometries to reduce file size for
ArcGIS Online upload, then re-exports slim GeoJSON and zipped shapefile.

Approach:
  - Reprojects back to EPSG:2264 (NC State Plane, feet) for simplification
    so tolerance is in real-world feet (not degrees)
  - Tests multiple tolerance levels and reports sizes
  - Reprojects back to EPSG:4326 for final export

Tolerance guide (in feet, EPSG:2264):
  50  ft → nearly invisible change, modest size reduction
  150 ft → slight smoothing on rural precincts, good reduction
  300 ft → noticeable on small urban precincts, best reduction

Requirements:
  pip install geopandas pandas pyogrio
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import os
import zipfile

# ── CONFIG ────────────────────────────────────────────────────────────────────
SLIM_GEOJSON    = "nc_precincts_slim.geojson"   # output from export_arcgis.py
OUTPUT_GEOJSON  = "nc_precincts_online.geojson"
OUTPUT_SHP_BASE = "nc_precincts_online"
OUTPUT_ZIP      = "nc_precincts_online.zip"
TOLERANCE_FT    = 150    # feet — change this after reviewing the test output below
# ──────────────────────────────────────────────────────────────────────────────

SHP_COL_MAP = {
    "county":           "county",
    "precinct_id":      "prec_id",
    "precinct_name":    "prec_name",
    "pop_total":        "pop_total",
    "pop_voting_age":   "pop_vap",
    "pop_18_24":        "pop_18_24",
    "pop_25_34":        "pop_25_34",
    "pop_35_44":        "pop_35_44",
    "pop_45_54":        "pop_45_54",
    "pop_55_64":        "pop_55_64",
    "pop_65_74":        "pop_65_74",
    "pop_75plus":       "pop_75plus",
    "pop_65plus":       "pop_65plus",
    "est_vap_total":    "vap_est",
    "est_vap_youth":    "vap_youth",
    "pop_white_alone":  "pop_white",
    "pop_black_alone":  "pop_black",
    "pop_hispanic":     "pop_hisp",
    "pop_asian_alone":  "pop_asian",
    "pop_nonwhite":     "pop_nonwht",
    "pop_white_nonhispanic": "pop_wht_nh",
    "pct_white":        "pct_white",
    "pct_black":        "pct_black",
    "pct_hispanic":     "pct_hisp",
    "pct_asian":        "pct_asian",
    "pct_nonwhite":     "pct_nonwht",
    "pct_white_nonhisp":"pct_wht_nh",
    "pct_18_24":        "pct_18_24",
    "pct_25_34":        "pct_25_34",
    "pct_65plus":       "pct_65plus",
    "reg_total":        "reg_total",
    "reg_active":       "reg_active",
    "reg_inactive":     "reg_inact",
    "reg_removed":      "reg_rmvd",
    "party_dem":        "pty_dem",
    "party_rep":        "pty_rep",
    "party_unaf":       "pty_unaf",
    "party_lib":        "pty_lib",
    "party_other":      "pty_other",
    "race_white":       "reg_white",
    "race_black":       "reg_black",
    "race_asian":       "reg_asian",
    "race_aian":        "reg_aian",
    "eth_hispanic":     "reg_hisp",
    "gender_male":      "reg_male",
    "gender_female":    "reg_female",
    "age_18_24":        "reg_18_24",
    "age_25_34":        "reg_25_34",
    "age_35_44":        "reg_35_44",
    "age_45_54":        "reg_45_54",
    "age_55_64":        "reg_55_64",
    "age_65_74":        "reg_65_74",
    "age_75plus":       "reg_75plus",
    "reg_rate":         "reg_rate",
    "reg_rate_youth":   "reg_rt_yth",
    "youth_gap":        "yth_gap",
    "youth_gap_pct":    "yth_gap_pt",
    "votes_11/05/2024": "v_g2024",
    "votes_11/03/2020": "v_g2020",
    "votes_11/08/2022": "v_g2022",
    "votes_11/08/2016": "v_g2016",
    "votes_11/06/2018": "v_g2018",
    "votes_11/07/2023": "v_g2023",
    "votes_11/07/2017": "v_g2017",
    "votes_03/05/2024": "v_p2024",
    "votes_03/03/2026": "v_p2026",
    "turnout_11/05/2024": "to_g2024",
    "turnout_11/03/2020": "to_g2020",
    "turnout_11/08/2022": "to_g2022",
    "turnout_11/08/2016": "to_g2016",
    "turnout_11/06/2018": "to_g2018",
    "turnout_03/05/2024": "to_p2024",
    "turnout_03/03/2026": "to_p2026",
}


def test_tolerances(gdf_projected: gpd.GeoDataFrame):
    """Test a range of tolerances and print size estimates."""
    print("\nTesting tolerance levels (geometry only):")
    print(f"  {'Tolerance':>12}  {'Avg vertices':>14}  {'Est. size reduction':>20}")
    print(f"  {'-'*12}  {'-'*14}  {'-'*20}")

    orig_verts = gdf_projected.geometry.apply(
        lambda g: sum(len(p.exterior.coords) for p in
                      (g.geoms if g.geom_type == "MultiPolygon"
                       else [g]) if hasattr(p, "exterior"))
    ).sum()

    for tol in [50, 150, 300, 500]:
        simplified = gdf_projected.geometry.simplify(tol, preserve_topology=True)
        simp_verts = simplified.apply(
            lambda g: sum(len(p.exterior.coords) for p in
                          (g.geoms if g.geom_type == "MultiPolygon"
                           else [g]) if hasattr(p, "exterior"))
        ).sum()
        reduction = (1 - simp_verts / orig_verts) * 100
        print(f"  {tol:>9} ft  {simp_verts:>14,.0f}  {reduction:>19.1f}%")

    print(f"\n  Original vertex count: {orig_verts:,.0f}")
    print(f"  Using TOLERANCE_FT = {TOLERANCE_FT} ft (edit at top of script to change)\n")


def zip_shapefile(base_name: str, zip_path: str):
    extensions = [".shp", ".dbf", ".shx", ".prj", ".cpg"]
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in extensions:
            f = base_name + ext
            if os.path.exists(f):
                zf.write(f)


def main():
    # ── Load slim GeoJSON ─────────────────────────────────────────────────────
    print(f"Loading {SLIM_GEOJSON}...")
    gdf = gpd.read_file(SLIM_GEOJSON)
    print(f"  {len(gdf):,} precincts, CRS: {gdf.crs}")

    # ── Reproject to EPSG:2264 for simplification in feet ────────────────────
    print("Reprojecting to EPSG:2264 (NC State Plane, feet) for simplification...")
    gdf_proj = gdf.to_crs(epsg=2264)

    # ── Test tolerances ───────────────────────────────────────────────────────
    test_tolerances(gdf_proj)

    # ── Apply chosen tolerance ────────────────────────────────────────────────
    print(f"Simplifying at {TOLERANCE_FT} ft tolerance...")
    gdf_proj["geometry"] = gdf_proj["geometry"].simplify(
        TOLERANCE_FT, preserve_topology=True
    )

    # Drop any null/empty geometries created by aggressive simplification
    before = len(gdf_proj)
    gdf_proj = gdf_proj[~gdf_proj.geometry.is_empty & gdf_proj.geometry.notna()]
    dropped = before - len(gdf_proj)
    if dropped > 0:
        print(f"  ⚠  Dropped {dropped} empty geometries after simplification.")

    # ── Reproject back to WGS84 for export ───────────────────────────────────
    print("Reprojecting back to EPSG:4326 (WGS84)...")
    gdf_final = gdf_proj.to_crs(epsg=4326)

    # ── Save GeoJSON ──────────────────────────────────────────────────────────
    print(f"Saving {OUTPUT_GEOJSON}...")
    gdf_final.to_file(OUTPUT_GEOJSON, driver="GeoJSON")
    geojson_mb = os.path.getsize(OUTPUT_GEOJSON) / 1024 / 1024
    print(f"  GeoJSON size: {geojson_mb:.1f} MB")

    # ── Save shapefile + zip ──────────────────────────────────────────────────
    print(f"Saving shapefile...")
    shp_gdf = gdf_final.rename(columns={
        k: v for k, v in SHP_COL_MAP.items() if k in gdf_final.columns
    })
    shp_gdf.to_file(OUTPUT_SHP_BASE + ".shp", driver="ESRI Shapefile")
    zip_shapefile(OUTPUT_SHP_BASE, OUTPUT_ZIP)
    zip_mb = os.path.getsize(OUTPUT_ZIP) / 1024 / 1024
    print(f"  Zipped shapefile size: {zip_mb:.1f} MB")

    # ── Upload guidance ───────────────────────────────────────────────────────
    print(f"\n{'='*55}")
    print(f"  ArcGIS Online upload guidance:")
    print(f"{'='*55}")
    if zip_mb <= 10:
        print(f"  ✅ ZIP ({zip_mb:.1f} MB) — upload {OUTPUT_ZIP}")
        print(f"     Content > Add Item > From your computer")
    elif geojson_mb <= 50:
        print(f"  ✅ GeoJSON ({geojson_mb:.1f} MB) — upload {OUTPUT_GEOJSON}")
        print(f"     Content > Add Item > From your computer")
    else:
        print(f"  ⚠  Still over limits. Try increasing TOLERANCE_FT to 300 or 500.")
        print(f"     Edit TOLERANCE_FT at the top of the script and rerun.")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()