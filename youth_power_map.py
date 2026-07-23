# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json
import janitor

cols_of_interest = [
    "county_id",
    "county",
    "election_dt",
    "result_type_lbl",
    "result_type_desc",
    "contest_id",
    "contest_title",
    "contest_party_lbl",
    "contest_vote_for",
    "precinct_code",
    "precinct_name",
    "candidate_id",
    "candidate_name",
    "candidate_party_lbl",
    "group_num",
    "group_name",
    "voting_method_lbl",
    "voting_method_rslt_desc",
    "vote_ct",
]

link = "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/results_precinct_sort/STATEWIDE_PRECINCT_SORT.txt"

pct_sort = pd.read_csv(link, sep="\t")

pct_results_filtered = pct_sort[
    pct_sort["contest_title"].str.startswith(
        (
            "NC HOUSE OF REPRESENTATIVES",
            "NC STATE SENATE",
            "US HOUSE OF REPRESENTATIVES",
        ),
        na=False,
    )
]

pct_results_unfiltered = (
    pct_results_filtered.clean_names()
    .assign(
        precinct_clean=lambda df: (
            df["precinct_code"].astype(str).str.strip().str.upper()
        ),
        candidate_party_lbl=lambda df: df["candidate_party_lbl"].str.strip(),
    )
    # remove non-candidate rows
    .query("candidate_party_lbl != ''")
    .assign(
        party_bucket=lambda df: np.where(
            df["candidate_party_lbl"].isin(["DEM", "REP"]),
            df["candidate_party_lbl"],
            "OTHER",
        ),
        election_type=lambda df: (
            df["contest_title"]
            .str.replace(r"^NC HOUSE OF REPRESENTATIVES.*", "NC_HOUSE", regex=True)
            .str.replace(r"^NC STATE SENATE.*", "NC_STATE_SENATE", regex=True)
            .str.replace(r"^US HOUSE OF REPRESENTATIVES.*", "US_HOUSE", regex=True)
        ),
    )
    .reset_index(drop=True)
)

# pivoting so year AND election_type are columns instead of separate rows --
# each precinct is now one row, with separate DEM/REP columns per race per year
# (e.g. NC_HOUSE_DEM_2020, US_PRESIDENT_REP_2024, etc.)
pct_pivoted = (
    pct_results_unfiltered.groupby(
        [
            "county",
            "precinct_clean",
            "election_type",
            "party_bucket",
        ],
        dropna=False,
    )["vote_ct"]
    .sum()
    .reset_index()
    .pivot(
        index=["county", "precinct_clean"],
        columns=["election_type", "party_bucket"],
        values="vote_ct",
    )
    .fillna(0)
    .reset_index()
)

# flatten column names
pct_pivoted.columns = [
    "_".join([str(x) for x in col if x != ""]) if isinstance(col, tuple) else col
    for col in pct_pivoted.columns
]

pct_pivoted.head()

precinct_corrected = gpd.read_file(
    "data/processed/nchousncsencong26cong24_precincts.geojson"
)

precinct_corrected = precinct_corrected.clean_names()

columns_of_interest = [
    "precinct",
    "county",
    "district",
    "district_1",
    "district_1_2",
    "district_1_2_3",
    "reg_total",
    "reg_active",
    "reg_inact",
    "dem_reg",
    "rep_reg",
    "age_18_24",
    "votes_g24",
    "votes_g20",
    "turnout_g2",
    "turnout_1",
    "pop_total",
    "vap_pct",
    "vap_youth",
    "yth_g24",
    "rep_pct",
    "dem_pct",
    "margin",
    "competit",
    "winner_24",
    "yth_tnt24",
    "youth_gap",
    "geometry",
    "id",
]
new_names = {
    "district": "ds_ushou24",
    "district_1": "ds_ushou26",
    "district_1_2": "ds_nc_sen",
    "district_1_2_3": "ds_nc_hou",
    "precinct": "precinct_clean",
}

precinct_corrected = precinct_corrected[columns_of_interest]

precinct_corrected_renamed = precinct_corrected.rename(columns=new_names)

precinct_corrected_updated = precinct_corrected_renamed.merge(
    pct_pivoted, on=["county", "precinct_clean"], how="left", indicator=True
)

pct_election_results_corrected = precinct_corrected_updated.assign(
    # Congressional (2024 districts)
    vtf_ushou24=lambda x: (
        x.groupby("ds_ushou24")["US_HOUSE_DEM"].transform("sum")
        - x.groupby("ds_ushou24")["US_HOUSE_REP"].transform("sum")
    ),
    # Congressional (2026 districts)
    vtf_ushou26=lambda x: (
        x.groupby("ds_ushou26")["US_HOUSE_DEM"].transform("sum")
        - x.groupby("ds_ushou26")["US_HOUSE_REP"].transform("sum")
    ),
    # NC Senate (2026 districts)
    vtf_nc_sen=lambda x: (
        x.groupby("ds_nc_sen")["NC_STATE_SENATE_DEM"].transform("sum")
        - x.groupby("ds_nc_sen")["NC_STATE_SENATE_REP"].transform("sum")
    ),
    # NC House (2026 districts)
    vtf_nc_hou=lambda x: (
        x.groupby("ds_nc_hou")["NC_HOUSE_DEM"].transform("sum")
        - x.groupby("ds_nc_hou")["NC_HOUSE_REP"].transform("sum")
    ),
    # Total votes (Congressional 2024)
    total_ushou24=lambda x: (
        x.groupby("ds_ushou24")[["US_HOUSE_DEM", "US_HOUSE_REP", "US_HOUSE_OTHER"]]
        .transform("sum")
        .sum(axis=1)
    ),
    # Total votes (Congressional 2026)
    total_ushou26=lambda x: (
        x.groupby("ds_ushou26")[["US_HOUSE_DEM", "US_HOUSE_REP", "US_HOUSE_OTHER"]]
        .transform("sum")
        .sum(axis=1)
    ),
    # Total votes (NC Senate)
    total_nc_sen=lambda x: (
        x.groupby("ds_nc_sen")[
            ["NC_STATE_SENATE_DEM", "NC_STATE_SENATE_REP", "NC_STATE_SENATE_OTHER"]
        ]
        .transform("sum")
        .sum(axis=1)
    ),
    # Total votes (NC House)
    total_nc_hou=lambda x: (
        x.groupby("ds_nc_hou")[["NC_HOUSE_DEM", "NC_HOUSE_REP", "NC_HOUSE_OTHER"]]
        .transform("sum")
        .sum(axis=1)
    ),
)

rename_long = {
    "NC_STATE_SENATE_DEM": "ncs_dem",
    "NC_STATE_SENATE_REP": "ncs_rep",
    "NC_STATE_SENATE_OTHER": "ncs_other",
    "NC_HOUSE_DEM": "nch_dem",
    "NC_HOUSE_REP": "nch_rep",
    "NC_HOUSE_OTHER": "nch_other",
    "US_HOUSE_DEM": "ush_dem",
    "US_HOUSE_REP": "ush_rep",
    "US_HOUSE_OTHER": "ush_other",
    "total_ushou24": "tot_us24",
    "total_ushou26": "tot_us26",
    "total_nc_sen": "tot_sen",
    "total_nc_hou": "tot_house",
    "vtf_ushou24": "vtf_us24",
    "vtf_ushou26": "vtf_us26",
    "vtf_nc_sen": "vtf_sen",
    "vtf_nc_hou": "vtf_house",
}

precinct_export = pct_election_results_corrected.rename(columns=rename_long)

precinct_export.to_file(
    "data/processed/precincts_2024_only.gpkg",
    layer="precincts_merged",
    driver="GPKG",
)

# Unmerged precincts
unmerged_precincts = precinct_corrected_updated[
    precinct_corrected_updated["_merge"] == "left_only"
].copy()

# Apply the same long-column renaming if needed
unmerged_export = unmerged_precincts.rename(columns=rename_long)

unmerged_export.to_file(
    "data/processed/precincts_unmerged_election_data.gpkg",
    layer="unmatched_precincts",
    driver="GPKG",
)

print("Saved unmerged precincts:", len(unmerged_export))
