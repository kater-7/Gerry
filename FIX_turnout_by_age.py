"""
aggregate_youth_turnout.py
---------------------------
Computes actual voter turnout by age band per precinct for selected elections
by joining ncvhis (who voted) to ncvoter (birth_year) on ncid.

Age is computed at the time of each election, not current age.
So a voter born in 2000 is counted as 24 in the 11/05/2024 election.

Age bands produced (matching our Census bands):
  age_under_18   : shouldn't exist but catches data anomalies
  age_18_24
  age_25_34
  age_35_44
  age_45_54
  age_55_64
  age_65_74
  age_75plus
  age_unknown    : missing/invalid birth_year

Elections covered:
  03/03/2026  (2026 primary)
  11/04/2025  (2025 general)
  11/05/2024  (2024 general)
  11/06/2018  (2018 general)

Output:
  nc_youth_turnout_by_precinct.csv

Requirements:
  pip install pandas
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

# ── CONFIG ────────────────────────────────────────────────────────────────────
NC_REG_FILE  = "nc_registration_by_precinct.csv"
NC_HIS_FILE  = "nc_voterhistory_by_precinct.csv"
OUTPUT_FILE  = "nc_youth_turnout_by_precinct.csv"
CHUNK_SIZE   = 300_000

# Elections to process: label -> election date for age calculation
TARGET_ELECTIONS = {
    "03/03/2026": datetime(2026, 3, 3),
    "11/04/2025": datetime(2025, 11, 4),
    "11/05/2024": datetime(2024, 11, 5),
    "11/06/2018": datetime(2018, 11, 6),
}
# ──────────────────────────────────────────────────────────────────────────────

GROUP = ["county_desc", "precinct_abbrv"]

AGE_BANDS = [
    ("age_under_18", -np.inf, 17),
    ("age_18_24",    18,      24),
    ("age_25_34",    25,      34),
    ("age_35_44",    35,      44),
    ("age_45_54",    45,      54),
    ("age_55_64",    55,      64),
    ("age_65_74",    65,      74),
    ("age_75plus",   75,      np.inf),
]


def assign_age_band_at_election(birth_year: pd.Series, election_date: datetime) -> pd.Series:
    """Compute age at election year and assign to band."""
    election_year = election_date.year
    age = election_year - pd.to_numeric(birth_year, errors="coerce")
    
    conditions = [age.isna()]
    choices    = ["age_unknown"]
    
    for band_name, low, high in AGE_BANDS:
        conditions.append((age >= low) & (age <= high))
        choices.append(band_name)
    
    # Default to unknown if nothing matches
    return np.select(conditions, choices, default="age_unknown")


def load_ncid_lookup(reg_file: str) -> pd.DataFrame:
    """
    Load ncid + county + precinct + birth_year from voter registration.
    This is our lookup table: ncid -> precinct + age info.
    """
    print("Loading voter registration lookup (ncid → precinct + birth_year)...")
    df = pd.read_csv(
        reg_file,
        sep="\t",
        usecols=["ncid", "county_desc", "precinct_abbrv", "birth_year"],
        dtype=str,
        encoding="latin-1",
        on_bad_lines="warn",
    )
    df["ncid"]           = df["ncid"].str.strip()
    df["county_desc"]    = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()
    df["birth_year"]     = df["birth_year"].str.strip()
    df = df.drop_duplicates(subset="ncid")
    print(f"  Loaded {len(df):,} unique voter records.")
    return df.set_index("ncid")


def main():
    for f in [NC_REG_FILE, NC_HIS_FILE]:
        if not os.path.exists(f):
            print(f"❌ File not found: {f}")
            return

    # ── Step 1: Load lookup ───────────────────────────────────────────────────
    lookup = load_ncid_lookup(NC_REG_FILE)

    # ── Step 2: Stream ncvhis, filter to target elections ─────────────────────
    print(f"\nReading voter history: {NC_HIS_FILE}")
    print(f"Target elections: {list(TARGET_ELECTIONS.keys())}\n")

    # Accumulate per-election chunks: election_lbl -> list of precinct DataFrames
    election_frames = {lbl: [] for lbl in TARGET_ELECTIONS}

    chunk_num = 0
    reader = pd.read_csv(
        NC_HIS_FILE,
        sep="\t",
        usecols=["ncid", "election_lbl"],
        dtype=str,
        encoding="latin-1",
        chunksize=CHUNK_SIZE,
        on_bad_lines="warn",
    )

    for chunk in reader:
        chunk_num += 1
        chunk["ncid"]         = chunk["ncid"].str.strip()
        chunk["election_lbl"] = chunk["election_lbl"].str.strip()

        # Filter to only our target elections
        chunk = chunk[chunk["election_lbl"].isin(TARGET_ELECTIONS)]
        if chunk.empty:
            continue

        print(f"  Chunk {chunk_num}: {len(chunk):,} relevant records...")

        # Join precinct + birth_year from lookup
        chunk = chunk.join(lookup, on="ncid", how="left")
        chunk = chunk.dropna(subset=["county_desc", "precinct_abbrv"])

        # Process each election in this chunk
        for elec_lbl, elec_date in TARGET_ELECTIONS.items():
            elec_chunk = chunk[chunk["election_lbl"] == elec_lbl].copy()
            if elec_chunk.empty:
                continue

            # Assign age band at time of THIS election
            elec_chunk["age_band"] = assign_age_band_at_election(
                elec_chunk["birth_year"], elec_date
            )

            # Count votes by precinct + age band
            agg = (
                elec_chunk
                .groupby(GROUP + ["age_band"])
                .size()
                .unstack(fill_value=0)
                .reset_index()
            )

            election_frames[elec_lbl].append(agg)

    # ── Step 3: Collapse chunks per election ──────────────────────────────────
    print("\nCollapsing chunks per election...")
    election_summaries = []

    all_bands = [b[0] for b in AGE_BANDS] + ["age_unknown"]

    for elec_lbl, frames in TARGET_ELECTIONS.items():
        if not election_frames[elec_lbl]:
            print(f"  ⚠  No data found for {elec_lbl} — skipping.")
            continue

        print(f"  {elec_lbl}...")
        combined = pd.concat(election_frames[elec_lbl], ignore_index=True)

        # Ensure all age band columns exist
        for band in all_bands:
            if band not in combined.columns:
                combined[band] = 0

        num_cols = [c for c in combined.columns if c not in GROUP]
        for col in num_cols:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0)

        summary = combined.groupby(GROUP, as_index=False)[num_cols].sum()

        # Create safe column names: e.g. age_18_24 -> tv_18_24_g2024
        # tv = "turnout votes", then age band, then election shortcode
        shortcode = elec_lbl.replace("/", "").replace("2026","p2026") \
                             .replace("2025","g2025") \
                             .replace("2024","g2024") \
                             .replace("2018","g2018")

        # Build election shortcode cleanly from date
        dt = TARGET_ELECTIONS[elec_lbl]
        if dt.month == 11:
            ecode = f"g{dt.year}"   # general
        else:
            ecode = f"p{dt.year}"   # primary

        rename = {}
        for band in all_bands:
            if band in summary.columns:
                short_band = band.replace("age_", "")  # e.g. "18_24"
                rename[band] = f"tv_{short_band}_{ecode}"

        summary = summary.rename(columns=rename)

        # Add total votes column for this election
        vote_cols = [c for c in summary.columns if c.startswith("tv_") and c not in GROUP]
        summary[f"tv_total_{ecode}"] = summary[vote_cols].sum(axis=1)

        # Add youth (18-24) turnout rate: youth votes / age_18_24 registered
        # (we'll compute this after merging with registration data below)

        election_summaries.append(summary)

    # ── Step 4: Merge all elections into one wide table ───────────────────────
    print("\nMerging all elections...")
    final = election_summaries[0]
    for df in election_summaries[1:]:
        final = final.merge(df, on=GROUP, how="outer")

    # Fill missing with 0
    num_cols = [c for c in final.columns if c not in GROUP]
    for col in num_cols:
        final[col] = pd.to_numeric(final[col], errors="coerce").fillna(0).astype(int)

    final = final.sort_values(GROUP).reset_index(drop=True)

    # ── Step 5: Save ──────────────────────────────────────────────────────────
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! {len(final):,} precincts saved to: {OUTPUT_FILE}")
    print(f"   Total columns: {len(final.columns)}")

    # Summary by age band for each election
    print(f"\n   Turnout by age band:")
    header = f"   {'Age Band':<15}"
    for dt in TARGET_ELECTIONS.values():
        ecode = f"g{dt.year}" if dt.month == 11 else f"p{dt.year}"
        header += f"  {ecode:>12}"
    print(header)
    print(f"   {'-'*15}" + f"  {'-'*12}" * len(TARGET_ELECTIONS))

    for band in all_bands:
        short = band.replace("age_", "")
        row = f"   {band:<15}"
        for dt in TARGET_ELECTIONS.values():
            ecode = f"g{dt.year}" if dt.month == 11 else f"p{dt.year}"
            col = f"tv_{short}_{ecode}"
            val = final[col].sum() if col in final.columns else 0
            row += f"  {val:>12,.0f}"
        print(row)

    # Total row
    row = f"   {'TOTAL':<15}"
    for dt in TARGET_ELECTIONS.values():
        ecode = f"g{dt.year}" if dt.month == 11 else f"p{dt.year}"
        col = f"tv_total_{ecode}"
        val = final[col].sum() if col in final.columns else 0
        row += f"  {val:>12,.0f}"
    print(f"   {'-'*15}" + f"  {'-'*12}" * len(TARGET_ELECTIONS))
    print(row)


if __name__ == "__main__":
    main()