import geopandas as gpd
import pandas as pd

counties = gpd.read_file(
    "data/processed/nc_counties.geojson"
)

census = pd.read_csv(
    "data/processed/census_counties.csv"
)

# IMPORTANT
counties["GEOID"] = counties["GEOID"].astype(str)
census["GEOID"] = census["GEOID"].astype(str)

merged = counties.merge(
    census,
    on="GEOID",
    how="left"
)

print(merged.head())

merged.to_file(
    "data/processed/nc_demographics.geojson",
    driver="GeoJSON"
)

print("Saved merged file")