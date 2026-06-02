import geopandas as gpd
import pandas as pd

from config import COUNTY_SHAPEFILE
from config import COLLEGE_FILE
from config import POLLING_FILE
import os

print("Working Directory:")
print(os.getcwd())

print("Loading counties...")
counties = gpd.read_file(
    COUNTY_SHAPEFILE
)
print("\nCounty Columns:")
print(counties.columns.tolist())


print("\nLoading colleges...")
colleges = pd.read_csv(
    COLLEGE_FILE
)
print("\nCollege Columns:")
print(colleges.columns.tolist())

print(
    colleges[["county", "enroll"]]
    .head(20)
)

### POLLLING PLACES HAS FILE ISSUES 
'''
print("\nLoading polling places...")

polls = pd.read_csv(
    POLLING_FILE,
    encoding="utf-16"
)

print(polls.head())
'''