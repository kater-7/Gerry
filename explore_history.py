import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

pum_cvap = pd.read_csv(
    "data/raw/cvap_clean.csv"
)

pum_cvap["percent"] = pum_cvap["youth_18_25_cit"] / pum_cvap["youth_18_25_total"] 

print(pum_cvap["percent"].round(decimals = 2).mode)