import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

# -----------------------------
# Load files
# -----------------------------

reg = pd.read_csv(
    "data/processed/precinct_registration.csv"
)

shape = gpd.read_file(
    "https://s3.amazonaws.com/dl.ncsbe.gov/ShapeFiles/Precinct/SBE_PRECINCTS_CENSUSBLOCKS_20251212.zip"
)

# -----------------------------
# Function to standardize precinct codes
# -----------------------------

def clean_precinct_code(x):

    if pd.isna(x):
        return None

    x = str(x).strip()

    try:
        return str(int(float(x)))
    except:
        return x

# -----------------------------
# Create merge key in registration
# -----------------------------

reg["precinct_code"] = (
    reg["precinct_id"]
    .str.split("_")
    .str[-1]
)

reg["precinct_code"] = (
    reg["precinct_code"]
    .apply(clean_precinct_code)
)

reg["merge_id"] = (
    reg["precinct_id"]
    .str.split("_")
    .str[0]
    + "_"
    + reg["precinct_code"]
)

# -----------------------------
# Create merge key in shapefile
# -----------------------------

shape["precinct_code"] = (
    shape["prec_id"]
    .apply(clean_precinct_code)
)

shape["merge_id"] = (
    shape["county_nam"]
    .str.upper()
    .str.strip()
    + "_"
    + shape["precinct_code"]
)

# -----------------------------
# Dissolve blocks into precincts
# -----------------------------

precincts = (
    shape
    .dissolve(by="merge_id")
    .reset_index()
)

# -----------------------------
# Merge registration data
# -----------------------------

merged = precincts.merge(
    reg,
    on="merge_id",
    how="left"
)

# -----------------------------
# Calculate youth share
# -----------------------------

merged["pct_youth_registered"] = (
    merged["registered_youth"]
    /
    merged["registered_total"]
    * 100
)

# -----------------------------
# Plot
# -----------------------------

fig, ax = plt.subplots(
    figsize=(14, 10)
)

merged.plot(
    column="pct_youth_registered",
    cmap="viridis",
    legend=True,
    legend_kwds={
        "shrink": 0.5
    },
    ax=ax
)

# Format colorbar as %
cbar = ax.get_figure().axes[-1]

cbar.yaxis.set_major_formatter(
    mtick.PercentFormatter()
)

ax.set_title(
    "Youth Share of Registered Voters by Precinct (18-24)"
)

ax.axis("off")

plt.tight_layout()

plt.savefig(
    "output/youth_share_registered_precincts.png",
    dpi=300,
    bbox_inches="tight"
)

plt.show()