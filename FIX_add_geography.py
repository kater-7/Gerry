import geopandas as gpd
import pandas as pd

# ── 1. The block-to-precinct shapefile (the one with 236k rows) ──
rdh = gpd.read_file("data/raw/nc_2024_gen_prec/nc_2024_gen_all_prec/nc_2024_gen_all_prec.shp")
import geopandas as gpd
import pandas as pd
import geopandas as gpd
import pandas as pd

ours = gpd.read_file("nc_precincts.geojson")

rdh["_key"] = rdh["COUNTY"].str.strip().str.upper() + "|||" + rdh["PRECINCT"].str.strip().str.upper()
ours["_key"] = ours["county"].str.strip().str.upper() + "|||" + ours["precinct_id"].str.strip().str.upper()

# All unmatched RDH precincts grouped by county
unmatched = rdh[~rdh["_key"].isin(ours["_key"])][["COUNTY","PRECINCT"]]
print(f"Total unmatched: {len(unmatched)}")
print("\nUnmatched by county:")
print(unmatched.groupby("COUNTY").size().sort_values(ascending=False).to_string())

# Also check reverse — our precincts not in RDH
unmatched_ours = ours[~ours["_key"].isin(rdh["_key"])][["county","precinct_id"]]
print(f"\nOur precincts not in RDH: {len(unmatched_ours)}")
print(unmatched_ours.groupby("county").size().sort_values(ascending=False).head(15).to_string())