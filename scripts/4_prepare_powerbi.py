"""
scripts/4_prepare_powerbi.py

Produces a star schema from the enriched dataset ready for Power BI.
Each output is a flat CSV — no transformations needed inside Power BI.

Output files (in outputs/powerbi/):
    fact_ingredients.csv    — one row per ingredient per frac job
    dim_well.csv            — one row per well
    dim_ingredient.csv      — one row per unique CAS number
    dim_supplier.csv        — one row per canonical supplier
    dim_additive_purpose.csv — one row per additive purpose

The same schema is used for Snowflake in Phase 3.
Point Power BI at these CSVs now, then swap the connector to Snowflake later
without changing the data model.

Usage:
    python scripts/4_prepare_powerbi.py
    python scripts/4_prepare_powerbi.py --input Hydraulic_Fracturing_Enriched.csv
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from utils.paths import DATA_PROCESSED, OUTPUTS


POWERBI_DIR = OUTPUTS / "powerbi"


# ══════════════════════════════════════════════════════════════════════════
# Load
# ══════════════════════════════════════════════════════════════════════════

def load_enriched(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        dtype={"well_licence_number": str, "cas_hmirc": str},
        low_memory=False,
    )
    print(f"  Loaded:  {len(df):,} rows, {len(df.columns)} columns")
    return df


# ══════════════════════════════════════════════════════════════════════════
# Dimension tables
# ══════════════════════════════════════════════════════════════════════════

def build_dim_well(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per well. All well-level attributes.
    Excludes ingredient/chemical columns — those belong in the fact table.
    """
    well_cols = [
        "well_licence_number",
        "uwi",
        "well_name",
        "licensee",
        "licensee_clean",
        "field_centre",
        "production_fluid_type",
        "number_of_stages",
        "bottom_hole_latitude",
        "bottom_hole_longitude",
        "max_true_vertical_depth",
        "total_water_volume",
        "start_date",
        "end_date",
        "start_year",
        "start_month",
        "field_name",
        "production_pool_name",
        "geological_pool_name",
    ]
    available = [c for c in well_cols if c in df.columns]
    dim = (
        df[available]
        .drop_duplicates(subset="well_licence_number")
        .reset_index(drop=True)
    )
    # Normalize well_licence_number to match fact table format:
    # strip whitespace and leading zeros so '  0002105  ' becomes '2105'
    dim["well_licence_number"] = (
        dim["well_licence_number"]
        .astype(str)
        .str.strip()
        .str.lstrip("0")
    )
    print(f"  dim_well:             {len(dim):,} wells")
    return dim


def build_dim_ingredient(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per unique CAS number.
    Carries the canonical ingredient name for display in Power BI.
    """
    ing_cols = ["cas_hmirc", "ingredient_name_clean", "ingredient_name"]
    available = [c for c in ing_cols if c in df.columns]

    dim = (
        df[available]
        .dropna(subset=["cas_hmirc"])
        .drop_duplicates(subset="cas_hmirc")
        .reset_index(drop=True)
    )

    # Add a display name — title case of the clean name for Power BI labels
    if "ingredient_name_clean" in dim.columns:
        dim["ingredient_name_display"] = dim["ingredient_name_clean"].str.title()

    print(f"  dim_ingredient:       {len(dim):,} unique CAS numbers")
    return dim


def build_dim_supplier(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per canonical supplier name.
    """
    dim = (
        df[["component_supplier_name_clean"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"component_supplier_name_clean": "supplier_name"})
        .sort_values("supplier_name")
        .reset_index(drop=True)
    )
    dim["supplier_id"] = dim.index + 1
    print(f"  dim_supplier:         {len(dim):,} unique suppliers")
    return dim


def build_dim_additive_purpose(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per additive purpose.
    Provides a clean filter for the three priority analyses.
    """
    dim = (
        df[["additive_purpose"]]
        .dropna()
        .drop_duplicates()
        .sort_values("additive_purpose")
        .reset_index(drop=True)
    )
    dim["purpose_id"] = dim.index + 1
    print(f"  dim_additive_purpose: {len(dim):,} unique purposes")
    return dim


# ══════════════════════════════════════════════════════════════════════════
# Fact table
# ══════════════════════════════════════════════════════════════════════════

def build_fact_ingredients(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per ingredient per frac job.
    Contains only measures and foreign keys — all descriptive attributes
    live in the dimension tables.

    Foreign keys:
        well_licence_number  → dim_well
        cas_hmirc            → dim_ingredient
        component_supplier_name_clean → dim_supplier
        additive_purpose     → dim_additive_purpose
    """
    fact_cols = [
        # Foreign keys
        "well_licence_number",
        "cas_hmirc",
        "component_supplier_name_clean",
        "additive_purpose",
        # Component context
        "component_type",
        "component_trade_name",
        "component_quantity_uom",
        "total_component_volume_weight",
        # Carrier fluid supplier (enriched)
        "carrier_fluid_supplier_inferred",
        "carrier_fluid_supplier_confidence",
        # Measures
        "concentration_component",
        "concentration_hff",
        "normalized_concentration",
        "pumped_amount",
        "normalized_pumped_amount",
        # Flags
        "supplier_flag",
    ]
    available = [c for c in fact_cols if c in df.columns]
    fact = df[available].reset_index(drop=True)
    print(f"  fact_ingredients:     {len(fact):,} rows, {len(fact.columns)} columns")
    return fact


# ══════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════

def save_all(tables: dict[str, pd.DataFrame]) -> None:
    POWERBI_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        path = POWERBI_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        size_kb = path.stat().st_size // 1024
        print(f"  Saved {name}.csv — {len(df):,} rows, {size_kb:,} KB")


# ══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ══════════════════════════════════════════════════════════════════════════

def prepare(input_path: Path) -> None:
    start = time.time()

    print(f"\n{'='*56}")
    print(f"  Alberta Frac Hub - Prepare Power BI")
    print(f"  Input:   {input_path.name}")
    print(f"{'='*56}\n")

    print("  Loading enriched dataset...")
    df = load_enriched(input_path)

    print("\n  Building dimension tables...")
    dim_well             = build_dim_well(df)
    dim_ingredient       = build_dim_ingredient(df)
    dim_supplier         = build_dim_supplier(df)
    dim_additive_purpose = build_dim_additive_purpose(df)

    print("\n  Building fact table...")
    fact_ingredients = build_fact_ingredients(df)

    print("\n  Saving to outputs/powerbi/...")
    save_all({
        "fact_ingredients":     fact_ingredients,
        "dim_well":             dim_well,
        "dim_ingredient":       dim_ingredient,
        "dim_supplier":         dim_supplier,
        "dim_additive_purpose": dim_additive_purpose,
    })

    elapsed = time.time() - start
    print(f"\n{'='*56}")
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Output: {POWERBI_DIR}")
    print(f"{'='*56}\n")


# ══════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare Power BI star schema tables.")
    parser.add_argument(
        "--input", type=str,
        default="Hydraulic_Fracturing_Enriched.csv",
        help="Enriched input filename (in data/processed/)",
    )
    args = parser.parse_args()

    prepare(input_path=DATA_PROCESSED / args.input)
