"""Shared look of the dashboard: number formats, KPI tiles, chart style and colors.

Colors (validated for color-vision deficiency, light and dark): categorical slots are assigned in a
fixed order and follow the entity (a region keeps its color on every chart); magnitudes use one blue
ramp; the three DSS risk levels use the status colors, always with their text label.
Every chart has a "Bảng số liệu" expander with the numbers behind it.
"""
import math
from decimal import Decimal

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
    theme = st.session_state.get("ui_theme")          # reported by theme_watcher(), most reliable
    if theme is None:
        try:
            theme = st.context.theme.type
        except Exception:
            theme = "light"
    return _DARK if theme == "dark" else _LIGHT


# Charts are styled in Python, so when the viewer switches theme in the ⋮ menu (Light / Dark / System)
# they would keep the old colours until the next rerun. This tiny inline component watches the app
# background in the browser and triggers a rerun as soon as it no longer matches the chart palette.
_WATCH_JS = """
export default function (component) {
    const { data, setTriggerValue } = component;
    let sent = null;
    const check = () => {
        const app = document.querySelector('.stApp');
        if (!app) return;
        const rgb = getComputedStyle(app).backgroundColor.match(/\\d+/g);
        if (!rgb) return;
        const lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
        const now = lum < 0.5 ? 'dark' : 'light';
        if (now !== data && now !== sent) { sent = now; setTriggerValue('theme', now); }
    };
    check();
    const id = setInterval(check, 400);
    return () => clearInterval(id);
}
"""
_watcher = None


def theme_watcher() -> None:
    global _watcher
    if _watcher is None:
        _watcher = st.components.v2.component("theme_watcher", html="<span></span>", js=_WATCH_JS)
    current = "dark" if palette() is _DARK else "light"
    res = _watcher(key="theme_watcher", data=current, height=0, on_theme_change=lambda: None)
    if res.theme and res.theme != current:
        st.session_state.ui_theme = res.theme


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
            show_table(table, **table_kwargs)


# ---------- tables in Vietnamese number format ----------
# Streamlit's own number formats follow the browser locale (usually 1,234.5), so every table goes
# through show_table(): numbers are rendered by a pandas Styler with num(); the underlying values stay
# numeric, so sorting a column still sorts by value.
def money_col(label: str):
    """Marks a money column: 2 decimals (13.494.400,74)."""
    return {"label": label, "_vn": ("money", 2)}


def pct_col(label: str, d: int = 2):
    """Marks a percentage column (values already in %): 6,77%."""
    return {"label": label, "_vn": ("pct", d)}


def _decimals(s: pd.Series, most: int) -> int:
    """Fewest decimals (0..most) that show every value of the column exactly."""
    v = s.dropna().astype(float)
    for d in range(most):
        if ((v - v.round(d)).abs() < 1e-9).all():
            return d
    return most


def _is_decimal(s: pd.Series) -> bool:
    v = s.dropna()
    return len(v) > 0 and all(isinstance(x, (Decimal, int, float)) and not isinstance(x, bool) for x in v)


def show_table(df: pd.DataFrame, column_config: dict | None = None, **kwargs) -> None:
    cfg, fmt = {}, {}
    for col, c in (column_config or {}).items():
        if isinstance(c, dict) and "_vn" in c:
            kind, d = c["_vn"]
            fmt[col] = (lambda x, d=d: pct(x, d)) if kind == "pct" else (lambda x, d=d: num(x, d))
            if c["label"] != col:
                cfg[col] = st.column_config.Column(c["label"])
        else:
            cfg[col] = c
    for col in df.columns:
        if col in fmt or col in cfg or df[col].dtype == bool:
            continue
        if df[col].dtype == object and _is_decimal(df[col]):    # PostgreSQL numeric (ROUND(...)) arrives as Decimal
            fmt[col] = lambda x, d=_decimals(df[col], 4): num(x, d)
        elif pd.api.types.is_integer_dtype(df[col]):
            fmt[col] = num
        elif pd.api.types.is_float_dtype(df[col]):    # computed in Python: at most 2 decimals
            fmt[col] = lambda x, d=_decimals(df[col], 2): num(x, d)
        elif df[col].isna().any():
            fmt[col] = str
    # Streamlit shows a missing cell as "None" whatever the Styler says, so a column with gaps is turned
    # into text here (it then sorts as text; only a few log columns have gaps).
    df = df.copy()
    for col in [c for c in df.columns if df[c].isna().any()]:
        f = fmt.pop(col, str)
        df[col] = df[col].map(lambda x, f=f: "–" if pd.isna(x) else f(x))
    kwargs.setdefault("hide_index", True)
    kwargs.setdefault("width", "stretch")
    data = df.style.format(fmt) if fmt else df
    st.dataframe(data, column_config=cfg or None, **kwargs)
