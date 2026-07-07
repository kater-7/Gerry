import geopandas as gpd
import os


gdf = gpd.read_file(
    "data/processed/nc_precinct_turnout.geojson"
)

gdf["precinct_id"] = (
    gdf["county_nam"].astype(str)
    + "_"
    + gdf["prec_id"].astype(str)
)

print("Rows:", len(gdf))

print(
    "Unique precincts:",
    gdf["precinct_id"].nunique()
)

precincts = gdf.dissolve(
    by="precinct_id",
    aggfunc="first"
).reset_index()

print(len(precincts))

size_mb = (
    os.path.getsize(
        "data/processed/nc_precincts_dissolved.geojson"
    )
    / 1024**2
)

print(size_mb)

drop_cols = [
    "id",
    "GEOID20",
    "COUNTYFP20",
    "TRACTCE20",
    "BLOCKCE20",
    "Shape_Leng",
    "Shape_Area"
]

precincts = precincts.drop(
    columns=drop_cols,
    errors="ignore"
)

print(precincts.columns.tolist())

precincts.to_file(
    "data/processed/nc_storymap_precincts.geojson",
    driver="GeoJSON"
)

size_mb = (
    os.path.getsize(
        "data/processed/nc_storymap_precincts.geojson"
    )
    / 1024**2
)

print(f"{size_mb:.1f} MB")

