import geopandas as gpd
import pandas as pd

# Load cong (has geometry)
cong = gpd.read_file(r"data\raw\nc_2024_gen_prec\nc_2024_gen_cong_prec\nc_2024_gen_cong_prec.shp")

# Load all (has all race results, no geometry)
all_votes = gpd.read_file(r"data\raw\nc_2024_gen_prec\nc_2024_gen_all_prec\nc_2024_gen_all_prec.shp")

# Normalize keys
for df in [cong, all_votes]:
    df["COUNTY"]   = df["COUNTY"].str.strip().str.upper()
    df["PRECINCT"] = df["PRECINCT"].str.strip().str.upper()

# Check cong columns — does it already have presidential results?
print("Presidential cols in cong:", [c for c in cong.columns if "PRE" in c])

# Check overlap
cong["_key"]      = cong["COUNTY"]      + "|||" + cong["PRECINCT"]
all_votes["_key"] = all_votes["COUNTY"] + "|||" + all_votes["PRECINCT"]
print(f"\ncong rows:      {len(cong):,}")
print(f"all_votes rows: {len(all_votes):,}")
print(f"Keys matching:  {cong['_key'].isin(all_votes['_key']).sum():,}")
print(f"\nSample cong keys:      {cong['_key'].iloc[:3].tolist()}")
print(f"Sample all_votes keys: {all_votes['_key'].iloc[:3].tolist()}")