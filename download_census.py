import requests
import pandas as pd
import geopandas as gpd

from config import (
    ACS_YEAR,
    STATE_FIPS,
    CENSUS_API_KEY,
    ACS_AGE_VARIABLES
)

print("Building Census API request...")

base_url = (
    f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
)

age = gpd.read_file(
    "data/processed/nc_age.geojson"
)

variable_codes = list(
    ACS_AGE_VARIABLES.values()
)

variable_string = ",".join(
    variable_codes
)

url = (
    f"{base_url}"
    f"?get=NAME,{variable_string}"
    f"&for=county:*"
    f"&in=state:{STATE_FIPS}"
    f"&key={CENSUS_API_KEY}"
)

print(url)

response = requests.get(url)

print(
    f"Status Code: {response.status_code}"
)
print(response.text)

data = response.json()

df = pd.DataFrame(
    data[1:],
    columns=data[0]
)

rename_dict = {
    code: name
    for name, code in ACS_AGE_VARIABLES.items()
}

df = df.rename(
    columns=rename_dict
)

# Convert every ACS variable to numeric
for col in ACS_AGE_VARIABLES.keys():
    df[col] = pd.to_numeric(df[col])

df["GEOID"] = (
    df["state"] +
    df["county"]
)

df["white_youth"] = (
    df["w_m18_19"]
    + df["w_m20_24"]
    + df["w_f18_19"]
    + df["w_f20_24"]
)

df["black_youth"] = (
    df["b_m18_19"]
    + df["b_m20_24"]
    + df["b_f18_19"]
    + df["b_f20_24"]
)

df["hispanic_youth"] = (
    df["h_m18_19"]
    + df["h_m20_24"]
    + df["h_f18_19"]
    + df["h_f20_24"]
)

df["youth_18_24"] = (
    df["m18_19"]
    +df["m20"]
    +df["m21"]
    +df["m22_24"]
    +df["f18_19"]
    +df["f20"]
    +df["f21"]
    +df["f22_24"]
)

output_file = (
    "data/processed/age_demographic.csv"
)

df.to_csv(
    output_file,
    index=False
)

print(
    f"Saved to {output_file}"
)

print(df.head())

df["pct_white_youth"] = (
    df["white_youth"]
    / df["youth_18_24"]
) * 100

df["pct_black_youth"] = (
    df["black_youth"]
    / df["youth_18_24"]
) * 100

df["pct_hispanic_youth"] = (
    df["hispanic_youth"]
    / df["youth_18_24"]
) * 100

