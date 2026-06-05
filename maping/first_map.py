import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

DEMOGRAPHIC = "hispanic"

gdf = gpd.read_file(
    "data/processed/nc_age_demographics.geojson"
)

gdf[f"pct_youth_{DEMOGRAPHIC}"] = (
    gdf[f"{DEMOGRAPHIC}_youth"].astype(float)
    /
    gdf["youth_18_24"].astype(float)
    * 100
)

fig, ax = plt.subplots(figsize=(10, 8))

gdf.plot(
    column=f"pct_youth_{DEMOGRAPHIC}",
    cmap="viridis",
    legend=True,
    legend_kwds={"shrink": 0.4},
    vmin=0,
    vmax=100,
    ax=ax
)

# Format colorbar as percentages
cbar = ax.get_figure().axes[-1]
cbar.yaxis.set_major_formatter(
    mtick.PercentFormatter(xmax=100)
)

ax.set_title(
    f"Percent {DEMOGRAPHIC.replace('_', ' ').title()} Population age 18-24 by County"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/{DEMOGRAPHIC}_youth_pop.png",
    dpi=300
)
print(gdf.columns.tolist())

plt.show()