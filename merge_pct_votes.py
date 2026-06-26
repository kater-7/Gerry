# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json
import janitor

cols_of_interest = [
    "Precinct",
    "County",
    "Election Date",
    "Contest Group ID",
    "Contest Name",
    "Choice Party",
    "Total Votes",
    "Real Precinct",
]

elections = {
    2024: "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_pct_20241105.zip",
    2022: "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2022_11_08/results_pct_20221108.zip",
    2020: "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2020_11_03/results_pct_20201103.zip",
}

pct_elections_raw = {
    year: pd.read_csv(url, delimiter="\t", usecols=cols_of_interest)
    for year, url in elections.items()
}

pct_results_all = pd.concat(
    [df.assign(year=year) for year, df in pct_elections_raw.items()], ignore_index=True
)

pct_results_raw = pd.read_csv(
    "data/raw/elections/results_pct_20241105.txt",
    delimiter="\t",
)

pct_results_filtered = pct_results_all[
    pct_results_all["Contest Name"].str.startswith(
        (
            "NC HOUSE OF REPRESENTATIVES",
            "NC STATE SENATE",
            "US PRESIDENT",
            "US HOUSE OF REPRESENTATIVES",
        )
    )
    & (pct_results_all["Real Precinct"] == "Y")
]

pct_results_unfiltered = (
    pct_results_filtered.clean_names()
    .assign(
        precinct_clean=lambda df: df["precinct"].str.replace(r"\.\d+$", "", regex=True),
        unique_id=lambda df: (
            df["county"].str.upper().str.strip()
            + "_"
            + df["precinct_clean"].str.strip()
        ),
        party_bucket=lambda x: x["choice_party"].where(
            lambda s: s.isin(["DEM", "REP"]), "OTHER"
        ),
        election_type=lambda df: (
            df["contest_name"]
            .str.replace(r"^NC HOUSE OF REPRESENTATIVES.*", "NC HOUSE", regex=True)
            .str.replace(r"^NC STATE SENATE.*", "NC STATE SENATE", regex=True)
            .str.replace(r"^US HOUSE OF REPRESENTATIVES.*", "US HOUSE", regex=True)
        ),
    )
    .reset_index(drop=True)
)

pct_results = pct_results_unfiltered[
    pct_results_unfiltered["precinct_clean"] != "TRANSFER"
]

pct_pivoted = (
    pct_results.groupby(
        [
            "unique_id",
            "election_type",
            "party_bucket",
            "year",
            "precinct_clean",
            "county",
        ]
    )["total_votes"]
    .sum()
    .reset_index()
    .pivot(
        index=["unique_id", "election_type", "precinct_clean", "county"],
        columns=["party_bucket", "year"],
        values="total_votes",
    )
    .reset_index()
)

pct_pivoted.columns = ["unique_id", "election_type", "precinct_clean", "county"] + [
    f"{party}_{year}" for party, year in pct_pivoted.columns[4:]
]

pct_election_results_final = pct_pivoted.assign(
    margin_of_victory_2020=lambda x: (x["DEM_2020"] - x["REP_2020"]).abs(),
    margin_of_victory_2022=lambda x: (x["DEM_2022"] - x["REP_2022"]).abs(),
    margin_of_victory_2024=lambda x: (x["DEM_2024"] - x["REP_2024"]).abs(),
    avg_votes_to_flip=lambda x: (
        (
            x[
                [
                    "margin_of_victory_2020",
                    "margin_of_victory_2022",
                    "margin_of_victory_2024",
                ]
            ].mean(axis=1)
        )
        / 2
    ),
)
