import os
import zipfile
import pandas as pd
import geopandas as gpd


youth_power_map = gpd.read_file("data/processed/youth_power_map.gpkg")

# Export shapefile
out_dir = "youth_power_shapefile"
os.makedirs(out_dir, exist_ok=True)

shp_path = os.path.join(out_dir, "youth_power_map.shp")

youth_power_map.to_file(shp_path, driver="ESRI Shapefile")

# Zip all shapefile components
zip_name = "youth_power_map.zip"

with zipfile.ZipFile(zip_name, "w") as z:
    for file in os.listdir(out_dir):
        z.write(os.path.join(out_dir, file), arcname=file)

print(f"Created {zip_name}")
