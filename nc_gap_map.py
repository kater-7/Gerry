import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import json
import janitor
import matplotlib as mpl
import matplotlib.ticker as mtick


gap_map = pd.read_csv("data/processed/1976-2024-house.tab", sep=",")
nc_gap = gap_map[gap_map["state_po"] == "NC"]
nc_gap = gap_map[gap_map["state_po"] == "NC"]

nc_gap["vote_prop"] = nc_gap["candidatevotes"] / nc_gap["totalvotes"]

nc_gap_wide = nc_gap.pivot_table(
    index=["year", "district", "totalvotes"],
    columns="party",
    values=["vote_prop", "candidatevotes"],
    aggfunc="first",
).reset_index()

nc_gap_wide.columns = [
    "_".join(col).strip("_") if isinstance(col, tuple) else col
    for col in nc_gap_wide.columns
]

cols_of_interest = [
    "year",
    "district",
    "totalvotes",
    "candidatevotes_DEMOCRAT",
    "candidatevotes_REPUBLICAN",
    "vote_prop_DEMOCRAT",
    "vote_prop_REPUBLICAN",
]

nc_gap_prop = nc_gap_wide[cols_of_interest]

nc_gap_prop["winner"] = (
    nc_gap_prop[["candidatevotes_DEMOCRAT", "candidatevotes_REPUBLICAN"]]
    .fillna(0)
    .idxmax(axis=1)
    .str.replace("candidatevotes_", "")
)

nc_gap_prop.to_csv("2024_congressional_results.csv", index=False)

nc_gap_graph = (
    nc_gap_prop.groupby("year")
    .agg(
        repub_dist=("winner", lambda x: (x == "REPUBLICAN").sum()),
        dem_dist=("winner", lambda x: (x == "DEMOCRAT").sum()),
        repub_votes=("candidatevotes_REPUBLICAN", "sum"),
        dem_votes=("candidatevotes_DEMOCRAT", "sum"),
        total_votes=("totalvotes", "sum"),
    )
    .assign(
        total_dist=lambda x: x["repub_dist"] + x["dem_dist"],
        repub_dist_pct=lambda x: x["repub_dist"] / (x["dem_dist"] + x["repub_dist"]),
        dem_dist_pct=lambda x: x["dem_dist"] / (x["dem_dist"] + x["repub_dist"]),
        gap_dist=lambda x: (
            (x["repub_dist"] - x["dem_dist"]) / (x["dem_dist"] + x["repub_dist"])
        ),
        repub_popular=lambda x: x["repub_votes"] / x["total_votes"],
        dem_popular=lambda x: x["dem_votes"] / x["total_votes"],
        gap_popular=lambda x: (x["repub_votes"] - x["dem_votes"]) / x["total_votes"],
        gerry_gap=lambda x: x["gap_dist"] - x["gap_popular"],
    )
)

plt.plot(nc_gap_graph.index, nc_gap_graph["gerry_gap"], marker="o")

# Presets & style customization
BLUE = "#446B84"
RED = "#B53927"

# ArcGIS-style font
mpl.rcParams["font.family"] = "Avenir Next"
# mpl.rcParams["font.weight"] = "bold"

fig, ax = plt.subplots(figsize=(20, 3))

# Set font sizes
TITLE_SIZE = 22
LABEL_SIZE = 16
TICK_SIZE = 22

ax.set_title(
    "NC Representation Gap, 1976 - 2024", fontsize=TITLE_SIZE, fontweight="bold"
)

ax.set_ylabel(
    "Congressional - Popular Vote Representation (%)",
    fontsize=LABEL_SIZE,
    fontweight="bold",
)

ax.tick_params(axis="both", labelsize=TICK_SIZE)

x = nc_gap_graph.index.values
y = nc_gap_graph["gerry_gap"].values

# Create continuous x-axis for shading
x_dense = np.linspace(x.min(), x.max(), 500)
y_dense = np.interp(x_dense, x, y)

# Shade positive and negative areas continuously
ax.fill_between(x_dense, y_dense, 0, where=(y_dense >= 0), color=RED, alpha=0.15)

ax.fill_between(x_dense, y_dense, 0, where=(y_dense < 0), color=BLUE, alpha=0.15)

# Thin line
ax.plot(x, y, color="#444444", linewidth=1, zorder=2)

# Colored points with white outline
colors = np.where(y >= 0, RED, BLUE)

ax.scatter(x, y, c=colors, s=45, edgecolor="white", linewidth=1.5, zorder=3)

# Zero line
ax.axhline(0, color="#999999", linewidth=0.8, zorder=1)

# Clean ArcGIS-style formatting
ax.set_facecolor("white")
fig.patch.set_facecolor("white")

ax.set_xlabel("")
ax.set_ylabel("Congressional - Popular Vote Representation (%)")
ax.set_title("NC Representation Gap, 1976 - 2024")

# Remove unnecessary borders
for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)

ax.spines["bottom"].set_color("#CCCCCC")

# Subtle grid
ax.grid(axis="y", linestyle="--", linewidth=0.5, alpha=0.25)

# Only show every 4 years
ax.set_xticks(nc_gap_graph.index[nc_gap_graph.index % 4 == 0])

# Format y-axis as percentages
ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))

plt.savefig(
    "nc_representation_gap_skinny_QUEENNN.png",
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)

plt.tight_layout()
plt.show()

##############
BLUE = "#446B84"
RED = "#B53927"
GRAY = "#999999"

mpl.rcParams["font.family"] = "Avenir Next"

# Get 2024 values
gap_2024 = nc_gap_graph.loc[2024]

# Popular vote shares
dem_popular = gap_2024["dem_popular"]
rep_popular = gap_2024["repub_popular"]
other_popular = 1 - dem_popular - rep_popular

# Seat shares
dem_seat = gap_2024["dem_dist_pct"]
rep_seat = gap_2024["repub_dist_pct"]
other_seat = 0

categories = ["Popular Vote", "Seat Share"]

dem_values = [dem_popular, dem_seat]
other_values = [other_popular, other_seat]
rep_values = [rep_popular, rep_seat]

y = np.arange(len(categories))

fig, ax = plt.subplots(figsize=(12, 2))
# Democrat segment
ax.barh(y, dem_values, color=BLUE, edgecolor="white", linewidth=1.5, label="Democrat")

# Other segment (center)
ax.barh(
    y,
    other_values,
    left=dem_values,
    color=GRAY,
    edgecolor="white",
    linewidth=1.5,
    label="Other",
)

# Republican segment
ax.barh(
    y,
    rep_values,
    left=np.array(dem_values) + np.array(other_values),
    color=RED,
    edgecolor="white",
    linewidth=1.5,
    label="Republican",
)

# Add percentage labels
# Add percentage labels (skip Other)
for i in range(len(categories)):
    segments = [
        (dem_values[i], 0, BLUE),
        (rep_values[i], dem_values[i] + other_values[i], RED),
    ]

    for value, left, color in segments:
        if value > 0.03:
            ax.text(
                left + value / 2,
                i,
                f"{value:.0%}",
                ha="center",
                va="center",
                fontweight="bold",
                color="white",
            )

# Formatting
ax.set_yticks(y)
ax.set_yticklabels(categories, fontweight="bold")

ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))

ax.set_xlim(0, 1)

ax.set_xlabel("")
ax.set_ylabel("")
ax.set_title("NC Congressional Representation, 2024", fontweight="bold")

# ArcGIS style cleanup
ax.set_facecolor("white")
fig.patch.set_facecolor("white")

for spine in ["top", "right", "left"]:
    ax.spines[spine].set_visible(False)

ax.spines["bottom"].set_color("#CCCCCC")

# Remove borders
for spine in ["top", "right", "left", "bottom"]:
    ax.spines[spine].set_visible(False)

# Remove x-axis
ax.set_xlabel("")
ax.set_xticks([])
ax.tick_params(axis="x", bottom=False, labelbottom=False)

plt.tight_layout()

plt.savefig(
    "nc_2024_vote_vs_seat_share_skinnier.png",
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
)

plt.show()
