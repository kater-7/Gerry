import numpy as np
import pandas as pd


REG_FILE = "data/raw/ncvoter_reg/ncvoter_Statewide.txt"

HIST_FILE = r"data/raw/ncvhist/ncvhist.txt"

CHUNKSIZE = 500_000

REG_COLS = [
    "ncid",
    "county_desc",
    "birth_year",
    "age_at_year_end",
    "party_cd",
    "registr_dt",
    "voter_status_desc",
    "vtd_abbrv",
    "vtd_desc"
]

reg = pd.read_csv(
    REG_FILE,
    sep="\t",
    encoding="latin1",
    dtype=str,
    usecols=REG_COLS,
    low_memory=False
)

reg["vtd_abbrv"].head(20)
