"""
scripts/3_enrich.py

Enriches the normalized AER frac dataset with formation, pool, licensee,
and basin data from AER reference files.

New columns appended (originals always preserved):
    field_name              — field name from ST37/FieldPoolList join
    production_pool_name    — production pool name from FieldPoolList
    geological_pool_name    — geological pool name (closest to formation)
    licensee_clean          — canonical company name from Well Licence List
    basin                   — derived from bottom hole coordinates

Data sources:
    data/raw/ST37/ST37.txt              — AER well list (UWI + field/pool codes)
    data/raw/st103/FieldPoolList.xlsx   — field and pool name lookup
    data/raw/st104/LicenseeAgent_Codes.xlsx  — licensee code lookup (not used directly)
    data/raw/well_licence_list.csv      — canonical company names by licence number

Usage:
    python scripts/3_enrich.py
    python scripts/3_enrich.py --input Hydraulic_Fracturing_Normalized.csv
    python scripts/3_enrich.py --input Hydraulic_Fracturing_Normalized.csv --output my_output.csv

Output:
    data/processed/Hydraulic_Fracturing_Enriched.csv
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from utils.paths import DATA_PROCESSED, DATA_RAW


# ── Reference file paths ───────────────────────────────────────────────────
ST37_PATH       = DATA_RAW / "ST37"   / "ST37.txt"
FIELD_POOL_PATH = DATA_RAW / "st103"  / "FieldPoolList.xlsx"
WELL_LIC_PATH   = DATA_RAW / "well_licence_list.csv"


# ══════════════════════════════════════════════════════════════════════════
# Step 1 — Load normalized dataset
# ══════════════════════════════════════════════════════════════════════════

def load_normalized(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype={"well_licence_number": str},
        low_memory=False,
    )
    print(f"  Loaded:  {len(df):,} rows, {len(df.columns)} columns")
    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 2 — Build ST37 lookup (UWI → field_code + pool_code)
# ══════════════════════════════════════════════════════════════════════════

def build_st37_lookup(path: Path) -> pd.DataFrame:
    """
    Parse ST37 as tab-delimited. Extract only the columns needed:
        col 0  — uwi_display (join key)
        col 4  — field_code
        col 5  — pool_code

    ST37 has 659k+ rows — load only needed columns for memory efficiency.
    Deduplicate on uwi_display keeping first occurrence.
    """
    st37 = pd.read_csv(
        path,
        sep="\t",
        header=None,
        encoding="latin-1",
        on_bad_lines="skip",
        low_memory=False,
        usecols=[0, 4, 5],
        names=["uwi_display", "field_code", "pool_code"],
    )

    st37["field_code"] = pd.to_numeric(st37["field_code"], errors="coerce")
    st37["pool_code"]  = pd.to_numeric(st37["pool_code"],  errors="coerce")

    # Drop rows with no field code — they can't join to FieldPoolList
    st37 = st37[st37["field_code"].notna() & (st37["field_code"] > 0)]

    # Deduplicate — keep first occurrence per UWI
    st37 = st37.drop_duplicates(subset="uwi_display").reset_index(drop=True)

    print(f"  ST37:    {len(st37):,} unique UWIs with field codes")
    return st37


# ══════════════════════════════════════════════════════════════════════════
# Step 3 — Build FieldPoolList lookup (field_code + pool_code → names)
# ══════════════════════════════════════════════════════════════════════════

def build_field_pool_lookup(path: Path) -> pd.DataFrame:
    """
    Load FieldPoolList and create a lookup keyed on field_code + pool_code.
    Returns columns: field_code, pool_code, field_name,
                     production_pool_name, geological_pool_name
    """
    fpl = pd.read_excel(path)

    fpl = fpl.rename(columns={
        "Field Name":            "field_name",
        "Production Pool Name":  "production_pool_name",
        "Field Code":            "field_code",
        "Production Pool Code":  "pool_code",
        "Geological Pool Name":  "geological_pool_name",
    })

    fpl["field_code"] = pd.to_numeric(fpl["field_code"], errors="coerce")
    fpl["pool_code"]  = pd.to_numeric(fpl["pool_code"],  errors="coerce")

    fpl = fpl[["field_code", "pool_code",
               "field_name", "production_pool_name", "geological_pool_name"]]
    fpl = fpl.dropna(subset=["field_code", "pool_code"])
    fpl = fpl.drop_duplicates(subset=["field_code", "pool_code"])

    print(f"  FieldPoolList: {len(fpl):,} field/pool combinations")
    return fpl


# ══════════════════════════════════════════════════════════════════════════
# Step 4 — Build well licence lookup (licence_number → licensee_clean)
# ══════════════════════════════════════════════════════════════════════════

def build_well_licence_lookup(path: Path) -> pd.DataFrame:
    """
    Load the Well Licence List CSV and normalize licence numbers to match
    the format in the frac dataset (strip 'W ' prefix and leading zeros).
    """
    wll = pd.read_csv(path, low_memory=False)

    wll["licence_clean"] = (
        wll["01.Licence Number"]
        .str.replace("W ", "", regex=False)
        .str.strip()
        .str.lstrip("0")
    )

    wll = wll.rename(columns={"02.Company Name": "licensee_clean"})
    wll = wll[["licence_clean", "licensee_clean"]].drop_duplicates(subset="licence_clean")

    # Clean company name — strip BA code suffix e.g. "Ovintiv Canada ULC(A123)"
    wll["licensee_clean"] = (
        wll["licensee_clean"]
        .str.replace(r"\([^)]*\)", "", regex=True)
        .str.strip()
    )

    print(f"  Well licence list: {len(wll):,} unique licence numbers")
    return wll


# ══════════════════════════════════════════════════════════════════════════
# Step 5 — Join formation data
# ══════════════════════════════════════════════════════════════════════════

def join_formation(df: pd.DataFrame, st37: pd.DataFrame,
                   fpl: pd.DataFrame) -> pd.DataFrame:
    """
    Two-step join:
    1. frac data (uwi) → ST37 (uwi_display) → field_code + pool_code
    2. field_code + pool_code → FieldPoolList → field/pool names
    """
    # Step 1: uwi → field_code + pool_code
    df = df.merge(st37, left_on="uwi", right_on="uwi_display", how="left")
    df = df.drop(columns=["uwi_display"], errors="ignore")

    matched_st37 = df["field_code"].notna().sum()
    print(f"  ST37 join:       {matched_st37:,} rows matched "
          f"({matched_st37/len(df)*100:.1f}%)")

    # Step 2: field_code + pool_code → names
    df = df.merge(fpl, on=["field_code", "pool_code"], how="left")

    matched_fpl = df["field_name"].notna().sum()
    print(f"  FieldPool join:  {matched_fpl:,} rows matched "
          f"({matched_fpl/len(df)*100:.1f}%)")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 6 — Join licensee clean
# ══════════════════════════════════════════════════════════════════════════

def join_licensee(df: pd.DataFrame, wll: pd.DataFrame) -> pd.DataFrame:
    """
    Join canonical company name from Well Licence List.
    well_licence_number in frac data is an integer — convert to string
    and strip leading zeros before joining.
    """
    df["_licence_key"] = (
        df["well_licence_number"]
        .astype(str)
        .str.strip()
        .str.lstrip("0")
    )

    df = df.merge(wll, left_on="_licence_key", right_on="licence_clean", how="left")
    df = df.drop(columns=["_licence_key", "licence_clean"], errors="ignore")

    matched = df["licensee_clean"].notna().sum()
    print(f"  Licensee join:   {matched:,} rows matched "
          f"({matched/len(df)*100:.1f}%)")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 7 — Drop intermediate join keys
# ══════════════════════════════════════════════════════════════════════════

def drop_intermediates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove intermediate columns used only for joining.
    field_code and pool_code are not useful for analysis —
    field_name, production_pool_name, and geological_pool_name
    carry the same information in human-readable form.
    """
    cols_to_drop = ["field_code", "pool_code"]
    df = df.drop(columns=[c for c in cols_to_drop if c in df.columns])
    print(f"  Dropped intermediate columns: {cols_to_drop}")
    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 8 — Save
# ══════════════════════════════════════════════════════════════════════════

def save(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Saved:   {output_path}")


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════

def enrich(input_path: Path, output_path: Path) -> pd.DataFrame:
    start = time.time()

    print(f"\n{'='*56}")
    print(f"  Alberta Frac Hub - Enrich")
    print(f"  Input:   {input_path.name}")
    print(f"{'='*56}\n")

    print("  Step 1 - Loading normalized data...")
    df = load_normalized(input_path)

    print("\n  Step 2 - Building ST37 lookup...")
    st37 = build_st37_lookup(ST37_PATH)

    print("\n  Step 3 - Building FieldPoolList lookup...")
    fpl = build_field_pool_lookup(FIELD_POOL_PATH)

    print("\n  Step 4 - Building well licence lookup...")
    wll = build_well_licence_lookup(WELL_LIC_PATH)

    print("\n  Step 5 - Joining formation data...")
    df = join_formation(df, st37, fpl)

    print("\n  Step 6 - Joining licensee clean...")
    df = join_licensee(df, wll)

    print("\n  Step 7 - Dropping intermediate join keys...")
    df = drop_intermediates(df)

    print("\n  Step 8 - Saving...")
    save(df, output_path)

    elapsed = time.time() - start
    print(f"\n{'='*56}")
    print(f"  Done in {elapsed:.1f}s - {len(df):,} rows, {len(df.columns)} columns")
    print(f"{'='*56}\n")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich normalized AER frac data.")
    parser.add_argument(
        "--input", type=str,
        default="Hydraulic_Fracturing_Normalized.csv",
        help="Normalized input filename (in data/processed/)",
    )
    parser.add_argument(
        "--output", type=str,
        default="Hydraulic_Fracturing_Enriched.csv",
        help="Output filename (in data/processed/)",
    )
    args = parser.parse_args()

    enrich(
        input_path  = DATA_PROCESSED / args.input,
        output_path = DATA_PROCESSED / args.output,
    )
