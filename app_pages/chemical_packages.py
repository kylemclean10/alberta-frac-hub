"""
pages/chemical_packages.py — Chemical Packages page.

Requires a single formation to be selected in the sidebar so the
recipe cards are directly comparable. Shows up to 10 cards per tab
(By Supplier / By Operator), each card listing every product grouped
by additive purpose with average pumped units per well, plus TVD
stats pulled from dim_well.
"""

import streamlit as st

from lib.components import (
    build_packages,
    render_package_grid,
    section_divider,
)
from lib.filters import FilterState, apply_filters
from lib.theme import inject_package_card_css


def render(fact, dim_well, dim_ingredient, state: FilterState):
    st.title("Chemical Packages")
    st.markdown(
        "Compare chemical recipes across suppliers and operators for a specific formation."
    )
    section_divider()

    # ── Gate: require exactly one formation ───────────────────────────
    if not state.formations or len(state.formations) != 1:
        st.info("Select a single formation in the sidebar to compare chemical packages.")
        st.markdown(
            '<div style="color:#555;font-size:0.875rem;padding:0.5rem 0">'
            "Use the Formation filter on the left — type to search. This page works best "
            "with one formation selected so packages are directly comparable.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    formation = state.formations[0]
    st.markdown(
        f"Showing top 10 by well count · **{formation}** · "
        f"{state.year_min}–{state.year_max}"
    )
    section_divider()

    # ── Build the package fact table ──────────────────────────────────
    # ignore_purposes=True so cards show the full recipe regardless of
    # what the user has selected in the Additive Purpose sidebar filter.
    wells_f, pkg_fact_base = apply_filters(dim_well, fact, state, ignore_purposes=True)
    pkg_fact = pkg_fact_base[pkg_fact_base["additive_purpose"].notna()].copy()
    pkg_fact = pkg_fact.merge(
        dim_ingredient[["cas_hmirc", "ingredient_name_display"]],
        on="cas_hmirc", how="left",
    )

    # Bring licensee_clean in from dim_well so we can group on it.
    pkg_fact = pkg_fact.merge(
        dim_well[["well_licence_number", "licensee_clean"]],
        on="well_licence_number", how="left",
    )

    # ── Card CSS + tabs ───────────────────────────────────────────────
    inject_package_card_css()

    tab1, tab2 = st.tabs(["By Supplier", "By Operator"])

    with tab1:
        packages = build_packages(
            pkg_fact, wells_f,
            group_col="component_supplier_name_clean",
        )
        render_package_grid(packages)

    with tab2:
        op_packages = build_packages(
            pkg_fact, wells_f,
            group_col="licensee_clean",
        )
        render_package_grid(op_packages)
