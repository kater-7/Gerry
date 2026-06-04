# Import packages
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
from config import AGE_VARIABLES

# Import Data
## Need census population charts
age_data = gpd.read_file(
    f"data/processed/nc_age.geojson"
)

rename_dict = {
    code: name
    for name, code in AGE_VARIABLES.items()
}

age_named_data = age_data.rename(columns=rename_dict)

for col in age_named_data.columns:
    print(col)

age_data["under_18"] = (
    age_data["B01001_003E"]
    + age_data["B01001_004E"]
    + age_data["B01001_005E"]
    + age_data["B01001_006E"]
    + age_data["B01001_027E"]
    + age_data["B01001_028E"]
    + age_data["B01001_029E"]
    + age_data["B01001_030E"]
)

age_data["vap"] = (
    age_data["B01001_001E"]
    - age_data["under_18"]
)

age_named_data["youth_share_vap"] = (
    age_data["youth_18_24"]
    / (age_data["vap"]) * 100
)


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


