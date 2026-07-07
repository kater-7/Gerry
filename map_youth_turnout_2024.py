import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import plotly.express as px


# ============================================================
# FILES
# ============================================================

VOTERS_FILE = "data/processed/nc_voters_enriched.csv"

PRECINCT_FILE = "data/processed/nc_precinct_turnout.geojson"

OUTPUT_MAP = "output/youth_turnout_2024.png"

# ============================================================
# LOAD DATA
# ============================================================

print("Loading data...")

voters = pd.read_csv(
    VOTERS_FILE,
    low_memory=False
)

precincts = gpd.read_file(
    PRECINCT_FILE
)

# ============================================================
# CLEAN
# ============================================================

voters["age_at_year_end"] = pd.to_numeric(
    voters["age_at_year_end"],
    errors="coerce"
)

voters["voted_2024_general"] = pd.to_numeric(
    voters["voted_2024_general"],
    errors="coerce"
).fillna(0)

# ============================================================
# YOUTH ONLY
# ============================================================

youth = voters[
    voters["age_at_year_end"].between(18, 24)
].copy()

print(f"Youth voters: {len(youth):,}")

# ============================================================
# PRECINCT TURNOUT
# ============================================================

youth_precinct = (
    youth
    .groupby("precinct_abbrv")
    .agg(
        youth_registered=("ncid", "count"),
        youth_voted_2024=("voted_2024_general", "sum")
    )
    .reset_index()
)

youth_precinct["youth_turnout_2024"] = (
    youth_precinct["youth_voted_2024"]
    /
    youth_precinct["youth_registered"]
    * 100
)

# ============================================================
# MERGE TO GEOMETRY
# ============================================================

precinct_map = precincts.merge(
    youth_precinct,
    on="precinct_abbrv",
    how="left"
)

# ============================================================
# MAP
# ============================================================

precinct_map.to_crs("EPSG:4326")


fig = px.choropleth_map(
    precinct_map,
    locations="precinct_abbrv",
    color_continuous_scale="Viridis",
    range_color=(0, youth_precinct["youth_turnout_2024"].max()),
    color="youth_turnout_2024",
    featureidkey="properties.prec_id",
)

fig.show()

'''
precinct_map.plot(
    column="youth_turnout_2024",
    cmap="viridis",
    linewidth=0,
    legend=True,
    missing_kwds={
        "color": "lightgrey",
        "label": "No Data"
    },
    legend_kwds={
        "shrink": 0.5
    },
    ax=ax
)

# Format legend as percentages

cbar = ax.get_figure().axes[-1]

cbar.yaxis.set_major_formatter(
    mtick.PercentFormatter()
)

ax.set_title(
    "Youth Voter Turnout (Age 18–24)\n2024 General Election",
    fontsize=16
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    OUTPUT_MAP,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print(f"Saved map: {OUTPUT_MAP}")
'''