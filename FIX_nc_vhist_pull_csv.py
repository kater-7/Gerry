"""
aggregate_nc_voterhistory.py
-----------------------------
Reads the NC statewide voter history TSV (ncvhis) and aggregates to the
precinct level, with one column per election showing actual turnout.

The ncvhis file links to ncvoter via `ncid`. Since ncvhis does NOT contain
precinct info directly, we join it against the ncvoter file to get each
voter's precinct assignment, then aggregate.

Output:
  nc_voterhistory_by_precinct.csv

Columns produced per precinct:
  county_desc, precinct_abbrv

  Per election (one set of columns per unique election_lbl found in file):
    votes_{election_lbl}              : total voters who voted
    votes_{election_lbl}_mail        : voted by mail/absentee
    votes_{election_lbl}_inperson    : voted in person (early + election day)
    votes_{election_lbl}_provisional : provisional ballots

  Summary columns:
    elections_count   : how many distinct elections appear in the file
    any_vote_total    : unique voters who voted in at least one election

Requirements:
  pip install pandas

Usage:
  1. Set NC_REG_FILE and NC_HIS_FILE paths below
  2. Run: python aggregate_nc_voterhistory.py
"""

import pandas as pd
import numpy as np
import os

# ── CONFIG ────────────────────────────────────────────────────────────────────
NC_REG_FILE  = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"    
NC_HIS_FILE  = "data/raw/ncvhis_Statewide/ncvhis_Statewide.txt"    
OUTPUT_FILE  = "nc_voterhistory_by_precinct.csv"
CHUNK_SIZE   = 300_000   # ncvhis rows are narrower so we can go bigger
# ──────────────────────────────────────────────────────────────────────────────

# Voting method → simplified category mapping
# Raw values in ncvhis include things like: ABSENTEE BY MAIL, CURBSIDE,
# IN-PERSON, EARLY, PROVISIONAL, ONE-STOP, ABSENTEE ONESTOP, etc.
def simplify_method(method: pd.Series) -> pd.Series:
    m = method.str.strip().str.upper()
    result = pd.Series("inperson", index=method.index)
    result[m.str.contains("MAIL|ABSENTEE", na=False)] = "mail"
    result[m.str.contains("PROVISIONAL", na=False)]   = "provisional"
    return result


def load_ncid_to_precinct(reg_file: str) -> pd.DataFrame:
    """
    Load only ncid + county + precinct from the voter registration file.
    This is our lookup table to assign precincts to history records.
    We load it all at once since it's just 3 columns (~600 MB → ~150 MB).
    """
    print("Loading ncid → precinct lookup from voter registration file...")
    df = pd.read_csv(
        reg_file,
        sep="\t",
        usecols=["ncid", "county_desc", "precinct_abbrv"],
        dtype=str,
        encoding="latin-1",
        on_bad_lines="warn",
    )
    df["ncid"]          = df["ncid"].str.strip()
    df["county_desc"]   = df["county_desc"].str.strip().str.upper()
    df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()
    df = df.drop_duplicates(subset="ncid")
    print(f"  Loaded {len(df):,} unique voter records.\n")
    return df.set_index("ncid")


def main():
    for f in [NC_REG_FILE, NC_HIS_FILE]:
        if not os.path.exists(f):
            print(f"❌ File not found: {f}")
            print("   Update the paths at the top of this script.")
            return

    # ── Step 1: Build ncid → precinct lookup ─────────────────────────────────
    lookup = load_ncid_to_precinct(NC_REG_FILE)

    # ── Step 2: Stream through ncvhis and accumulate precinct-level counts ───
    print(f"Reading voter history: {NC_HIS_FILE}")
    print(f"Chunk size: {CHUNK_SIZE:,} rows\n")

    GROUP = ["county_desc", "precinct_abbrv"]

    # We'll accumulate a dict of DataFrames keyed by election_lbl
    election_frames = {}   # election_lbl -> precinct-level DataFrame
    unique_ncids    = {}   # election_lbl -> set of ncids (for dedup within election)

    chunk_num = 0
    reader = pd.read_csv(
        NC_HIS_FILE,
        sep="\t",
        usecols=["ncid", "election_lbl", "election_desc", "voting_method"],
        dtype=str,
        encoding="latin-1",
        chunksize=CHUNK_SIZE,
        on_bad_lines="warn",
    )

    for chunk in reader:
        chunk_num += 1
        print(f"  Processing chunk {chunk_num} ({len(chunk):,} rows)...")

        chunk["ncid"]         = chunk["ncid"].str.strip()
        chunk["election_lbl"] = chunk["election_lbl"].str.strip()
        chunk["voting_method"] = simplify_method(chunk["voting_method"])

        # Join precinct info from lookup
        chunk = chunk.join(lookup, on="ncid", how="left")

        # Drop rows where we couldn't match a precinct
        chunk = chunk.dropna(subset=["county_desc", "precinct_abbrv"])

        # Process each election separately within the chunk
        for elec_lbl, elec_df in chunk.groupby("election_lbl"):

            # Count total votes and votes by method per precinct
            total = (
                elec_df.groupby(GROUP)
                .size()
                .reset_index(name=f"votes_{elec_lbl}")
            )

            method_counts = (
                elec_df.groupby(GROUP + ["voting_method"])
                .size()
                .unstack(fill_value=0)
            )
            for col in ["mail", "inperson", "provisional"]:
                if col not in method_counts.columns:
                    method_counts[col] = 0
            method_counts = method_counts[["mail", "inperson", "provisional"]].reset_index()
            method_counts = method_counts.rename(columns={
                "mail":        f"votes_{elec_lbl}_mail",
                "inperson":    f"votes_{elec_lbl}_inperson",
                "provisional": f"votes_{elec_lbl}_provisional",
            })

            merged = total.merge(method_counts, on=GROUP, how="outer")

            if elec_lbl not in election_frames:
                election_frames[elec_lbl] = []
            election_frames[elec_lbl].append(merged)

    # ── Step 3: Collapse chunks within each election ─────────────────────────
    print("\nCollapsing chunks per election...")
    election_summaries = []

    for elec_lbl, frames in sorted(election_frames.items()):
        print(f"  {elec_lbl}...")
        combined = pd.concat(frames, ignore_index=True)
        numeric_cols = [c for c in combined.columns if c not in GROUP]
        for col in numeric_cols:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").fillna(0)
        summary = combined.groupby(GROUP, as_index=False)[numeric_cols].sum()
        election_summaries.append(summary)

    # ── Step 4: Merge all elections into one wide precinct table ─────────────
    print("\nMerging all elections into final table...")
    final = election_summaries[0]
    for df in election_summaries[1:]:
        final = final.merge(df, on=GROUP, how="outer")

    # Fill any missing election/precinct combos with 0
    vote_cols = [c for c in final.columns if c not in GROUP]
    for col in vote_cols:
        final[col] = pd.to_numeric(final[col], errors="coerce").fillna(0).astype(int)

    # Summary: total unique elections and total votes across all elections
    final["elections_in_file"] = len(election_frames)
    total_vote_cols = [f"votes_{e}" for e in election_frames]
    final["any_vote_total"] = final[total_vote_cols].sum(axis=1)

    final = final.sort_values(GROUP).reset_index(drop=True)
    final.to_csv(OUTPUT_FILE, index=False)

    # ── Summary printout ──────────────────────────────────────────────────────
    print(f"\n✅ Done! {len(final):,} precincts saved to: {OUTPUT_FILE}")
    print(f"\n   Elections found in file ({len(election_frames)}):")
    for elec in sorted(election_frames.keys()):
        col = f"votes_{elec}"
        print(f"   {elec:<15}: {final[col].sum():>10,.0f} votes")
    print(f"\n   Total vote records across all elections: {final['any_vote_total'].sum():>12,.0f}")


if __name__ == "__main__":
    main()