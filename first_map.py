import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick


DEMOGRAPHIC = "hispanic"
gdf = gpd.read_file(
    "data/processed/nc_demographics.geojson"
)

gdf[f"pct_{DEMOGRAPHIC}"] = (
    gdf[f"{DEMOGRAPHIC}_population"].astype(float)
    /
    gdf["population"].astype(float)
    * 100
)

fig, ax = plt.subplots(figsize=(10, 8))

gdf.plot(
    column=f"pct_{DEMOGRAPHIC}",
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
    f"Percent {DEMOGRAPHIC.replace('_', ' ').title()} Population by County"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/{DEMOGRAPHIC}_pop.png",
    dpi=300
)

plt.show()