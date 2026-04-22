"""
app.py — Alberta Frac Hub entry point.

This file is deliberately thin. Its job is:
    1. Configure the Streamlit page.
    2. Inject global CSS.
    3. Load the star schema data (cached).
    4. Render the sidebar and capture FilterState.
    5. Dispatch to the selected page module.

All analytics and chart code lives in app_pages/ and lib/.

Run with: streamlit run app.py
"""

import sys
from pathlib import Path

# Ensure the project root is on sys.path so `lib` and `app_pages` import
# correctly regardless of the working directory Streamlit was launched from.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from lib.data import load_data
from lib.filters import render_sidebar
from lib.theme import inject_css

from app_pages import (
    additive_purpose,
    chemical_packages,
    chemicals,
    formations,
    overview,
    suppliers,
)


# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="Alberta Frac Hub",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()


# ── Data & sidebar ─────────────────────────────────────────────────────────
fact, dim_well, dim_ingredient, dim_supplier, dim_purpose = load_data()

PAGES = [
    "Overview",
    "Formations",
    "Suppliers",
    "Additive Purpose",
    "Chemicals",
    "Chemical Packages",
]

selected_page, state = render_sidebar(dim_well, fact, PAGES)


# ── Dispatch ───────────────────────────────────────────────────────────────
if selected_page == "Overview":
    overview.render(fact, dim_well, dim_ingredient, state)
elif selected_page == "Formations":
    formations.render(fact, dim_well, dim_ingredient, state)
elif selected_page == "Suppliers":
    suppliers.render(fact, dim_well, dim_ingredient, state)
elif selected_page == "Additive Purpose":
    additive_purpose.render(fact, dim_well, dim_ingredient, state)
elif selected_page == "Chemicals":
    chemicals.render(fact, dim_well, dim_ingredient, state)
elif selected_page == "Chemical Packages":
    chemical_packages.render(fact, dim_well, dim_ingredient, state)
