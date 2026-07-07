"""
map_youth_potential_png.py
---------------------------
Static choropleth PNG of youth voter gap.
Red = high gap (many unregistered youth)
Green = low gap (youth well registered)

Requirements:
  pip install geopandas pandas matplotlib mapclassify
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.cm as cm
import matplotlib.ticker as mticker
import mapclassify
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
GEOJSON_FILE = "nc_precincts.geojson"
PNG_OUTPUT   = "nc_youth_potential.png"
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("Loading GeoJSON...")
    gdf = gpd.read_file(GEOJSON_FILE)

    # ── Compute youth gap ─────────────────────────────────────────────────────
    for col in ["est_vap_youth", "age_18_24"]:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)

    gdf["youth_gap"] = (gdf["est_vap_youth"] - gdf["age_18_24"]).clip(lower=0)
    gdf["has_youth_pop"] = gdf["est_vap_youth"] >= 10

    plot_gdf = gdf[gdf["has_youth_pop"]].copy()
    null_gdf = gdf[~gdf["has_youth_pop"]].copy()

    # ── Natural breaks classification (5 classes) ─────────────────────────────
    classifier = mapclassify.NaturalBreaks(plot_gdf["youth_gap"], k=5)
    breaks = np.concatenate([[0], classifier.bins])
    breaks = np.unique(breaks)
    print(f"  Break points: {[round(b) for b in breaks]}")

    # ── Color scale: green (low gap) → yellow → red (high gap) ───────────────
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "gap_scale",
        ["#1a9641", "#a6d96a", "#ffffbf", "#fdae61", "#d7191c"],
        N=512,
    )
    norm = mcolors.BoundaryNorm(breaks, ncolors=512, clip=True)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(1, 1, figsize=(20, 12))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1a1a2e")

    # No-data precincts (too few youth) in muted gray
    if len(null_gdf) > 0:
        null_gdf.plot(ax=ax, color="#3a3a4a", linewidth=0, alpha=0.6)

    # Main choropleth
    plot_gdf.plot(
        column="youth_gap",
        ax=ax,
        cmap=cmap,
        norm=norm,
        linewidth=0.1,
        edgecolor="#1a1a2e",
        alpha=1.0,
        legend=False,
    )

    # County borders
    county_borders = gdf.dissolve(by="county").reset_index()
    county_borders.plot(
        ax=ax,
        facecolor="none",
        edgecolor="white",
        linewidth=0.6,
        alpha=0.35,
    )

    # ── Colorbar ──────────────────────────────────────────────────────────────
    sm = cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(
        sm, ax=ax,
        fraction=0.022, pad=0.015, aspect=25,
        ticks=breaks,
    )
    cbar.ax.set_yticklabels(
        [f"{int(b):,}" for b in breaks],
        color="white", fontsize=9,
    )
    cbar.set_label(
        "Estimated Unregistered Youth (18–24)",
        color="white", fontsize=11, labelpad=12,
    )
    cbar.outline.set_edgecolor("#555555")

    # Add green/red labels on colorbar
    cbar.ax.text(
        2.2, 0.02, "Low gap\n(well registered)",
        transform=cbar.ax.transAxes,
        color="#1a9641", fontsize=8, va="bottom",
    )
    cbar.ax.text(
        2.2, 0.98, "High gap\n(underregistered)",
        transform=cbar.ax.transAxes,
        color="#d7191c", fontsize=8, va="top",
    )

    # ── Title & subtitle ──────────────────────────────────────────────────────
    ax.set_title(
        "Youth Voter Potential — North Carolina",
        fontsize=24, fontweight="bold", color="white",
        pad=18, loc="left", fontfamily="sans-serif",
    )
    ax.text(
        0, -0.03,
        "Estimated unregistered 18–24 year olds per precinct  ·  "
        "ACS 2024 5-Year Estimates + NC SBE Voter Registration (2025)",
        transform=ax.transAxes,
        fontsize=9, color="#aaaaaa",
    )

    # ── Top 5 callout box ─────────────────────────────────────────────────────
    top5 = plot_gdf.nlargest(5, "youth_gap")[
        ["county", "precinct_name", "youth_gap"]
    ]
    lines = ["  Highest-gap precincts:\n"]
    for _, row in top5.iterrows():
        lines.append(f"  {row['county']} · {row['precinct_name']}: {int(row['youth_gap']):,}")
    callout = "\n".join(lines)

    ax.text(
        0.01, 0.28, callout,
        transform=ax.transAxes,
        fontsize=8.5, color="white",
        fontfamily="monospace",
        bbox=dict(
            boxstyle="round,pad=0.5",
            facecolor="#2a1a1a",
            alpha=0.88,
            edgecolor="#d7191c",
            linewidth=1.2,
        ),
        verticalalignment="top",
    )

    # ── Legend for no-data ────────────────────────────────────────────────────
    no_data_patch = plt.Rectangle(
        (0, 0), 1, 1, fc="#3a3a4a", alpha=0.6, label="Fewer than 10 est. youth VAP"
    )
    ax.legend(
        handles=[no_data_patch],
        loc="lower left", fontsize=8,
        facecolor="#1a1a2e", edgecolor="#555555",
        labelcolor="white", framealpha=0.85,
    )

    ax.set_axis_off()
    plt.tight_layout(pad=0.8)

    plt.savefig(PNG_OUTPUT, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()

    print(f"\n✅ Static map saved to: {PNG_OUTPUT}")

    # Console summary
    print("\nTop 10 highest-gap precincts:")
    top10 = plot_gdf.nlargest(10, "youth_gap")[
        ["county", "precinct_name", "est_vap_youth", "age_18_24", "youth_gap"]
    ]
    print(top10.to_string(index=False))


if __name__ == "__main__":
    main()