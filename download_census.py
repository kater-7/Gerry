import requests
import pandas as pd

from config import (
    ACS_YEAR,
    STATE_FIPS,
    CENSUS_API_KEY,
    ACS_VARIABLES
)

print("Building Census API request...")

base_url = (
    f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
)

variable_codes = list(
    ACS_VARIABLES.values()
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

data = response.json()

df = pd.DataFrame(
    data[1:],
    columns=data[0]
)

rename_dict = {
    code: name
    for name, code in ACS_VARIABLES.items()
}

df = df.rename(
    columns=rename_dict
)

df["GEOID"] = (
    df["state"] +
    df["county"]
)

output_file = (
    "data/processed/census_counties.csv"
)

df.to_csv(
    output_file,
    index=False
)

print(
    f"Saved to {output_file}"
)

print(df.head())