import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

gdf = gpd.read_file(
    "data/processed/nc_age.geojson"
)

fig, ax = plt.subplots(
    figsize=(10, 8)
)

gdf.plot(
    column="pct_youth",
    cmap="viridis",
    legend=True,
    legend_kwds={"shrink": 0.4},
    ax=ax
)

cbar = ax.get_figure().axes[-1]
cbar.yaxis.set_major_formatter(
    mtick.PercentFormatter(xmax=100)
)

ax.set_title(
    "Percent Age 18–24 by County"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/youth_pct.png",
    dpi=300
)

print(gdf.columns.tolist())

plt.show()