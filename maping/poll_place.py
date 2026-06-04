from config import POLLING_FILE
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import geopandas as gpd
import pandas as pd

polls = pd.read_csv(
    "data/raw/polling_place_20260303.csv",
    encoding="utf-16",
    sep="\t"
)

poll_count = (
    polls.groupby("county_name")
    .size()
    .reset_index(name="polling_places")
)

print(
    poll_count
    .sort_values(
        "polling_places",
        ascending=False
    )
    .head(20)
)

poll_count["county"] = (
    poll_count["county_name"]
    .str.upper()
)

gdf = gpd.read_file(
    "data/processed/nc_demographics.geojson"
)

gdf["county"] = (
    gdf["NAME_x"]
    .str.upper()
)

gdf = gdf.merge(
    poll_count[["county", "polling_places"]],
    on="county",
    how="left"
)

print(
    gdf[
        ["NAME_x", "polling_places"]
    ]
    .sort_values(
        "polling_places",
        ascending=False
    )
    .head(15)
)

gdf["polls_per_10000"] = (
    gdf["polling_places"]
    /
    gdf["population"].astype(float)
    * 10000
)

fig,ax = plt.subplots(figsize = (10, 8))

gdf.plot(
    column = f"polls_per_10000",
    cmap = "viridis",
    legend = True,
    legend_kwds={"shrink": 0.4},
    ax=ax
)

ax.set_title(
    f"Number of Polling Places Available for Every 10,000 Residents"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/polling_density.png",
    dpi=300
)

plt.show()



