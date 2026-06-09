# load packages
import requests
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px

cols = [
    "race_code",
    "ethnic_code",
    "birth_year",
    "age_at_year_end",
    "res_street_address",
    "res_city_desc",
    "zip_code",
    "precinct_abbrv",
    "precinct_desc",
]

alamance = pd.read_csv("data/processed/alamance.csv")[cols]

alamance = (
    alamance.groupby("precinct_abbrv")
    .agg(
        total_reg=("age_at_year_end", "count"),
        under_25=("age_at_year_end", lambda x: (x < 25).sum()),
    )
    .reset_index()
    .assign(youth_prop=lambda df: df["under_25"] / df["total_reg"])
)

ala_shape = gpd.read_file(
    f"https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_CENSUSBLOCKS_20251212.zip"
)
ala_shape = ala_shape[ala_shape["county_nam"] == "ALAMANCE"]

alamance_shape = ala_shape.merge(
    alamance, left_on="prec_id", right_on="precinct_abbrv", how="left"
)

ax = alamance_shape.plot(
    column="youth_prop",
    cmap="magma",
    legend=True,
    figsize=(12, 12),
    legend_kwds={"shrink": 0.7},
)
ax.axis("off")
ax.set_title(f"Youth Voters in Alamance County")


"""

fig = px.choropleth(
    alamance_shape,
    geojson=alamance_shape,
    locations="precincts",
    color_continuous_scale="Viridis",
    range_color=(0, 12),
)

"""

"""
voters = pd.read_csv("data/processed/voters.csv")
voters = voters.filter(regex="(^(voted_age|reg_age|pct_voted_age))|(geoid20)")

county_reg.head()


alamance_map = gpd.GeoDataFrame(
    alamance.merge(ala_shape, left_on="prec_id", right_on="precinct_abbrv", how="left"),
    geometry="data/processed/SBE_PRECINCTS_CENSUSBLOCKS_20251212",
)

"""
