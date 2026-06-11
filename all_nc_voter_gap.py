# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json
from tqdm import tqdm

nc_votes = gpd.read_file(
    "https://duke.box.com/s/as1pdlqhp6rqdslp8rz3svbi1tpds1cv/download"
)

# reading in alamance county and joining voter registration/voter history data
alamance = pd.read_csv("data/processed/alamance.csv", usecols=cols_alamance)

ala_voter_history_raw = pd.read_csv(
    "https://s3.amazonaws.com/dl.ncsbe.gov/data/ncvhis1.zip",
    sep="\t",
    usecols=cols_ala_vhistory,
)
ala_voter_history_raw.to_csv("ala_voter_history.csv", index=False)
ala_voter_history = ala_voter_history_raw[
    ala_voter_history_raw["election_desc"] == "11/05/2024 GENERAL"
]

alamance = alamance.merge(ala_voter_history, on="voter_reg_num", how="left")

alamance["voted"] = alamance["voted_party_cd"].notna()

alamance_merged = (
    alamance.groupby("precinct_abbrv")
    .agg(
        total_reg=("age_at_year_end", "count"),
        under_25_reg=("age_at_year_end", lambda x: (x < 25).sum()),
        total_vote=("voted", "sum"),
        under_25_vote=(
            "age_at_year_end",
            lambda x: ((x < 25) & x.index.map(alamance["voted"])).sum(),
        ),
        d_reg=("party_cd", lambda x: (x == "DEM").sum()),
        d_youth_reg=(
            "party_cd",
            lambda x: (
                (x == "DEM") & (x.index.map(alamance["age_at_year_end"]) < 25)
            ).sum(),
        ),
        d_vote=("voted_party_cd", lambda x: (x == "DEM").sum()),
        d_youth_vote=(
            "voted_party_cd",
            lambda x: (
                (x == "DEM") & (x.index.map(alamance["age_at_year_end"]) < 25)
            ).sum(),
        ),
        r_reg=("party_cd", lambda x: (x == "REP").sum()),
        r_youth_reg=(
            "party_cd",
            lambda x: (
                (x == "REP") & (x.index.map(alamance["age_at_year_end"]) < 25)
            ).sum(),
        ),
        r_vote=("voted_party_cd", lambda x: (x == "REP").sum()),
        r_youth_vote=(
            "voted_party_cd",
            lambda x: (
                (x == "REP") & (x.index.map(alamance["age_at_year_end"]) < 25)
            ).sum(),
        ),
    )
    .reset_index()
    .assign(
        youth_prop_reg=lambda x: x["under_25_reg"] / x["total_reg"],
        youth_vot_turnout=lambda x: x["under_25_vote"] / x["under_25_reg"],
        prop_dem=lambda x: x["d_vote"] / x["total_vote"],
        prop_youth_dem=lambda x: x["d_youth_vote"] / x["under_25_vote"],
        prop_rep=lambda x: x["r_vote"] / x["total_vote"],
        prop_youth_rep=lambda x: x["r_youth_vote"] / x["under_25_vote"],
    )
)

shape = gpd.read_file(
    f"https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_CENSUSBLOCKS_20251212.zip"
)
ala_shape = ala_shape[ala_shape["county_nam"] == "ALAMANCE"]

ala_shape = ala_shape.dissolve(by="prec_id").reset_index()

alamance_map = ala_shape.merge(
    alamance_merged, left_on="prec_id", right_on="precinct_abbrv", how="left"
)

alamance_map = alamance_map.to_crs("EPSG:4326")

geojson_ala = json.loads(alamance_map.to_json())

var_of_interest = "prop_youth_dem"

fig = px.choropleth_map(
    alamance_map,
    geojson=geojson_ala,
    locations="prec_id",
    color_continuous_scale="RdYlBu",
    range_color=(0, alamance_map[var_of_interest].max()),
    color=var_of_interest,
    featureidkey="properties.prec_id",
    center={"lat": 36.0, "lon": -79.4},
    zoom=10,
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
