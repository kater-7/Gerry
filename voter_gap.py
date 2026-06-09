# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json

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

ala_shape = ala_shape.dissolve(by="prec_id").reset_index()


alamance_shape = ala_shape.merge(
    alamance, left_on="prec_id", right_on="precinct_abbrv", how="left"
)

alamance_shape = alamance_shape.to_crs("EPSG:4326")

geojson_ala = json.loads(alamance_shape.to_json())

fig = px.choropleth_map(
    alamance_shape,
    locations="prec_id",
    color_continuous_scale="Viridis",
    range_color=(0, alamance_shape["youth_prop"].max()),
    color="youth_prop",
    featureidkey="properties.prec_id",
)

fig.show()

"""
voters = pd.read_csv("data/processed/voters.csv")
voters = voters.filter(regex="(^(voted_age|reg_age|pct_voted_age))|(geoid20)")

county_reg.head()


ax = alamance_shape.plot(
    column="youth_prop",
    cmap="RdYlBu",
    legend=True,
    figsize=(12, 12),
    legend_kwds={"shrink": 0.7},
)
ax.axis("off")
ax.set_title(f"Youth Voters in Alamance County")

alamance_map = gpd.GeoDataFrame(
    alamance.merge(ala_shape, left_on="prec_id", right_on="precinct_abbrv", how="left"),
    geometry="data/processed/SBE_PRECINCTS_CENSUSBLOCKS_20251212",
)

"""
