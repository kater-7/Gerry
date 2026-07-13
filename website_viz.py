# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json

cols_to_use = [
    "voter_reg_num",
    "election_lbl",
    "election_desc",
    "voted_party_cd",
    "vtd_label",
    "vtd_description",
]
nc_votes = pd.read_csv(
    "data/processed/NC_voters_hist_reg.csv",
)

bins = [17, 25, 34, 49, 64, 79, 169]
labels = ["18-25", "26-34", "35-49", "50-64", "65-79", "80+"]

nc_votes["age_group"] = pd.cut(
    nc_votes["age_at_year_end"], bins=bins, labels=labels, right=True
)

voted_2024 = nc_votes[nc_votes["voted_2024_general"] == 1].copy()

voted_2024["party_bucket"] = voted_2024["party_2024_general"].apply(
    lambda x: x if x in ["DEM", "REP"] else "OTHER"
)

party_pct = (
    voted_2024.groupby(["age_group", "party_bucket"]).size().reset_index(name="votes")
)

party_pct["pct"] = (
    party_pct["votes"] / party_pct.groupby("age_group")["votes"].transform("sum") * 100
)

fig = px.bar(
    party_pct,
    x="age_group",
    y="pct",
    color="party_bucket",
    color_discrete_map={"DEM": "blue", "REP": "red", "OTHER": "lightgrey"},
    barmode="stack",
    labels={
        "pct": "Share of Votes (%)",
        "age_group": "Age Group",
        "party_bucket": "Party",
    },
    title="2024 NC General Election: Vote Share by Age Group",
    category_orders={"party_bucket": ["DEM", "REP", "OTHER"]},
)

fig.update_layout(yaxis_ticksuffix="%")
fig.show()

plt.show()
