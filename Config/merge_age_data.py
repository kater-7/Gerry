import geopandas as gpd
import pandas as pd

counties = gpd.read_file(
    "data/processed/nc_counties.geojson"
)

age = pd.read_csv(
    "data/processed/census_age.csv"
)

counties["GEOID"] = counties["GEOID"].astype(str)
age["GEOID"] = age["GEOID"].astype(str)

merged = counties.merge(
    age,
    on="GEOID",
    how="left"
)

print(merged[["NAME_x", "pct_youth"]].head())

merged.to_file(
    "data/processed/nc_age.geojson",
    driver="GeoJSON"
)

print("Saved nc_age.geojson")