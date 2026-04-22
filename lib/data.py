"""
lib/data.py — data loading for the Alberta Frac Hub app.

Reads the star schema CSVs from outputs/powerbi/ and returns them as
pandas DataFrames with the right dtypes. Results are cached for the
session via @st.cache_data so subsequent page loads are instant.

Path is resolved relative to this file's parent-parent (the repo root)
so it works identically on local dev and Streamlit Cloud.
"""

from pathlib import Path

import pandas as pd
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parent.parent
POWERBI_DIR = REPO_ROOT / "outputs" / "powerbi"


@st.cache_data(show_spinner="Loading AER frac data…")
def load_data():
    """
    Load all five star schema tables.

    Returns
    -------
    tuple of DataFrames: (fact, dim_well, dim_ingredient, dim_supplier, dim_purpose)
    """
    # fact_ingredients — try compressed first, fall back to raw CSV
    fact_path = POWERBI_DIR / "fact_ingredients.csv.gz"
    if not fact_path.exists():
        fact_path = POWERBI_DIR / "fact_ingredients.csv"
    fact = pd.read_csv(
        fact_path,
        dtype={"well_licence_number": str, "cas_hmirc": str},
        low_memory=False,
    )
    fact["well_licence_number"] = fact["well_licence_number"].astype(str).str.strip()

    # dim_well
    dim_well = pd.read_csv(
        POWERBI_DIR / "dim_well.csv",
        dtype={"well_licence_number": str},
        low_memory=False,
    )
    dim_well["well_licence_number"] = dim_well["well_licence_number"].astype(str).str.strip()
    dim_well["start_year"] = pd.to_numeric(dim_well["start_year"], errors="coerce")

    # dim_ingredient
    dim_ingredient = pd.read_csv(
        POWERBI_DIR / "dim_ingredient.csv",
        dtype={"cas_hmirc": str},
        low_memory=False,
    )

    # dim_supplier and dim_purpose — small reference tables
    dim_supplier = pd.read_csv(POWERBI_DIR / "dim_supplier.csv")
    dim_purpose = pd.read_csv(POWERBI_DIR / "dim_additive_purpose.csv")

    return fact, dim_well, dim_ingredient, dim_supplier, dim_purpose
