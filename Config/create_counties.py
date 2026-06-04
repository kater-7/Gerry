import geopandas as gpd

from config import COUNTY_SHAPEFILE

counties = gpd.read_file(
    COUNTY_SHAPEFILE
)

nc_counties = counties[
    counties["STATEFP"] == "37"
].copy()

print(
    f"NC counties: {len(nc_counties)}"
)

print(
    nc_counties[["NAME", "GEOID"]].head()
)

nc_counties.to_file(
    "data/processed/nc_counties.geojson",
    driver="GeoJSON"
)