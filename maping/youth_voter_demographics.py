# load packages
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
import gdown

file_id = "1AfD4CT8aRHBdZYNORIvOB11fWG9UBX4o"
url = f"https://drive.google.com/uc?id={file_id}"

gdown.download(url, "voters.csv")
voters_raw = pd.read_csv("voters.csv")
voters_raw.head()
