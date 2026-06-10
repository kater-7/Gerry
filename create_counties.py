import geopandas as gpd

from config import PRECINCT_SHAPEFILE

precincts = gpd.read_file(
    PRECINCT_SHAPEFILE
)

print(
    f"NC counties: {len(precincts)}"
)

for col in precincts.columns:
    print(col)


precincts.to_file(
    "data/processed/nc_precincts.geojson",
    driver="GeoJSON"
)