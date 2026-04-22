"""
lib/filters.py — sidebar filter rendering and filter application.

The sidebar has one job: capture the user's filter intent and expose it
via a single FilterState object. Each page then calls apply_filters()
with that state to get (filtered_wells_df, filtered_fact_df) back.

Cascading logic: selecting an operator narrows the field centres list;
selecting a field centre narrows formations; selecting a formation
narrows suppliers; selecting a supplier narrows additive purposes.
The year range is independent and always applied last.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

import pandas as pd
import streamlit as st


@dataclass
class FilterState:
    """Captures everything the user has selected in the sidebar."""
    year_min: int
    year_max: int
    operators: List[str] = field(default_factory=list)
    centres: List[str] = field(default_factory=list)
    formations: List[str] = field(default_factory=list)
    suppliers: List[str] = field(default_factory=list)
    purposes: List[str] = field(default_factory=list)


def render_sidebar(dim_well: pd.DataFrame, fact: pd.DataFrame, pages: list) -> Tuple[str, FilterState]:
    """
    Render the sidebar (title, page picker, cascading filters) and return
    the selected page name plus the current FilterState.

    Parameters
    ----------
    dim_well : DataFrame
        Well dimension — drives operator/centre/formation choices.
    fact : DataFrame
        Fact table — drives supplier/purpose choices once wells are narrowed.
    pages : list of str
        Page names to show in the nav radio.
    """
    with st.sidebar:
        st.markdown(
            '<div class="sidebar-title">Alberta Frac Hub</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="sidebar-subtitle">Public frac data · AER disclosures</div>',
            unsafe_allow_html=True,
        )

        page = st.radio("", pages, label_visibility="collapsed")

        st.markdown("<hr style='border-color:#333;margin:1rem 0'>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.7rem;color:#888;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:0.75rem">Filters</div>',
            unsafe_allow_html=True,
        )

        # ── Year range ─────────────────────────────────────────────────
        years = sorted(dim_well["start_year"].dropna().astype(int).unique())
        year_min, year_max = int(min(years)), int(max(years))
        # Default to 2011+ — pre-2011 disclosures are sparse and skew charts.
        default_start = max(2011, year_min)
        year_range = st.slider(
            "Year range", year_min, year_max, (default_start, year_max)
        )

        # ── Operator (top of cascade) ──────────────────────────────────
        all_operators = sorted(dim_well["licensee_clean"].dropna().unique().tolist())
        sel_operators = st.multiselect(
            "Operator", all_operators, placeholder="All operators"
        )

        avail_wells = (
            dim_well[dim_well["licensee_clean"].isin(sel_operators)]
            if sel_operators
            else dim_well.copy()
        )

        # ── Field centre (cascaded from operator) ──────────────────────
        avail_centres = sorted(avail_wells["field_centre"].dropna().unique().tolist())
        sel_centres = st.multiselect(
            "Field centre", avail_centres, placeholder="All field centres"
        )

        if sel_centres:
            avail_wells = avail_wells[avail_wells["field_centre"].isin(sel_centres)]

        # ── Formation (cascaded from operator + centre) ────────────────
        avail_formations = sorted(
            avail_wells["geological_pool_name"].dropna().unique().tolist()
        )
        sel_formations = st.multiselect(
            "Formation", avail_formations, placeholder="All formations"
        )

        # ── Narrow fact rows to everything selected so far ─────────────
        if sel_formations:
            avail_wells_for_fact = avail_wells[
                avail_wells["geological_pool_name"].isin(sel_formations)
            ]
        else:
            avail_wells_for_fact = avail_wells

        avail_fact = fact[
            fact["well_licence_number"].isin(avail_wells_for_fact["well_licence_number"])
        ]

        # ── Supplier (cascaded) ────────────────────────────────────────
        avail_suppliers = sorted(
            avail_fact["component_supplier_name_clean"].dropna().unique().tolist()
        )
        sel_suppliers = st.multiselect(
            "Supplier", avail_suppliers, placeholder="All suppliers"
        )

        if sel_suppliers:
            avail_fact = avail_fact[
                avail_fact["component_supplier_name_clean"].isin(sel_suppliers)
            ]

        # ── Additive purpose (last in cascade) ─────────────────────────
        avail_purposes = sorted(avail_fact["additive_purpose"].dropna().unique().tolist())
        sel_purposes = st.multiselect(
            "Additive purpose", avail_purposes, placeholder="All purposes"
        )

        st.markdown(
            '<div style="font-size:0.65rem;color:#555;margin-top:0.25rem;'
            'margin-bottom:1rem">Tip: type to search in any filter</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<hr style='border-color:#333;margin:1rem 0'>", unsafe_allow_html=True)
        st.markdown(
            '<div style="font-size:0.65rem;color:#555;line-height:1.5">'
            "Data: AER Hydraulic Fracturing Disclosures<br>Built by Kyle McLean</div>",
            unsafe_allow_html=True,
        )

    state = FilterState(
        year_min=year_range[0],
        year_max=year_range[1],
        operators=sel_operators,
        centres=sel_centres,
        formations=sel_formations,
        suppliers=sel_suppliers,
        purposes=sel_purposes,
    )
    return page, state


def apply_filters(
    dim_well: pd.DataFrame,
    fact: pd.DataFrame,
    state: FilterState,
    ignore_purposes: bool = False,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply a FilterState to the raw tables and return (wells, fact) subsets.

    Parameters
    ----------
    dim_well, fact : DataFrame
        The full star schema tables.
    state : FilterState
        Current sidebar selections.
    ignore_purposes : bool, default False
        If True, skip the additive_purpose filter. The Chemical Packages
        page uses this so it can always show every purpose per card.
    """
    wells = dim_well.copy()
    wells = wells[wells["start_year"].between(state.year_min, state.year_max, inclusive="both")]
    if state.operators:
        wells = wells[wells["licensee_clean"].isin(state.operators)]
    if state.centres:
        wells = wells[wells["field_centre"].isin(state.centres)]
    if state.formations:
        wells = wells[wells["geological_pool_name"].isin(state.formations)]

    filtered_fact = fact[fact["well_licence_number"].isin(wells["well_licence_number"])]
    if state.suppliers:
        filtered_fact = filtered_fact[
            filtered_fact["component_supplier_name_clean"].isin(state.suppliers)
        ]
    if state.purposes and not ignore_purposes:
        filtered_fact = filtered_fact[filtered_fact["additive_purpose"].isin(state.purposes)]

    return wells, filtered_fact
