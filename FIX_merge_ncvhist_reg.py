"""
merge_nc_reg_history.py
------------------------
Merges the two aggregated precinct-level files:
  - nc_registration_by_precinct.csv   (from aggregate_nc_registration.py)
  - nc_voterhistory_by_precinct.csv   (from aggregate_nc_voterhistory.py)

Drops any election where statewide total votes < MIN_VOTE_THRESHOLD.
Adds turnout rate columns for each kept election (votes / reg_active).

Output:
  nc_voters_by_precinct.csv

Requirements:
  pip install pandas
"""

import pandas as pd

# ── CONFIG ────────────────────────────────────────────────────────────────────
REG_FILE          = "nc_registration_by_precinct.csv"
HIS_FILE          = "nc_voterhistory_by_precinct.csv"
OUTPUT_FILE       = "nc_voters_by_precinct.csv"
MIN_VOTE_THRESHOLD = 100_000   # drop elections with fewer statewide votes
# ──────────────────────────────────────────────────────────────────────────────

GROUP = ["county_desc", "precinct_abbrv"]


def main():
    # ── 1. Load both files ────────────────────────────────────────────────────
    print("Loading registration file...")
    reg = pd.read_csv(REG_FILE, dtype={"county_desc": str, "precinct_abbrv": str})

    print("Loading voter history file...")
    his = pd.read_csv(HIS_FILE, dtype={"county_desc": str, "precinct_abbrv": str})

    # Normalize join keys
    for df in [reg, his]:
        df["county_desc"]    = df["county_desc"].str.strip().str.upper()
        df["precinct_abbrv"] = df["precinct_abbrv"].str.strip().str.upper()

    # ── 2. Identify election total columns and filter by threshold ────────────
    # Total-vote columns are named  votes_{election_lbl}  (no suffix after lbl)
    # Method columns are            votes_{election_lbl}_mail  etc.
    all_vote_cols = [c for c in his.columns if c.startswith("votes_")]
    total_cols    = [c for c in all_vote_cols
                     if not any(c.endswith(s) for s in ["_mail", "_inperson", "_provisional"])]

    print(f"\nAll elections in history file: {len(total_cols)}")
    print(f"Applying threshold: {MIN_VOTE_THRESHOLD:,} votes\n")

    kept_elections   = []
    dropped_elections = []

    for col in sorted(total_cols):
        total = his[col].sum()
        elec  = col.replace("votes_", "")
        if total >= MIN_VOTE_THRESHOLD:
            kept_elections.append(elec)
            print(f"  ✅ KEEP  {elec:<15}  {total:>12,.0f} votes")
        else:
            dropped_elections.append(elec)
            print(f"  ❌ DROP  {elec:<15}  {total:>12,.0f} votes")

    # Build list of all columns to drop (total + method columns for dropped elections)
    cols_to_drop = []
    for elec in dropped_elections:
        cols_to_drop += [c for c in his.columns if c.startswith(f"votes_{elec}")]

    # Also drop the summary cols we no longer need
    cols_to_drop += ["elections_in_file", "any_vote_total"]
    cols_to_drop  = [c for c in cols_to_drop if c in his.columns]

    his_filtered = his.drop(columns=cols_to_drop)

    # ── 3. Merge registration + history ──────────────────────────────────────
    print(f"\nMerging on county_desc + precinct_abbrv...")

    # Drop precinct_desc from history if present to avoid duplicate cols
    if "precinct_desc" in his_filtered.columns:
        his_filtered = his_filtered.drop(columns=["precinct_desc"])

    merged = reg.merge(his_filtered, on=GROUP, how="left")

    # Fill missing vote counts (precincts with no history match) with 0
    vote_cols_kept = [c for c in merged.columns if c.startswith("votes_")]
    merged[vote_cols_kept] = merged[vote_cols_kept].fillna(0).astype(int)

    # ── 4. Add turnout rate columns for each kept election ────────────────────
    # turnout = votes / reg_active  (capped at 1.0 to handle edge cases)
    print("Computing turnout rates...")
    for elec in kept_elections:
        vote_col    = f"votes_{elec}"
        turnout_col = f"turnout_{elec}"
        if vote_col in merged.columns and "reg_active" in merged.columns:
            merged[turnout_col] = (
                merged[vote_col] / merged["reg_active"].replace(0, pd.NA)
            ).clip(upper=1.0).round(4)

    # ── 5. Save ───────────────────────────────────────────────────────────────
    merged = merged.sort_values(GROUP).reset_index(drop=True)
    merged.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! {len(merged):,} precincts saved to: {OUTPUT_FILE}")
    print(f"   Kept {len(kept_elections)} elections, dropped {len(dropped_elections)}")
    print(f"   Total columns in output: {len(merged.columns)}")

    print(f"\n   Registration summary:")
    for col in ["reg_total", "reg_active", "reg_inactive", "reg_removed"]:
        if col in merged.columns:
            print(f"   {col:<22}: {merged[col].sum():>12,.0f}")

    print(f"\n   Turnout in kept elections:")
    for elec in sorted(kept_elections):
        vote_col = f"votes_{elec}"
        turn_col = f"turnout_{elec}"
        votes    = merged[vote_col].sum()
        avg_turn = merged[turn_col].mean()
        print(f"   {elec:<15}  votes: {votes:>10,.0f}   avg precinct turnout: {avg_turn:.1%}")


if __name__ == "__main__":
    main()