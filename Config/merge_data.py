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

print(merged.head())

print(len(merged))
print(merged.crs)
print(merged.geometry.head())

merged.to_file(
    "data/processed/nc_demographic_pct.shp"
)


print("Saved merged file")