"""
build_master_dataset.py
------------------------
Assembles the master precinct-level dataset for the youth voter
turnout simulator by joining:

  1. nc_voters_by_precinct.csv        -- registration + overall turnout
  2. nc_youth_turnout_by_precinct.csv -- youth votes by age band per election
  3. 2024 presidential results         -- from RDH cong + all_prec shapefiles
  4. NC exit poll calibration          -- 2024 statewide youth vote split

Key derived columns added:
  -- Turnout rates --
  youth_turnout_rate_2024   : tv_18_24_g2024 / age_18_24 (registered youth)
  overall_turnout_rate_2024 : total_votes_2024 / reg_active
  youth_share_2024          : tv_18_24_g2024 / total_votes_2024

  -- Partisan lean (overall precinct) --
  precinct_dem_pct   : harris votes / two-party total
  precinct_rep_pct   : trump votes / two-party total
  precinct_margin    : trump_pct - harris_pct (+ = R, - = D)

  -- Youth partisan lean (Option A + D blend) --
  youth_dem_pct  : blended estimate of how new youth voters vote D
  youth_rep_pct  : blended estimate of how new youth voters vote R

  Blend formula:
    EXIT_POLL_WEIGHT = 0.6  (60% weight on NC statewide exit poll)
    PRECINCT_WEIGHT  = 0.4  (40% weight on precinct partisan lean)
    youth_dem_pct = EXIT_POLL_WEIGHT * EXIT_DEM + PRECINCT_WEIGHT * precinct_dem_pct

Output:
  nc_master_precinct.csv

Requirements:
  pip install geopandas pandas numpy
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
VOTERS_CSV   = "nc_voters_by_precinct.csv"
YOUTH_CSV    = "nc_youth_turnout_by_precinct.csv"
CONG_SHP     = r"data\raw\nc_2024_gen_prec\nc_2024_gen_cong_prec\nc_2024_gen_cong_prec.shp"
ALL_SHP      = r"data\raw\nc_2024_gen_prec\nc_2024_gen_all_prec\nc_2024_gen_all_prec.shp"
OUTPUT_FILE  = "nc_master_precinct.csv"

# NC 2024 exit poll: 18-24 year olds (CCES 2024 / exit poll estimates)
# Harris 60%, Trump 40% among NC 18-24 voters
EXIT_DEM     = 0.60
EXIT_REP     = 0.40

# Blend weights: how much to trust exit poll vs precinct lean
EXIT_WEIGHT     = 0.6   # weight on statewide exit poll prior
PRECINCT_WEIGHT = 0.4   # weight on local precinct partisan lean

TRUMP_COL  = "G24PRERTRU"
HARRIS_COL = "G24PREDHAR"
# ──────────────────────────────────────────────────────────────────────────────

GROUP_REG   = ["county_desc", "precinct_abbrv"]
GROUP_YOUTH = ["county_desc", "precinct_abbrv"]


def load_census() -> pd.DataFrame:
    """
    Load 2020 Census block-level population (exact counts, no apportionment)
    and supplement with ACS estimates for age sub-bands (18-24 etc.)
    since PL 94-171 only has total 18+, not age sub-groups.
    """
    import geopandas as gpd

    print("Loading 2020 Census block population data...")
    df = pd.read_csv("nc_pop_by_precinct.csv",
                     dtype={"county_desc": str, "precinct_abbrv": str})
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()
    print(f"  {len(df):,} precincts. Total pop: {df['pop_total'].sum():,.0f}")
    print(f"  VAP total: {df['vap_total'].sum():,.0f}")

    # Pull age sub-bands from ACS GeoJSON (still needed for youth analysis)
    print("  Supplementing with ACS age bands from nc_precincts.geojson...")
    gdf = gpd.read_file("nc_precincts.geojson")
    gdf["county"]      = gdf["county"].str.strip().str.upper()
    gdf["precinct_id"] = gdf["precinct_id"].str.strip().str.upper()
    acs_cols = ["county", "precinct_id", "pop_18_24", "est_vap_youth",
                "pop_25_34", "pop_35_44", "pop_45_54",
                "pop_55_64", "pop_65_74", "pop_75plus",
                "pct_18_24", "pct_65plus", "youth_gap", "youth_gap_pct"]
    acs_cols = [c for c in acs_cols if c in gdf.columns]
    acs = pd.DataFrame(gdf[acs_cols]).rename(columns={
        "county":      "county_desc",
        "precinct_id": "precinct_abbrv",
    })
    df = df.merge(acs, on=["county_desc", "precinct_abbrv"], how="left")
    print(f"  ACS age bands merged for {df['pop_18_24'].notna().sum():,} precincts.")
    return df


def load_registration() -> pd.DataFrame:
    print("Loading registration file...")
    df = pd.read_csv(VOTERS_CSV, dtype={"county_desc": str, "precinct_abbrv": str})
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()

    # Keep key registration columns
    keep = [
        "county_desc", "precinct_abbrv", "precinct_desc",
        "reg_total", "reg_active", "reg_inactive",
        "party_dem", "party_rep", "party_unaf", "party_lib", "party_other",
        "race_white", "race_black", "race_asian", "race_aian",
        "eth_hispanic",
        "gender_male", "gender_female",
        "age_18_24", "age_25_34", "age_35_44",
        "age_45_54", "age_55_64", "age_65_74", "age_75plus",
        # Overall turnout from voter history (all ages)
        "votes_11/05/2024", "votes_11/03/2020", "votes_11/06/2018",
        "turnout_11/05/2024", "turnout_11/03/2020", "turnout_11/06/2018",
    ]
    keep = [c for c in keep if c in df.columns]
    df = df[keep]

    # Rename turnout cols for clarity
    rename = {
        "votes_11/05/2024":   "total_votes_g2024",
        "votes_11/03/2020":   "total_votes_g2020",
        "votes_11/06/2018":   "total_votes_g2018",
        "turnout_11/05/2024": "turnout_rate_g2024",
        "turnout_11/03/2020": "turnout_rate_g2020",
        "turnout_11/06/2018": "turnout_rate_g2018",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    print(f"  {len(df):,} precincts loaded.")
    return df


def load_youth_turnout() -> pd.DataFrame:
    print("Loading youth turnout file...")
    df = pd.read_csv(YOUTH_CSV, dtype={"county_desc": str, "precinct_abbrv": str})
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()

    # Keep youth (18-24) and total columns for our key elections
    keep_patterns = ["county_desc", "precinct_abbrv",
                     "tv_18_24", "tv_25_34", "tv_total"]
    keep = [c for c in df.columns if any(p in c for p in keep_patterns)]
    df = df[keep]

    print(f"  {len(df):,} precincts. Youth columns: {[c for c in df.columns if 'tv_' in c]}")
    return df


def load_election_results() -> pd.DataFrame:
    print("Loading 2024 election results...")
    cong = gpd.read_file(CONG_SHP)
    cong["COUNTY"]   = cong["COUNTY"].str.strip().str.upper()
    cong["PRECINCT"] = cong["PRECINCT"].str.strip().str.upper()
    cong = cong.dissolve(by=["COUNTY", "PRECINCT"]).reset_index()

    votes = gpd.read_file(ALL_SHP)
    votes["COUNTY"]   = votes["COUNTY"].str.strip().str.upper()
    votes["PRECINCT"] = votes["PRECINCT"].str.strip().str.upper()
    for col in [TRUMP_COL, HARRIS_COL]:
        votes[col] = pd.to_numeric(votes[col], errors="coerce").fillna(0)

    # Also grab governor race for comparison
    gov_cols = ["G24GOVDSTE", "G24GOVRROB"]
    for col in gov_cols:
        if col in votes.columns:
            votes[col] = pd.to_numeric(votes[col], errors="coerce").fillna(0)

    result_cols = ["COUNTY", "PRECINCT", TRUMP_COL, HARRIS_COL] + \
                  [c for c in gov_cols if c in votes.columns]
    votes = votes[result_cols]

    results = cong[["COUNTY", "PRECINCT"]].merge(votes, on=["COUNTY", "PRECINCT"], how="left")
    results = results.rename(columns={
        "COUNTY":    "county_desc",
        "PRECINCT":  "precinct_abbrv",
        TRUMP_COL:   "v_trump_2024",
        HARRIS_COL:  "v_harris_2024",
        "G24GOVDSTE":"v_stein_gov_2024",
        "G24GOVRROB":"v_robinson_gov_2024",
    })
    print(f"  {len(results):,} precincts with election results.")
    return results


def compute_partisan_lean(df: pd.DataFrame) -> pd.DataFrame:
    """Compute overall precinct partisan lean from 2024 presidential results."""
    df["two_pty_2024"]     = df["v_trump_2024"] + df["v_harris_2024"]
    df["precinct_rep_pct"] = np.where(df["two_pty_2024"] > 0,
                                       df["v_trump_2024"]  / df["two_pty_2024"], np.nan)
    df["precinct_dem_pct"] = np.where(df["two_pty_2024"] > 0,
                                       df["v_harris_2024"] / df["two_pty_2024"], np.nan)
    df["precinct_margin"]  = df["precinct_rep_pct"] - df["precinct_dem_pct"]

    # Competitiveness label
    def comp(m):
        if pd.isna(m):    return "no_data"
        if abs(m) <= 0.05: return "tossup"
        if abs(m) <= 0.10: return "competitive"
        if abs(m) <= 0.20: return "lean"
        return                   "safe"

    df["competitiveness"] = df["precinct_margin"].apply(comp)
    df["winner_2024"]     = np.where(df["precinct_margin"].isna(), "no_data",
                            np.where(df["precinct_margin"] > 0, "Trump", "Harris"))
    return df


def compute_youth_lean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute two versions of youth partisan lean:

    Version 1 — Precinct lean only (Option A, no exit poll):
      youth_dem_pct_raw / youth_rep_pct_raw
      Assumes new youth voters follow the same D/R split as the
      overall precinct. No external calibration applied.

    Version 2 — Blended with exit poll (Option A + D):
      youth_dem_pct / youth_rep_pct
      60% weight on NC statewide exit poll (Harris 60%, Trump 40%)
      40% weight on local precinct lean.
      More realistic — youth skew more Dem even in red precincts.

    For precincts with no election data, both fall back to exit poll.
    """
    has_results = df["precinct_dem_pct"].notna()

    # ── Version 1: Precinct lean only (no exit poll calibration) ─────────────
    df["youth_dem_pct_raw"] = np.where(
        has_results,
        df["precinct_dem_pct"],
        EXIT_DEM,  # fallback for precincts with no results
    )
    df["youth_rep_pct_raw"] = np.where(
        has_results,
        df["precinct_rep_pct"],
        EXIT_REP,
    )
    # Normalize
    total_raw = df["youth_dem_pct_raw"] + df["youth_rep_pct_raw"]
    df["youth_dem_pct_raw"] = (df["youth_dem_pct_raw"] / total_raw.replace(0, np.nan)).fillna(EXIT_DEM)
    df["youth_rep_pct_raw"] = (df["youth_rep_pct_raw"] / total_raw.replace(0, np.nan)).fillna(EXIT_REP)

    # ── Version 2: Blended with exit poll (60% exit poll, 40% precinct) ──────
    df["youth_dem_pct"] = np.where(
        has_results,
        EXIT_WEIGHT * EXIT_DEM + PRECINCT_WEIGHT * df["precinct_dem_pct"],
        EXIT_DEM,
    )
    df["youth_rep_pct"] = np.where(
        has_results,
        EXIT_WEIGHT * EXIT_REP + PRECINCT_WEIGHT * df["precinct_rep_pct"],
        EXIT_REP,
    )
    # Normalize
    total = df["youth_dem_pct"] + df["youth_rep_pct"]
    df["youth_dem_pct"] = (df["youth_dem_pct"] / total.replace(0, np.nan)).fillna(EXIT_DEM)
    df["youth_rep_pct"] = (df["youth_rep_pct"] / total.replace(0, np.nan)).fillna(EXIT_REP)

    return df


def compute_turnout_rates(df: pd.DataFrame) -> pd.DataFrame:
    """Compute youth and overall turnout rates."""

    # Overall turnout rate (already in voter file as turnout_rate_g2024)
    # Recompute from raw for consistency
    df["overall_turnout_2024"] = (
        df["total_votes_g2024"] / df["reg_active"].replace(0, np.nan)
    ).clip(0, 1).round(4)

    # Youth turnout rate = youth votes cast / youth registered
    if "tv_18_24_g2024" in df.columns:
        df["youth_turnout_2024"] = (
            df["tv_18_24_g2024"] / df["age_18_24"].replace(0, np.nan)
        ).clip(0, 1.5).round(4)  # allow slightly over 1 for data quirks

        # Youth share of total electorate
        df["youth_share_2024"] = (
            df["tv_18_24_g2024"] / df["total_votes_g2024"].replace(0, np.nan)
        ).clip(0, 1).round(4)

        # Youth turnout gap vs overall (negative = youth underperform)
        df["youth_turnout_gap"] = (
            df["youth_turnout_2024"] - df["overall_turnout_2024"]
        ).round(4)

    # Same for 2018
    if "tv_18_24_g2018" in df.columns:
        df["youth_turnout_2018"] = (
            df["tv_18_24_g2018"] / df["age_18_24"].replace(0, np.nan)
        ).clip(0, 1.5).round(4)

    return df


def main():
    # ── Load all sources ──────────────────────────────────────────────────────
    census  = load_census()
    reg     = load_registration()
    youth   = load_youth_turnout()
    results = load_election_results()

    # ── Join Census + registration + youth turnout ────────────────────────────
    print("\nJoining Census + registration + youth turnout...")
    df = reg.merge(census, on=GROUP_REG, how="left")
    census_matched = df["est_vap_youth"].notna().sum()
    print(f"  Census matched: {census_matched:,} / {len(df):,} precincts")
    df = df.merge(youth, on=GROUP_REG, how="left")
    print(f"  {len(df):,} precincts after join.")

    # ── Join election results ─────────────────────────────────────────────────
    print("Joining 2024 election results...")
    df = df.merge(results, on=GROUP_REG, how="left")
    matched = df["v_trump_2024"].notna().sum()
    print(f"  {matched:,} / {len(df):,} precincts matched to election results.")

    # ── Compute derived columns ───────────────────────────────────────────────
    print("Computing partisan lean...")
    df = compute_partisan_lean(df)

    print("Computing youth partisan lean (Option A + D blend)...")
    df = compute_youth_lean(df)

    print("Computing turnout rates...")
    df = compute_turnout_rates(df)

    # ── Fill NaN ──────────────────────────────────────────────────────────────
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].fillna(0)

    # ── Save ──────────────────────────────────────────────────────────────────
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! {len(df):,} precincts saved to: {OUTPUT_FILE}")
    print(f"   Total columns: {len(df.columns)}")

    print(f"\n   Key statewide metrics:")
    print(f"   reg_active:            {df['reg_active'].sum():>12,.0f}")
    print(f"   age_18_24 registered:  {df['age_18_24'].sum():>12,.0f}")
    if "tv_18_24_g2024" in df.columns:
        print(f"   youth votes 2024:      {df['tv_18_24_g2024'].sum():>12,.0f}")
    print(f"   total votes 2024:      {df['total_votes_g2024'].sum():>12,.0f}")
    print(f"   trump votes 2024:      {df['v_trump_2024'].sum():>12,.0f}")
    print(f"   harris votes 2024:     {df['v_harris_2024'].sum():>12,.0f}")

    print(f"\n   Youth turnout summary:")
    if "youth_turnout_2024" in df.columns:
        valid = df[df["youth_turnout_2024"] > 0]
        print(f"   Avg youth turnout 2024:   {valid['youth_turnout_2024'].mean():.1%}")
        print(f"   Avg overall turnout 2024: {valid['overall_turnout_2024'].mean():.1%}")
        print(f"   Avg youth turnout gap:    {valid['youth_turnout_gap'].mean():.1%}")

    print(f"\n   Youth partisan lean:")
    print(f"   Version 1 — precinct lean only (no exit poll):")
    print(f"     Avg youth_dem_pct_raw: {df['youth_dem_pct_raw'].mean():.1%}")
    print(f"     Avg youth_rep_pct_raw: {df['youth_rep_pct_raw'].mean():.1%}")
    print(f"   Version 2 — blended with exit poll (60/40 prior):")
    print(f"     Avg youth_dem_pct:     {df['youth_dem_pct'].mean():.1%}")
    print(f"     Avg youth_rep_pct:     {df['youth_rep_pct'].mean():.1%}")

    print(f"\n   Competitiveness breakdown:")
    print(df["competitiveness"].value_counts().to_string())


if __name__ == "__main__":
    main()