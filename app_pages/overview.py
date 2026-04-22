"""
pages/overview.py — Overview (landing) page.

Four KPI tiles across the top, then four charts in a 2x2 grid:
    - Frac activity by year (vertical bar)
    - Top 10 operators by well count (horizontal bar)
    - Additive purpose breakdown (donut)
    - Top field centres by well count (horizontal bar)
"""

import streamlit as st

from lib.charts import donut, horizontal_bar, vertical_bar
from lib.components import metric_card, section_divider
from lib.filters import FilterState, apply_filters
from lib.theme import COLORS


def render(fact, dim_well, dim_ingredient, state: FilterState):
    wells_f, fact_f = apply_filters(dim_well, fact, state)

    st.title("Overview")
    st.markdown(
        f"Showing **{len(wells_f):,} wells** · "
        f"**{len(fact_f):,} ingredient disclosures** · "
        f"{state.year_min}–{state.year_max}"
    )
    section_divider()

    # ── KPIs ──────────────────────────────────────────────────────────
    total_volume = fact_f["normalized_pumped_amount"].sum()
    unique_ops = wells_f["licensee_clean"].nunique()
    unique_chems = fact_f["cas_hmirc"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card(f"{len(wells_f):,}", "Wells"), unsafe_allow_html=True)
    c2.markdown(
        metric_card(f"{total_volume / 1e6:,.1f}M", "Total pumped volume (mixed units)"),
        unsafe_allow_html=True,
    )
    c3.markdown(metric_card(f"{unique_ops:,}", "Operators"), unsafe_allow_html=True)
    c4.markdown(metric_card(f"{unique_chems:,}", "Unique chemicals"), unsafe_allow_html=True)

    section_divider()

    # ── Row 1: activity + top operators ───────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Frac activity by year")
        activity = (
            wells_f.groupby("start_year")["well_licence_number"]
            .nunique()
            .reset_index()
            .rename(columns={"well_licence_number": "wells", "start_year": "year"})
        )
        fig = vertical_bar(activity, x="year", y="wells", color="#c45e2a")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 10 operators by well count")
        top_ops = (
            wells_f.groupby("licensee_clean")["well_licence_number"]
            .nunique()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
            .rename(columns={"well_licence_number": "wells", "licensee_clean": "operator"})
        )
        fig = horizontal_bar(top_ops, x="wells", y="operator", color=COLORS[2], height=300)
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Row 2: purpose donut + field centres ──────────────────────────
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Additive purpose breakdown")
        purpose_vol = (
            fact_f[fact_f["additive_purpose"].notna()]
            .groupby("additive_purpose")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        fig = donut(purpose_vol, values="normalized_pumped_amount", names="additive_purpose", height=320)
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Top field centres by well count")
        centre_counts = (
            wells_f.groupby("field_centre")["well_licence_number"]
            .nunique()
            .sort_values(ascending=True)
            .reset_index()
            .rename(columns={"well_licence_number": "wells", "field_centre": "centre"})
        )
        fig = horizontal_bar(
            centre_counts, x="wells", y="centre",
            color=COLORS[1], height=320, left_margin=160,
        )
        st.plotly_chart(fig, use_container_width=True)
