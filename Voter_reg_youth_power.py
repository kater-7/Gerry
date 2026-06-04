import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"
df = pd.read_csv(
    "data/raw/ncvoter_reg/ncvoter_Statewide.txt",
    nrows=5,
    sep="\t"
)

print(df.columns.tolist())

import os

size_gb = os.path.getsize(FILE) / 1024**3
print(f"{size_gb:.2f} GB")