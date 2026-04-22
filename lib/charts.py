"""
lib/charts.py — reusable Plotly chart builders.

Each page was repeating the same update_layout(margin=..., height=...,
yaxis_title="") boilerplate after every px.bar / px.pie call. These
helpers collapse that into a single call and apply CHART_LAYOUT from
the theme module so the whole app reads as one piece.

Every builder returns a `go.Figure` — the page is still responsible for
`st.plotly_chart(fig, use_container_width=True)`.
"""

import pandas as pd
import plotly.express as px

from lib.theme import CHART_LAYOUT, COLORS


# ── Bars ───────────────────────────────────────────────────────────────────

def horizontal_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: str = COLORS[0],
    height: int = 340,
    left_margin: int = 200,
    x_title: str = "",
    y_title: str = "",
):
    """
    Horizontal bar chart — the most-repeated pattern in the app.
    `df` should already be sorted ascending on x so the longest bar is on top.
    """
    fig = px.bar(df, x=x, y=y, orientation="h", color_discrete_sequence=[color])
    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(t=20, b=40, l=left_margin, r=20),
    )
    fig.update_traces(marker_line_width=0)
    return fig


def vertical_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: str = COLORS[0],
    height: int = 300,
    x_title: str = "",
    y_title: str = "",
):
    """Vertical bar — e.g. activity by year."""
    fig = px.bar(df, x=x, y=y, color_discrete_sequence=[color])
    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(t=20, b=40, l=60, r=20),
    )
    fig.update_traces(marker_line_width=0)
    return fig


def stacked_horizontal_bar(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    *,
    height: int = 460,
    left_margin: int = 240,
    x_title: str = "",
    y_title: str = "",
    legend_font: int = 9,
):
    """Horizontal bar with a categorical color dimension (stacked)."""
    fig = px.bar(
        df, x=x, y=y, color=color, orientation="h",
        color_discrete_sequence=COLORS,
    )
    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(t=20, b=40, l=left_margin, r=20),
        legend=dict(font_size=legend_font),
    )
    fig.update_traces(marker_line_width=0)
    return fig


# ── Pies ───────────────────────────────────────────────────────────────────

def donut(
    df: pd.DataFrame,
    values: str,
    names: str,
    *,
    height: int = 340,
    legend_font: int = 10,
    tight_margin: bool = False,
):
    """Donut chart — used for share/percentage breakdowns."""
    fig = px.pie(
        df, values=values, names=names,
        color_discrete_sequence=COLORS, hole=0.45,
    )
    margin = dict(t=20, b=20, l=20, r=20) if tight_margin else dict(t=20, b=40, l=20, r=20)
    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        legend=dict(font_size=legend_font),
        margin=margin,
    )
    fig.update_traces(textinfo="percent", textfont_size=11)
    return fig


# ── Lines ──────────────────────────────────────────────────────────────────

def line_over_time(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    color: str | None = None,
    single_color: str = COLORS[0],
    height: int = 260,
    x_title: str = "Year",
    y_title: str = "",
    integer_years: bool = True,
    legend_font: int = 10,
):
    """
    Line chart over years. Pass `color=` for a multi-series line, otherwise
    a single-colour line is drawn.
    """
    if color is not None:
        fig = px.line(
            df, x=x, y=y, color=color,
            color_discrete_sequence=COLORS, markers=True,
        )
    else:
        fig = px.line(
            df, x=x, y=y, color_discrete_sequence=[single_color], markers=True,
        )

    fig.update_layout(
        **CHART_LAYOUT,
        height=height,
        xaxis_title=x_title,
        yaxis_title=y_title,
        margin=dict(t=20, b=40, l=80, r=20),
        legend=dict(font_size=legend_font),
    )
    if integer_years:
        # Must use update_xaxes here — passing xaxis= to update_layout
        # alongside CHART_LAYOUT's xaxis causes a "multiple values" error.
        fig.update_xaxes(dtick=1, tickformat="d")
    fig.update_traces(line_width=2, marker_size=5)
    return fig
