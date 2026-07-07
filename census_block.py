import requests
import pandas as pd
import geopandas as gpd
from tqdm import tqdm

# ============================================================
# USER SETTINGS
# ============================================================

API_KEY = "a06207caa3490ef482e89196770ed4aab23428cb"

BLOCKGROUP_SHAPEFILE = "data/raw/shapefiles/tl_2020_37_bg/tl_2020_37_bg.shp"

OUTPUT_GEOJSON = "data/processed/nc_blockgroup_demographics.geojson"

STATE_FIPS = "37"

# ============================================================
# VARIABLES
# ============================================================

VARIABLES = {

    # Total population
    "P1_001N": "total_pop",

    # Race
    "P3_002N": "white_pop",
    "P3_003N": "black_pop",
    "P3_004N": "native_pop",
    "P3_005N": "asian_pop",
    "P3_006N": "pacific_pop",
    "P3_007N": "other_pop",
    "P3_008N": "multiracial_pop",

    # Hispanic
    "P4_003N": "hispanic_pop",

    # Sex
    "P12_002N": "male_pop",
    "P12_026N": "female_pop",

    # Male age bins
    "P12_006N": "m18_19",
    "P12_007N": "m20",
    "P12_008N": "m21",
    "P12_009N": "m22_24",

    "P12_010N": "m25_29",
    "P12_011N": "m30_34",

    "P12_012N": "m35_39",
    "P12_013N": "m40_44",

    "P12_014N": "m45_49",
    "P12_015N": "m50_54",
    "P12_016N": "m55_59",
    "P12_017N": "m60_61",
    "P12_018N": "m62_64",

    "P12_019N": "m65_66",
    "P12_020N": "m67_69",
    "P12_021N": "m70_74",
    "P12_022N": "m75_79",
    "P12_023N": "m80_84",
    "P12_024N": "m85_plus",

    # Female age bins
    "P12_030N": "f18_19",
    "P12_031N": "f20",
    "P12_032N": "f21",
    "P12_033N": "f22_24",

    "P12_034N": "f25_29",
    "P12_035N": "f30_34",

    "P12_036N": "f35_39",
    "P12_037N": "f40_44",

    "P12_038N": "f45_49",
    "P12_039N": "f50_54",
    "P12_040N": "f55_59",
    "P12_041N": "f60_61",
    "P12_042N": "f62_64",

    "P12_043N": "f65_66",
    "P12_044N": "f67_69",
    "P12_045N": "f70_74",
    "P12_046N": "f75_79",
    "P12_047N": "f80_84",
    "P12_048N": "f85_plus"
}

# ============================================================
# NC COUNTY FIPS
# ============================================================

county_fips = [f"{i:03d}" for i in range(1, 200, 2)]

# ============================================================
# DOWNLOAD DATA
# ============================================================

all_dfs = []

var_string = ",".join(VARIABLES.keys())

for county in tqdm(county_fips):

    url = (
        "https://api.census.gov/data/2020/dec/dhc"
        f"?get={var_string}"
        f"&for=block%20group:*"
        f"&in=state:{STATE_FIPS}"
        f"&in=county:{county}"
        f"&key={API_KEY}"
    )

    r = requests.get(url)

    if r.status_code != 200:
        print(f"Failed county {county}")
        print(r.text)
        continue

    data = r.json()

    county_df = pd.DataFrame(
        data[1:],
        columns=data[0]
    )

    all_dfs.append(county_df)

# ============================================================
# COMBINE
# ============================================================

print("Combining counties...")

df = pd.concat(
    all_dfs,
    ignore_index=True
)

# ============================================================
# RENAME VARIABLES
# ============================================================

df = df.rename(columns=VARIABLES)

# ============================================================
# GEOID
# ============================================================

df["GEOID"] = (
    df["state"]
    + df["county"]
    + df["tract"]
    + df["block group"]
)

# ============================================================
# NUMERIC CONVERSION
# ============================================================

for col in VARIABLES.values():
    df[col] = pd.to_numeric(
        df[col],
        errors="coerce"
    )

# ============================================================
# AGE GROUPS
# ============================================================

df["age_18_24"] = (
    df["m18_19"] +
    df["m20"] +
    df["m21"] +
    df["m22_24"] +
    df["f18_19"] +
    df["f20"] +
    df["f21"] +
    df["f22_24"]
)

df["age_25_34"] = (
    df["m25_29"] +
    df["m30_34"] +
    df["f25_29"] +
    df["f30_34"]
)

df["age_35_44"] = (
    df["m35_39"] +
    df["m40_44"] +
    df["f35_39"] +
    df["f40_44"]
)

df["age_45_64"] = (
    df["m45_49"] +
    df["m50_54"] +
    df["m55_59"] +
    df["m60_61"] +
    df["m62_64"] +
    df["f45_49"] +
    df["f50_54"] +
    df["f55_59"] +
    df["f60_61"] +
    df["f62_64"]
)

df["age_65_plus"] = (
    df["m65_66"] +
    df["m67_69"] +
    df["m70_74"] +
    df["m75_79"] +
    df["m80_84"] +
    df["m85_plus"] +
    df["f65_66"] +
    df["f67_69"] +
    df["f70_74"] +
    df["f75_79"] +
    df["f80_84"] +
    df["f85_plus"]
)

df["under_18"] = (
    df["total_pop"]
    - df["age_18_24"]
    - df["age_25_34"]
    - df["age_35_44"]
    - df["age_45_64"]
    - df["age_65_plus"]
)

# ============================================================
# DERIVED PERCENTAGES
# ============================================================

df["pct_youth"] = (
    df["age_18_24"] /
    df["total_pop"]
)

df["pct_under_35"] = (
    (df["age_18_24"] + df["age_25_34"]) /
    df["total_pop"]
)

df["pct_senior"] = (
    df["age_65_plus"] /
    df["total_pop"]
)

# ============================================================
# VALIDATION
# ============================================================

print("\nValidation")

print(
    "Male + Female diff:",
    abs(
        df["total_pop"].sum()
        - (
            df["male_pop"].sum()
            + df["female_pop"].sum()
        )
    )
)

print(
    "Age groups diff:",
    abs(
        df["total_pop"].sum()
        - (
            df["under_18"].sum()
            + df["age_18_24"].sum()
            + df["age_25_34"].sum()
            + df["age_35_44"].sum()
            + df["age_45_64"].sum()
            + df["age_65_plus"].sum()
        )
    )
)

print(
    "\nNC Population:",
    f"{df['total_pop'].sum():,}"
)

print(
    "NC Youth (18-24):",
    f"{df['age_18_24'].sum():,}"
)

# ============================================================
# KEEP FINAL COLUMNS
# ============================================================

df = df[[
    "GEOID",

    "total_pop",

    "male_pop",
    "female_pop",

    "white_pop",
    "black_pop",
    "native_pop",
    "asian_pop",
    "pacific_pop",
    "other_pop",
    "multiracial_pop",
    "hispanic_pop",

    "under_18",
    "age_18_24",
    "age_25_34",
    "age_35_44",
    "age_45_64",
    "age_65_plus",

    "pct_youth",
    "pct_under_35",
    "pct_senior"
]]

# ============================================================
# LOAD SHAPEFILE
# ============================================================

print("\nLoading shapefile...")

gdf = gpd.read_file(BLOCKGROUP_SHAPEFILE)

print("Rows in shapefile:", len(gdf))

gdf["GEOID"] = gdf["GEOID"].astype(str)

# ============================================================
# MERGE
# ============================================================

merged = gdf.merge(
    df,
    on="GEOID",
    how="left"
)

print("Rows after merge:", len(merged))

print(
    "Matched rows:",
    merged["total_pop"].notna().sum()
)

# ============================================================
# SAVE
# ============================================================

print("\nSaving GeoJSON...")

merged.to_file(
    OUTPUT_GEOJSON,
    driver="GeoJSON"
)

print(f"\nSaved: {OUTPUT_GEOJSON}")