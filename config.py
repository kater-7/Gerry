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

PRECINCT_SHAPEFILE = (
    r"data/raw/shapefiles/precincts/SBE_PRECINCTS_CENSUSBLOCKS_20251212.shp"
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
    r"data\raw\polling_place_20260303.csv"
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

VOTER_REG = (
    r"data/raw/ncvoter_reg/ncvoter_Statewide.txt"
)

import pandas as pd

FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"

sample = pd.read_csv(
    FILE,
    sep="\t",
    encoding="latin1",
    nrows=5
)

for col in sample.columns:
    print(col)

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

AGE_VARIABLES = {

    # Male
    "m18_19": "B01001_007E",
    "m20": "B01001_008E",
    "m21": "B01001_009E",
    "m22_24": "B01001_010E",

    # Female
    "f18_19": "B01001_031E",
    "f20": "B01001_032E",
    "f21": "B01001_033E",
    "f22_24": "B01001_034E",
}

WHITE_AGE_VARIABLES = {
    "w_m18_19": "B01001A_007E",
    "w_m20": "B01001A_008E",
    "w_m21": "B01001A_009E",
    "w_m22_24": "B01001A_010E",

    "w_f18_19": "B01001A_031E",
    "w_f20": "B01001A_032E",
    "w_f21": "B01001A_033E",
    "w_f22_24": "B01001A_034E"
}

BLACK_AGE_VARIABLES = {
    "b_m18_19": "B01001B_007E",
    "b_m20": "B01001B_008E",
    "b_m21": "B01001B_009E",
    "b_m22_24": "B01001B_010E",

    "b_f18_19": "B01001B_031E",
    "b_f20": "B01001B_032E",
    "b_f21": "B01001B_033E",
    "b_f22_24": "B01001B_034E"
}

HISPANIC_AGE_VARIABLES = {
    "h_m18_19": "B01001I_007E",
    "h_m20": "B01001I_008E",
    "h_m21": "B01001I_009E",
    "h_m22_24": "B01001I_010E",

    "h_f18_19": "B01001I_031E",
    "h_f20": "B01001I_032E",
    "h_f21": "B01001I_033E",
    "h_f22_24": "B01001I_034E"
}

ACS_AGE_VARIABLES = {

    # White
    "w_m18_19": "B01001A_007E",
    "w_m20_24": "B01001A_008E",
    "w_f18_19": "B01001A_022E",
    "w_f20_24": "B01001A_023E",

    # Black
    "b_m18_19": "B01001B_007E",
    "b_m20_24": "B01001B_008E",
    "b_f18_19": "B01001B_022E",
    "b_f20_24": "B01001B_023E",

    # Hispanic
    "h_m18_19": "B01001I_007E",
    "h_m20_24": "B01001I_008E",
    "h_f18_19": "B01001I_022E",
    "h_f20_24": "B01001I_023E",

     # Male
    "m18_19": "B01001_007E",
    "m20": "B01001_008E",
    "m21": "B01001_009E",
    "m22_24": "B01001_010E",

    # Female
    "f18_19": "B01001_031E",
    "f20": "B01001_032E",
    "f21": "B01001_033E",
    "f22_24": "B01001_034E",
}
