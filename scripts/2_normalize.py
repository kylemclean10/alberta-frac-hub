"""
scripts/2_normalize.py

Calculates pumped amounts and normalized concentrations for each ingredient
in the cleaned AER hydraulic fracturing dataset.

Normalization is performed within tight groups:
    [well_licence_number, start_date, component_trade_name, component_quantity_uom]

This ensures concentrations are normalized within each distinct product/unit
combination per well, making values comparable across wells and operators.

Usage:
    python scripts/2_normalize.py
    python scripts/2_normalize.py --input Hydraulic_Fracturing_Clean.csv
    python scripts/2_normalize.py --input Hydraulic_Fracturing_Clean.csv --output my_output.csv

Output:
    data/processed/Hydraulic_Fracturing_Normalized.csv
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from utils.paths import DATA_PROCESSED
from utils.schema import AER_NULL_VALUES


# ══════════════════════════════════════════════════════════════════════════
# Step 1 — Load
# ══════════════════════════════════════════════════════════════════════════

def load_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype={"well_licence_number": str},
        na_values=AER_NULL_VALUES,
        keep_default_na=True,
        low_memory=False,
    )
    print(f"  Loaded:  {len(df):,} rows, {len(df.columns)} columns")
    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 2 — Cast numeric columns
# ══════════════════════════════════════════════════════════════════════════

def cast_numerics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure concentration and volume columns are numeric.
    Non-numeric values (including AER sentinel strings) become NaN.
    """
    numeric_cols = [
        "concentration_component",
        "concentration_hff",
        "total_component_volume_weight",
    ]
    for col in numeric_cols:
        if col in df.columns:
            before = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            after  = df[col].isna().sum()
            new_nulls = after - before
            if new_nulls > 0:
                print(f"  {col}: {new_nulls:,} non-numeric values coerced to NaN")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 3 — Calculate pumped amount
# ══════════════════════════════════════════════════════════════════════════

def calculate_pumped_amount(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate the absolute quantity of each ingredient pumped per component.

    pumped_amount = total_component_volume_weight x (concentration_component / 100)

    Unit matches total_component_volume_weight (Litres, kg, Metric Tonnes, m3, etc.)
    """
    df["pumped_amount"] = (
        df["total_component_volume_weight"] * (df["concentration_component"] / 100)
    ).round(6)

    null_count = df["pumped_amount"].isna().sum()
    print(f"  pumped_amount: {len(df) - null_count:,} calculated, {null_count:,} null")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 4 — Normalize concentration per group
# ══════════════════════════════════════════════════════════════════════════

def normalize_concentration(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize concentration_component within each tight group:
        [well_licence_number, start_date, component_trade_name, component_quantity_uom]

    Within each group, concentration values are rescaled to sum to 100%.
    This makes concentrations comparable across wells and operators regardless
    of how the operator originally reported their values.

    Groups where the sum of concentration_component is 0 or NaN are set to 0
    rather than producing divide-by-zero errors.
    """
    group_cols = [
        "well_licence_number",
        "start_date",
        "component_trade_name",
        "component_quantity_uom",
    ]

    group_sums = df.groupby(group_cols, dropna=False)["concentration_component"].transform("sum")
    df["normalized_concentration"] = (
        df["concentration_component"] / group_sums * 100
    ).where(group_sums > 0, 0.0).round(6)

    zero_count = (df["normalized_concentration"] == 0).sum()
    if zero_count > 0:
        print(f"  normalized_concentration: {zero_count:,} rows set to 0 "
              f"(group sum was 0 or NaN)")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 5 — Calculate normalized pumped amount
# ══════════════════════════════════════════════════════════════════════════

def calculate_normalized_pumped_amount(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate pumped amount using the normalized concentration.
    Comparable across all wells and operators.

    normalized_pumped_amount = (normalized_concentration / 100) x total_component_volume_weight
    """
    df["normalized_pumped_amount"] = (
        (df["normalized_concentration"] / 100) * df["total_component_volume_weight"]
    ).round(6)

    null_count = df["normalized_pumped_amount"].isna().sum()
    print(f"  normalized_pumped_amount: {len(df) - null_count:,} calculated, "
          f"{null_count:,} null")

    return df


# ══════════════════════════════════════════════════════════════════════════
# Step 6 — Save
# ══════════════════════════════════════════════════════════════════════════

def save(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"  Saved:   {output_path}")


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════

def normalize(input_path: Path, output_path: Path) -> pd.DataFrame:
    start = time.time()

    print(f"\n{'='*56}")
    print(f"  Alberta Frac Hub — Normalize")
    print(f"  Input:   {input_path.name}")
    print(f"{'='*56}\n")

    print("  Step 1 — Loading clean file...")
    df = load_clean(input_path)

    print("\n  Step 2 — Casting numeric columns...")
    df = cast_numerics(df)

    print("\n  Step 3 — Calculating pumped amount...")
    df = calculate_pumped_amount(df)

    print("\n  Step 4 — Normalizing concentration per group...")
    df = normalize_concentration(df)

    print("\n  Step 5 — Calculating normalized pumped amount...")
    df = calculate_normalized_pumped_amount(df)

    print("\n  Step 6 — Saving...")
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
    parser = argparse.ArgumentParser(description="Normalize AER frac data.")
    parser.add_argument(
        "--input", type=str,
        default="Hydraulic_Fracturing_Clean.csv",
        help="Cleaned input filename (in data/processed/)",
    )
    parser.add_argument(
        "--output", type=str,
        default="Hydraulic_Fracturing_Normalized.csv",
        help="Output filename (in data/processed/)",
    )
    args = parser.parse_args()

    normalize(
        input_path  = DATA_PROCESSED / args.input,
        output_path = DATA_PROCESSED / args.output,
    )
