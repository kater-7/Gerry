import pandas as pd
import geopandas as gpd
import numpy as np

# ============================================================
# FILE PATHS
# ============================================================

REG_FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"

HIST_FILE = r"data/raw/ncvhist/ncvhist.txt"

OUTPUT_VOTERS = "data/processed/nc_voters_enriched.csv"

OUTPUT_PRECINCTS = "data/processed/nc_precinct_turnout.geojson"

CHUNKSIZE = 500_000

# ============================================================
# LOAD REGISTRATION FILE
# ============================================================

print("Loading voter registration file...")

REG_COLS = [
    "ncid",
    "county_desc",
    "race_code",
    "ethnic_code",
    "gender_code",
    "birth_year",
    "age_at_year_end",
    "party_cd",
    "registr_dt",
    "voter_status_desc",
    "precinct_abbrv",
    "precinct_desc",
    "vtd_abbrv",
    "vtd_desc",
    "cong_dist_abbrv",
    "nc_senate_abbrv",
    "nc_house_abbrv"
]

reg = pd.read_csv(
    REG_FILE,
    sep="\t",
    encoding="latin1",
    dtype=str,
    usecols=REG_COLS,
    low_memory=False
)

print(f"Registration records: {len(reg):,}")

# ============================================================
# CLEAN REGISTRATION DATA
# ============================================================

reg["age_at_year_end"] = pd.to_numeric(
    reg["age_at_year_end"],
    errors="coerce"
)

reg["birth_year"] = pd.to_numeric(
    reg["birth_year"],
    errors="coerce"
)

reg["registr_dt"] = pd.to_datetime(
    reg["registr_dt"],
    errors="coerce"
)

reg["years_registered"] = (
    pd.Timestamp("2026-01-01").year
    - reg["registr_dt"].dt.year
)

# ============================================================
# AGE GROUPS
# ============================================================

reg["is_youth"] = reg["age_at_year_end"].between(18, 24)

reg["age_group"] = pd.cut(
    reg["age_at_year_end"],
    bins=[18, 24, 34, 49, 64, 120],
    labels=[
        "18-24",
        "25-34",
        "35-49",
        "50-64",
        "65+"
    ]
)

# ============================================================
# PROCESS HISTORY FILE
# ============================================================

print("Processing voter history...")

history_features = []

for i, chunk in enumerate(
    pd.read_csv(
        HIST_FILE,
        sep="\t",
        encoding="latin1",
        dtype=str,
        chunksize=CHUNKSIZE,
        low_memory=False
    )
):

    print(f"Chunk {i+1}")

    chunk["election_desc"] = (
        chunk["election_desc"]
        .fillna("")
        .str.upper()
    )

    chunk["voting_method"] = (
        chunk["voting_method"]
        .fillna("")
        .str.upper()
    )

    chunk["election_lbl"] = (
        chunk["election_lbl"]
        .fillna("")
    )

    # -------------------------
    # Election Types
    # -------------------------

    chunk["general_vote"] = (
        chunk["election_desc"]
        .str.contains("GENERAL", na=False)
        .astype(int)
    )

    chunk["primary_vote"] = (
        chunk["election_desc"]
        .str.contains("PRIMARY", na=False)
        .astype(int)
    )

    # -------------------------
    # Voting Methods
    # -------------------------

    chunk["early_vote"] = (
        chunk["voting_method"]
        .str.contains("ONE-STOP", na=False)
        .astype(int)
    )

    chunk["absentee_vote"] = (
        chunk["voting_method"]
        .str.contains("ABSENTEE", na=False)
        .astype(int)
    )

    chunk["election_day_vote"] = (
        (
            ~chunk["voting_method"].str.contains(
                "ONE-STOP|ABSENTEE",
                na=False
            )
        )
        .astype(int)
    )

    # -------------------------
    # Major Election Flags
    # -------------------------

    chunk["voted_2024_general"] = (
        chunk["election_lbl"] == "11/05/2024"
    ).astype(int)

    chunk["voted_2022_general"] = (
        chunk["election_lbl"] == "11/08/2022"
    ).astype(int)

    chunk["voted_2020_general"] = (
        chunk["election_lbl"] == "11/03/2020"
    ).astype(int)

    # -------------------------
    # Aggregate
    # -------------------------

    voter_chunk = (
        chunk
        .groupby("ncid")
        .agg(
            total_elections=("election_lbl", "count"),

            general_elections=("general_vote", "sum"),

            primary_elections=("primary_vote", "sum"),

            early_votes=("early_vote", "sum"),

            absentee_votes=("absentee_vote", "sum"),

            election_day_votes=("election_day_vote", "sum"),

            voted_2024_general=("voted_2024_general", "max"),

            voted_2022_general=("voted_2022_general", "max"),

            voted_2020_general=("voted_2020_general", "max"),

            last_voted_party=("voted_party_cd", "last"),

            last_vote_date=("election_lbl", "max")
        )
        .reset_index()
    )

    history_features.append(voter_chunk)

# ============================================================
# COMBINE CHUNKS
# ============================================================

print("Combining chunks...")

history = pd.concat(
    history_features,
    ignore_index=True
)

history = (
    history
    .groupby("ncid")
    .agg(
        total_elections=("total_elections", "sum"),

        general_elections=("general_elections", "sum"),

        primary_elections=("primary_elections", "sum"),

        early_votes=("early_votes", "sum"),

        absentee_votes=("absentee_votes", "sum"),

        election_day_votes=("election_day_votes", "sum"),

        voted_2024_general=("voted_2024_general", "max"),

        voted_2022_general=("voted_2022_general", "max"),

        voted_2020_general=("voted_2020_general", "max"),

        last_voted_party=("last_voted_party", "last"),

        last_vote_date=("last_vote_date", "max")
    )
    .reset_index()
)

# ============================================================
# MERGE REGISTRATION + HISTORY
# ============================================================

print("Merging voter data...")

voters = reg.merge(
    history,
    on="ncid",
    how="left"
)

# ============================================================
# FILL MISSING TURNOUT VALUES
# ============================================================

turnout_cols = [
    "total_elections",
    "general_elections",
    "primary_elections",
    "early_votes",
    "absentee_votes",
    "election_day_votes",
    "voted_2024_general",
    "voted_2022_general",
    "voted_2020_general"
]

for col in turnout_cols:
    voters[col] = voters[col].fillna(0)

# ============================================================
# TURNOUT RATES
# ============================================================

voters["general_turnout_rate"] = (
    voters["general_elections"]
    /
    voters["years_registered"].clip(lower=1)
)

voters["primary_turnout_rate"] = (
    voters["primary_elections"]
    /
    voters["years_registered"].clip(lower=1)
)

# ============================================================
# SAVE VOTER DATASET
# ============================================================

print("Saving voter dataset...")

voters.to_csv(
    OUTPUT_VOTERS,
    index=False
)

# ============================================================
# AGGREGATE TO PRECINCT
# ============================================================

print("Building precinct statistics...")

precinct_stats = (
    voters
    .groupby("precinct_abbrv")
    .agg(
        total_registered=("ncid", "count"),

        youth_registered=("is_youth", "sum"),

        avg_age=("age_at_year_end", "mean"),

        avg_turnout=("total_elections", "mean"),

        avg_general_turnout_rate=(
            "general_turnout_rate",
            "mean"
        ),

        pct_voted_2024=(
            "voted_2024_general",
            "mean"
        ),

        pct_voted_2022=(
            "voted_2022_general",
            "mean"
        ),

        pct_voted_2020=(
            "voted_2020_general",
            "mean"
        )
    )
    .reset_index()
)

precinct_stats["youth_share"] = (
    precinct_stats["youth_registered"]
    /
    precinct_stats["total_registered"]
)

# ============================================================
# LOAD PRECINCT SHAPEFILE
# ============================================================

print("Loading precinct geometries...")

shape = gpd.read_file(
    "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_CENSUSBLOCKS_20251212.zip"
)

print(shape.columns.tolist())

# ============================================================
# FIND CORRECT JOIN FIELD
# ============================================================

possible_cols = [
    c for c in shape.columns
    if "PREC" in c.upper()
]

print("\nPossible precinct columns:")
print(possible_cols)

# ------------------------------------------------------------
# CHANGE THIS IF NECESSARY
# ------------------------------------------------------------

PRECINCT_FIELD = "prec_id"

# ============================================================
# MERGE TO GEOMETRY
# ============================================================

shape[PRECINCT_FIELD] = (
    shape[PRECINCT_FIELD]
    .astype(str)
)

precinct_stats["precinct_abbrv"] = (
    precinct_stats["precinct_abbrv"]
    .astype(str)
)

precinct_map = shape.merge(
    precinct_stats,
    left_on=PRECINCT_FIELD,
    right_on="precinct_abbrv",
    how="left"
)

# ============================================================
# SAVE GEOJSON
# ============================================================

print("Saving precinct GeoJSON...")

precinct_map.to_file(
    OUTPUT_PRECINCTS,
    driver="GeoJSON"
)

print("\nDONE")
print(f"Voter file: {OUTPUT_VOTERS}")
print(f"Map file:   {OUTPUT_PRECINCTS}")