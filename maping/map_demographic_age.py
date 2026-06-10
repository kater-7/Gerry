## Packages
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

age_demographic = gpd.read_file(
    "data/processed/nc_counties.geojson"
)
DEMOGRAPHIC = "white"

## PLOT!
fig,ax = plt.subplots(figsize = (10,8))

age_named_data.plot(
    column=f"youth_share_vap",
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
    f"Youth Percentage of Voting Age Population"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/vap_pct.png",
    dpi=300
)

plt.show()



