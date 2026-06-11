import pandas as pd
from tqdm import tqdm

FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"
FILE2 = "data/raw/ncvhis_Statewide"

precinct_counts = {}

chunks = pd.read_csv(
    FILE,
    sep="\t",
    encoding="latin1",
    usecols=[
        "county_desc",
        "precinct_abbrv",
        "age_at_year_end",
        "voter_status_desc"
    ],
    chunksize=500000,
    low_memory=False
)

for chunk in tqdm(
    chunks,
    desc="Processing voter file"
):

    # Keep only active voters
    active = chunk[
        chunk["voter_status_desc"] == "ACTIVE"
    ].copy()

    # Remove records with missing precincts
    active = active.dropna(
        subset=["precinct_abbrv"]
    )

    # Clean precinct codes
    active["precinct_abbrv"] = (
        active["precinct_abbrv"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Pad purely numeric precincts
    mask = active["precinct_abbrv"].str.isnumeric()

    active.loc[mask, "precinct_abbrv"] = (
        active.loc[mask, "precinct_abbrv"]
        .str.zfill(3)
    )

    # Create unique statewide precinct ID
    active["precinct_id"] = (
        active["county_desc"]
        .str.upper()
        .str.strip()
        + "_"
        + active["precinct_abbrv"]
    )

    # Count all active voters
    total_counts = (
        active
        .groupby("precinct_id")
        .size()
    )

    # Count youth voters
    youth = active[
        (active["age_at_year_end"] >= 18)
        &
        (active["age_at_year_end"] <= 24)
    ]

    youth_counts = (
        youth
        .groupby("precinct_id")
        .size()
    )

    # Store results
    for precinct_id, total in total_counts.items():

        if precinct_id not in precinct_counts:

            precinct_counts[precinct_id] = {
                "registered_total": 0,
                "registered_youth": 0
            }

        precinct_counts[precinct_id]["registered_total"] += total

    for precinct_id, youth_total in youth_counts.items():

        if precinct_id not in precinct_counts:

            precinct_counts[precinct_id] = {
                "registered_total": 0,
                "registered_youth": 0
            }

        precinct_counts[precinct_id]["registered_youth"] += youth_total

# Convert dictionary to dataframe
precinct_registration = (
    pd.DataFrame.from_dict(
        precinct_counts,
        orient="index"
    )
    .reset_index()
    .rename(
        columns={
            "index": "precinct_id"
        }
    )
)

# Save file
precinct_registration.to_csv(
    "data/processed/precinct_registration.csv",
    index=False
)

# Summary
print("\nFirst rows:")
print(precinct_registration.head())

print(
    "\nNumber of precincts:",
    len(precinct_registration)
)

print(
    "\nRegistered voters:",
    precinct_registration["registered_total"].sum()
)

print(
    "\nRegistered youth:",
    precinct_registration["registered_youth"].sum()
)