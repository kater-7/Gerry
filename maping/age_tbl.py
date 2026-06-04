import requests
import pandas as pd

from config import (
    ACS_YEAR,
    STATE_FIPS,
    CENSUS_API_KEY
)

variables = []

for i in range(1, 50):
    variables.append(
        f"B01001_{i:03d}E"
    )

variable_string = ",".join(
    variables
)

url = (
    f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
    f"?get=NAME,{variable_string}"
    f"&for=county:*"
    f"&in=state:{STATE_FIPS}"
    f"&key={CENSUS_API_KEY}"
)

response = requests.get(url)

df = pd.DataFrame(
    response.json()[1:],
    columns=response.json()[0]
)
print(df.columns.tolist())

youth_cols = [
    "B01001_007E",
    "B01001_008E",
    "B01001_009E",
    "B01001_010E",
    "B01001_031E",
    "B01001_032E",
    "B01001_033E",
    "B01001_034E"
]

df[youth_cols] = df[youth_cols].astype(float)

df["youth_18_24"] = df[youth_cols].sum(axis=1)

print(df[["NAME", "youth_18_24"]].head())

df["B01001_001E"] = df["B01001_001E"].astype(float)

df["pct_youth"] = (
    df["youth_18_24"]
    /
    df["B01001_001E"]
    * 100
)

print(
    df[["NAME", "youth_18_24", "pct_youth"]]
    .head(10)
)

df["GEOID"] = (
    df["state"]
    +
    df["county"]
)

df.to_csv(
    "data/processed/census_age.csv",
    index=False
)

print(
    df[["NAME", "GEOID", "pct_youth"]]
    .head()
)
