import io
import os
import zipfile
import pandas as pd
import requests
import geopandas as gpd
from shapely.geometry import Point

INPUT_CSV = (
    "https://s3.amazonaws.com/dl.ncsbe.gov/ENRS/2024_11_05/polling_place_20241105.csv"
)
OUTPUT_SHAPEFILE = "2024_nc_polling_places.shp"
OUTPUT_ZIP = "2024_nc_polling_places.zip"

# Census Bureau batch geocoder endpoint (free, no key needed)
CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

# ---------------------------------------------------------------------------
# 1. Load the source data
# ---------------------------------------------------------------------------
df = pd.read_csv(INPUT_CSV, encoding="utf-16-le", sep="\t")

# One record (Polkton Fire Dept, Anson County) is missing a city — fill it in
# based on the zip code (28133 = Polkton, NC). Check your own data for other
# gaps before geocoding, since blank fields lower match rates.
df["city"] = df["city"].fillna("POLKTON")

# NOTE: polling_place_id is NOT unique across the whole file — it resets
# per county (e.g. Alamance has an id "1", but so do dozens of other
# counties). Using it as a join key would silently corrupt merges later on.
# Use the dataframe's row index instead, which is guaranteed unique.
df = df.reset_index(drop=True)
df["_row_id"] = df.index

# ---------------------------------------------------------------------------
# 2. Build the batch geocoder input file
# ---------------------------------------------------------------------------
# The Census batch API expects a headerless CSV with columns:
# Unique ID, Street address, City, State, ZIP
batch_input = df[["_row_id", "street_address", "city", "state", "zip"]].copy()
batch_csv = io.StringIO()
batch_input.to_csv(batch_csv, index=False, header=False)
batch_csv.seek(0)

# ---------------------------------------------------------------------------
# 3. Submit to the Census batch geocoder
# ---------------------------------------------------------------------------
files = {"addressFile": ("batch.csv", batch_csv.getvalue(), "text/csv")}
data = {"benchmark": "Public_AR_Current"}

print(f"Submitting {len(batch_input)} addresses to the Census batch geocoder...")
# A ~2,600-row batch can take several minutes to process — use a generous
# read timeout rather than a short one, which would raise a spurious
# timeout error on a large file even though the job is fine.
response = requests.post(CENSUS_BATCH_URL, files=files, data=data, timeout=(30, 900))
response.raise_for_status()

# Response is a headerless CSV. Matched rows have 8 fields; No_Match rows
# have only 3 (ID, input address, "No_Match") — pandas fills the rest with
# NaN automatically, so this is safe to parse directly.
result_cols = [
    "_row_id",
    "input_address",
    "match_status",
    "match_type",
    "matched_address",
    "lonlat",
    "tiger_line_id",
    "side",
]
results = pd.read_csv(io.StringIO(response.text), header=None, names=result_cols)

# Split "lon,lat" into two columns (only present for matches)
coords = results["lonlat"].str.split(",", expand=True)
results["longitude"] = pd.to_numeric(coords[0], errors="coerce")
results["latitude"] = pd.to_numeric(coords[1], errors="coerce")

unmatched = results[results["match_status"] != "Match"]
if len(unmatched):
    print(f"{len(unmatched)} addresses did not match and will be dropped:")
    print(unmatched[["_row_id", "input_address"]].to_string(index=False))

# ---------------------------------------------------------------------------
# 4. Merge coordinates back onto the original data
# ---------------------------------------------------------------------------
merged = df.merge(
    results[["_row_id", "match_status", "latitude", "longitude"]],
    on="_row_id",
    how="left",
)
geocoded = merged.dropna(subset=["latitude", "longitude"]).copy()
geocoded = geocoded.drop(columns=["_row_id"])

print(
    f"\nFinal result: {len(geocoded)} / {len(df)} addresses geocoded "
    f"({(len(geocoded) / len(df)) * 100:.1f}%)."
)

# ---------------------------------------------------------------------------
# 5. Build a GeoDataFrame and write the shapefile
# ---------------------------------------------------------------------------
geometry = [Point(xy) for xy in zip(geocoded["longitude"], geocoded["latitude"])]
gdf = gpd.GeoDataFrame(geocoded, geometry=geometry, crs="EPSG:4326")

# Shapefile column names are capped at 10 characters — rename to fit
gdf = gdf.rename(
    columns={
        "election_dt": "elect_dt",
        "county_name": "county",
        "polling_place_id": "pp_id",
        "polling_place_name": "pp_name",
        "precinct_name": "precinct",
        "street_address": "street",
        "match_status": "match_stat",
    }
)

gdf.to_file(OUTPUT_SHAPEFILE)
print(f"Wrote {len(gdf)} points to {OUTPUT_SHAPEFILE}")

# ---------------------------------------------------------------------------
# 6. Zip up the shapefile components (.shp/.shx/.dbf/.prj/.cpg)
# ---------------------------------------------------------------------------
base_name = os.path.splitext(OUTPUT_SHAPEFILE)[0]
shp_extensions = [".shp", ".shx", ".dbf", ".prj", ".cpg"]

with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for ext in shp_extensions:
        component = base_name + ext
        if os.path.exists(component):
            zf.write(component, arcname=os.path.basename(component))

print(f"Zipped shapefile components into {OUTPUT_ZIP}")


INPUT_CSV = "early_voting_sites_march_2026.csv"
OUTPUT_SHAPEFILE = "2026_nc_early_voting_sites.shp"
OUTPUT_ZIP = "2026_nc_early_voting_sites.zip"

# Census Bureau batch geocoder endpoint (free, no key needed)
CENSUS_BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"

# ---------------------------------------------------------------------------
# 1. Load the source data
# ---------------------------------------------------------------------------
# Plain UTF-8 CSV (unlike the polling-place file, this one isn't UTF-16/tab).
df = pd.read_csv(INPUT_CSV, encoding="utf-8")

# site_id is unique within this file already, but reset/rebuild _row_id the
# same way as the polling-place script so the join logic is identical and
# doesn't depend on any particular ID column being unique.
df = df.reset_index(drop=True)
df["_row_id"] = df.index

# ---------------------------------------------------------------------------
# 2. Build the batch geocoder input file
# ---------------------------------------------------------------------------
batch_input = df[["_row_id", "street_address", "city", "state", "zip"]].copy()
batch_csv = io.StringIO()
batch_input.to_csv(batch_csv, index=False, header=False)
batch_csv.seek(0)

# ---------------------------------------------------------------------------
# 3. Submit to the Census batch geocoder
# ---------------------------------------------------------------------------
files = {"addressFile": ("batch.csv", batch_csv.getvalue(), "text/csv")}
data = {"benchmark": "Public_AR_Current"}

print(f"Submitting {len(batch_input)} addresses to the Census batch geocoder...")
response = requests.post(CENSUS_BATCH_URL, files=files, data=data, timeout=(30, 900))
response.raise_for_status()

result_cols = [
    "_row_id",
    "input_address",
    "match_status",
    "match_type",
    "matched_address",
    "lonlat",
    "tiger_line_id",
    "side",
]
results = pd.read_csv(io.StringIO(response.text), header=None, names=result_cols)

coords = results["lonlat"].str.split(",", expand=True)
results["longitude"] = pd.to_numeric(coords[0], errors="coerce")
results["latitude"] = pd.to_numeric(coords[1], errors="coerce")

unmatched = results[results["match_status"] != "Match"]
if len(unmatched):
    print(f"{len(unmatched)} addresses did not match and will be dropped:")
    print(unmatched[["_row_id", "input_address"]].to_string(index=False))

# ---------------------------------------------------------------------------
# 4. Merge coordinates back onto the original data
# ---------------------------------------------------------------------------
merged = df.merge(
    results[["_row_id", "match_status", "latitude", "longitude"]],
    on="_row_id",
    how="left",
)
geocoded = merged.dropna(subset=["latitude", "longitude"]).copy()
geocoded = geocoded.drop(columns=["_row_id"])

print(
    f"\nFinal result: {len(geocoded)} / {len(df)} addresses geocoded "
    f"({(len(geocoded) / len(df)) * 100:.1f}%)."
)

# ---------------------------------------------------------------------------
# 5. Build a GeoDataFrame and write the shapefile
# ---------------------------------------------------------------------------
geometry = [Point(xy) for xy in zip(geocoded["longitude"], geocoded["latitude"])]
gdf = gpd.GeoDataFrame(geocoded, geometry=geometry, crs="EPSG:4326")

# Shapefile column names are capped at 10 characters — rename to fit
gdf = gdf.rename(
    columns={
        "election_dt": "elect_dt",
        "county_name": "county",
        "site_id": "site_id",
        "polling_place_name": "site_name",
        "street_address": "street",
        "match_status": "match_stat",
    }
)

gdf.to_file(OUTPUT_SHAPEFILE)
print(f"Wrote {len(gdf)} points to {OUTPUT_SHAPEFILE}")

# ---------------------------------------------------------------------------
# 6. Zip up the shapefile components (.shp/.shx/.dbf/.prj/.cpg)
# ---------------------------------------------------------------------------
base_name = os.path.splitext(OUTPUT_SHAPEFILE)[0]
shp_extensions = [".shp", ".shx", ".dbf", ".prj", ".cpg"]

with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
    for ext in shp_extensions:
        component = base_name + ext
        if os.path.exists(component):
            zf.write(component, arcname=os.path.basename(component))

print(f"Zipped shapefile components into {OUTPUT_ZIP}")
