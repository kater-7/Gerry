"""
create_age_chart_data.py
-------------------------
Creates a CSV for ArcGIS Online bar chart showing:
  - Voting Age Population (VAP) by age band
  - Registered Voters by age band
  - Actual Voters in 2024 General by age band

Includes STATEWIDE totals + breakdown for all 100 NC counties.
In ArcGIS Online, add a filter on 'county' to let users
select any county and the chart updates automatically.

Output:
  nc_age_chart_data.csv

Requirements:
  pip install pandas geopandas
"""

import pandas as pd
import geopandas as gpd
import warnings
warnings.filterwarnings("ignore")

MASTER_CSV   = "nc_master_precinct.csv"
GEOJSON_FILE = "nc_precincts.geojson"
OUTPUT_FILE  = "nc_age_chart_data.csv"

AGE_BANDS = ["18_24", "25_34", "35_44", "45_54", "55_64", "65_74", "75plus"]
AGE_LABELS = {
    "18_24":  "18-24",
    "25_34":  "25-34",
    "35_44":  "35-44",
    "45_54":  "45-54",
    "55_64":  "55-64",
    "65_74":  "65-74",
    "75plus": "75+",
}


def build_rows(m, g, county_label):
    rows = []
    for band in AGE_BANDS:
        pop_col   = f"pop_{band}"
        reg_col   = f"age_{band}"
        voted_col = f"tv_{band}_g2024"

        vap        = pd.to_numeric(g[pop_col],   errors="coerce").sum() if pop_col   in g.columns else None
        registered = pd.to_numeric(m[reg_col],   errors="coerce").sum() if reg_col   in m.columns else None
        voted      = pd.to_numeric(m[voted_col], errors="coerce").sum() if voted_col in m.columns else None

        rows.append({
            "county":     county_label,
            "age_band":   AGE_LABELS[band],
            "vap":        round(vap)        if vap        is not None else None,
            "registered": round(registered) if registered is not None else None,
            "voted_2024": round(voted)      if voted      is not None else None,
        })
    return rows


def main():
    print("Loading master precinct data...")
    master = pd.read_csv(MASTER_CSV)
    master["county_desc"] = master["county_desc"].str.strip().str.upper()

    print("Loading ACS age band population...")
    gdf = gpd.read_file(GEOJSON_FILE)
    gdf["county"] = gdf["county"].str.strip().str.upper()

    all_rows = []

    # Statewide
    all_rows += build_rows(master, gdf, "STATEWIDE")

    # Each county
    counties = sorted(master["county_desc"].unique().tolist())
    print(f"Building rows for {len(counties)} counties...")
    for county in counties:
        m = master[master["county_desc"] == county]
        g = gdf[gdf["county"] == county]
        all_rows += build_rows(m, g, county)

    df = pd.DataFrame(all_rows)

    # Derived columns
    df["reg_rate"]      = (df["registered"] / df["vap"]        * 100).round(1)
    df["turnout_rate"]  = (df["voted_2024"] / df["registered"] * 100).round(1)
    df["voted_of_vap"]  = (df["voted_2024"] / df["vap"]        * 100).round(1)
    df["unreg"]         = (df["vap"] - df["registered"]).clip(lower=0)
    df["reg_not_voted"] = (df["registered"] - df["voted_2024"]).clip(lower=0)

    # Print statewide summary
    sw = df[df["county"] == "STATEWIDE"]
    print(f"\n{'='*75}")
    print(f"  NC 2024 — VAP, Registration & Turnout by Age Band (Statewide)")
    print(f"{'='*75}")
    print(f"  {'Age':>8}  {'VAP':>10}  {'Registered':>12}  {'Voted':>10}  {'Reg%':>6}  {'Turn%':>6}  {'Voted/VAP':>9}")
    print(f"  {'-'*75}")
    for _, row in sw.iterrows():
        print(f"  {row['age_band']:>8}  {row['vap']:>10,.0f}  {row['registered']:>12,.0f}  "
              f"{row['voted_2024']:>10,.0f}  {row['reg_rate']:>5.1f}%  "
              f"{row['turnout_rate']:>5.1f}%  {row['voted_of_vap']:>8.1f}%")
    print(f"{'='*75}")

    df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Saved: {OUTPUT_FILE}")
    print(f"   Rows: {len(df):,}  ({len(counties)+1} areas x {len(AGE_BANDS)} age bands)")
    print(f"\n   ArcGIS Online:")
    print(f"   1. Add {OUTPUT_FILE} as a table item")
    print(f"   2. Charts > Bar Chart > Category: age_band > Series: vap, registered, voted_2024")
    print(f"   3. Add a Filter widget on 'county' to switch between statewide and any county")


if __name__ == "__main__":
    main()