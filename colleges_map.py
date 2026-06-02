import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from config import COLLEGE_FILE

colleges = pd.read_csv(
    COLLEGE_FILE
)

gdf = gpd.read_file(
    "data/processed/nc_demographics.geojson"
)

college_enrollment = (
    colleges.groupby("county")["enroll"]
    .sum()
    .reset_index()
)

gdf["county"] = (
    gdf["NAME_x"]
    .str.upper()
)

college_enrollment["county"] = (
    college_enrollment["county"]
    .str.upper()
)

gdf = gdf.merge(
    college_enrollment,
    on="county",
    how="left"
)

gdf["enroll"] = gdf["enroll"].fillna(0)

gdf["college_pct"] = (
    gdf["enroll"]
    /
    gdf["population"].astype(float)
    * 100
)

print(
    gdf[
        ["NAME_x", "college_pct"]
    ]
    .sort_values(
        "college_pct",
        ascending=False
    )
    .head(15)
)

gdf["enroll"] = gdf["enroll"].fillna(0)

###PLOT###

fig, ax = plt.subplots(figsize=(10, 8))

gdf.plot(
    column=f"college_pct",
    cmap="viridis",
    legend=True,
    legend_kwds={"shrink": 0.4},
    ax=ax
)

# Format colorbar as percentages
cbar = ax.get_figure().axes[-1]
cbar.yaxis.set_major_formatter(
    mtick.PercentFormatter(xmax=100)
)

ax.set_title(
    f"College Enrollment as Percent of County Population"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/college_pct.png",
    dpi=300
)

plt.show()


