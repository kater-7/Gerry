import geopandas as gpd
import pandas as pd

precincts_gdf = gpd.read_file("data/raw/shapefiles/precincts/SBE_PRECINCTS_CENSUSBLOCKS_20251212.shp")
voters = pd.read_csv("nc_voters_by_precinct.csv", dtype=str)

precincts_gdf["county_nam"] = precincts_gdf["county_nam"].str.strip().str.upper()
precincts_gdf["prec_id"]    = precincts_gdf["prec_id"].str.strip().str.upper()
voters["county_desc"]       = voters["county_desc"].str.strip().str.upper()
voters["precinct_abbrv"]    = voters["precinct_abbrv"].str.strip().str.upper()

# Check 1: Does S4A exist in voter file for Cleveland?
print("=== CLEVELAND precinct search ===")
print(voters[voters["county_desc"] == "CLEVELAND"][["county_desc","precinct_abbrv"]].to_string())

# Check 2: Does LEE county have a D1 precinct in voter file?
print("\n=== LEE county D1 search ===")
print(voters[voters["county_desc"] == "LEE"][["county_desc","precinct_abbrv"]].to_string())

# Check 3: What does the NaN row look like in the shapefile?
print("\n=== NaN row in shapefile ===")
print(precincts_gdf[precincts_gdf["county_nam"].isna()][["county_nam","prec_id","county_id","enr_desc"]].to_string())

# Check 4: How many registered voters are in HENDERSON CV?
print("\n=== HENDERSON CV voter data ===")
print(voters[voters["precinct_abbrv"] == "CV"][["county_desc","precinct_abbrv","reg_total","reg_active"]].to_string())