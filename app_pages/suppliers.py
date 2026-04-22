"""
pages/suppliers.py — Suppliers page.

Market share by supplier (bar + share donut), product breakdown,
and supplier activity over time. Responds to every sidebar filter
including the Supplier multi-select so users can focus on one or
a handful of suppliers at a time.
"""

import pandas as pd
import streamlit as st

from lib.charts import donut, horizontal_bar, line_over_time
from lib.components import metric_card, section_divider
from lib.filters import FilterState, apply_filters
from lib.theme import COLORS


def render(fact, dim_well, dim_ingredient, state: FilterState):
    wells_f, fact_f = apply_filters(dim_well, fact, state)

    st.title("Suppliers")
    st.markdown(
        f"Showing **{len(wells_f):,} wells** · "
        f"**{fact_f['component_supplier_name_clean'].nunique():,} suppliers** · "
        f"{state.year_min}–{state.year_max}"
    )
    section_divider()

    # ── KPIs ──────────────────────────────────────────────────────────
    top_supplier = (
        fact_f.groupby("component_supplier_name_clean")["normalized_pumped_amount"]
        .sum()
        .idxmax()
        if not fact_f.empty
        else "—"
    )
    unique_products = fact_f["component_trade_name"].nunique()

    k1, k2, k3 = st.columns(3)
    k1.markdown(
        metric_card(
            f"{fact_f['component_supplier_name_clean'].nunique():,}", "Suppliers"
        ),
        unsafe_allow_html=True,
    )
    k2.markdown(metric_card(f"{unique_products:,}", "Unique products"), unsafe_allow_html=True)
    k3.markdown(
        metric_card(str(top_supplier).title()[:28], "Top supplier by volume"),
        unsafe_allow_html=True,
    )

    section_divider()

    # ── Market share ──────────────────────────────────────────────────
    supplier_vol = (
        fact_f[fact_f["component_supplier_name_clean"].notna()]
        .groupby("component_supplier_name_clean")["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={
            "component_supplier_name_clean": "supplier",
            "normalized_pumped_amount": "volume",
        })
        .sort_values("volume", ascending=False)
    )
    total = supplier_vol["volume"].sum()
    supplier_vol["share_pct"] = (supplier_vol["volume"] / total * 100).round(1)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Market share by pumped volume")
        top15 = supplier_vol.head(15).sort_values("volume", ascending=True)
        fig = horizontal_bar(
            top15, x="volume", y="supplier",
            color=COLORS[0], height=440, left_margin=220, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 10 suppliers — volume share")
        top10 = supplier_vol.head(10).copy()
        others_vol = supplier_vol.iloc[10:]["volume"].sum()
        if others_vol > 0:
            others_row = pd.DataFrame([{
                "supplier": "All others",
                "volume": others_vol,
                "share_pct": others_vol / total * 100,
            }])
            top10 = pd.concat([top10, others_row], ignore_index=True)
        fig = donut(
            top10, values="volume", names="supplier",
            height=440, legend_font=9, tight_margin=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Product breakdown ─────────────────────────────────────────────
    st.subheader("Product breakdown")
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("**Top products by pumped volume**")
        top_products = (
            fact_f[fact_f["component_trade_name"].notna()]
            .groupby("component_trade_name")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(12)
            .reset_index()
            .rename(columns={"component_trade_name": "product"})
        )
        fig = horizontal_bar(
            top_products, x="normalized_pumped_amount", y="product",
            color=COLORS[2], height=400, left_margin=200, x_title="Pumped volume",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.markdown("**Additive purposes**")
        purpose_vol = (
            fact_f[fact_f["additive_purpose"].notna()]
            .groupby("additive_purpose")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        fig = donut(
            purpose_vol, values="normalized_pumped_amount", names="additive_purpose",
            height=400, legend_font=9, tight_margin=True,
        )
        st.plotly_chart(fig, use_container_width=True)

    section_divider()

    # ── Activity over time ────────────────────────────────────────────
    st.markdown("**Supplier activity over time**")
    supplier_yearly = (
        wells_f.groupby("start_year")["well_licence_number"]
        .nunique()
        .reset_index()
        .rename(columns={"well_licence_number": "wells", "start_year": "year"})
    )
    fig = line_over_time(
        supplier_yearly, x="year", y="wells",
        single_color=COLORS[0], y_title="Wells",
    )
    st.plotly_chart(fig, use_container_width=True)
