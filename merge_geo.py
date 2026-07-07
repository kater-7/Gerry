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
# LOAD VOTER DATASET
# ============================================================
voters = pd.read_csv(OUTPUT_VOTERS)

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