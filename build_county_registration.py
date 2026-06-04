import pandas as pd

FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"

county_counts = {}

chunks = pd.read_csv(
    FILE,
    sep="\t",
    encoding = "latin1",
    usecols=[
        "county_desc",
        "age_at_year_end",
        "voter_status_desc"
    ],
    chunksize=500000,
    low_memory=False
)

for chunk in chunks:

    youth = chunk[
        (chunk["voter_status_desc"] == "ACTIVE")
        & (chunk["age_at_year_end"] >= 18)
        & (chunk["age_at_year_end"] <= 24)
    ]
    
    counts = youth.groupby("county_desc").size()

    for county, count in counts.items():
        county_counts[county] = county_counts.get(county, 0) + count

county_registration = pd.DataFrame(
    county_counts.items(),
    columns=["county", "registered_youth"]
)

county_registration.to_csv(
    "data/processed/county_registration.csv",
    index=False
)

print(county_registration.head())

print(county_registration["registered_youth"].sum())

county_registration.to_csv(
    "data/processed/county_registration.csv",
    index=False
)

