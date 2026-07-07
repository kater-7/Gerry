"""
fetch_dhc_youth_vap.py
-----------------------
Pulls 2020 Census DHC (Demographic and Housing Characteristics)
block-level population aged 18-24 for North Carolina.

Unlike the PL 94-171 file which only has total 18+, the DHC file
has population by single year of age at the block level, letting
us compute exact 18-24 VAP per Census block.

Then joins directly to the RDH 2024 precinct shapefile on GEOID20
for an exact youth VAP count per precinct — no apportionment needed.

DHC variables used (male + female, ages 18-24):
  PCT12_026N  Male: 18 years
  PCT12_027N  Male: 19 years
  PCT12_028N  Male: 20 years
  PCT12_029N  Male: 21 years
  PCT12_030N  Male: 22 years
  PCT12_031N  Male: 23 years
  PCT12_032N  Male: 24 years
  PCT12_068N  Female: 18 years
  PCT12_069N  Female: 19 years
  PCT12_070N  Female: 20 years
  PCT12_071N  Female: 21 years
  PCT12_072N  Female: 22 years
  PCT12_073N  Female: 23 years
  PCT12_074N  Female: 24 years

Also pulls:
  P1_001N     Total population (for reference)
  P3_001N     Total VAP 18+ (for reference)

Outputs:
  nc_dhc_blocks_youth.csv       -- one row per block with youth VAP
  nc_youth_vap_by_precinct.csv  -- aggregated to 2024 RDH precincts

Requirements:
  pip install requests pandas geopandas
"""

import requests
import pandas as pd
import geopandas as gpd
import os
import time
import warnings
warnings.filterwarnings("ignore")

# ── CONFIG ────────────────────────────────────────────────────────────────────
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "a06207caa3490ef482e89196770ed4aab23428cb")
STATE_FIPS     = "37"   # North Carolina

# RDH 2024 precinct shapefile — our geographic spine
# This is the _cong_ file which has geometry + GEOID20 via UNIQUE_ID
# We use it to get COUNTY + PRECINCT + block membership
SBE_BLOCKS_SHP = r"data\raw\shapefiles\precincts\SBE_PRECINCTS_CENSUSBLOCKS_20251212.shp"

BLOCK_CSV_OUT   = "nc_dhc_blocks_youth.csv"
PRECINCT_CSV_OUT= "nc_youth_vap_by_precinct.csv"
# ──────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://api.census.gov/data/2020/dec/dhc"

# Male 18-24: PCT12_026N through PCT12_032N
MALE_VARS = [f"PCT12_{str(i).zfill(3)}N" for i in range(26, 33)]   # 026-032

# Female 18-24: PCT12_068N through PCT12_074N
FEMALE_VARS = [f"PCT12_{str(i).zfill(3)}N" for i in range(68, 75)] # 068-074

# Reference totals
REF_VARS = ["P1_001N", "P3_001N"]

ALL_VARS = REF_VARS + MALE_VARS + FEMALE_VARS


def fetch_county(county_fips: str, max_retries: int = 4) -> pd.DataFrame:
    """Fetch DHC block data for one county with retry logic."""
    var_str = ",".join(["NAME"] + ALL_VARS)
    url = (
        f"{BASE_URL}?get={var_str}"
        f"&for=block:*"
        f"&in=state:{STATE_FIPS}+county:{county_fips}+tract:*"
        f"&key={CENSUS_API_KEY}"
    )
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return pd.DataFrame(data[1:], columns=data[0])
            elif resp.status_code in [503, 429, 500]:
                wait = 5 * (attempt + 1)
                print(f"    ⚠  County {county_fips} got {resp.status_code} "
                      f"— retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                print(f"    ⚠  County {county_fips} failed: {resp.status_code}")
                return None
        except requests.exceptions.Timeout:
            wait = 5 * (attempt + 1)
            print(f"    ⚠  County {county_fips} timed out — retrying in {wait}s...")
            time.sleep(wait)
    print(f"    ❌ County {county_fips} failed after {max_retries} attempts.")
    return None


def build_geoid(df: pd.DataFrame) -> pd.DataFrame:
    """Build 15-digit block GEOID20."""
    df["GEOID20"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
        + df["block"].str.zfill(4)
    )
    return df


def fetch_all_blocks() -> pd.DataFrame:
    """Fetch DHC data for all NC counties."""
    # Get county list
    print("Fetching NC county FIPS codes...")
    url = (f"https://api.census.gov/data/2020/dec/pl"
           f"?get=NAME,P1_001N&for=county:*"
           f"&in=state:{STATE_FIPS}&key={CENSUS_API_KEY}")
    resp = requests.get(url, timeout=30)
    counties = pd.DataFrame(resp.json()[1:], columns=resp.json()[0])
    county_fips = counties["county"].tolist()
    print(f"  {len(county_fips)} counties found.\n")

    frames = []
    for i, fips in enumerate(county_fips):
        df = fetch_county(fips)
        if df is not None:
            frames.append(df)
        if (i + 1) % 10 == 0:
            print(f"  Fetched {i+1}/{len(county_fips)} counties...")
        time.sleep(0.15)

    print(f"\n  Combining {len(frames)} county frames...")
    combined = pd.concat(frames, ignore_index=True)
    return combined


def compute_youth_vap(df: pd.DataFrame) -> pd.DataFrame:
    """Sum male + female 18-24 into a single youth_vap column."""
    for col in ALL_VARS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["pop_total"]  = df["P1_001N"]
    df["vap_total"]  = df["P3_001N"]
    df["vap_18_24"]  = df[MALE_VARS].sum(axis=1) + df[FEMALE_VARS].sum(axis=1)
    df["vap_18_pct"] = (df["vap_total"] / df["pop_total"].replace(0, pd.NA)).round(4)

    # Drop raw age columns to keep file slim
    df = df.drop(columns=ALL_VARS + ["NAME"], errors="ignore")
    return df


def aggregate_to_precincts(blocks: pd.DataFrame) -> pd.DataFrame:
    """
    Join block-level youth VAP to SBE precinct-block shapefile
    and aggregate to precinct level.
    The SBE shapefile has one row per block with GEOID20 + county_nam + prec_id.
    """
    print("\nLoading SBE precinct-block shapefile...")
    shp = gpd.read_file(SBE_BLOCKS_SHP)
    shp["GEOID20"]    = shp["GEOID20"].astype(str).str.strip().str.zfill(15)
    shp["county_nam"] = shp["county_nam"].str.strip().str.upper()
    shp["prec_id"]    = shp["prec_id"].str.strip().str.upper()

    # Apply same cleaning as before
    shp["county_nam"] = shp["county_nam"].replace({"53": "LEE"})
    shp = shp[shp["county_id"] != 0].copy()
    shp = shp[~(
        (shp["county_nam"] == "CLEVELAND") & (shp["prec_id"] == "S 4A")
    )].copy()
    print(f"  {len(shp):,} blocks in shapefile.")

    # Join DHC data onto blocks
    blocks["GEOID20"] = blocks["GEOID20"].str.zfill(15)
    merged = shp[["county_nam", "prec_id", "GEOID20"]].merge(
        blocks[["GEOID20", "pop_total", "vap_total", "vap_18_24"]],
        on="GEOID20", how="left"
    )

    matched = merged["vap_18_24"].notna().sum()
    unmatched = merged["vap_18_24"].isna().sum()
    print(f"  Matched: {matched:,} blocks | Unmatched: {unmatched:,} blocks")

    if unmatched > 0:
        print(f"  ⚠  {unmatched} unmatched blocks will have vap_18_24 = 0")

    for col in ["pop_total", "vap_total", "vap_18_24"]:
        merged[col] = merged[col].fillna(0)

    # Aggregate to precinct
    GROUP = ["county_nam", "prec_id"]
    precinct = merged.groupby(GROUP)[["pop_total", "vap_total", "vap_18_24"]].sum().reset_index()

    # Derived columns
    precinct["vap_18_24_pct"] = (
        precinct["vap_18_24"] / precinct["pop_total"].replace(0, pd.NA)
    ).round(4)

    precinct = precinct.rename(columns={
        "county_nam": "county_desc",
        "prec_id":    "precinct_abbrv",
    })

    return precinct


def main():
    if CENSUS_API_KEY == "YOUR_KEY_HERE":
        print("❌ Set CENSUS_API_KEY env variable or paste key in script.")
        return

    print("Fetching 2020 Census DHC block-level youth VAP for NC...\n")

    # ── Fetch ─────────────────────────────────────────────────────────────────
    blocks = fetch_all_blocks()
    blocks = build_geoid(blocks)
    blocks = compute_youth_vap(blocks)

    blocks.to_csv(BLOCK_CSV_OUT, index=False)
    print(f"\n✅ Block data saved: {BLOCK_CSV_OUT} ({len(blocks):,} blocks)")

    # Sanity check
    total_youth = blocks["vap_18_24"].sum()
    total_pop   = blocks["pop_total"].sum()
    print(f"   Statewide youth VAP 18-24: {total_youth:,.0f}")
    print(f"   Statewide total pop:       {total_pop:,.0f}  (expected ~10,439,388)")
    print(f"   Youth as % of total pop:   {total_youth/total_pop*100:.1f}%")

    # ── Aggregate to precincts ────────────────────────────────────────────────
    precincts = aggregate_to_precincts(blocks)
    precincts.to_csv(PRECINCT_CSV_OUT, index=False)

    print(f"\n✅ Precinct youth VAP saved: {PRECINCT_CSV_OUT}")
    print(f"\n   Statewide precinct totals:")
    print(f"   pop_total:  {precincts['pop_total'].sum():>12,.0f}")
    print(f"   vap_total:  {precincts['vap_total'].sum():>12,.0f}")
    print(f"   vap_18_24:  {precincts['vap_18_24'].sum():>12,.0f}")
    print(f"\n   Top 10 precincts by youth VAP:")
    top10 = precincts.nlargest(10, "vap_18_24")[
        ["county_desc", "precinct_abbrv", "pop_total", "vap_18_24", "vap_18_24_pct"]
    ]
    print(top10.to_string(index=False))


if __name__ == "__main__":
    main()