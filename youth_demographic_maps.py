## Packages
import pandas as pd
import geopandas as gpd


age = pd.read_csv(
    "data/processed/age_demographic.csv"
)

counties = gpd.read_file(
    "data/processed/nc_counties.geojson"
)

counties["GEOID"] = counties["GEOID"].astype(str)
age["GEOID"] = age["GEOID"].astype(str)

voting_reg = pd.read_csv(
    "data/processed/county_registration.csv"
)

for col in voting_reg.columns:
    print(col)

print(voting_reg["county"].unique)

'''
counties_age = counties.merge(
    age,
    on="GEOID",
    how="left"
)

counties_age["county"] = (
    counties_age[""]
    .str.upper()
)

merged = counties_age.merge(
    voting_reg,
    on="county",
    how="left"
)

merged.to_file(
    "data/processed/nc_age_demographics.geojson",
    driver="GeoJSON"
)

for col in counties.columns:
    print(col)

for col in census.columns:
    print(col)


## Merge counties and census
counties["GEOID"] = counties["GEOID"].astype(str)
census["GEOID"] = census["GEOID"].astype(str)

merged = counties.merge(
    census,
    on="GEOID",
    how="left"
)

'''
'''
merged[f"pct_asian"] = (
    merged[f"asian_population"].astype(float)
    /
    merged["population"].astype(float)
    * 100
)

merged[f"pct_black"] = (
    merged[f"black_population"].astype(float)
    /
    merged["population"].astype(float)
    * 100
)

merged[f"pct_white"] = (
    merged[f"white_population"].astype(float)
    /
    merged["population"].astype(float)
    * 100
)

merged[f"pct_hispanic"] = (
    merged[f"hispanic_population"].astype(float)
    /
    merged["population"].astype(float)
    * 100
)

merged.to_file(
    "data/processed/nc_demographic_pct.shp"
)


print("Saved merged file")

##  merge age and demographic dataframes
'''