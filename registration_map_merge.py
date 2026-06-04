import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

youth_reg = gpd.read_file(
    "data/processed/county_registration.csv"
)

age_data = gpd.read_file(
    f"data/processed/nc_age.geojson"
)

registration_map = age_data.merge(
    youth_reg,
    left_on="NAME_x",
    right_on="county"
)

print(age_data["NAME_x"].head())
print(youth_reg["county"].head())


## Percent of Youth Registered to Vote
registration_map["registration_rate"] = (
    registration_map["registered_youth"]
    / registration_map["youth_18_24"]
) * 100

## PLOT!
fig,ax = plt.subplots(figsize = (10,8))

registration_map.plot(
    column=f"registration_rate",
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
    f"Percent of Youth Registered to Vote"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    f"output/maps/registration_youth_pct.png",
    dpi=300
)

plt.show()



