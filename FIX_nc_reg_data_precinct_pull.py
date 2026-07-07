"""
aggregate_nc_registration.py
-----------------------------
Reads the NC statewide voter registration TSV and aggregates to the
precinct level. Designed to handle 1–5 GB files without loading
everything into memory at once (uses chunked reading).

Output:
  nc_registration_by_precinct.csv

Precinct key used:
  county_desc + precinct_abbrv  (unique statewide when combined)

Columns produced per precinct:
  -- Identity --
  county_desc, precinct_abbrv, precinct_desc

  -- Registration counts by status --
  reg_total         : all records
  reg_active        : status_cd == 'A'
  reg_inactive      : status_cd == 'I'
  reg_removed       : status_cd == 'R'
  reg_other_status  : D, S, etc.

  -- Party (active voters only) --
  party_dem         : DEM
  party_rep         : REP
  party_unaf        : UNA
  party_lib         : LIB
  party_other       : everything else

  -- Race (all registered) --
  race_white        : W
  race_black        : B
  race_hispanic     : H  (note: NC reg uses race field, not separate ethnicity for this)
  race_asian        : A
  race_aian         : I
  race_other        : O, M, P, U combined

  -- Ethnicity (all registered) --
  eth_hispanic      : ethnic_code == 'HL'
  eth_not_hispanic  : ethnic_code == 'NL'
  eth_undesignated  : ethnic_code == 'UN'

  -- Gender (all registered) --
  gender_male       : gender_code == 'M'
  gender_female     : gender_code == 'F'
  gender_unknown    : gender_code not M/F

  -- Age bands (all registered, computed from birth_year) --
  Uses current year to compute age. Matches Census age bands.
  age_under_18
  age_18_24
  age_25_34
  age_35_44
  age_45_54
  age_55_64
  age_65_74
  age_75plus
  age_unknown       : missing or invalid birth_year

Requirements:
  pip install pandas

Usage:
  1. Set NC_REG_FILE to your TSV path below
  2. Run: python aggregate_nc_registration.py
"""

import pandas as pd
import numpy as np
from datetime import date
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────
NC_REG_FILE  = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"   # <-- update this path
OUTPUT_FILE  = "nc_registration_by_precinct.csv"
CHUNK_SIZE   = 200_000   # rows per chunk; tune down if you hit memory issues
CURRENT_YEAR = date.today().year
# ──────────────────────────────────────────────────────────────────────────────

# Only load the columns we actually need (keeps memory low)
COLS_NEEDED = [
    "county_desc",
    "precinct_abbrv",
    "precinct_desc",
    "status_cd",
    "party_cd",
    "race_code",
    "ethnic_code",
    "gender_code",
    "birth_year",
]


def assign_age_band(birth_year_series: pd.Series) -> pd.Series:
    """Convert a birth_year column to age-band string labels."""
    age = CURRENT_YEAR - pd.to_numeric(birth_year_series, errors="coerce")
    bands = pd.cut(
        age,
        bins=[-np.inf, 17, 24, 34, 44, 54, 64, 74, np.inf],
        labels=["under_18", "18_24", "25_34", "35_44", "45_54", "55_64", "65_74", "75plus"],
    )
    # NaN ages (bad birth_year) become "unknown"
    return bands.astype(str).replace("nan", "unknown")


def aggregate_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """
    Given a chunk of the raw registration file, return a precinct-level
    summary DataFrame with all our metrics.
    """
    # Standardize key columns
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()
    df["precinct_desc"]  = df["precinct_desc"].str.strip()
    df["status_cd"]      = df["status_cd"].str.strip().str.upper()
    df["party_cd"]       = df["party_cd"].str.strip().str.upper()
    df["race_code"]      = df["race_code"].str.strip().str.upper()
    df["ethnic_code"]    = df["ethnic_code"].str.strip().str.upper()
    df["gender_code"]    = df["gender_code"].str.strip().str.upper()

    df["age_band"] = assign_age_band(df["birth_year"])

    GROUP = ["county_desc", "precinct_abbrv", "precinct_desc"]

    # ── Registration totals by status ─────────────────────────────────────────
    status_counts = (
        df.groupby(GROUP + ["status_cd"])
        .size()
        .unstack(fill_value=0)
        .rename(columns={"A": "reg_active", "I": "reg_inactive", "R": "reg_removed"})
    )
    # Combine any non-A/I/R statuses into reg_other_status
    known = {"reg_active", "reg_inactive", "reg_removed"}
    other_cols = [c for c in status_counts.columns if c not in known]
    status_counts["reg_other_status"] = status_counts[other_cols].sum(axis=1)
    status_counts = status_counts.drop(columns=other_cols)
    status_counts["reg_total"] = status_counts[list(known & set(status_counts.columns))].sum(axis=1) + status_counts["reg_other_status"]
    status_counts = status_counts.reset_index()

    # ── Party (active voters only) ────────────────────────────────────────────
    active = df[df["status_cd"] == "A"]
    party_counts = (
        active.groupby(GROUP + ["party_cd"])
        .size()
        .unstack(fill_value=0)
    )
    party_map = {"DEM": "party_dem", "REP": "party_rep", "UNA": "party_unaf", "LIB": "party_lib"}
    party_counts = party_counts.rename(columns=party_map)
    known_party = set(party_map.values())
    other_party = [c for c in party_counts.columns if c not in known_party]
    party_counts["party_other"] = party_counts[other_party].sum(axis=1)
    party_counts = party_counts.drop(columns=other_party)
    # Ensure all party cols exist even if absent in this chunk
    for col in party_map.values():
        if col not in party_counts.columns:
            party_counts[col] = 0
    party_counts = party_counts.reset_index()

    # ── Race ──────────────────────────────────────────────────────────────────
    race_counts = (
        df.groupby(GROUP + ["race_code"])
        .size()
        .unstack(fill_value=0)
    )
    race_map = {
        "W": "race_white", "B": "race_black", "A": "race_asian",
        "I": "race_aian",  "P": "race_nhpi",  "M": "race_multiracial",
        "O": "race_other_race", "U": "race_undesignated",
    }
    race_counts = race_counts.rename(columns={k: v for k, v in race_map.items() if k in race_counts.columns})
    for col in race_map.values():
        if col not in race_counts.columns:
            race_counts[col] = 0
    race_counts = race_counts.reset_index()

    # ── Ethnicity ─────────────────────────────────────────────────────────────
    eth_counts = (
        df.groupby(GROUP + ["ethnic_code"])
        .size()
        .unstack(fill_value=0)
    )
    eth_map = {"HL": "eth_hispanic", "NL": "eth_not_hispanic", "UN": "eth_undesignated"}
    eth_counts = eth_counts.rename(columns={k: v for k, v in eth_map.items() if k in eth_counts.columns})
    for col in eth_map.values():
        if col not in eth_counts.columns:
            eth_counts[col] = 0
    eth_counts = eth_counts.reset_index()

    # ── Gender ────────────────────────────────────────────────────────────────
    gender_counts = (
        df.groupby(GROUP + ["gender_code"])
        .size()
        .unstack(fill_value=0)
    )
    gender_map = {"M": "gender_male", "F": "gender_female"}
    gender_counts = gender_counts.rename(columns={k: v for k, v in gender_map.items() if k in gender_counts.columns})
    other_gender = [c for c in gender_counts.columns if c not in gender_map.values()]
    gender_counts["gender_unknown"] = gender_counts[other_gender].sum(axis=1)
    gender_counts = gender_counts.drop(columns=other_gender)
    for col in gender_map.values():
        if col not in gender_counts.columns:
            gender_counts[col] = 0
    gender_counts = gender_counts.reset_index()

    # ── Age bands ─────────────────────────────────────────────────────────────
    age_counts = (
        df.groupby(GROUP + ["age_band"])
        .size()
        .unstack(fill_value=0)
    )
    age_band_labels = ["under_18", "18_24", "25_34", "35_44", "45_54", "55_64", "65_74", "75plus", "unknown"]
    age_counts = age_counts.rename(columns={b: f"age_{b}" for b in age_band_labels if b in age_counts.columns})
    for b in age_band_labels:
        col = f"age_{b}"
        if col not in age_counts.columns:
            age_counts[col] = 0
    age_counts = age_counts.reset_index()

    # ── Merge all summaries for this chunk ────────────────────────────────────
    result = status_counts
    for df_part in [party_counts, race_counts, eth_counts, gender_counts, age_counts]:
        # drop duplicate precinct_desc if present to avoid _x/_y issues
        merge_cols = [c for c in df_part.columns if c in GROUP]
        result = result.merge(df_part, on=merge_cols, how="outer")

    return result


def main():
    if not os.path.exists(NC_REG_FILE):
        print(f"❌ File not found: {NC_REG_FILE}")
        print("   Update NC_REG_FILE in the script to point to your TSV.")
        return

    print(f"Reading: {NC_REG_FILE}")
    print(f"Chunk size: {CHUNK_SIZE:,} rows\n")

    accumulated = []
    chunk_num = 0

    reader = pd.read_csv(
        NC_REG_FILE,
        sep="\t",
        usecols=COLS_NEEDED,
        dtype=str,           # read everything as string; we parse types ourselves
        encoding="latin-1",  # NC files sometimes have non-UTF8 chars
        chunksize=CHUNK_SIZE,
        on_bad_lines="warn",
    )

    for chunk in reader:
        chunk_num += 1
        print(f"  Processing chunk {chunk_num} ({len(chunk):,} rows)...")
        agg = aggregate_chunk(chunk)
        accumulated.append(agg)

    print(f"\nCombining {chunk_num} chunks...")
    combined = pd.concat(accumulated, ignore_index=True)

    # Sum across all chunks for the same precinct
    GROUP = ["county_desc", "precinct_abbrv", "precinct_desc"]
    numeric_cols = [c for c in combined.columns if c not in GROUP]

    # coerce all numeric cols
    for col in numeric_cols:
        combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0)

    final = combined.groupby(GROUP, as_index=False)[numeric_cols].sum()
    final = final.sort_values(["county_desc", "precinct_abbrv"]).reset_index(drop=True)

    final.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! {len(final):,} precincts saved to: {OUTPUT_FILE}")
    print(f"\n   Statewide registration totals:")
    for col in ["reg_total", "reg_active", "reg_inactive", "reg_removed"]:
        if col in final.columns:
            print(f"   {col:<20}: {final[col].sum():>12,.0f}")
    print(f"\n   Active voters by party:")
    for col in ["party_dem", "party_rep", "party_unaf", "party_lib", "party_other"]:
        if col in final.columns:
            print(f"   {col:<20}: {final[col].sum():>12,.0f}")


if __name__ == "__main__":
    main()