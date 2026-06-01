"""
Project configuration.
Change settings here instead of throughout the project.
"""
import os
os.getcwd()
# ------------------
# Geography
# ------------------

STATE_NAME = "North Carolina"
STATE_FIPS = "37"

ACS_YEAR = 2024

# ------------------
# Shapefiles
# ------------------

COUNTY_SHAPEFILE = (
    r"data/raw/shapefiles/counties/tl_2025_us_county.shp"
)

TRACT_SHAPEFILE = (
    r"data/raw/shapefiles/tracts/tl_2025_37_tract.shp"
)

# ------------------
# Colleges
# ------------------

COLLEGE_FILE = (
    r"data/raw/colleges.csv"
)

# ------------------
# Polling Places
# ------------------

POLLING_FILE = (
    r"data/raw/polling_places.csv"
)

# ------------------
# Processed Data
# ------------------

NC_COUNTIES_FILE = (
    r"data/processed/nc_counties.geojson"
)

CENSUS_COUNTIES_FILE = (
    r"data/processed/census_counties.csv"
)

# ------------------
# Outputs
# ------------------

MAP_OUTPUT_FOLDER = (
    r"outputs"
)

# ------------------
# Census API
# ------------------

CENSUS_API_KEY = "a06207caa3490ef482e89196770ed4aab23428cb"

# ------------------
# Census Variables
# ------------------

ACS_VARIABLES = {

    "population":
        "B01003_001E",

    "median_income":
        "B19013_001E",

    "white_population":
        "B02001_002E",

    "black_population":
        "B02001_003E",

    "asian_population":
        "B02001_005E",

    "hispanic_population":
        "B03003_003E"

}