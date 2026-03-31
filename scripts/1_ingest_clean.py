"""
scripts/1_ingest_clean.py

Ingests the raw AER hydraulic fracturing CSV and produces a clean,
consistently structured dataset ready for normalization.

This script only cleans — it does not normalize, enrich, or analyze.

Usage:
    python scripts/1_ingest_clean.py
    python scripts/1_ingest_clean.py --input SummaryChemical-WaterUse.csv
    python scripts/1_ingest_clean.py --input SummaryChemical-WaterUse.csv --output my_output.csv

Output:
    data/processed/Hydraulic_Fracturing_Clean.csv
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from utils.paths import CONFIG, DATA_PROCESSED, DATA_RAW
from utils.schema import (
    AER_NULL_VALUES,
    COLUMN_RENAME,
    DATE_COLUMNS,
    DATE_FORMAT,
    DELIMITER,
    ENCODING,
    PREAMBLE_ROWS,
    STRING_COLUMNS,
    UNDISCLOSED_CAS,
    WELL_LICENCE_PATTERN,
)


# ══════════════════════════════════════════════════════════════════════════
# Step 1 — Load
# ══════════════════════════════════════════════════════════════════════════

def load_raw(path: Path) -> pd.DataFrame:
    """
    Read the raw AER pipe-delimited file, skipping the 7-row preamble.

    Post-load cleanup:
    - Drop trailing unnamed columns (artifact from some exports)
    - Filter out footer rows (rows affected, completion time) by checking
      well_licence_number matches a numeric pattern
    """
    dtype_map = {col: str for col in STRING_COLUMNS}

    df = pd.read_csv(
        path,
        skiprows=PREAMBLE_ROWS,
        encoding=ENCODING,
        delimiter=DELIMITER,
        dtype=dtype_map,
        na_values=AER_NULL_VALUES,
        keep_default_na=True,
        low_memory=False,
    )

    # Drop trailing unnamed columns if present (older export artifact)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]

    # Strip header whitespace before footer check
    df.columns = [c.strip() for c in df.columns]

    # Filter out footer rows using well licence number pattern
    well_col = "Well Licence Number"
    if well_col in df.columns:
        valid = df[well_col].str.strip().str.match(WELL_LICENCE_PATTERN, na=False)
        footer_count = (~valid).sum()
        if footer_count > 0:
            print(f"  Dropped: {footer_count} footer row(s)")
        df = df[valid].reset_index(drop=True)

    print(f"  Loaded:  {len(df):,} rows, {len(df.columns)} columns")
    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 2 — Standardize column names
# ══════════════════════════════════════════════════════════════════════════

def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rename columns to snake_case.
    Header whitespace is already stripped in load_raw.
    Any unexpected columns are preserved and reported.
    """
    df = df.rename(columns=COLUMN_RENAME)

    unexpected = [c for c in df.columns if c not in COLUMN_RENAME.values()]
    if unexpected:
        print(f"  Warning: unexpected columns kept as-is: {unexpected}")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 3 — Parse dates
# ══════════════════════════════════════════════════════════════════════════

def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse date columns using mixed format to handle AER date variants.
    Unparseable values become NaT rather than being dropped or filled.
    Derives start_year and start_month for time-series analysis.
    """
    renamed_date_cols = [COLUMN_RENAME[c] for c in DATE_COLUMNS if c in COLUMN_RENAME]

    for col in renamed_date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", format=DATE_FORMAT).dt.date

    if "start_date" in df.columns:
        start = pd.to_datetime(df["start_date"], errors="coerce")
        df["start_year"]  = start.dt.year.astype("Int64")
        df["start_month"] = start.dt.month.astype("Int64")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 4 — Clean string fields
# ══════════════════════════════════════════════════════════════════════════

def clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    """
    Strip whitespace from all string columns.
    Uppercase fields used for grouping and matching downstream.
    """
    renamed_date_cols = {COLUMN_RENAME[c] for c in DATE_COLUMNS if c in COLUMN_RENAME}
    str_cols = [
        c for c in df.columns
        if df[c].dtype == "object" and c not in renamed_date_cols
    ]

    for col in str_cols:
        df[col] = df[col].str.strip().str.replace(r"\s+", " ", regex=True)

    for col in ["licensee", "component_supplier_name"]:
        if col in df.columns:
            df[col] = df[col].str.upper()

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 5 — Canonicalize supplier names
# ══════════════════════════════════════════════════════════════════════════

def canonicalize_suppliers(df: pd.DataFrame, supplier_map_path: Path) -> pd.DataFrame:
    """
    Apply the supplier name mapping to produce component_supplier_name_clean.
    Raw value is always preserved in component_supplier_name.
    """
    if not supplier_map_path.exists():
        print(f"  Warning: supplier map not found at {supplier_map_path}. "
              f"component_supplier_name_clean will use raw values.")
        df["component_supplier_name_clean"] = df["component_supplier_name"]
        return df

    map_df = pd.read_csv(supplier_map_path)
    supplier_map = dict(zip(
        map_df["Variant"].str.upper().str.strip(),
        map_df["Canonical"].str.upper().str.strip(),
    ))

    # Strip and collapse whitespace immediately before lookup
    # component_supplier_name is set from a shifted column and may contain
    # trailing spaces that survive the earlier clean_strings() step
    df["component_supplier_name"] = (
        df["component_supplier_name"]
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    mapped = df["component_supplier_name"].map(supplier_map)
    df["component_supplier_name_clean"] = mapped.fillna(df["component_supplier_name"])
    df["_supplier_mapped"] = mapped.notna()

    matched   = df["_supplier_mapped"].sum()
    unmatched = df["component_supplier_name"].notna().sum() - matched
    print(f"  Supplier map: {matched:,} rows matched, {unmatched:,} unmatched")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 6 — Flag data quality issues
# ══════════════════════════════════════════════════════════════════════════

def flag_data_quality(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add a supplier_flag column to mark known data quality issues.
    Data is never removed — flags let downstream processes decide.

    Flag values:
        UNMATCHED   — supplier name not found in the canonical map
        None        — matched or null
    """
    is_unmatched = (
        df["component_supplier_name"].notna()
        & ~df["_supplier_mapped"]
    )

    df["supplier_flag"] = None
    df.loc[is_unmatched, "supplier_flag"] = "UNMATCHED"
    df = df.drop(columns=["_supplier_mapped"])

    unmatched_count = is_unmatched.sum()
    clean_count     = len(df) - unmatched_count
    print(f"  Supplier flags: {unmatched_count:,} UNMATCHED, {clean_count:,} matched or null")

    return df



# ══════════════════════════════════════════════════════════════════════════
# Step 7 — Deduplicate ingredient names via CAS number
# ══════════════════════════════════════════════════════════════════════════

def deduplicate_ingredients(df: pd.DataFrame) -> pd.DataFrame:
    """
    Produce ingredient_name_clean using two strategies:

    1. Valid CAS number  → find the most frequently used ingredient_name
       for that CAS across the entire dataset and use it as the canonical
       name. Purely data-driven — no manual curation required.

    2. Undisclosed CAS  → basic string normalization of ingredient_name
       (lowercase, strip, collapse whitespace). Best-effort only.

    ingredient_name is always preserved unchanged.
    ingredient_name_clean is lowercase for analysis consistency.
    """
    # Build canonical name lookup: most frequent ingredient_name per CAS
    is_valid_cas = (
        df["cas_hmirc"].notna()
        & ~df["cas_hmirc"].isin(UNDISCLOSED_CAS)
    )

    canonical_map = (
        df[is_valid_cas]
        .assign(ingredient_lower=df["ingredient_name"].str.lower().str.strip())
        .groupby("cas_hmirc")["ingredient_lower"]
        .agg(lambda x: x.value_counts().index[0] if len(x.value_counts()) > 0 else None)
    )

    # Apply canonical name where CAS is valid
    df["ingredient_name_clean"] = df["cas_hmirc"].map(canonical_map)

    # Fallback: normalize ingredient_name string for undisclosed CAS rows
    needs_fallback = df["ingredient_name_clean"].isna() & df["ingredient_name"].notna()
    df.loc[needs_fallback, "ingredient_name_clean"] = (
        df.loc[needs_fallback, "ingredient_name"]
        .str.lower()
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    cas_deduped  = is_valid_cas.sum()
    fallback     = needs_fallback.sum()
    null_count   = df["ingredient_name_clean"].isna().sum()
    print(f"  CAS-deduped: {cas_deduped:,} rows, fallback normalized: {fallback:,} rows, null: {null_count:,} rows")

    return df



# ══════════════════════════════════════════════════════════════════════════
# Step 8 — Infer carrier fluid supplier
# ══════════════════════════════════════════════════════════════════════════

def infer_carrier_fluid_supplier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Carrier fluid rows (water, CO2, etc.) have no supplier name in the AER
    disclosure — operators only report suppliers for additives and proppants.

    This step infers the likely supplier for carrier fluid rows only, using
    the most common supplier on the same well from non-carrier-fluid rows.

    Two new columns are added:
        carrier_fluid_supplier_inferred  — the inferred supplier name
        carrier_fluid_supplier_confidence — HIGH (1 supplier on well) or
                                            LOW (2+ suppliers, majority used)

    The original component_supplier_name is never modified.
    """
    non_carrier = df[
        (df["component_type"] != "Carrier Fluid")
        & df["component_supplier_name_clean"].notna()
    ]

    # Most frequent supplier per well
    supplier_per_well = (
        non_carrier.groupby("well_licence_number")["component_supplier_name_clean"]
        .agg(lambda x: x.value_counts().index[0] if len(x.value_counts()) > 0 else None)
    )

    # Number of distinct suppliers per well (drives confidence flag)
    supplier_count_per_well = (
        non_carrier.groupby("well_licence_number")["component_supplier_name_clean"]
        .nunique()
    )

    is_carrier = df["component_type"] == "Carrier Fluid"

    df["carrier_fluid_supplier_inferred"] = None
    df["carrier_fluid_supplier_confidence"] = None

    df.loc[is_carrier, "carrier_fluid_supplier_inferred"] = (
        df.loc[is_carrier, "well_licence_number"].map(supplier_per_well)
    )

    distinct = df.loc[is_carrier, "well_licence_number"].map(supplier_count_per_well)
    df.loc[is_carrier & (distinct == 1), "carrier_fluid_supplier_confidence"] = "HIGH"
    df.loc[is_carrier & (distinct > 1),  "carrier_fluid_supplier_confidence"] = "LOW"

    inferred    = is_carrier & df["carrier_fluid_supplier_inferred"].notna()
    not_inferred = is_carrier & df["carrier_fluid_supplier_inferred"].isna()
    high = (df["carrier_fluid_supplier_confidence"] == "HIGH").sum()
    low  = (df["carrier_fluid_supplier_confidence"] == "LOW").sum()

    print(f"  Carrier fluid rows: {is_carrier.sum():,} total, "
          f"{inferred.sum():,} inferred ({high:,} HIGH, {low:,} LOW confidence), "
          f"{not_inferred.sum():,} null (no suppliers on well)")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 9 — Save
# ══════════════════════════════════════════════════════════════════════════

def save(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Saved:   {output_path}")


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════

def ingest(input_path: Path, supplier_map_path: Path, output_path: Path) -> pd.DataFrame:
    start = time.time()

    print(f"\n{'='*56}")
    print(f"  Alberta Frac Hub — Ingest & Clean")
    print(f"  Input:   {input_path.name}")
    print(f"{'='*56}\n")

    print("  Step 1 — Loading raw file...")
    df = load_raw(input_path)

    print("\n  Step 2 — Standardizing column names...")
    df = standardize_columns(df)

    print("\n  Step 3 — Parsing dates...")
    df = parse_dates(df)

    print("\n  Step 4 — Cleaning string fields...")
    df = clean_strings(df)

    print("\n  Step 5 — Canonicalizing supplier names...")
    df = canonicalize_suppliers(df, supplier_map_path)

    print("\n  Step 6 — Flagging data quality issues...")
    df = flag_data_quality(df)

    print("\n  Step 7 — Deduplicating ingredient names...")
    df = deduplicate_ingredients(df)

    print("\n  Step 8 - Inferring carrier fluid suppliers...")
    df = infer_carrier_fluid_supplier(df)

    print("\n  Step 9 - Saving...")
    save(df, output_path)

    elapsed = time.time() - start
    print(f"\n{'='*56}")
    print(f"  Done in {elapsed:.1f}s — {len(df):,} rows, {len(df.columns)} columns")
    print(f"{'='*56}\n")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest and clean raw AER frac data.")
    parser.add_argument(
        "--input", type=str,
        default="SummaryChemical-WaterUse.csv",
        help="Raw input filename (in data/raw/)",
    )
    parser.add_argument(
        "--output", type=str,
        default="Hydraulic_Fracturing_Clean.csv",
        help="Output filename (in data/processed/)",
    )
    args = parser.parse_args()

    ingest(
        input_path        = DATA_RAW / args.input,
        supplier_map_path = CONFIG / "supplier_name_map.csv",
        output_path       = DATA_PROCESSED / args.output,
    )
