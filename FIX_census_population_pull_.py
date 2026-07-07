"""
fetch_census_nc.py
------------------
Pulls 2024 ACS 5-Year estimates for North Carolina at the block group level.

Tables pulled:
  B01001  - Sex by Age (used to build age bands)
  B02001  - Race
  B03003  - Hispanic or Latino Origin

Age bands produced (male + female combined):
  pop_under_18      : <18  (not voting age, useful as context)
  pop_18_24         : 18–24
  pop_25_34         : 25–34
  pop_35_44         : 35–44
  pop_45_54         : 45–54
  pop_55_64         : 55–64
  pop_65_74         : 65–74
  pop_75plus        : 75+
  pop_voting_age    : 18+  (sum of all voting-age bands)
  pop_total         : total all ages

Output:
  nc_census_blockgroups.csv

Requirements:
  pip install requests pandas

Usage:
  1. Get a free Census API key at: https://api.census.gov/data/key_signup.html
  2. Set your key below or: export CENSUS_API_KEY=your_key
  3. Run: python fetch_census_nc.py
"""

import requests
import pandas as pd
import os
import time

# ── CONFIG ────────────────────────────────────────────────────────────────────
CENSUS_API_KEY = os.environ.get("CENSUS_API_KEY", "a06207caa3490ef482e89196770ed4aab23428cb")
ACS_YEAR       = 2024
STATE_FIPS     = "37"          # North Carolina
BASE_URL       = f"https://api.census.gov/data/{ACS_YEAR}/acs/acs5"
OUTPUT_FILE    = "nc_census_blockgroups.csv"
# ──────────────────────────────────────────────────────────────────────────────


# ── B01001 VARIABLE MAP ───────────────────────────────────────────────────────
# Each entry: variable_code -> (sex, age_label)
# Male:   007–025  Female: 031–049
# The ACS age buckets within B01001 are:
#   007/031 = 18-19,  008/032 = 20,  009/033 = 21,  010/034 = 22-24
#   011/035 = 25-29,  012/036 = 30-34
#   013/037 = 35-39,  014/038 = 40-44
#   015/039 = 45-49,  016/040 = 50-54
#   017/041 = 55-59,  018/042 = 60-61,  019/043 = 62-64
#   020/044 = 65-66,  021/045 = 67-69,  022/046 = 70-74
#   023/047 = 75-79,  024/048 = 80-84,  025/049 = 85+
#   Male under 18: 003=5-9, 004=10-14, 005=15-17 (002=<5)
#   Female under 18: 027=5-9, 028=10-14, 029=15-17 (026=<5)

AGE_BAND_VARS = {
    # band_name : [male_vars, female_vars]
    "pop_under_18": {
        "male":   ["B01001_003E","B01001_004E","B01001_005E","B01001_006E"],
        "female": ["B01001_027E","B01001_028E","B01001_029E","B01001_030E"],
    },
    "pop_18_24": {
        "male":   ["B01001_007E","B01001_008E","B01001_009E","B01001_010E"],
        "female": ["B01001_031E","B01001_032E","B01001_033E","B01001_034E"],
    },
    "pop_25_34": {
        "male":   ["B01001_011E","B01001_012E"],
        "female": ["B01001_035E","B01001_036E"],
    },
    "pop_35_44": {
        "male":   ["B01001_013E","B01001_014E"],
        "female": ["B01001_037E","B01001_038E"],
    },
    "pop_45_54": {
        "male":   ["B01001_015E","B01001_016E"],
        "female": ["B01001_039E","B01001_040E"],
    },
    "pop_55_64": {
        "male":   ["B01001_017E","B01001_018E","B01001_019E"],
        "female": ["B01001_041E","B01001_042E","B01001_043E"],
    },
    "pop_65_74": {
        "male":   ["B01001_020E","B01001_021E","B01001_022E"],
        "female": ["B01001_044E","B01001_045E","B01001_046E"],
    },
    "pop_75plus": {
        "male":   ["B01001_023E","B01001_024E","B01001_025E"],
        "female": ["B01001_047E","B01001_048E","B01001_049E"],
    },
}

# Flatten to a unique list of all raw vars we need to fetch
ALL_AGE_VARS = ["B01001_001E"]  # total population
for band in AGE_BAND_VARS.values():
    ALL_AGE_VARS += band["male"] + band["female"]
ALL_AGE_VARS = list(dict.fromkeys(ALL_AGE_VARS))  # deduplicate, preserve order

# ── RACE VARIABLES ────────────────────────────────────────────────────────────
RACE_VARS = {
    "pop_white_alone":  "B02001_002E",
    "pop_black_alone":  "B02001_003E",
    "pop_aian_alone":   "B02001_004E",  # American Indian / Alaska Native
    "pop_asian_alone":  "B02001_005E",
    "pop_nhpi_alone":   "B02001_006E",  # Native Hawaiian / Pacific Islander
    "pop_other_alone":  "B02001_007E",
    "pop_two_or_more":  "B02001_008E",
}

# ── HISPANIC/LATINO VARIABLES ─────────────────────────────────────────────────
HISPANIC_VARS = {
    "pop_hispanic":     "B03003_003E",
    "pop_not_hispanic": "B03003_002E",
}
# ──────────────────────────────────────────────────────────────────────────────


def fetch_acs(variables: list, state: str, label: str) -> pd.DataFrame:
    """
    Fetch ACS variables for all block groups in a state.
    Chunks requests to stay under the 50-variable API limit.
    """
    GEO        = f"for=block+group:*&in=state:{state}+county:*+tract:*"
    ID_COLS    = ["NAME", "state", "county", "tract", "block group"]
    CHUNK_SIZE = 45

    chunks = [variables[i:i+CHUNK_SIZE] for i in range(0, len(variables), CHUNK_SIZE)]
    frames = []

    for idx, chunk in enumerate(chunks):
        var_str = ",".join(["NAME"] + chunk)
        url = f"{BASE_URL}?get={var_str}&{GEO}&key={CENSUS_API_KEY}"

        print(f"  [{label}] chunk {idx+1}/{len(chunks)} — {len(chunk)} vars...")
        resp = requests.get(url, timeout=60)

        if resp.status_code != 200:
            raise RuntimeError(f"API error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        df = pd.DataFrame(data[1:], columns=data[0])
        frames.append(df)
        time.sleep(0.3)

    merged = frames[0]
    for df in frames[1:]:
        merged = merged.merge(df, on=ID_COLS, how="outer")

    return merged


def build_geoid(df: pd.DataFrame) -> pd.DataFrame:
    """Standard 12-digit Census GEOID: state(2) + county(3) + tract(6) + block group(1)."""
    df["GEOID"] = (
        df["state"].str.zfill(2)
        + df["county"].str.zfill(3)
        + df["tract"].str.zfill(6)
        + df["block group"].str.zfill(1)
    )
    return df


def main():
    if CENSUS_API_KEY == "YOUR_KEY_HERE":
        print("⚠  No API key set!")
        print("   Get one free at: https://api.census.gov/data/key_signup.html")
        print("   Then set CENSUS_API_KEY in this script or: export CENSUS_API_KEY=your_key\n")
        return

    print(f"Fetching {ACS_YEAR} ACS 5-Year data for NC block groups...\n")

    # ── 1. Age variables ──────────────────────────────────────────────────────
    df_age = fetch_acs(ALL_AGE_VARS, STATE_FIPS, "B01001 Age")
    df_age = build_geoid(df_age)

    for col in ALL_AGE_VARS:
        df_age[col] = pd.to_numeric(df_age[col], errors="coerce")

    df_age["pop_total"] = df_age["B01001_001E"]

    # Build each age band by summing its male + female raw vars
    for band_name, band_vars in AGE_BAND_VARS.items():
        all_vars = band_vars["male"] + band_vars["female"]
        df_age[band_name] = df_age[all_vars].sum(axis=1)

    # Voting-age total = all bands except under_18
    voting_age_bands = [b for b in AGE_BAND_VARS if b != "pop_under_18"]
    df_age["pop_voting_age"] = df_age[voting_age_bands].sum(axis=1)

    # ── 2. Race variables ─────────────────────────────────────────────────────
    df_race = fetch_acs(list(RACE_VARS.values()), STATE_FIPS, "B02001 Race")
    df_race = build_geoid(df_race)

    for col in RACE_VARS.values():
        df_race[col] = pd.to_numeric(df_race[col], errors="coerce")

    df_race.rename(columns={v: k for k, v in RACE_VARS.items()}, inplace=True)

    # ── 3. Hispanic/Latino variables ──────────────────────────────────────────
    df_hisp = fetch_acs(list(HISPANIC_VARS.values()), STATE_FIPS, "B03003 Hispanic")
    df_hisp = build_geoid(df_hisp)

    for col in HISPANIC_VARS.values():
        df_hisp[col] = pd.to_numeric(df_hisp[col], errors="coerce")

    df_hisp.rename(columns={v: k for k, v in HISPANIC_VARS.items()}, inplace=True)

    # ── 4. Merge everything ───────────────────────────────────────────────────
    ID_COLS = ["GEOID", "NAME", "state", "county", "tract", "block group"]

    age_band_cols = list(AGE_BAND_VARS.keys())
    keep_age  = ID_COLS + ["pop_total", "pop_voting_age"] + age_band_cols
    keep_race = ["GEOID"] + list(RACE_VARS.keys())
    keep_hisp = ["GEOID"] + list(HISPANIC_VARS.keys())

    final = (
        df_age[keep_age]
        .merge(df_race[keep_race], on="GEOID", how="left")
        .merge(df_hisp[keep_hisp], on="GEOID", how="left")
    )

    # ── 5. Derived columns ────────────────────────────────────────────────────
    final["pop_white_nonhispanic"] = (
        final["pop_white_alone"] - final["pop_hispanic"]
    ).clip(lower=0)
    final["pop_nonwhite"] = final["pop_total"] - final["pop_white_alone"]

    # ── 6. Save ───────────────────────────────────────────────────────────────
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅ Done! {len(final):,} block groups saved to: {OUTPUT_FILE}")
    print(f"\n   Age band totals (statewide):")
    for col in ["pop_total", "pop_voting_age"] + age_band_cols:
        print(f"   {col:<22}: {final[col].sum():>12,.0f}")


if __name__ == "__main__":
    main()