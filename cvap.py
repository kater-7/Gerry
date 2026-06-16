import pandas as pd

cvap = pd.read_csv(
    "data/raw/raw_pums_nc_only.csv", usecols=range(1, 12), skiprows=11, header=None
)

cols = {
    1: "pums_code",
    2: "all_persons",
    3: "youth_18_25_total",
    4: "youth_18_25_cit",
    5: "youth_18_25_noncit",
    6: "not_youth_26_99_total",
    7: "not_youth_26_99_cit",
    8: "not_youth_26_99_noncit",
    9: "minor_0_17_total",
    10: "minor_0_17_cit",
    11: "minor_0_17_noncit",
}

cvap = cvap.rename(columns=cols)
cvap["pums_code"] = cvap["pums_code"].str.extract(r"(\d{5})")
numeric_cols = cvap.columns.drop("pums_code")
cvap[numeric_cols] = cvap[numeric_cols].map(
    lambda x: pd.to_numeric(str(x).replace(",", ""), errors="coerce")
)
cvap = cvap[cvap["all_persons"] != 0].reset_index(drop=True)

cvap.to_csv("data/processed/cvap_clean.csv", index=False)

print(cvap["all_persons"].sum())
vap = cvap["youth_18_25_cit"].sum() + cvap["not_youth_26_99_cit"].sum()
yvap = cvap["youth_18_25_cit"].sum()
