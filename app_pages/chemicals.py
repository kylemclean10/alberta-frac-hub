"""
pages/chemicals.py — Chemicals page.

Top 15 chemicals by volume, a stacked bar showing which purposes
each top chemical is used for, and a live chemical explorer where
the user types a name or CAS number to see where that chemical
shows up across the dataset.
"""

import streamlit as st

from lib.charts import horizontal_bar, stacked_horizontal_bar
from lib.components import metric_card, section_divider
from lib.filters import FilterState, apply_filters
from lib.theme import COLORS


# CAS values we treat as "unknown" — they're catch-alls that would
# dominate the top-chemical KPI if we didn't exclude them.
_UNKNOWN_CAS = {"Trade Secret", "Not Available", "not available"}


def render(fact, dim_well, dim_ingredient, state: FilterState):
    wells_f, fact_f = apply_filters(dim_well, fact, state)

    st.title("Chemicals")
    st.markdown(
        f"Showing **{len(wells_f):,} wells** · "
        f"**{fact_f['cas_hmirc'].nunique():,} unique chemicals** · "
        f"{state.year_min}–{state.year_max}"
    )
    section_divider()

    # Exclude carrier fluid rows — we only care about additive chemicals here.
    chem_fact = fact_f[fact_f["additive_purpose"].notna()].copy()
    chem_fact = chem_fact.merge(
        dim_ingredient[["cas_hmirc", "ingredient_name_display", "ingredient_name_clean"]],
        on="cas_hmirc", how="left",
    )

    # ── KPIs ──────────────────────────────────────────────────────────
    k1, k2, k3 = st.columns(3)
    k1.markdown(
        metric_card(f"{chem_fact['cas_hmirc'].nunique():,}", "Unique chemicals (CAS)"),
        unsafe_allow_html=True,
    )
    trade_secret_wells = chem_fact[chem_fact["cas_hmirc"] == "Trade Secret"]["well_licence_number"].nunique()
    k2.markdown(
        metric_card(f"{trade_secret_wells:,}", "Wells with trade secret chemicals"),
        unsafe_allow_html=True,
    )
    valid_chems = chem_fact[~chem_fact["cas_hmirc"].isin(_UNKNOWN_CAS)]
    top_chem = (
        valid_chems.groupby("ingredient_name_display")["normalized_pumped_amount"].sum().idxmax()
        if not valid_chems.empty
        else "—"
    )
    k3.markdown(metric_card(str(top_chem)[:28], "Top chemical by volume"), unsafe_allow_html=True)

    section_divider()

    # ── Top 15 and stacked-by-purpose ─────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top 15 chemicals by pumped volume")
        top_chems = (
            chem_fact[chem_fact["ingredient_name_display"].notna()]
            .groupby("ingredient_name_display")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(15)
            .reset_index()
            .rename(columns={"ingredient_name_display": "chemical"})
        )
        fig = horizontal_bar(
            top_chems, x="normalized_pumped_amount", y="chemical",
            color=COLORS[0], height=460, left_margin=240, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Chemical use by additive purpose")
        top8_chems = (
            chem_fact[chem_fact["ingredient_name_display"].notna()]
            .groupby("ingredient_name_display")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .index.tolist()
        )
        chem_purpose = (
            chem_fact[
                chem_fact["ingredient_name_display"].isin(top8_chems)
                & chem_fact["additive_purpose"].notna()
            ]
            .groupby(["ingredient_name_display", "additive_purpose"])["normalized_pumped_amount"]
            .sum()
            .reset_index()
            .rename(columns={
                "ingredient_name_display": "chemical",
                "normalized_pumped_amount": "volume",
            })
        )
        fig = stacked_horizontal_bar(
            chem_purpose, x="volume", y="chemical", color="additive_purpose",
            height=460, left_margin=240, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Chemical explorer (search) ────────────────────────────────────
    st.subheader("Chemical explorer")
    st.markdown(
        "Search by ingredient name or CAS number to see where and how a chemical is used."
    )

    search_col, _ = st.columns([2, 1])
    with search_col:
        search_term = st.text_input(
            "", placeholder="e.g. methanol, polyacrylamide, 67-56-1",
            label_visibility="collapsed",
        )

    if not search_term:
        st.markdown(
            '<div style="color:#555;font-size:0.875rem;padding:1rem 0">'
            "Enter a chemical name or CAS number above to explore its use across the dataset.</div>",
            unsafe_allow_html=True,
        )
        return

    mask = (
        chem_fact["ingredient_name_clean"].str.contains(search_term.lower(), na=False)
        | chem_fact["cas_hmirc"].str.contains(search_term, na=False)
    )
    search_results = chem_fact[mask]

    if search_results.empty:
        st.info(f"No results found for '{search_term}'")
        return

    cas_found = search_results["cas_hmirc"].iloc[0]
    name_found = search_results["ingredient_name_display"].iloc[0]
    total_vol = search_results["normalized_pumped_amount"].sum()
    well_count = search_results["well_licence_number"].nunique()

    st.markdown("<br>", unsafe_allow_html=True)
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(metric_card(str(name_found)[:24], "Canonical name"), unsafe_allow_html=True)
    r2.markdown(metric_card(str(cas_found), "CAS / HMIRC"), unsafe_allow_html=True)
    r3.markdown(metric_card(f"{well_count:,}", "Wells"), unsafe_allow_html=True)
    vol_fmt = f"{total_vol / 1e6:.1f}M" if total_vol >= 1e6 else f"{total_vol / 1e3:.1f}K"
    r4.markdown(metric_card(vol_fmt, "Total pumped"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    e1, e2 = st.columns(2)

    with e1:
        st.markdown("**Used by purpose**")
        by_purpose = (
            search_results.groupby("additive_purpose")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .reset_index()
        )
        fig = horizontal_bar(
            by_purpose, x="normalized_pumped_amount", y="additive_purpose",
            color=COLORS[2], height=260, left_margin=160, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with e2:
        st.markdown("**Top suppliers using this chemical**")
        by_supplier = (
            search_results.groupby("component_supplier_name_clean")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(8)
            .reset_index()
            .rename(columns={"component_supplier_name_clean": "supplier"})
        )
        fig = horizontal_bar(
            by_supplier, x="normalized_pumped_amount", y="supplier",
            color=COLORS[1], height=260, left_margin=200, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)
