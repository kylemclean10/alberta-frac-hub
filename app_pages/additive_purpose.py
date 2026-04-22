"""
pages/additive_purpose.py — Additive Purpose page.

Volume/share by purpose, trends over time for the top 6 purposes,
and a drilldown to top chemicals and top suppliers for a chosen
purpose. The in-page selectbox is intentional — it lets users
explore purpose-level detail without burning a sidebar filter slot.
"""

import streamlit as st

from lib.charts import donut, horizontal_bar, line_over_time
from lib.components import metric_card, section_divider
from lib.filters import FilterState, apply_filters
from lib.theme import COLORS


def render(fact, dim_well, dim_ingredient, state: FilterState):
    wells_f, fact_f = apply_filters(dim_well, fact, state)

    st.title("Additive Purpose")
    st.markdown(
        f"Showing **{len(wells_f):,} wells** · "
        f"**{fact_f['additive_purpose'].nunique():,} purposes** · "
        f"{state.year_min}–{state.year_max}"
    )
    section_divider()

    # Additive rows only — carrier fluid/proppant have no purpose label.
    additive_fact = fact_f[fact_f["additive_purpose"].notna()]

    # ── KPIs ──────────────────────────────────────────────────────────
    total_additive_vol = additive_fact["normalized_pumped_amount"].sum()
    if not additive_fact.empty:
        purpose_totals = additive_fact.groupby("additive_purpose")["normalized_pumped_amount"].sum()
        top_purpose = purpose_totals.idxmax()
        top_purpose_pct = (purpose_totals.max() / total_additive_vol * 100) if total_additive_vol > 0 else 0
    else:
        top_purpose, top_purpose_pct = "—", 0

    k1, k2, k3 = st.columns(3)
    k1.markdown(
        metric_card(f"{additive_fact['additive_purpose'].nunique():,}", "Additive purposes"),
        unsafe_allow_html=True,
    )
    k2.markdown(metric_card(str(top_purpose), "Largest purpose by volume"), unsafe_allow_html=True)
    k3.markdown(metric_card(f"{top_purpose_pct:.1f}%", "Top purpose share"), unsafe_allow_html=True)

    section_divider()

    # ── Volume + share ────────────────────────────────────────────────
    purpose_vol = (
        additive_fact.groupby("additive_purpose")["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={"additive_purpose": "purpose", "normalized_pumped_amount": "volume"})
        .sort_values("volume", ascending=False)
    )

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Volume by additive purpose")
        fig = horizontal_bar(
            purpose_vol.sort_values("volume", ascending=True),
            x="volume", y="purpose",
            color=COLORS[0], height=420, left_margin=180, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Volume share by purpose")
        fig = donut(
            purpose_vol, values="volume", names="purpose",
            height=420, legend_font=9, tight_margin=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Trends over time (top 6) ──────────────────────────────────────
    st.subheader("Purpose trends over time")
    top6_purposes = purpose_vol.head(6)["purpose"].tolist()
    trend_fact = additive_fact[additive_fact["additive_purpose"].isin(top6_purposes)]
    trend_fact = trend_fact.merge(
        wells_f[["well_licence_number", "start_year"]],
        on="well_licence_number", how="left",
    )
    trend = (
        trend_fact.groupby(["start_year", "additive_purpose"])["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={
            "additive_purpose": "purpose",
            "normalized_pumped_amount": "volume",
            "start_year": "year",
        })
    )
    fig = line_over_time(
        trend, x="year", y="volume", color="purpose",
        height=320, y_title="Pumped volume",
    )
    st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Top chemicals + suppliers by purpose ──────────────────────────
    st.subheader("Top chemicals by purpose")
    purpose_list = sorted(additive_fact["additive_purpose"].dropna().unique().tolist())
    default_idx = purpose_list.index("Friction Reducer") if "Friction Reducer" in purpose_list else 0
    sel_purpose_detail = st.selectbox("Select a purpose", purpose_list, index=default_idx)

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(f"**Top chemicals in {sel_purpose_detail}**")
        purpose_chems = (
            additive_fact[additive_fact["additive_purpose"] == sel_purpose_detail]
            .merge(
                dim_ingredient[["cas_hmirc", "ingredient_name_display"]],
                on="cas_hmirc", how="left",
            )
            .groupby("ingredient_name_display")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(12)
            .reset_index()
        )
        fig = horizontal_bar(
            purpose_chems, x="normalized_pumped_amount", y="ingredient_name_display",
            color=COLORS[3], height=380, left_margin=220, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.markdown(f"**Top suppliers for {sel_purpose_detail}**")
        purpose_suppliers = (
            additive_fact[additive_fact["additive_purpose"] == sel_purpose_detail]
            .groupby("component_supplier_name_clean")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
            .rename(columns={"component_supplier_name_clean": "supplier"})
        )
        fig = horizontal_bar(
            purpose_suppliers, x="normalized_pumped_amount", y="supplier",
            color=COLORS[1], height=380, left_margin=220, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)
