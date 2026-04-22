"""
lib/theme.py — visual theme for the Alberta Frac Hub app.

Exposes:
    COLORS         — Plotly colour palette (categorical)
    CHART_LAYOUT   — default Plotly layout dict (paper/plot bg, fonts, axes)
    inject_css()   — call once per page to inject app-wide CSS
"""

import streamlit as st


# ── Palette ────────────────────────────────────────────────────────────────
# Primary accent is burnt orange; balance colours are muted earth tones so
# the overall feel stays industrial rather than playful.
COLORS = [
    "#c45e2a",  # burnt orange (primary)
    "#5a9a7a",  # muted green
    "#4a7aaa",  # muted blue
    "#a07a45",  # tan
    "#7a5aaa",  # muted purple
    "#aa5a6a",  # muted rose
    "#5a8aaa",  # steel blue
]


# ── Plotly layout defaults ────────────────────────────────────────────────
# Applied via fig.update_layout(**CHART_LAYOUT) on every chart so the whole
# app reads as one piece. Per-chart overrides (height, margin, titles) are
# still passed individually at call sites.
CHART_LAYOUT = dict(
    paper_bgcolor="#1a1a1a",
    plot_bgcolor="#1a1a1a",
    font_family="DM Sans",
    font_color="#e8e6e1",
    showlegend=True,
    xaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickfont=dict(color="#888")),
    yaxis=dict(gridcolor="#2a2a2a", linecolor="#333", tickfont=dict(color="#e8e6e1")),
)


# ── Global CSS ─────────────────────────────────────────────────────────────
_APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
    .main { background-color: #f8f7f4; }
    .block-container { padding: 2rem 2.5rem; }

    h1 { font-size: 1.8rem; font-weight: 600; color: #1a1a1a; letter-spacing: -0.02em; }
    h2 { font-size: 1.2rem; font-weight: 500; color: #1a1a1a; letter-spacing: -0.01em; }
    h3 { font-size: 1rem;   font-weight: 500; color: #444; }

    /* Metric cards */
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

    /* Section dividers */
    .section-divider {
        border: none;
        border-top: 1px solid #e8e6e1;
        margin: 1.5rem 0;
    }

    /* Filter labels (main area) */
    .stSelectbox label, .stMultiSelect label, .stSlider label {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: #888 !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #1a1a1a; }
    section[data-testid="stSidebar"] * { color: #e8e6e1 !important; }
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

    .stRadio > div { gap: 0.25rem; }
    .stRadio label { font-size: 0.875rem !important; }
</style>
"""

_PKG_CARD_CSS = """
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
"""


def inject_css():
    """Inject the app-wide CSS. Call once at the top of each page."""
    st.markdown(_APP_CSS, unsafe_allow_html=True)


def inject_package_card_css():
    """Inject the Chemical Packages card CSS. Only used on that page."""
    st.markdown(_PKG_CARD_CSS, unsafe_allow_html=True)
