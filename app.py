"""
app.py — Alberta Frac Hub web application
Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Alberta Frac Hub",
    page_icon="⛽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .main { background-color: #f8f7f4; }
    .block-container { padding: 2rem 2.5rem; }

    h1 { font-size: 1.8rem; font-weight: 600; color: #1a1a1a; letter-spacing: -0.02em; }
    h2 { font-size: 1.2rem; font-weight: 500; color: #1a1a1a; letter-spacing: -0.01em; }
    h3 { font-size: 1rem; font-weight: 500; color: #444; }

    .metric-card {
        background: #242424;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #e8e6e1;
        letter-spacing: -0.03em;
        line-height: 1;
    }
    .metric-label {
        font-size: 0.75rem;
        font-weight: 500;
        color: #666;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-top: 0.35rem;
    }
    .section-divider {
        border: none;
        border-top: 1px solid #e8e6e1;
        margin: 1.5rem 0;
    }
    .stSelectbox label, .stMultiSelect label, .stSlider label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: #888 !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #1a1a1a;
    }
    section[data-testid="stSidebar"] * {
        color: #e8e6e1 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stMultiSelect label,
    section[data-testid="stSidebar"] .stSlider label {
        color: #888 !important;
    }
    .sidebar-title {
        font-size: 1rem;
        font-weight: 600;
        color: white !important;
        letter-spacing: -0.01em;
        margin-bottom: 0.25rem;
    }
    .sidebar-subtitle {
        font-size: 0.7rem;
        color: #888 !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 1.5rem;
    }
    .nav-item {
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        cursor: pointer;
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 0.25rem;
    }
    .stRadio > div { gap: 0.25rem; }
    .stRadio label { font-size: 0.875rem !important; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ───────────────────────────────────────────────────────────
# Path relative to this file so it works on Streamlit Cloud
POWERBI_DIR = Path(__file__).parent / "outputs" / "powerbi"

@st.cache_data
def load_data():
    # Try compressed version first, fall back to uncompressed
    fact_path = POWERBI_DIR / "fact_ingredients.csv.gz"
    if not fact_path.exists():
        fact_path = POWERBI_DIR / "fact_ingredients.csv"
    fact = pd.read_csv(fact_path,
                       dtype={"well_licence_number": str, "cas_hmirc": str},
                       low_memory=False)
    fact["well_licence_number"] = fact["well_licence_number"].astype(str).str.strip()
    dim_well = pd.read_csv(POWERBI_DIR / "dim_well.csv",
                           dtype={"well_licence_number": str},
                           low_memory=False)
    dim_well["well_licence_number"] = dim_well["well_licence_number"].astype(str).str.strip()
    dim_ingredient = pd.read_csv(POWERBI_DIR / "dim_ingredient.csv",
                                 dtype={"cas_hmirc": str},
                                 low_memory=False)
    dim_supplier = pd.read_csv(POWERBI_DIR / "dim_supplier.csv")
    dim_purpose = pd.read_csv(POWERBI_DIR / "dim_additive_purpose.csv")
    return fact, dim_well, dim_ingredient, dim_supplier, dim_purpose

fact, dim_well, dim_ingredient, dim_supplier, dim_purpose = load_data()

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-title">Alberta Frac Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-subtitle">Public frac data · AER disclosures</div>', unsafe_allow_html=True)

    page = st.radio("", ["Overview", "Formations", "Suppliers", "Additive Purpose", "Chemicals", "Chemical Packages"], label_visibility="collapsed")

    st.markdown("<hr style='border-color:#333;margin:1rem 0'>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.7rem;color:#888;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.75rem">Filters</div>', unsafe_allow_html=True)

    # Year range
    years = sorted(dim_well["start_year"].dropna().astype(int).unique())
    year_min, year_max = int(min(years)), int(max(years))
    year_range = st.slider("Year range", year_min, year_max, (2011, year_max))

    # Step 1: Operator (not cascaded — pick operator first to narrow everything else)
    all_operators = sorted(dim_well["licensee_clean"].dropna().unique().tolist())
    sel_operators = st.multiselect("Operator", all_operators, placeholder="All operators")

    # Cascade: narrow available field centres based on selected operators
    if sel_operators:
        avail_wells = dim_well[dim_well["licensee_clean"].isin(sel_operators)]
    else:
        avail_wells = dim_well.copy()

    # Step 2: Field centre (cascaded from operator)
    avail_centres = sorted(avail_wells["field_centre"].dropna().unique().tolist())
    sel_centres = st.multiselect("Field centre", avail_centres, placeholder="All field centres")

    # Cascade: narrow formations based on operator + field centre
    if sel_centres:
        avail_wells = avail_wells[avail_wells["field_centre"].isin(sel_centres)]

    # Step 3: Formation (cascaded from operator + field centre)
    avail_formations = sorted(avail_wells["geological_pool_name"].dropna().unique().tolist())
    sel_formations = st.multiselect("Formation", avail_formations, placeholder="All formations")

    # Cascade: narrow to wells matching operator + centre + formation
    if sel_formations:
        avail_wells_for_fact = avail_wells[avail_wells["geological_pool_name"].isin(sel_formations)]
    else:
        avail_wells_for_fact = avail_wells

    avail_fact = fact[fact["well_licence_number"].isin(avail_wells_for_fact["well_licence_number"])]

    # Step 4: Supplier (cascaded from operator + centre + formation)
    avail_suppliers = sorted(avail_fact["component_supplier_name_clean"].dropna().unique().tolist())
    sel_suppliers = st.multiselect("Supplier", avail_suppliers, placeholder="All suppliers")
    st.markdown('<div style="font-size:0.65rem;color:#555;margin-top:-0.75rem;margin-bottom:0.5rem">Type to search</div>', unsafe_allow_html=True)

    # Cascade: narrow purposes based on all above including supplier
    if sel_suppliers:
        avail_fact = avail_fact[avail_fact["component_supplier_name_clean"].isin(sel_suppliers)]

    # Step 5: Additive purpose (cascaded from all above)
    avail_purposes = sorted(avail_fact["additive_purpose"].dropna().unique().tolist())
    sel_purposes = st.multiselect("Additive purpose", avail_purposes, placeholder="All purposes")

    st.markdown('<div style="font-size:0.65rem;color:#555;margin-top:0.25rem;margin-bottom:1rem">Tip: type to search in any filter</div>', unsafe_allow_html=True)
    st.markdown("<hr style='border-color:#333;margin:1rem 0'>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.65rem;color:#555;line-height:1.5">Data: AER Hydraulic Fracturing Disclosures<br>Built by Kyle McLean</div>', unsafe_allow_html=True)

# ── Filter logic ───────────────────────────────────────────────────────────
def apply_filters(year_min, year_max, centres, formations, operators, suppliers, purposes):
    wells = dim_well.copy()
    wells = wells[wells["start_year"].between(year_min, year_max, inclusive="both")]
    if operators:
        wells = wells[wells["licensee_clean"].isin(operators)]
    if centres:
        wells = wells[wells["field_centre"].isin(centres)]
    if formations:
        wells = wells[wells["geological_pool_name"].isin(formations)]

    filtered_fact = fact[fact["well_licence_number"].isin(wells["well_licence_number"])]
    if suppliers:
        filtered_fact = filtered_fact[filtered_fact["component_supplier_name_clean"].isin(suppliers)]
    if purposes:
        filtered_fact = filtered_fact[filtered_fact["additive_purpose"].isin(purposes)]
    return wells, filtered_fact

wells_f, fact_f = apply_filters(year_range[0], year_range[1], sel_centres, sel_formations, sel_operators, sel_suppliers, sel_purposes)

# ── Plotly theme ───────────────────────────────────────────────────────────
COLORS = ["#c45e2a", "#5a9a7a", "#4a7aaa", "#a07a45", "#7a5aaa", "#aa5a6a", "#5a8aaa"]
CHART_LAYOUT = dict(
    paper_bgcolor="#1a1a1a",
    plot_bgcolor="#1a1a1a",
    font_family="DM Sans",
    font_color="#e8e6e1",
    showlegend=True,
    xaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickfont=dict(color="#888")),
    yaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickfont=dict(color="#e8e6e1")),
)

def metric_card(value, label):
    return f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>"""

# ══════════════════════════════════════════════════════════════════════════
# Page 1 — Overview
# ══════════════════════════════════════════════════════════════════════════

if page == "Overview":
    st.title("Overview")
    st.markdown(f"Showing **{len(wells_f):,} wells** · **{len(fact_f):,} ingredient disclosures** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # KPI row
    total_volume = fact_f["normalized_pumped_amount"].sum()
    total_water  = wells_f["total_water_volume"].sum()
    unique_ops   = wells_f["licensee_clean"].nunique()
    unique_chems = fact_f["cas_hmirc"].nunique()

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(metric_card(f"{len(wells_f):,}", "Wells"), unsafe_allow_html=True)
    c2.markdown(metric_card(f"{total_volume/1e6:,.1f}M", "Total pumped volume (mixed units)"), unsafe_allow_html=True)
    c3.markdown(metric_card(f"{unique_ops:,}", "Operators"), unsafe_allow_html=True)
    c4.markdown(metric_card(f"{unique_chems:,}", "Unique chemicals"), unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Frac activity by year")
        activity = (
            wells_f.groupby("start_year")["well_licence_number"]
            .nunique()
            .reset_index()
            .rename(columns={"well_licence_number": "wells", "start_year": "year"})
        )
        fig = px.bar(activity, x="year", y="wells", color_discrete_sequence=["#c45e2a"])
        fig.update_layout(**CHART_LAYOUT, height=300, margin=dict(t=20, b=40, l=60, r=20))
        fig.update_traces(marker_line_width=0)
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
        fig = px.bar(top_ops, x="wells", y="operator", orientation="h",
                     color_discrete_sequence=[COLORS[2]])
        fig.update_layout(**CHART_LAYOUT, height=300, yaxis_title="",
                          margin=dict(t=20, b=40, l=200, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

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
        fig = px.pie(purpose_vol, values="normalized_pumped_amount",
                     names="additive_purpose",
                     color_discrete_sequence=COLORS,
                     hole=0.45)
        fig.update_layout(**CHART_LAYOUT, height=320,
                          legend=dict(font_size=10))
        fig.update_traces(textinfo="percent", textfont_size=11)
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
        fig = px.bar(centre_counts, x="wells", y="centre", orientation="h",
                     color_discrete_sequence=[COLORS[1]])
        fig.update_layout(**CHART_LAYOUT, height=320, yaxis_title="",
                          margin=dict(t=20, b=40, l=160, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# Page 2 — Formations
# ══════════════════════════════════════════════════════════════════════════

elif page == "Formations":
    st.title("Formations")
    st.markdown(f"Showing **{len(wells_f):,} wells** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Formation coverage note
    null_pct = wells_f["geological_pool_name"].isna().mean() * 100
    if null_pct > 0:
        st.info(f"{null_pct:.0f}% of filtered wells have no formation data — these are excluded from formation charts. See methodology for details.")

    wells_with_formation = wells_f[wells_f["geological_pool_name"].notna()]
    fact_with_formation = fact_f[fact_f["well_licence_number"].isin(wells_with_formation["well_licence_number"])]

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
        fig = px.bar(top_formations, x="wells", y="formation", orientation="h",
                     color_discrete_sequence=[COLORS[0]])
        fig.update_layout(**CHART_LAYOUT, height=420, yaxis_title="",
                          margin=dict(t=20, b=40, l=220, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top formations by pumped volume")
        form_fact = fact_with_formation.merge(
            wells_f[["well_licence_number", "geological_pool_name"]],
            on="well_licence_number", how="left"
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
        fig = px.bar(top_vol, x="normalized_pumped_amount", y="formation",
                     orientation="h", color_discrete_sequence=[COLORS[2]])
        fig.update_layout(**CHART_LAYOUT, height=420, yaxis_title="",
                          xaxis_title="Normalized pumped amount",
                          margin=dict(t=20, b=40, l=220, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Formation deep dive — uses whatever is selected in the sidebar filters
    formation_label = ", ".join(sel_formations) if sel_formations else "all selected formations"
    st.subheader(f"Chemical breakdown")

    col5, col6 = st.columns(2)

    with col5:
        st.markdown(f"**Top chemicals**")
        top_chems = (
            fact_with_formation[fact_with_formation["additive_purpose"].notna()]
            .merge(dim_ingredient[["cas_hmirc", "ingredient_name_display"]],
                   on="cas_hmirc", how="left")
            .groupby("ingredient_name_display")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=True)
            .tail(10)
            .reset_index()
        )
        fig = px.bar(top_chems, x="normalized_pumped_amount",
                     y="ingredient_name_display", orientation="h",
                     color_discrete_sequence=[COLORS[3]])
        fig.update_layout(**CHART_LAYOUT, height=340,
                          yaxis_title="", xaxis_title="Pumped amount",
                          margin=dict(t=20, b=40, l=200, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col6:
        st.markdown(f"**Additive purposes**")
        purpose_breakdown = (
            fact_with_formation[fact_with_formation["additive_purpose"].notna()]
            .groupby("additive_purpose")["normalized_pumped_amount"]
            .sum()
            .sort_values(ascending=False)
            .head(8)
            .reset_index()
        )
        fig = px.pie(purpose_breakdown,
                     values="normalized_pumped_amount",
                     names="additive_purpose",
                     color_discrete_sequence=COLORS,
                     hole=0.45)
        fig.update_layout(**CHART_LAYOUT, height=340,
                          legend=dict(font_size=10))
        fig.update_traces(textinfo="percent", textfont_size=11)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    st.markdown(f"**Activity over time**")
    form_yearly = (
        wells_with_formation.groupby("start_year")["well_licence_number"]
        .nunique()
        .reset_index()
        .rename(columns={"well_licence_number": "wells", "start_year": "year"})
    )
    fig = px.line(form_yearly, x="year", y="wells",
                  color_discrete_sequence=[COLORS[0]],
                  markers=True)
    fig.update_layout(**CHART_LAYOUT, height=260,
                      xaxis_title="Year", yaxis_title="Wells",
                      margin=dict(t=20, b=40, l=60, r=20))
    fig.update_traces(line_width=2, marker_size=6)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# Page 3 — Suppliers
# ══════════════════════════════════════════════════════════════════════════

elif page == "Suppliers":
    st.title("Suppliers")
    st.markdown(f"Showing **{len(wells_f):,} wells** · **{fact_f['component_supplier_name_clean'].nunique():,} suppliers** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # KPIs
    total_vol    = fact_f["normalized_pumped_amount"].sum()
    top_supplier = (
        fact_f.groupby("component_supplier_name_clean")["normalized_pumped_amount"]
        .sum().idxmax()
    ) if not fact_f.empty else "—"
    unique_products = fact_f["component_trade_name"].nunique()

    k1, k2, k3 = st.columns(3)
    k1.markdown(metric_card(f"{fact_f['component_supplier_name_clean'].nunique():,}", "Suppliers"), unsafe_allow_html=True)
    k2.markdown(metric_card(f"{unique_products:,}", "Unique products"), unsafe_allow_html=True)
    k3.markdown(metric_card(str(top_supplier).title()[:28], "Top supplier by volume"), unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Market share charts
    supplier_vol = (
        fact_f[fact_f["component_supplier_name_clean"].notna()]
        .groupby("component_supplier_name_clean")["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={"component_supplier_name_clean": "supplier",
                          "normalized_pumped_amount": "volume"})
        .sort_values("volume", ascending=False)
    )
    total = supplier_vol["volume"].sum()
    supplier_vol["share_pct"] = (supplier_vol["volume"] / total * 100).round(1)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Market share by pumped volume")
        top15 = supplier_vol.head(15).sort_values("volume", ascending=True)
        fig = px.bar(top15, x="volume", y="supplier", orientation="h",
                     color_discrete_sequence=[COLORS[0]])
        fig.update_layout(**CHART_LAYOUT, height=440,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=220, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 10 suppliers — volume share")
        top10 = supplier_vol.head(10).copy()
        others_vol = supplier_vol.iloc[10:]["volume"].sum()
        if others_vol > 0:
            others_row = pd.DataFrame([{"supplier": "All others", "volume": others_vol,
                                        "share_pct": others_vol / total * 100}])
            top10 = pd.concat([top10, others_row], ignore_index=True)
        fig = px.pie(top10, values="volume", names="supplier",
                     color_discrete_sequence=COLORS, hole=0.45)
        fig.update_layout(**CHART_LAYOUT, height=440,
                          legend=dict(font_size=9),
                          margin=dict(t=20, b=20, l=20, r=20))
        fig.update_traces(textinfo="percent", textfont_size=10)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Product breakdown — uses sidebar supplier filter
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
        fig = px.bar(top_products, x="normalized_pumped_amount", y="product",
                     orientation="h", color_discrete_sequence=[COLORS[2]])
        fig.update_layout(**CHART_LAYOUT, height=400,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=200, r=20))
        fig.update_traces(marker_line_width=0)
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
        fig = px.pie(purpose_vol, values="normalized_pumped_amount",
                     names="additive_purpose",
                     color_discrete_sequence=COLORS, hole=0.45)
        fig.update_layout(**CHART_LAYOUT, height=400,
                          legend=dict(font_size=9),
                          margin=dict(t=20, b=20, l=20, r=20))
        fig.update_traces(textinfo="percent", textfont_size=10)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    st.markdown("**Supplier activity over time**")
    supplier_yearly = (
        wells_f.groupby("start_year")["well_licence_number"]
        .nunique()
        .reset_index()
        .rename(columns={"well_licence_number": "wells", "start_year": "year"})
    )
    fig = px.line(supplier_yearly, x="year", y="wells",
                  color_discrete_sequence=[COLORS[0]],
                  markers=True)
    fig.update_layout(**CHART_LAYOUT, height=260,
                      xaxis_title="Year", yaxis_title="Wells",
                      margin=dict(t=20, b=40, l=60, r=20))
    fig.update_traces(line_width=2, marker_size=6)
    st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# Page 4 — Additive Purpose
# ══════════════════════════════════════════════════════════════════════════

elif page == "Additive Purpose":
    st.title("Additive Purpose")
    st.markdown(f"Showing **{len(wells_f):,} wells** · **{fact_f['additive_purpose'].nunique():,} purposes** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Filter to additive rows only (exclude carrier fluid and proppant for purpose analysis)
    additive_fact = fact_f[fact_f["additive_purpose"].notna()]

    # KPIs
    total_additive_vol = additive_fact["normalized_pumped_amount"].sum()
    top_purpose = additive_fact.groupby("additive_purpose")["normalized_pumped_amount"].sum().idxmax() if not additive_fact.empty else "—"
    top_purpose_pct = (additive_fact.groupby("additive_purpose")["normalized_pumped_amount"].sum().max() / total_additive_vol * 100) if total_additive_vol > 0 else 0

    k1, k2, k3 = st.columns(3)
    k1.markdown(metric_card(f"{additive_fact['additive_purpose'].nunique():,}", "Additive purposes"), unsafe_allow_html=True)
    k2.markdown(metric_card(str(top_purpose), "Largest purpose by volume"), unsafe_allow_html=True)
    k3.markdown(metric_card(f"{top_purpose_pct:.1f}%", "Top purpose share"), unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Purpose volume + share
    col1, col2 = st.columns(2)

    purpose_vol = (
        additive_fact.groupby("additive_purpose")["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={"additive_purpose": "purpose", "normalized_pumped_amount": "volume"})
        .sort_values("volume", ascending=False)
    )

    with col1:
        st.subheader("Volume by additive purpose")
        top_purposes = purpose_vol.sort_values("volume", ascending=True)
        fig = px.bar(top_purposes, x="volume", y="purpose", orientation="h",
                     color_discrete_sequence=[COLORS[0]])
        fig.update_layout(**CHART_LAYOUT, height=420,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=180, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Volume share by purpose")
        fig = px.pie(purpose_vol, values="volume", names="purpose",
                     color_discrete_sequence=COLORS, hole=0.45)
        fig.update_layout(**CHART_LAYOUT, height=420,
                          legend=dict(font_size=9),
                          margin=dict(t=20, b=20, l=20, r=20))
        fig.update_traces(textinfo="percent", textfont_size=10)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Purpose trends over time
    st.subheader("Purpose trends over time")

    # Top 6 purposes for readability
    top6_purposes = purpose_vol.head(6)["purpose"].tolist()
    trend_fact = additive_fact[additive_fact["additive_purpose"].isin(top6_purposes)]
    trend_fact = trend_fact.merge(
        wells_f[["well_licence_number", "start_year"]],
        on="well_licence_number", how="left"
    )

    trend = (
        trend_fact.groupby(["start_year", "additive_purpose"])["normalized_pumped_amount"]
        .sum()
        .reset_index()
        .rename(columns={"additive_purpose": "purpose", "normalized_pumped_amount": "volume", "start_year": "year"})
    )

    fig = px.line(trend, x="year", y="volume", color="purpose",
                  color_discrete_sequence=COLORS, markers=True)
    fig.update_layout(**CHART_LAYOUT, height=320,
                      xaxis_title="Year", yaxis_title="Pumped volume",
                      margin=dict(t=20, b=40, l=80, r=20),
                      legend=dict(font_size=10))
    fig.update_xaxes(dtick=1, tickformat="d")
    fig.update_traces(line_width=2, marker_size=5)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Top chemicals per purpose
    st.subheader("Top chemicals by purpose")

    purpose_list = sorted(additive_fact["additive_purpose"].dropna().unique().tolist())
    sel_purpose_detail = st.selectbox("Select a purpose", purpose_list,
                                      index=purpose_list.index("Friction Reducer") if "Friction Reducer" in purpose_list else 0)

    purpose_chems = (
        additive_fact[additive_fact["additive_purpose"] == sel_purpose_detail]
        .merge(dim_ingredient[["cas_hmirc", "ingredient_name_display"]], on="cas_hmirc", how="left")
        .groupby("ingredient_name_display")["normalized_pumped_amount"]
        .sum()
        .sort_values(ascending=True)
        .tail(12)
        .reset_index()
    )

    col3, col4 = st.columns(2)

    with col3:
        st.markdown(f"**Top chemicals in {sel_purpose_detail}**")
        fig = px.bar(purpose_chems, x="normalized_pumped_amount",
                     y="ingredient_name_display", orientation="h",
                     color_discrete_sequence=[COLORS[3]])
        fig.update_layout(**CHART_LAYOUT, height=380,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=220, r=20))
        fig.update_traces(marker_line_width=0)
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
        fig = px.bar(purpose_suppliers, x="normalized_pumped_amount",
                     y="supplier", orientation="h",
                     color_discrete_sequence=[COLORS[1]])
        fig.update_layout(**CHART_LAYOUT, height=380,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=220, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════
# Page 5 — Chemicals
# ══════════════════════════════════════════════════════════════════════════

elif page == "Chemicals":
    st.title("Chemicals")
    st.markdown(f"Showing **{len(wells_f):,} wells** · **{fact_f['cas_hmirc'].nunique():,} unique chemicals** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Exclude carrier fluid rows — focus on additive/proppant chemicals
    chem_fact = fact_f[fact_f["additive_purpose"].notna()].copy()
    chem_fact = chem_fact.merge(
        dim_ingredient[["cas_hmirc", "ingredient_name_display", "ingredient_name_clean"]],
        on="cas_hmirc", how="left"
    )

    # KPIs
    k1, k2, k3 = st.columns(3)
    k1.markdown(metric_card(f"{chem_fact['cas_hmirc'].nunique():,}", "Unique chemicals (CAS)"), unsafe_allow_html=True)
    trade_secret_wells = chem_fact[chem_fact['cas_hmirc'] == 'Trade Secret']['well_licence_number'].nunique()
    k2.markdown(metric_card(f"{trade_secret_wells:,}", "Wells with trade secret chemicals"), unsafe_allow_html=True)
    valid_chems = chem_fact[~chem_fact["cas_hmirc"].isin(["Trade Secret", "Not Available", "not available"])]
    top_chem = valid_chems.groupby("ingredient_name_display")["normalized_pumped_amount"].sum().idxmax() if not valid_chems.empty else "—"
    k3.markdown(metric_card(str(top_chem)[:28], "Top chemical by volume"), unsafe_allow_html=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

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
        fig = px.bar(top_chems, x="normalized_pumped_amount", y="chemical",
                     orientation="h", color_discrete_sequence=[COLORS[0]])
        fig.update_layout(**CHART_LAYOUT, height=460,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=240, r=20))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Chemical use by additive purpose")
        # Show top 8 chemicals across purposes as a stacked bar
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
                chem_fact["ingredient_name_display"].isin(top8_chems) &
                chem_fact["additive_purpose"].notna()
            ]
            .groupby(["ingredient_name_display", "additive_purpose"])["normalized_pumped_amount"]
            .sum()
            .reset_index()
            .rename(columns={"ingredient_name_display": "chemical",
                              "normalized_pumped_amount": "volume"})
        )
        fig = px.bar(chem_purpose, x="volume", y="chemical",
                     color="additive_purpose", orientation="h",
                     color_discrete_sequence=COLORS)
        fig.update_layout(**CHART_LAYOUT, height=460,
                          yaxis_title="", xaxis_title="Pumped volume",
                          margin=dict(t=20, b=40, l=240, r=20),
                          legend=dict(font_size=9))
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Chemical search / explorer
    st.subheader("Chemical explorer")
    st.markdown("Search by ingredient name or CAS number to see where and how a chemical is used.")

    search_col, _ = st.columns([2, 1])
    with search_col:
        search_term = st.text_input("", placeholder="e.g. methanol, polyacrylamide, 67-56-1",
                                    label_visibility="collapsed")

    if search_term:
        mask = (
            chem_fact["ingredient_name_clean"].str.contains(search_term.lower(), na=False) |
            chem_fact["cas_hmirc"].str.contains(search_term, na=False)
        )
        search_results = chem_fact[mask]

        if search_results.empty:
            st.info(f"No results found for '{search_term}'")
        else:
            cas_found = search_results["cas_hmirc"].iloc[0]
            name_found = search_results["ingredient_name_display"].iloc[0]
            total_vol = search_results["normalized_pumped_amount"].sum()
            well_count = search_results["well_licence_number"].nunique()

            st.markdown("<br>", unsafe_allow_html=True)
            r1, r2, r3, r4 = st.columns(4)
            r1.markdown(metric_card(str(name_found)[:24], "Canonical name"), unsafe_allow_html=True)
            r2.markdown(metric_card(str(cas_found), "CAS / HMIRC"), unsafe_allow_html=True)
            r3.markdown(metric_card(f"{well_count:,}", "Wells"), unsafe_allow_html=True)
            vol_fmt = f"{total_vol/1e6:.1f}M" if total_vol >= 1e6 else f"{total_vol/1e3:.1f}K"
            r4.markdown(metric_card(vol_fmt, "Total pumped"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            e1, e2 = st.columns(2)

            with e1:
                st.markdown("**Used by purpose**")
                by_purpose = (
                    search_results.groupby("additive_purpose")["normalized_pumped_amount"]
                    .sum().sort_values(ascending=True).reset_index()
                )
                fig = px.bar(by_purpose, x="normalized_pumped_amount",
                             y="additive_purpose", orientation="h",
                             color_discrete_sequence=[COLORS[2]])
                fig.update_layout(**CHART_LAYOUT, height=260,
                                  yaxis_title="", xaxis_title="Pumped volume",
                                  margin=dict(t=20, b=40, l=160, r=20))
                fig.update_traces(marker_line_width=0)
                st.plotly_chart(fig, use_container_width=True)

            with e2:
                st.markdown("**Top suppliers using this chemical**")
                by_supplier = (
                    search_results.groupby("component_supplier_name_clean")["normalized_pumped_amount"]
                    .sum().sort_values(ascending=True).tail(8).reset_index()
                    .rename(columns={"component_supplier_name_clean": "supplier"})
                )
                fig = px.bar(by_supplier, x="normalized_pumped_amount",
                             y="supplier", orientation="h",
                             color_discrete_sequence=[COLORS[1]])
                fig.update_layout(**CHART_LAYOUT, height=260,
                                  yaxis_title="", xaxis_title="Pumped volume",
                                  margin=dict(t=20, b=40, l=200, r=20))
                fig.update_traces(marker_line_width=0)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.markdown('<div style="color:#555;font-size:0.875rem;padding:1rem 0">Enter a chemical name or CAS number above to explore its use across the dataset.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
# Page 6 — Chemical Packages
# ══════════════════════════════════════════════════════════════════════════

elif page == "Chemical Packages":
    st.title("Chemical Packages")
    st.markdown("Compare chemical recipes across suppliers and operators for a specific formation.")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Require exactly one formation selected
    if not sel_formations or len(sel_formations) != 1:
        st.info("Select a single formation in the sidebar to compare chemical packages.")
        st.markdown('<div style="color:#555;font-size:0.875rem;padding:0.5rem 0">Use the Formation filter on the left — type to search. This page works best with one formation selected so packages are directly comparable.</div>', unsafe_allow_html=True)
        st.stop()

    formation = sel_formations[0]
    st.markdown(f"Showing top 10 by well count · **{formation}** · {year_range[0]}–{year_range[1]}")
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)

    # Prepare package data — bypass additive purpose filter so all
    # purposes show in the cards regardless of sidebar selection
    pkg_fact_base = apply_filters(
        year_range[0], year_range[1],
        sel_centres, sel_formations, sel_operators, sel_suppliers, []
    )[1]  # [1] = fact, ignore wells
    pkg_fact = pkg_fact_base[pkg_fact_base["additive_purpose"].notna()].copy()
    pkg_fact = pkg_fact.merge(
        dim_ingredient[["cas_hmirc", "ingredient_name_display"]],
        on="cas_hmirc", how="left"
    )

    def build_packages(group_col, group_label):
        """Build top-chemical-per-purpose summary grouped by group_col."""
        if pkg_fact.empty or group_col not in pkg_fact.columns:
            return pd.DataFrame()

        # Total wells per group
        wells_per_group = (
            pkg_fact.groupby(group_col)["well_licence_number"]
            .nunique()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .rename(columns={"well_licence_number": "well_count"})
        )

        packages = []
        for _, row in wells_per_group.iterrows():
            grp = row[group_col]
            n_wells = row["well_count"]
            grp_fact = pkg_fact[pkg_fact[group_col] == grp]

            # Top chemical per purpose (by avg pumped per well)
            # All products per purpose, sorted by avg volume
            product_summary = (
                grp_fact.groupby(["additive_purpose", "component_trade_name"])
                .agg(total_vol=("normalized_pumped_amount", "sum"))
                .reset_index()
            )
            product_summary["avg_per_well"] = (product_summary["total_vol"] / n_wells).round(1)

            # Sort: purpose by total purpose volume desc, then products within purpose by volume desc
            purpose_totals = (
                product_summary.groupby("additive_purpose")["avg_per_well"]
                .sum().sort_values(ascending=False)
                .reset_index()
                .rename(columns={"avg_per_well": "purpose_total"})
            )
            product_summary = product_summary.merge(purpose_totals, on="additive_purpose")
            top_per_purpose = (
                product_summary
                .sort_values(["purpose_total", "avg_per_well"], ascending=[False, False])
                [["additive_purpose", "component_trade_name", "avg_per_well"]]
                .rename(columns={"component_trade_name": "ingredient_name_display"})
            )

            # TVD stats from dim_well
            grp_wells = wells_f[wells_f["well_licence_number"].isin(grp_fact["well_licence_number"].unique())]
            tvd_vals = pd.to_numeric(grp_wells["max_true_vertical_depth"], errors="coerce").dropna()
            if len(tvd_vals) > 0:
                tvd_str = f"TVD: {tvd_vals.min():.0f}m min · {tvd_vals.mean():.0f}m avg · {tvd_vals.max():.0f}m max"
            else:
                tvd_str = ""

            packages.append({
                "name": grp,
                "wells": n_wells,
                "products": grp_fact["component_trade_name"].nunique(),
                "purposes": top_per_purpose,
                "tvd": tvd_str,
            })

        return packages

    # Card CSS
    st.markdown("""
    <style>
    .pkg-card {
        background: #1e1e1e;
        border: 1px solid #2a2a2a;
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    .pkg-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #ffffff;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        margin-bottom: 0.25rem;
    }
    .pkg-meta {
        font-size: 0.7rem;
        color: #aaa;
        margin-bottom: 0.4rem;
    }
    .pkg-tvd {
        font-size: 0.68rem;
        color: #999;
        margin-bottom: 1rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #333;
    }
    .pkg-row {
        display: grid;
        grid-template-columns: 120px 1fr auto;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.55rem;
        padding-bottom: 0.55rem;
        border-bottom: 1px solid #2a2a2a;
    }
    .pkg-row:last-child {
        border-bottom: none;
        margin-bottom: 0;
        padding-bottom: 0;
    }
    .pkg-purpose {
        font-size: 0.62rem;
        color: #c45e2a;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 500;
    }
    .pkg-chem {
        font-size: 0.78rem;
        color: #ffffff;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .pkg-vol {
        font-size: 0.65rem;
        color: #888;
        text-align: right;
        white-space: nowrap;
    }
    </style>
    """, unsafe_allow_html=True)

    def render_card(pkg):
        rows_html = ""
        for _, r in pkg["purposes"].reset_index(drop=True).iterrows():
            chem = str(r["ingredient_name_display"]) if pd.notna(r["ingredient_name_display"]) else "Unknown"
            chem_short = (chem[:30] + "…") if len(chem) > 30 else chem
            purpose_short = str(r["additive_purpose"])[:20]
            vol = r["avg_per_well"]
            vol_str = f"{vol:,.1f} units/well"
            rows_html += (
                "<div class=\"pkg-row\">"
                f"<div class=\"pkg-purpose\">{purpose_short}</div>"
                f"<div class=\"pkg-chem\">{chem_short}</div>"
                f"<div class=\"pkg-vol\">{vol_str}</div>"
                "</div>"
            )

        name = str(pkg["name"])[:40]
        wells = f"{pkg['wells']:,}"
        products = f"{pkg['products']:,}"
        tvd = pkg.get("tvd", "")
        tvd_html = f"<div class=\"pkg-tvd\">{tvd}</div>" if tvd else "<div class=\"pkg-tvd\"> </div>"
        card = (
            "<div class=\"pkg-card\">"
            f"<div class=\"pkg-header\">{name}</div>"
            f"<div class=\"pkg-meta\">{wells} wells · {products} products</div>"
            f"{tvd_html}"
            f"{rows_html}"
            "</div>"
        )
        return card

    # Tabs for supplier vs operator
    tab1, tab2 = st.tabs(["By Supplier", "By Operator"])

    with tab1:
        packages = build_packages("component_supplier_name_clean", "Supplier")
        if not packages:
            st.info("No supplier data available for this selection.")
        else:
            cols = st.columns(3)
            for i, pkg in enumerate(packages):
                with cols[i % 3]:
                    st.markdown(render_card(pkg), unsafe_allow_html=True)

    with tab2:
        # Map operator via well dimension
        pkg_fact_op = pkg_fact.merge(
            wells_f[["well_licence_number", "licensee_clean"]],
            on="well_licence_number", how="left"
        )
        packages_op = build_packages.__wrapped__(pkg_fact_op, "licensee_clean", "Operator") if hasattr(build_packages, "__wrapped__") else None

        # Re-run for operator using licensee_clean
        if "licensee_clean" not in pkg_fact.columns:
            pkg_fact_op2 = pkg_fact.merge(
                wells_f[["well_licence_number", "licensee_clean"]],
                on="well_licence_number", how="left"
            )
        else:
            pkg_fact_op2 = pkg_fact

        wells_per_op = (
            pkg_fact_op2.groupby("licensee_clean")["well_licence_number"]
            .nunique()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
            .rename(columns={"well_licence_number": "well_count"})
        )

        op_packages = []
        for _, row in wells_per_op.iterrows():
            grp = row["licensee_clean"]
            n_wells = row["well_count"]
            grp_fact = pkg_fact_op2[pkg_fact_op2["licensee_clean"] == grp]

            op_product_summary = (
                grp_fact.groupby(["additive_purpose", "component_trade_name"])
                .agg(total_vol=("normalized_pumped_amount", "sum"))
                .reset_index()
            )
            op_product_summary["avg_per_well"] = (op_product_summary["total_vol"] / n_wells).round(1)
            op_purpose_totals = (
                op_product_summary.groupby("additive_purpose")["avg_per_well"]
                .sum().sort_values(ascending=False)
                .reset_index()
                .rename(columns={"avg_per_well": "purpose_total"})
            )
            op_product_summary = op_product_summary.merge(op_purpose_totals, on="additive_purpose")
            top_per_purpose = (
                op_product_summary
                .sort_values(["purpose_total", "avg_per_well"], ascending=[False, False])
                [["additive_purpose", "component_trade_name", "avg_per_well"]]
                .rename(columns={"component_trade_name": "ingredient_name_display"})
            )
            op_grp_wells = wells_f[wells_f["well_licence_number"].isin(grp_fact["well_licence_number"].unique())]
            op_tvd_vals = pd.to_numeric(op_grp_wells["max_true_vertical_depth"], errors="coerce").dropna()
            if len(op_tvd_vals) > 0:
                op_tvd_str = f"TVD: {op_tvd_vals.min():.0f}m min · {op_tvd_vals.mean():.0f}m avg · {op_tvd_vals.max():.0f}m max"
            else:
                op_tvd_str = ""
            op_packages.append({
                "name": grp,
                "wells": n_wells,
                "products": grp_fact["component_trade_name"].nunique(),
                "purposes": top_per_purpose,
                "tvd": op_tvd_str,
            })

        if not op_packages:
            st.info("No operator data available for this selection.")
        else:
            cols = st.columns(3)
            for i, pkg in enumerate(op_packages):
                with cols[i % 3]:
                    st.markdown(render_card(pkg), unsafe_allow_html=True)
