"""
pages/formations.py — Formations page.

Top 15 formations by well count and by pumped volume, a chemical
breakdown, and activity over time. Honours the sidebar formation
filter — if one or more formations are selected the whole page
narrows to that slice.
"""

import streamlit as st

from lib.charts import donut, horizontal_bar, line_over_time
from lib.components import section_divider
from lib.filters import FilterState, apply_filters
from lib.theme import COLORS


def render(fact, dim_well, dim_ingredient, state: FilterState):
    wells_f, fact_f = apply_filters(dim_well, fact, state)

    st.title("Formations")
    st.markdown(f"Showing **{len(wells_f):,} wells** · {state.year_min}–{state.year_max}")
    section_divider()

    # Coverage note — geological_pool_name is ~21% null because the AER
    # pool registry hasn't assigned names to every field.
    null_pct = wells_f["geological_pool_name"].isna().mean() * 100
    if null_pct > 0:
        st.info(
            f"{null_pct:.0f}% of filtered wells have no formation data — "
            "these are excluded from formation charts. See methodology for details."
        )

    wells_with_formation = wells_f[wells_f["geological_pool_name"].notna()]
    fact_with_formation = fact_f[
        fact_f["well_licence_number"].isin(wells_with_formation["well_licence_number"])
    ]

    # ── Top 15 by count / volume ──────────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top formations by well count")
        top_formations = (
            wells_with_formation.groupby("geological_pool_name")["well_licence_number"]
            .nunique()
            .sort_values(ascending=True)
            .tail(15)
            .reset_index()
            .rename(columns={"well_licence_number": "wells", "geological_pool_name": "formation"})
        )
        fig = horizontal_bar(
            top_formations, x="wells", y="formation",
            color=COLORS[0], height=420, left_margin=220,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top formations by pumped volume")
        form_fact = fact_with_formation.merge(
            wells_f[["well_licence_number", "geological_pool_name"]],
            on="well_licence_number", how="left",
        )
        top_vol = (
            form_fact[form_fact["geological_pool_name"].notna()]
            .groupby("geological_pool_name")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(15)
            .reset_index()
            .rename(columns={"geological_pool_name": "formation"})
        )
        fig = horizontal_bar(
            top_vol, x="normalized_pumped_amount", y="formation",
            color=COLORS[2], height=420, left_margin=220,
            x_title="Normalized pumped amount",
        )
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Chemical breakdown for the filtered formation(s) ──────────────
    st.subheader("Chemical breakdown")
    col5, col6 = st.columns(2)

    with col5:
        st.markdown("**Top chemicals**")
        top_chems = (
            fact_with_formation[fact_with_formation["additive_purpose"].notna()]
            .merge(
                dim_ingredient[["cas_hmirc", "ingredient_name_display"]],
                on="cas_hmirc", how="left",
            )
            .groupby("ingredient_name_display")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
        )
        fig = horizontal_bar(
            top_chems, x="normalized_pumped_amount", y="ingredient_name_display",
            color=COLORS[3], height=340, left_margin=200, x_title="Pumped amount",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col6:
        st.markdown("**Additive purposes**")
        purpose_breakdown = (
            fact_with_formation[fact_with_formation["additive_purpose"].notna()]
            .groupby("additive_purpose")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        fig = donut(purpose_breakdown, values="normalized_pumped_amount", names="additive_purpose", height=340)
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Activity over time ────────────────────────────────────────────
    st.markdown("**Activity over time**")
    form_yearly = (
        wells_with_formation.groupby("start_year")["well_licence_number"]
        .nunique()
        .reset_index()
        .rename(columns={"well_licence_number": "wells", "start_year": "year"})
    )
    fig = line_over_time(
        form_yearly, x="year", y="wells",
        single_color=COLORS[0], y_title="Wells",
    )
    st.plotly_chart(fig, use_container_width=True)
