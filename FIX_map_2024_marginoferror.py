"""
map_2024_president.py
----------------------
Maps the 2024 US Presidential race margin of victory by precinct.

Margin = (Trump % - Harris %) two-party
Positive = Trump, Negative = Harris
Diverging red-blue scale centered at 0.

Produces:
  nc_2024_president_margin.png     — static map
  nc_2024_pres_margin.zip          — zipped shapefile for ArcGIS Online

Requirements:
  pip install geopandas pandas matplotlib
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import zipfile
import os
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
RDH_FILE   = "data/raw/nc_2024_gen_prec/nc_2024_gen_all_prec/nc_2024_gen_all_prec.shp"   # <-- update
PNG_OUTPUT = "nc_2024_president_margin.png"
SHP_BASE   = "nc_2024_pres_margin"
ZIP_OUTPUT = "nc_2024_pres_margin.zip"

TRUMP_COL  = "G24PRERTRU"
HARRIS_COL = "G24PREDHAR"
THIRD_PARTY = [
    "G24PRECTER", "G24PREGSTE", "G24PREJWES",
    "G24PRELOLI", "G24PRENAYY", "G24PRENDEL", "G24PREOWRI",
]
# ──────────────────────────────────────────────────────────────────────────────


def load_and_compute(rdh_file: str) -> gpd.GeoDataFrame:
    print("Loading RDH shapefile...")
    gdf = gpd.read_file(rdh_file)
    print(f"  {len(gdf):,} precincts. CRS: {gdf.crs}")

    for col in [TRUMP_COL, HARRIS_COL] + THIRD_PARTY:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)

    all_cols = [TRUMP_COL, HARRIS_COL] + [c for c in THIRD_PARTY if c in gdf.columns]
    gdf["total_votes"]     = gdf[all_cols].sum(axis=1)
    gdf["two_party_total"] = gdf[TRUMP_COL] + gdf[HARRIS_COL]

    gdf["trump_pct"]  = np.where(gdf["two_party_total"] > 0,
                                  gdf[TRUMP_COL]  / gdf["two_party_total"] * 100, np.nan)
    gdf["harris_pct"] = np.where(gdf["two_party_total"] > 0,
                                  gdf[HARRIS_COL] / gdf["two_party_total"] * 100, np.nan)
    gdf["margin"]     = gdf["trump_pct"] - gdf["harris_pct"]

    def comp_label(m):
        if pd.isna(m):      return "No data"
        if abs(m) <= 5:     return "Toss-up (<=5 pts)"
        if abs(m) <= 10:    return "Competitive (5-10 pts)"
        if abs(m) <= 20:    return "Lean (10-20 pts)"
        return                     "Safe (>20 pts)"

    gdf["competitive"] = gdf["margin"].apply(comp_label)
    gdf["winner"]      = np.where(gdf["margin"].isna(), "No data",
                         np.where(gdf["margin"] > 0, "Trump (R)", "Harris (D)"))
    gdf["has_votes"]   = gdf["total_votes"] >= 10

    if gdf.crs and gdf.crs.to_epsg() != 4326:
        print(f"  Reprojecting → EPSG:4326...")
        gdf = gdf.to_crs(epsg=4326)

    print(f"  Trump precincts:     {(gdf['margin'] > 0).sum():,}")
    print(f"  Harris precincts:    {(gdf['margin'] < 0).sum():,}")
    print(f"  Toss-up (<=5 pts):   {(gdf['margin'].abs() <= 5).sum():,}")
    print(f"  Competitive (<=10):  {(gdf['margin'].abs() <= 10).sum():,}")
    return gdf


def make_static_map(gdf: gpd.GeoDataFrame, output_file: str):
    print("\nBuilding static map...")
    plot_gdf = gdf[gdf["has_votes"]].copy()

    # Drop invalid/empty geometries to avoid matplotlib aspect ratio errors
    plot_gdf = plot_gdf[
        plot_gdf.geometry.notna() &
        ~plot_gdf.geometry.is_empty &
        plot_gdf.geometry.is_valid
    ].copy()

    cmap = mcolors.LinearSegmentedColormap.from_list(
        "margin",
        ["#1a6fba", "#4a9fd4", "#a8cfe8", "#f0f0f0", "#f4a8a8", "#d44a4a", "#a51c1c"],
        N=512,
    )
    norm = mcolors.TwoSlopeNorm(vmin=-60, vcenter=0, vmax=60)

    fig, ax = plt.subplots(1, 1, figsize=(20, 12))
    fig.patch.set_facecolor("#0f0f1a")
    ax.set_facecolor("#0f0f1a")
    ax.set_aspect("equal")

    no_data = gdf[
        ~gdf["has_votes"] &
        gdf.geometry.notna() &
        ~gdf.geometry.is_empty &
        gdf.geometry.is_valid
    ]
    if len(no_data) > 0:
        no_data.plot(ax=ax, color="#2a2a3a", linewidth=0, alpha=0.5)

    plot_gdf.plot(
        column="margin", ax=ax, cmap=cmap, norm=norm,
        linewidth=0.08, edgecolor="#0f0f1a", alpha=0.95,
        legend=False, missing_kwds={"color": "#2a2a3a"},
        aspect=None,
    )

    gdf.dissolve(by="COUNTY").reset_index().plot(
        ax=ax, facecolor="none", edgecolor="white",
        linewidth=0.5, alpha=0.25, aspect=None,
    )

    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.02, pad=0.01, aspect=28)
    cbar.set_ticks([-60, -40, -20, -10, -5, 0, 5, 10, 20, 40, 60])
    cbar.set_ticklabels(
        ["D+60","D+40","D+20","D+10","D+5","EVEN","R+5","R+10","R+20","R+40","R+60"],
        color="white", fontsize=8,
    )
    cbar.outline.set_edgecolor("#444444")
    cbar.ax.text(2.3, 0.02, "Harris (D)", transform=cbar.ax.transAxes,
                 color="#4a9fd4", fontsize=9, va="bottom", fontweight="bold")
    cbar.ax.text(2.3, 0.98, "Trump (R)",  transform=cbar.ax.transAxes,
                 color="#d44a4a", fontsize=9, va="top",    fontweight="bold")

    ax.set_title("2024 US Presidential Election — Margin of Victory",
                 fontsize=22, fontweight="bold", color="white", pad=16, loc="left")
    ax.text(0, -0.03,
            "Two-party margin per precinct  ·  Positive = Trump (R), Negative = Harris (D)  ·  "
            "Source: NC SBE via Redistricting Data Hub",
            transform=ax.transAxes, fontsize=9, color="#aaaaaa")

    tossup      = (plot_gdf["margin"].abs() <= 5).sum()
    competitive = ((plot_gdf["margin"].abs() > 5) & (plot_gdf["margin"].abs() <= 10)).sum()
    trump_n     = (plot_gdf["margin"] > 0).sum()
    harris_n    = (plot_gdf["margin"] < 0).sum()
    trump_v     = plot_gdf[TRUMP_COL].sum()
    harris_v    = plot_gdf[HARRIS_COL].sum()

    summary = (
        f"  Statewide summary:\n"
        f"  Trump precincts:   {trump_n:,}    votes: {trump_v:,.0f}\n"
        f"  Harris precincts:  {harris_n:,}    votes: {harris_v:,.0f}\n"
        f"  Toss-up (<=5 pts): {tossup:,} precincts\n"
        f"  Competitive (<=10):{competitive:,} precincts"
    )
    ax.text(0.01, 0.22, summary, transform=ax.transAxes,
            fontsize=8.5, color="white", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1a2e",
                      alpha=0.88, edgecolor="#555577", linewidth=1.0),
            verticalalignment="top")

    ax.set_axis_off()
    plt.tight_layout(pad=0.8)
    plt.savefig(output_file, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ Static map saved: {output_file}")


def export_arcgis(gdf: gpd.GeoDataFrame, shp_base: str, zip_output: str):
    """Export a slim shapefile with just the key columns for ArcGIS Online."""
    print("\nExporting ArcGIS Online shapefile...")

    keep = ["COUNTY", "PRECINCT", "winner", "margin",
            "trump_pct", "harris_pct", "total_votes",
            "competitive", TRUMP_COL, HARRIS_COL, "geometry"]
    keep = [c for c in keep if c in gdf.columns]

    slim = gdf[gdf["has_votes"]][keep].copy()

    # Round floats
    for col in ["margin", "trump_pct", "harris_pct"]:
        if col in slim.columns:
            slim[col] = slim[col].round(2)

    # Rename to safe 10-char shapefile names
    rename = {
        "COUNTY":      "county",
        "PRECINCT":    "precinct",
        "winner":      "winner",
        "margin":      "margin",
        "trump_pct":   "trump_pct",
        "harris_pct":  "harris_pct",
        "total_votes": "tot_votes",
        "competitive": "competitiv",
        TRUMP_COL:     "v_trump",
        HARRIS_COL:    "v_harris",
    }
    slim = slim.rename(columns={k: v for k, v in rename.items() if k in slim.columns})
    slim.to_file(shp_base + ".shp", driver="ESRI Shapefile")

    exts = [".shp", ".dbf", ".shx", ".prj", ".cpg"]
    with zipfile.ZipFile(zip_output, "w", zipfile.ZIP_DEFLATED) as zf:
        for ext in exts:
            f = shp_base + ext
            if os.path.exists(f):
                zf.write(f)

    size_mb = os.path.getsize(zip_output) / 1024 / 1024
    print(f"  ✅ Shapefile zip saved: {zip_output}  ({size_mb:.1f} MB)")

    if size_mb <= 10:
        print(f"  ✅ Under 10 MB — upload directly to ArcGIS Online.")
        print(f"     Content > Add Item > From your computer > {zip_output}")
    else:
        print(f"  ⚠  Over 10 MB — try ArcGIS Pro or run simplify_geometry.py first.")


def main():
    gdf = load_and_compute(RDH_FILE)

    print("\nTop 15 most competitive precincts:")
    top15 = gdf[gdf["has_votes"]].copy()
    top15["abs_margin"] = top15["margin"].abs()
    top15 = top15.nsmallest(15, "abs_margin")[
        ["COUNTY", "PRECINCT", "winner", "margin", TRUMP_COL, HARRIS_COL, "total_votes"]
    ]
    print(top15.to_string(index=False))

    make_static_map(gdf, PNG_OUTPUT)
    export_arcgis(gdf, SHP_BASE, ZIP_OUTPUT)

    print(f"\n✅ All done!")
    print(f"   Static map: {PNG_OUTPUT}")
    print(f"   ArcGIS zip: {ZIP_OUTPUT}")


if __name__ == "__main__":
    main()