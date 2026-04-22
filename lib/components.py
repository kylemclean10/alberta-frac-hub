"""
lib/components.py — reusable HTML/markdown components.

Keeps HTML-in-Python noise out of the page files. Every function here
returns a string intended to be passed to st.markdown(..., unsafe_allow_html=True)
— the page decides when to render it.
"""

import pandas as pd
import streamlit as st


# ── Section helpers ────────────────────────────────────────────────────────

def metric_card(value: str, label: str) -> str:
    """KPI tile. Typically rendered inside an st.columns() cell."""
    return f"""
    <div class="metric-card">
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>"""


def section_divider():
    """Thin horizontal rule between sections on a page."""
    st.markdown('<hr class="section-divider">', unsafe_allow_html=True)


# ── Chemical-package cards ─────────────────────────────────────────────────
# These are the cards on the Chemical Packages page — one per supplier or
# operator in the selected formation, showing their full recipe.

def _format_tvd(wells_subset: pd.DataFrame) -> str:
    """Build the 'TVD: X min · Y avg · Z max' line for a package card."""
    tvd_vals = pd.to_numeric(
        wells_subset["max_true_vertical_depth"], errors="coerce"
    ).dropna()
    if len(tvd_vals) == 0:
        return ""
    return (
        f"TVD: {tvd_vals.min():.0f}m min · "
        f"{tvd_vals.mean():.0f}m avg · "
        f"{tvd_vals.max():.0f}m max"
    )


def build_packages(
    pkg_fact: pd.DataFrame,
    wells_f: pd.DataFrame,
    group_col: str,
    top_n: int = 10,
) -> list:
    """
    Build the top-N package cards for a grouping column (supplier or operator).

    Parameters
    ----------
    pkg_fact : DataFrame
        Fact rows, already filtered to the chosen formation and merged with
        dim_ingredient so ingredient_name_display is present.
    wells_f : DataFrame
        Filtered wells table — used for TVD stats.
    group_col : str
        Column to group by ("component_supplier_name_clean" or "licensee_clean").
    top_n : int, default 10
        Number of top groups to return.

    Returns
    -------
    list of dict, one per group, ready for render_card().
    """
    if pkg_fact.empty or group_col not in pkg_fact.columns:
        return []

    # Wells per group, top N by count
    wells_per_group = (
        pkg_fact.groupby(group_col)["well_licence_number"]
        .nunique()
        .sort_values(ascending=False)
        .head(top_n)
        .reset_index()
        .rename(columns={"well_licence_number": "well_count"})
    )

    packages = []
    for _, row in wells_per_group.iterrows():
        grp = row[group_col]
        n_wells = row["well_count"]
        grp_fact = pkg_fact[pkg_fact[group_col] == grp]

        # All products per purpose, with avg pumped per well
        product_summary = (
            grp_fact.groupby(["additive_purpose", "component_trade_name"])
            .agg(total_vol=("normalized_pumped_amount", "sum"))
            .reset_index()
        )
        product_summary["avg_per_well"] = (
            product_summary["total_vol"] / n_wells
        ).round(1)

        # Sort purposes by total volume, products within each by volume
        purpose_totals = (
            product_summary.groupby("additive_purpose")["avg_per_well"]
            .sum()
            .sort_values(ascending=False)
            .reset_index()
            .rename(columns={"avg_per_well": "purpose_total"})
        )
        product_summary = product_summary.merge(purpose_totals, on="additive_purpose")
        top_per_purpose = (
            product_summary.sort_values(
                ["purpose_total", "avg_per_well"], ascending=[False, False]
            )[["additive_purpose", "component_trade_name", "avg_per_well"]]
            .rename(columns={"component_trade_name": "ingredient_name_display"})
        )

        # TVD stats
        grp_wells = wells_f[
            wells_f["well_licence_number"].isin(grp_fact["well_licence_number"].unique())
        ]
        tvd_str = _format_tvd(grp_wells)

        packages.append(
            {
                "name": grp,
                "wells": int(n_wells),
                "products": int(grp_fact["component_trade_name"].nunique()),
                "purposes": top_per_purpose,
                "tvd": tvd_str,
            }
        )

    return packages


def render_card(pkg: dict) -> str:
    """Render a single package dict as an HTML card string."""
    rows_html = ""
    for _, r in pkg["purposes"].reset_index(drop=True).iterrows():
        chem = (
            str(r["ingredient_name_display"])
            if pd.notna(r["ingredient_name_display"])
            else "Unknown"
        )
        chem_short = (chem[:30] + "…") if len(chem) > 30 else chem
        purpose_short = str(r["additive_purpose"])[:20]
        vol_str = f"{r['avg_per_well']:,.1f} units/well"
        rows_html += (
            '<div class="pkg-row">'
            f'<div class="pkg-purpose">{purpose_short}</div>'
            f'<div class="pkg-chem">{chem_short}</div>'
            f'<div class="pkg-vol">{vol_str}</div>'
            "</div>"
        )

    name = str(pkg["name"])[:40]
    wells = f"{pkg['wells']:,}"
    products = f"{pkg['products']:,}"
    tvd = pkg.get("tvd", "")
    tvd_html = f'<div class="pkg-tvd">{tvd}</div>' if tvd else '<div class="pkg-tvd"> </div>'

    return (
        '<div class="pkg-card">'
        f'<div class="pkg-header">{name}</div>'
        f'<div class="pkg-meta">{wells} wells · {products} products</div>'
        f"{tvd_html}"
        f"{rows_html}"
        "</div>"
    )


def render_package_grid(packages: list, cols_per_row: int = 3):
    """Render a list of packages in a grid of Streamlit columns."""
    if len(packages) == 0:
        st.info("No data available for this selection.")
        return
    cols = st.columns(cols_per_row)
    for i, pkg in enumerate(packages):
        with cols[i % cols_per_row]:
            st.markdown(render_card(pkg), unsafe_allow_html=True)
