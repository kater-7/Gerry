"""
simulate_youth_turnout.py
--------------------------
Simulates the effect of increased youth voter turnout on election outcomes
at the precinct, congressional, state senate, and state house levels.

HOW IT WORKS:
  1. Loads master precinct dataset (nc_master_precinct.csv)
  2. Computes the pool of non-voting youth per precinct:
       youth_nonvoters = est_vap_youth - tv_18_24_g2024
  3. Adds YOUTH_UPLIFT % of that pool as new voters
  4. Splits new votes using youth partisan lean (both raw and blended)
  5. Recomputes precinct winners
  6. Joins district assignments from RDH shapefiles
  7. Aggregates to district level → recomputes district winners
  8. Reports flipped precincts and districts

PLUG IN YOUR SCENARIO:
  Change YOUTH_UPLIFT below. Examples:
    0.05 = 5% more of non-voting youth show up
    0.10 = 10%
    0.20 = 20%
    0.50 = 50%

OUTPUTS:
  sim_results_{pct}pct.csv          -- full precinct-level results
  sim_district_results_{pct}pct.csv -- district-level winners
  sim_flipped_{pct}pct.csv          -- only flipped precincts/districts

Requirements:
  pip install geopandas pandas numpy
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings("ignore")

# ── PLUG IN YOUR SCENARIO HERE ────────────────────────────────────────────────
YOUTH_UPLIFT = 1   # <-- change to 0.05, 0.10, 0.20, 0.50 etc.
# ──────────────────────────────────────────────────────────────────────────────

# ── CONFIG ────────────────────────────────────────────────────────────────────
MASTER_CSV  = "nc_master_precinct.csv"
CONG_SHP    = r"data\raw\nc_2024_gen_prec\nc_2024_gen_cong_prec\nc_2024_gen_cong_prec.shp"
SLDU_SHP    = r"data\raw\nc_2024_gen_prec\nc_2024_gen_sldu_prec\nc_2024_gen_sldu_prec.shp"
SLDL_SHP    = r"data\raw\nc_2024_gen_prec\nc_2024_gen_sldl_prec\nc_2024_gen_sldl_prec.shp"

PCT_LABEL   = f"{int(YOUTH_UPLIFT * 100)}pct"
OUT_PREC    = f"sim_results_{PCT_LABEL}.csv"
OUT_DIST    = f"sim_district_results_{PCT_LABEL}.csv"
OUT_FLIP    = f"sim_flipped_{PCT_LABEL}.csv"
# ──────────────────────────────────────────────────────────────────────────────


def load_district_assignments() -> pd.DataFrame:
    """
    Load precinct -> district mappings from RDH shapefiles.
    District number parsed from UNIQUE_ID.

    For split precincts (appearing in multiple districts), we keep
    ALL rows so each precinct-district split gets its own record.
    Simulation votes are then apportioned by share of precinct votes
    in each split when aggregating to district level.
    """
    print("Loading district assignments...")

    def load_shp(path, pattern, dist_label):
        gdf = gpd.read_file(path)
        gdf["COUNTY"]   = gdf["COUNTY"].str.strip().str.upper()
        gdf["PRECINCT"] = gdf["PRECINCT"].str.strip().str.upper()
        # Parse district from UNIQUE_ID
        gdf[dist_label] = gdf["UNIQUE_ID"].str.extract(pattern, expand=False)
        gdf[dist_label] = pd.to_numeric(gdf[dist_label], errors="coerce")
        result = gdf[["COUNTY", "PRECINCT", dist_label, "UNIQUE_ID"]].copy()
        n_dist = result[dist_label].nunique()
        n_prec = result[["COUNTY","PRECINCT"]].drop_duplicates().shape[0]
        print(f"  {dist_label}: {n_dist} districts, {n_prec:,} unique precincts, "
              f"{len(result):,} rows (incl. splits)")
        return result

    cong = load_shp(CONG_SHP, r"CON-(\d+)", "cong_dist")
    sldu = load_shp(SLDU_SHP, r"SU-(\d+)",  "sldu_dist")
    sldl = load_shp(SLDL_SHP, r"SL-(\d+)",  "sldl_dist")

    # Merge all three — outer join on COUNTY+PRECINCT+UNIQUE_ID
    # keeps split rows intact
    districts = cong.merge(
        sldu[["COUNTY","PRECINCT","UNIQUE_ID","sldu_dist"]],
        on=["COUNTY","PRECINCT","UNIQUE_ID"], how="outer"
    ).merge(
        sldl[["COUNTY","PRECINCT","UNIQUE_ID","sldl_dist"]],
        on=["COUNTY","PRECINCT","UNIQUE_ID"], how="outer"
    )

    # Count splits per precinct (useful for apportionment)
    split_counts = (
        districts.groupby(["COUNTY","PRECINCT"])
        .size()
        .rename("n_splits")
        .reset_index()
    )
    districts = districts.merge(split_counts, on=["COUNTY","PRECINCT"])

    districts = districts.rename(columns={
        "COUNTY":   "county_desc",
        "PRECINCT": "precinct_abbrv",
    })
    print(f"  {len(districts):,} total precinct-district rows after merge.")
    return districts


def simulate(df: pd.DataFrame, uplift: float) -> pd.DataFrame:
    """
    Core simulation logic.
    For each precinct:
      new_youth_voters = youth_nonvoters * uplift
      new_dem_votes    = new_youth_voters * youth_dem_pct
      new_rep_votes    = new_youth_voters * youth_rep_pct
      sim_trump        = v_trump_2024 + new_rep_votes
      sim_harris       = v_harris_2024 + new_dem_votes

    Run twice: once with raw lean, once with blended lean.
    """
    sim = df.copy()

    # ── Pool of non-voting youth ──────────────────────────────────────────────
    # We use REGISTERED youth who didn't vote as the pool.
    # This is more accurate than est_vap_youth because:
    #   - age_18_24 comes from actual voter registration data
    #   - est_vap_youth is a Census area-weighted estimate that
    #     underestimates dense urban/college precincts
    #
    # Pool = registered 18-24 year olds who did not vote in 2024
    # Uplift % = share of that pool who show up in the simulation
    #
    # Note: this is a conservative estimate — it excludes unregistered
    # youth entirely. The youth_gap column captures unregistered youth
    # but relies on the imperfect Census apportionment.
    sim["youth_nonvoters"] = (
        sim["age_18_24"] - sim["tv_18_24_g2024"]
    ).clip(lower=0)

    sim["new_youth_voters"] = (sim["youth_nonvoters"] * uplift).round(0)

    # ── Version 1: Raw precinct lean (no exit poll) ───────────────────────────
    sim["new_dem_raw"]    = (sim["new_youth_voters"] * sim["youth_dem_pct_raw"]).round(0)
    sim["new_rep_raw"]    = (sim["new_youth_voters"] * sim["youth_rep_pct_raw"]).round(0)
    sim["sim_trump_raw"]  = sim["v_trump_2024"]  + sim["new_rep_raw"]
    sim["sim_harris_raw"] = sim["v_harris_2024"] + sim["new_dem_raw"]
    sim["sim_total_raw"]  = sim["sim_trump_raw"] + sim["sim_harris_raw"]

    sim["sim_margin_raw"] = np.where(
        sim["sim_total_raw"] > 0,
        (sim["sim_trump_raw"] - sim["sim_harris_raw"]) / sim["sim_total_raw"] * 100,
        np.nan,
    )
    sim["sim_winner_raw"] = np.where(
        sim["sim_margin_raw"].isna(), "no_data",
        np.where(sim["sim_margin_raw"] > 0, "Trump", "Harris"),
    )

    # ── Version 2: Blended exit poll lean ────────────────────────────────────
    sim["new_dem_blend"]    = (sim["new_youth_voters"] * sim["youth_dem_pct"]).round(0)
    sim["new_rep_blend"]    = (sim["new_youth_voters"] * sim["youth_rep_pct"]).round(0)
    sim["sim_trump_blend"]  = sim["v_trump_2024"]  + sim["new_rep_blend"]
    sim["sim_harris_blend"] = sim["v_harris_2024"] + sim["new_dem_blend"]
    sim["sim_total_blend"]  = sim["sim_trump_blend"] + sim["sim_harris_blend"]

    sim["sim_margin_blend"] = np.where(
        sim["sim_total_blend"] > 0,
        (sim["sim_trump_blend"] - sim["sim_harris_blend"]) / sim["sim_total_blend"] * 100,
        np.nan,
    )
    sim["sim_winner_blend"] = np.where(
        sim["sim_margin_blend"].isna(), "no_data",
        np.where(sim["sim_margin_blend"] > 0, "Trump", "Harris"),
    )

    # ── Flag flipped precincts ────────────────────────────────────────────────
    sim["flipped_raw"]   = (
        sim["winner_2024"].notna() &
        sim["sim_winner_raw"].notna() &
        (sim["winner_2024"] != "no_data") &
        (sim["sim_winner_raw"] != "no_data") &
        (sim["winner_2024"] != sim["sim_winner_raw"])
    )
    sim["flipped_blend"] = (
        sim["winner_2024"].notna() &
        sim["sim_winner_blend"].notna() &
        (sim["winner_2024"] != "no_data") &
        (sim["sim_winner_blend"] != "no_data") &
        (sim["winner_2024"] != sim["sim_winner_blend"])
    )

    return sim


def aggregate_districts(sim: pd.DataFrame, districts: pd.DataFrame) -> pd.DataFrame:
    """
    Join district assignments and aggregate precinct votes to district level.
    Compute district winners under baseline and both simulation versions.
    """
    print("Aggregating to district level...")

    # Join district assignments (keeps split precinct rows)
    sim_dist = sim.merge(districts, on=["county_desc", "precinct_abbrv"], how="left")

    # Apportion votes for split precincts equally across splits
    # e.g. a precinct in 2 districts gets 50% of its votes assigned to each
    for col in ["v_trump_2024","v_harris_2024",
                "sim_trump_raw","sim_harris_raw",
                "sim_trump_blend","sim_harris_blend"]:
        if col in sim_dist.columns:
            sim_dist[col] = sim_dist[col] / sim_dist["n_splits"].fillna(1)

    dist_cols = ["cong_dist", "sldu_dist", "sldl_dist"]
    vote_cols = {
        "baseline": ("v_trump_2024",    "v_harris_2024"),
        "raw":      ("sim_trump_raw",   "sim_harris_raw"),
        "blend":    ("sim_trump_blend", "sim_harris_blend"),
    }

    all_results = []

    for dist_col in dist_cols:
        if dist_col not in sim_dist.columns:
            continue

        valid = sim_dist[sim_dist[dist_col].notna()].copy()
        if len(valid) == 0:
            continue

        for version, (trump_col, harris_col) in vote_cols.items():
            agg = valid.groupby(dist_col).agg(
                trump_votes    = (trump_col,  "sum"),
                harris_votes   = (harris_col, "sum"),
                precinct_count = (trump_col,  "count"),
            ).reset_index()

            agg["total_votes"] = agg["trump_votes"] + agg["harris_votes"]
            agg["margin_pct"]  = np.where(
                agg["total_votes"] > 0,
                (agg["trump_votes"] - agg["harris_votes"]) / agg["total_votes"] * 100,
                np.nan,
            ).round(2)
            agg["winner"]       = np.where(agg["margin_pct"] > 0, "Trump", "Harris")
            agg["district_type"] = dist_col
            agg["version"]       = version
            agg = agg.rename(columns={dist_col: "district"})
            all_results.append(agg)

    dist_df = pd.concat(all_results, ignore_index=True)

    # Pivot to compare baseline vs simulations side by side
    baseline = dist_df[dist_df["version"] == "baseline"][
        ["district_type", "district", "trump_votes", "harris_votes",
         "total_votes", "margin_pct", "winner"]
    ].rename(columns={
        "trump_votes":  "base_trump",
        "harris_votes": "base_harris",
        "total_votes":  "base_total",
        "margin_pct":   "base_margin",
        "winner":       "base_winner",
    })

    for version in ["raw", "blend"]:
        ver = dist_df[dist_df["version"] == version][
            ["district_type", "district", "trump_votes", "harris_votes",
             "margin_pct", "winner"]
        ].rename(columns={
            "trump_votes":  f"sim_trump_{version}",
            "harris_votes": f"sim_harris_{version}",
            "margin_pct":   f"sim_margin_{version}",
            "winner":       f"sim_winner_{version}",
        })
        baseline = baseline.merge(ver, on=["district_type", "district"], how="left")

    # Flag flipped districts
    baseline["flipped_raw"]   = baseline["base_winner"] != baseline["sim_winner_raw"]
    baseline["flipped_blend"] = baseline["base_winner"] != baseline["sim_winner_blend"]

    return baseline, sim


def make_district_map(dist_df: pd.DataFrame, uplift: float):
    """
    Build a congressional district map colored by simulated winner (blended lean).
    Districts that flipped from baseline are outlined in gold.
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    import geopandas as gpd

    pct   = int(uplift * 100)
    print(f"\nBuilding congressional district map...")

    # ── Load cong shapefile and dissolve to district level ────────────────────
    cong_shp = gpd.read_file(CONG_SHP)
    cong_shp["cong_dist"] = cong_shp["UNIQUE_ID"].str.extract(r"CON-(\d+)", expand=False)
    cong_shp["cong_dist"] = pd.to_numeric(cong_shp["cong_dist"], errors="coerce")
    cong_shp = cong_shp[cong_shp["cong_dist"].notna()].copy()

    # Dissolve all precinct polygons into district polygons
    dist_geom = cong_shp.dissolve(by="cong_dist").reset_index()[["cong_dist","geometry"]]
    dist_geom = dist_geom.to_crs(epsg=4326)

    # ── Join simulation results ───────────────────────────────────────────────
    cong_results = dist_df[dist_df["district_type"] == "cong_dist"].copy()
    cong_results["district"] = pd.to_numeric(cong_results["district"], errors="coerce")

    merged = dist_geom.merge(
        cong_results[["district","base_winner","sim_winner_blend",
                      "base_margin","sim_margin_blend","flipped_blend"]],
        left_on="cong_dist", right_on="district", how="left"
    )

    if len(merged) == 0 or merged["sim_winner_blend"].isna().all():
        print("  ⚠  No district results to map — skipping map.")
        return

    # ── Colors ────────────────────────────────────────────────────────────────
    def winner_color(w):
        if w == "Trump":  return "#d44a4a"
        if w == "Harris": return "#4a9fd4"
        return "#cccccc"

    merged["fill_color"] = merged["sim_winner_blend"].apply(winner_color)

    # ── Filter valid geometries ───────────────────────────────────────────────
    merged = merged[
        merged.geometry.notna() &
        ~merged.geometry.is_empty &
        merged.geometry.is_valid
    ].copy()

    if len(merged) == 0:
        print("  No valid geometries to plot.")
        return

    # ── Plot ──────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(1, 1, figsize=(18, 10))
    fig.patch.set_facecolor("#0f0f1a")
    ax.set_facecolor("#0f0f1a")

    # Draw all districts in one call — red for Trump, blue for Harris
    trump_gdf  = merged[merged["sim_winner_blend"] == "Trump"]
    harris_gdf = merged[merged["sim_winner_blend"] == "Harris"]
    other_gdf  = merged[~merged["sim_winner_blend"].isin(["Trump","Harris"])]

    if len(trump_gdf) > 0:
        trump_gdf.plot(ax=ax, color="#d44a4a", edgecolor="white",
                       linewidth=1.2, alpha=0.9, aspect=None)
    if len(harris_gdf) > 0:
        harris_gdf.plot(ax=ax, color="#4a9fd4", edgecolor="white",
                        linewidth=1.2, alpha=0.9, aspect=None)
    if len(other_gdf) > 0:
        other_gdf.plot(ax=ax, color="#cccccc", edgecolor="white",
                       linewidth=1.2, alpha=0.9, aspect=None)

    # Gold outline for flipped districts
    flipped = merged[merged["flipped_blend"] == True]
    if len(flipped) > 0:
        flipped.plot(ax=ax, facecolor="none", edgecolor="#FFD700",
                     linewidth=3.5, aspect=None)

    # Label each district
    for _, row in merged.iterrows():
        try:
            centroid = row.geometry.centroid
            dist_num = int(row["cong_dist"]) if not pd.isna(row["cong_dist"]) else "?"
            margin   = row["sim_margin_blend"]
            margin_s = f"{abs(margin):.1f}%" if not pd.isna(margin) else ""
            ax.text(centroid.x, centroid.y, f"CD-{dist_num}\n{margin_s}",
                    ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold")
        except Exception:
            pass

    # ── Title & legend ────────────────────────────────────────────────────────
    ax.set_title(
        f"2024 NC Congressional Districts — Simulated Winner ({pct}% Youth Uplift)",
        fontsize=18, fontweight="bold", color="white", pad=14, loc="left",
    )
    ax.text(0, -0.04,
            f"Blended lean model (60% exit poll + 40% precinct lean)  |  "
            f"Based on {pct}% increase in registered-but-non-voting youth  |  "
            f"Gold outline = flipped from 2024 baseline",
            transform=ax.transAxes, fontsize=8.5, color="#aaaaaa")

    trump_patch  = mpatches.Patch(color="#d44a4a", label="Trump (R)")
    harris_patch = mpatches.Patch(color="#4a9fd4", label="Harris (D)")
    flip_patch   = mpatches.Patch(facecolor="none", edgecolor="#FFD700",
                                   linewidth=2, label="Flipped from baseline")
    ax.legend(handles=[trump_patch, harris_patch, flip_patch],
              loc="lower left", fontsize=9,
              facecolor="#1a1a2e", edgecolor="#555577",
              labelcolor="white", framealpha=0.9)

    # District count summary
    trump_n  = (merged["sim_winner_blend"] == "Trump").sum()
    harris_n = (merged["sim_winner_blend"] == "Harris").sum()
    flip_n   = merged["flipped_blend"].sum()
    summary  = (f"  Congressional Districts:\n"
                f"  Trump (R):  {trump_n}\n"
                f"  Harris (D): {harris_n}\n"
                f"  Flipped:    {flip_n}")
    ax.text(0.01, 0.25, summary, transform=ax.transAxes,
            fontsize=9, color="white", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#1a1a2e",
                      alpha=0.88, edgecolor="#555577"),
            verticalalignment="top")

    ax.set_axis_off()
    plt.tight_layout(pad=0.8)

    out = f"sim_cong_map_{pct}pct.png"
    plt.savefig(out, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"  ✅ Map saved: {out}")


def print_summary(sim: pd.DataFrame, dist_df: pd.DataFrame, uplift: float):
    pct = int(uplift * 100)
    print(f"\n{'='*60}")
    print(f"  SIMULATION RESULTS — {pct}% Youth Turnout Increase")
    print(f"{'='*60}")

    print(f"\n  New youth voters added: {sim['new_youth_voters'].sum():,.0f}")
    print(f"  (from pool of {sim['youth_nonvoters'].sum():,.0f} non-voting youth)")

    # Statewide totals
    print(f"\n  STATEWIDE PRESIDENTIAL TOTALS:")
    print(f"  {'':25} {'Baseline':>12} {'Raw lean':>12} {'Blended':>12}")
    print(f"  {'-'*63}")
    print(f"  {'Trump votes':25} {sim['v_trump_2024'].sum():>12,.0f} "
          f"{sim['sim_trump_raw'].sum():>12,.0f} {sim['sim_trump_blend'].sum():>12,.0f}")
    print(f"  {'Harris votes':25} {sim['v_harris_2024'].sum():>12,.0f} "
          f"{sim['sim_harris_raw'].sum():>12,.0f} {sim['sim_harris_blend'].sum():>12,.0f}")

    base_margin   = sim['v_trump_2024'].sum() - sim['v_harris_2024'].sum()
    raw_margin    = sim['sim_trump_raw'].sum() - sim['sim_harris_raw'].sum()
    blend_margin  = sim['sim_trump_blend'].sum() - sim['sim_harris_blend'].sum()
    print(f"  {'Trump margin':25} {base_margin:>+12,.0f} "
          f"{raw_margin:>+12,.0f} {blend_margin:>+12,.0f}")

    # Flipped precincts
    print(f"\n  FLIPPED PRECINCTS:")
    raw_flips   = sim["flipped_raw"].sum()
    blend_flips = sim["flipped_blend"].sum()
    print(f"  Raw lean:    {raw_flips:,} precincts flipped")
    print(f"  Blended:     {blend_flips:,} precincts flipped")

    if raw_flips > 0:
        flipped = sim[sim["flipped_raw"]][
            ["county_desc","precinct_abbrv","winner_2024",
             "sim_winner_raw","precinct_margin","sim_margin_raw","new_youth_voters"]
        ].head(10)
        print(f"\n  Sample flipped precincts (raw lean):")
        print(flipped.to_string(index=False))

    # Flipped districts
    print(f"\n  FLIPPED DISTRICTS:")
    for dist_type in ["cong_dist", "sldu_dist", "sldl_dist"]:
        subset = dist_df[dist_df["district_type"] == dist_type]
        raw_d   = subset["flipped_raw"].sum()
        blend_d = subset["flipped_blend"].sum()
        label   = {"cong_dist": "Congressional",
                   "sldu_dist": "State Senate",
                   "sldl_dist": "State House"}[dist_type]
        print(f"  {label:<20} Raw: {raw_d:>3}  Blended: {blend_d:>3}")

        flipped_dist = subset[subset["flipped_blend"]][
            ["district","base_winner","sim_winner_blend",
             "base_margin","sim_margin_blend"]
        ]
        if len(flipped_dist) > 0:
            print(f"    Flipped (blended):")
            print(flipped_dist.to_string(index=False))

    print(f"\n{'='*60}")


def main():
    pct = int(YOUTH_UPLIFT * 100)
    print(f"Youth Turnout Simulator — {pct}% uplift scenario\n")

    # ── Load master dataset ───────────────────────────────────────────────────
    print("Loading master precinct dataset...")
    df = pd.read_csv(MASTER_CSV, dtype={"county_desc": str, "precinct_abbrv": str})
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()
    print(f"  {len(df):,} precincts loaded.")

    # Ensure required columns exist
    required = ["age_18_24", "tv_18_24_g2024", "v_trump_2024", "v_harris_2024",
                "youth_dem_pct", "youth_rep_pct", "youth_dem_pct_raw", "youth_rep_pct_raw",
                "winner_2024"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"❌ Missing columns: {missing}")
        print("   Re-run build_master_dataset.py first.")
        return

    # ── Load district assignments ─────────────────────────────────────────────
    districts = load_district_assignments()

    # ── Run simulation ────────────────────────────────────────────────────────
    print(f"\nRunning simulation at {pct}% youth uplift...")
    sim = simulate(df, YOUTH_UPLIFT)

    # ── Aggregate to districts ────────────────────────────────────────────────
    dist_df, sim = aggregate_districts(sim, districts)

    # ── Print summary ─────────────────────────────────────────────────────────
    print_summary(sim, dist_df, YOUTH_UPLIFT)
    make_district_map(dist_df, YOUTH_UPLIFT)

    # ── Save outputs ──────────────────────────────────────────────────────────
    sim.to_csv(OUT_PREC, index=False)
    dist_df.to_csv(OUT_DIST, index=False)

    # Flipped precincts only
    flipped = sim[sim["flipped_raw"] | sim["flipped_blend"]].copy()
    flipped.to_csv(OUT_FLIP, index=False)

    print(f"\n  Files saved:")
    print(f"  {OUT_PREC}   — full precinct results")
    print(f"  {OUT_DIST}   — district-level results")
    print(f"  {OUT_FLIP}   — flipped precincts only")
    print(f"\n  To run a different scenario, change YOUTH_UPLIFT at the top")
    print(f"  and rerun. Try: 0.05, 0.10, 0.20, 0.50")


if __name__ == "__main__":
    main()