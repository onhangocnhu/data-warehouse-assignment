"""Shared look of the dashboard: number formats, KPI tiles, chart style and colors.

Colors (validated for color-vision deficiency, light and dark): categorical slots are assigned in a
fixed order and follow the entity (a region keeps its color on every chart); magnitudes use one blue
ramp; the three DSS risk levels use the status colors, always with their text label.
Every chart has a "Bảng số liệu" expander with the numbers behind it.
"""
import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .filters import REGIONS

_LIGHT = {"series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
          "grid": "#e1e0d9", "axis": "#c3c2b7", "muted": "#898781", "ink": "#0b0b0b", "ink2": "#52514e"}
_DARK = {"series": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
         "grid": "#2c2c2a", "axis": "#383835", "muted": "#898781", "ink": "#f0efec", "ink2": "#c3c2b7"}
SEQ_BLUE = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
            "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
STATUS = {"RED": "#d03b3b", "YELLOW": "#fab219", "GREEN": "#0ca30c"}


def palette() -> dict:
    try:
        dark = st.context.theme.type == "dark"
    except Exception:
        dark = False
    return _DARK if dark else _LIGHT


def series(i: int) -> str:
    return palette()["series"][i]


def region_colors() -> dict:
    return dict(zip(REGIONS, palette()["series"]))


# ---------- numbers in Vietnamese format: 13.494.400,74 ; 6,77% ----------
def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def num(x, d: int = 0) -> str:
    if _missing(x):
        return "–"
    s = f"{float(x):,.{d}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def pct(x, d: int = 2) -> str:
    return "–" if _missing(x) else num(x, d) + "%"


def money(x, d: int = 2) -> str:
    return "–" if _missing(x) else num(x, d) + " BRL"


def ratio(a, b):
    return None if _missing(a) or _missing(b) or not b else float(a) / float(b)


def kpis(items: list[tuple]) -> None:
    """items: (label, value[, help]) per tile, shown in one row."""
    for col, item in zip(st.columns(len(items)), items):
        label, value, *rest = item
        col.metric(label, value, help=rest[0] if rest else None, border=True)


# ---------- charts ----------
def style(fig: go.Figure, height: int = 360) -> go.Figure:
    """Full styling here; the chart is drawn with theme=None so Streamlit does not override the layout."""
    t = palette()
    # legend (if any) sits under the plot so it never collides with the title
    has_legend = sum(1 for tr in fig.data if tr.showlegend is not False and tr.type != "heatmap") > 1
    fig.update_layout(
        template="none", height=height, separators=",.",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", size=13, color=t["ink2"]),
        title=dict(font=dict(size=15, color=t["ink"]), x=0, xanchor="left", y=0.98, yanchor="top"),
        margin=dict(l=8, r=8, t=48, b=80 if has_legend else 8),
        legend=dict(orientation="h", yanchor="top", y=-0.16, x=0, title_text="", font_color=t["ink2"]),
        barcornerradius=4, bargap=0.3, bargroupgap=0.08,
        hoverlabel=dict(font_size=12),
    )
    fig.update_xaxes(showgrid=False, linecolor=t["axis"], tickcolor=t["axis"], ticks="outside",
                     automargin=True, title_font_color=t["muted"], tickfont_color=t["ink2"])
    fig.update_yaxes(gridcolor=t["grid"], zeroline=False, linecolor=t["axis"], automargin=True,
                     title_font_color=t["muted"], tickfont_color=t["ink2"])
    fig.update_traces(selector=dict(type="scatter"), line_width=2)
    fig.update_traces(selector=dict(type="heatmap"), colorbar=dict(outlinewidth=0, tickfont_color=t["ink2"]))
    return fig


def chart(fig: go.Figure, table: pd.DataFrame | None = None, height: int = 360, **table_kwargs) -> None:
    st.plotly_chart(style(fig, height), width="stretch", theme=None, config={"displaylogo": False})
    if table is not None:
        with st.expander("Bảng số liệu"):
            st.dataframe(table, hide_index=True, width="stretch", **table_kwargs)


def money_col(label: str):
    return st.column_config.NumberColumn(label, format="localized")


def pct_col(label: str, d: int = 2):
    return st.column_config.NumberColumn(label, format=f"%.{d}f%%")
