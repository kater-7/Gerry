import geopandas as gpd

gdf = gpd.read_file(
    "data/processed/nc_party_turnout_map.geojson"
)

print(gdf.total_bounds)
gdf = gdf.fillna(0)

gdf.to_file(
    "data/processed/nc_party_turnout_map.shp"
)