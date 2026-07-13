# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json
import janitor

precinct_election_shape = gpd.read_file("data/raw/precinct_youth_power_shape")

results_raw = pd.read_csv("data/processed/pct_election_results.csv")

lookup = pd.read_csv("data/processed/lookup.csv")
lookup = lookup.rename(
    columns={"county": "county_desc", "precinct_code": "precinct_abbrv"}
)

master = pd.read_csv("data/processed/nc_master_precinct.csv")

master_lookup = master.merge(lookup, on=["county_desc", "precinct_abbrv"], how="left")

results = results_raw.rename(
    columns={
        "county_": "county_desc",
        "county": "district_number",
        "precinct_clean": "precinct_abbrv",
    }
)

results["county_desc"] = results["county_desc"].astype(str).str.strip().str.upper()
results["precinct_abbrv"] = (
    results["precinct_abbrv"].astype(str).str.strip().str.upper()
)

master_lookup["county_desc"] = (
    master_lookup["county_desc"].astype(str).str.strip().str.upper()
)
master_lookup["precinct_abbrv"] = (
    master_lookup["precinct_abbrv"].astype(str).str.strip().str.upper()
)

youth_power = master_lookup.merge(
    results, on=["county_desc", "precinct_abbrv"], how="left"
)

youth_power_anti = master_lookup.merge(
    results, on=["county_desc", "precinct_abbrv"], how="left_anti"
)

master_lookup[master_lookup["county_desc"] == "BUNCOMBE"]
results[results["county_desc"] == "BUNCOMBE"]


print("merged rows:", len(youth_power))
print("nulls:", youth_power["REP_2020"].isna().sum())

youth_power["dist_vtf"] = youth_power.groupby(["election_type", "district_number"])[
    "avg_votes_to_flip"
].transform("sum")

youth_power["youth_power_index"] = (
    (youth_power["est_vap_youth"] - youth_power["tv_18_24_g2024"])
    / youth_power["dist_vtf"]
) * 100

cols_of_interest = [
    "precinct_abbrv",
    "election_type",
    "youth_power_index",
    "youth_turnout_gap",
    "county_desc",
    "vap_total",
    "est_vap_youth",
    "avg_votes_to_flip",
    "winner_2024",
    "precinct_name",
    "district_number",
    "dist_vtf",
    "precinct_desc",
]

youth_power_condensed = youth_power[cols_of_interest]

youth_power_wide = youth_power_condensed.pivot_table(
    index=["county_desc", "precinct_abbrv"],
    columns="election_type",
    values=["youth_power_index", "district_number", "dist_vtf"],
    aggfunc="first",
).reset_index()

# Flatten MultiIndex columns
youth_power_wide.columns = [
    "_".join(col).strip("_") if isinstance(col, tuple) else col
    for col in youth_power_wide.columns
]

youth_power_wide = youth_power_wide.clean_names()

# Keep the remaining columns (one row per precinct)
other_cols = [
    "county_desc",
    "precinct_abbrv",
    "youth_turnout_gap",
    "vap_total",
    "est_vap_youth",
    "avg_votes_to_flip",
    "winner_2024",
    "precinct_name",
    "district_number",
    "dist_vtf",
    "precinct_desc",
]

other_data = youth_power_condensed[other_cols].drop_duplicates(
    subset=["county_desc", "precinct_abbrv"]
)

# Merge back
youth_power_wide = youth_power_wide.merge(
    other_data,
    on=["county_desc", "precinct_abbrv"],
    how="left",
)

# Rename merge keys
precinct_election_shape = precinct_election_shape.rename(
    columns={
        "county_nam": "county_desc",
        "prec_id": "precinct_abbrv",
    }
)

# Make merge keys strings in BOTH datasets
precinct_election_shape["county_desc"] = precinct_election_shape["county_desc"].astype(
    str
)
youth_power_wide["county_desc"] = youth_power_wide["county_desc"].astype(str)

precinct_election_shape["precinct_abbrv"] = precinct_election_shape[
    "precinct_abbrv"
].astype(str)
youth_power_wide["precinct_abbrv"] = youth_power_wide["precinct_abbrv"].astype(str)


# Merge youth power data onto the shapefile
youth_power_map = precinct_election_shape.merge(
    youth_power_wide,
    on=["county_desc", "precinct_abbrv"],
    how="left",
)

condensed_names = {
    "dist_vtf_nc_house": "vtf_nchouse",
    "dist_vtf_nc_state_senate": "vtf_ncsenate",
    "dist_vtf_us_house": "vtf_ushouse",
    "district_number_nc_house": "nchouse_dist",
    "district_number_nc_state_senate": "ncsenate_dist",
    "district_number_us_house": "ushouse_dist",
    "youth_power_index_nc_house": "ypi_nchouse",
    "youth_power_index_nc_state_senate": "ypi_ncsenate",
    "youth_power_index_us_house": "ypi_ushouse",
    "avg_votes_to_flip": "prct_vtf",
}

youth_power_map_final = youth_power_map.rename(columns=condensed_names)

youth_power_map_final.to_file("data/processed/youth_power_map.gpkg", driver="GPKG")
