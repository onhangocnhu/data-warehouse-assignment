"""Generate every data figure of the report from the database and the analysis results.

Figures are typeset through matplotlib's PGF backend, so pdflatex draws all text with the same vntex
fonts as the report, then rasterised to PNG at 300 dpi with pdftoppm (poppler, shipped with MiKTeX and
TeX Live). The PNG carries its resolution, so LaTeX prints it at the size it was built: FULL = text
width; include it WITHOUT a width option.

Output: latex-report/Pictures/fig-*.png
Usage:  python -m src.report.make_figures            (all figures)
        python -m src.report.make_figures dss        (only figures whose function name contains 'dss')
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("pgf")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter
from PIL import Image
from sqlalchemy import create_engine, text

from src.eda.run_eda import load_raw, raw_delivery_days
from src.etl.config import ROOT, SQLALCHEMY_URL

OUT = ROOT / "latex-report" / "Pictures"
OLAP = ROOT / "src" / "olap" / "results"
DSS = ROOT / "src" / "dss" / "results"
EDA = ROOT / "src" / "eda" / "results"
DPI = 300

# ---------------------------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------------------------
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, MUTED, GRID, AXIS, SOFT = "#0b0b0b", "#52514e", "#898781", "#e6e5df", "#c3c2b7", "#d3d1ca"
REGIONS = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]
REGION_COLOR = dict(zip(REGIONS, [BLUE, ORANGE, AQUA, YELLOW, MAGENTA]))
SEQ = LinearSegmentedColormap.from_list("seq_blue", ["#eef5fd", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"])
DIV = LinearSegmentedColormap.from_list("div", ["#b4441a", "#eb6834", "#f6b89a", "#f7f7f5", "#a9c9f2", "#2a78d6", "#184f95"])
FULL = 6.05                       # inches = text width of the report (155 mm)

plt.rcParams.update({
    "pgf.texsystem": "pdflatex", "pgf.rcfonts": False,
    "pgf.preamble": r"\usepackage[utf8]{vntex}\usepackage{xcolor}",
    "font.family": "serif", "font.size": 9.5, "axes.titlesize": 9.5, "axes.labelsize": 9.5,
    "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8.5,
    "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.5, "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "xtick.major.size": 0, "ytick.major.size": 0, "xtick.major.pad": 4,
    "ytick.major.pad": 4, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK2,
    "text.color": INK, "legend.frameon": False, "legend.handlelength": 1.0, "legend.handleheight": 0.8,
    "legend.borderaxespad": 0.2, "figure.facecolor": "white", "figure.constrained_layout.use": True,
    "figure.constrained_layout.h_pad": 0.03, "figure.constrained_layout.w_pad": 0.03,
})

ENGINE = None


def q(sql: str) -> pd.DataFrame:
    global ENGINE
    ENGINE = ENGINE or create_engine(SQLALCHEMY_URL)
    with ENGINE.connect() as c:
        return pd.read_sql(text(sql), c)


def vn(x, d=0):
    """Vietnamese number: 1.234.567,8"""
    s = f"{x:,.{d}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x, d=0):
    return vn(x, d) + r"\%"


def tt(name: str) -> str:
    """Category / code name in the report's \\code{} style."""
    return r"\texttt{" + name.replace("_", r"\_") + "}"


VN_INT = FuncFormatter(lambda x, _: vn(x))
VN_PCT = FuncFormatter(lambda x, _: pct(x))


def style_axis(ax, grid="y"):
    ax.grid(axis="x" if grid == "y" else "y", visible=False)
    ax.grid(axis=grid, visible=True)
    if grid == "x":
        ax.spines["bottom"].set_visible(False)
        ax.spines["left"].set_visible(True)


def panel_title(ax, s):
    ax.set_title(s, loc="left", fontsize=9.5, fontweight="bold", pad=6)


def legend_top(ax, ncol, **kw):
    return ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=ncol, borderaxespad=0.3,
                     columnspacing=1.4, handletextpad=0.5, **kw)


def save(fig, name):
    """Typeset to PDF in a temporary folder, rasterise to PNG and stamp the resolution."""
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / f"{name}.pdf"
        fig.savefig(pdf)
        subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-singlefile", str(pdf), str(Path(tmp) / name)],
                       check=True)
        with Image.open(Path(tmp) / f"{name}.png") as im:
            im.convert("RGB").save(OUT / f"{name}.png", dpi=(DPI, DPI), optimize=True)
    plt.close(fig)
    print("  ", name)


# =============================================================================================
# Part 1 - source data
# =============================================================================================
def fig_orders_by_month():
    df = q("""SELECT date_trunc('month', order_purchase_timestamp::timestamp)::date AS m, COUNT(*) AS n
              FROM staging.raw_orders GROUP BY 1""")
    months = pd.date_range("2016-09-01", "2018-10-01", freq="MS")
    df = df.set_index(pd.to_datetime(df.m)).reindex(months, fill_value=0)
    stable = (months >= "2017-01-01") & (months <= "2018-08-01")
    fig, ax = plt.subplots(figsize=(FULL, 2.35))
    colors = np.where(stable, BLUE, SOFT)
    colors[list(months).index(pd.Timestamp("2017-11-01"))] = ORANGE
    ax.bar(months, df.n, width=24, color=colors, edgecolor="white", linewidth=0.6)
    style_axis(ax)
    ax.yaxis.set_major_formatter(VN_INT)
    ax.set_ylabel("Số đơn hàng")
    ax.set_ylim(0, 8700)
    ticks = months[1::3]
    ax.set_xticks(ticks, [t.strftime("%m/%Y") for t in ticks])
    ax.annotate(r"\textbf{11/2017: 7.544 đơn} (Black Friday)", (pd.Timestamp("2017-11-01"), 7544),
                xytext=(pd.Timestamp("2017-03-15"), 8000), fontsize=8.5, color=INK2, va="center",
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6, shrinkB=2))
    ax.text(pd.Timestamp("2016-08-25"), 3600, "Cột xám: giai đoạn ít dữ liệu,\nngoài cửa sổ 01/2017-08/2018",
            fontsize=8, color=MUTED, va="bottom", linespacing=1.3)
    save(fig, "fig-don-hang-theo-thang")


def fig_delivery_time():
    df = q("""SELECT delivery_days::float AS d, (delivered_ts::date - estimated_ts::date) AS delay
              FROM staging.stg_orders WHERE order_status = 'delivered' AND delivered_ts IS NOT NULL""")
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL, 2.45))
    a.hist(df.d.clip(upper=60), bins=np.arange(0, 61, 1), color=BLUE, edgecolor="white", linewidth=0.4)
    med = df.d.median()
    a.axvline(med, color=INK, lw=0.8)
    a.text(med + 1.2, a.get_ylim()[1] * 0.93, f"trung vị {vn(med, 1)} ngày", fontsize=8.5, color=INK, va="top")
    style_axis(a)
    a.set_xlabel("Số ngày từ lúc mua đến lúc nhận (cắt ở 60)")
    a.set_ylabel("Số đơn hàng")
    a.yaxis.set_major_formatter(VN_INT)
    panel_title(a, "(a) Thời gian giao hàng")
    delay = df.delay.clip(-45, 30)
    counts, edges = np.histogram(delay, bins=np.arange(-45, 31, 1))
    b.bar(edges[:-1], counts, width=1, align="edge", color=np.where(edges[:-1] >= 1, ORANGE, SOFT),
          edgecolor="white", linewidth=0.4)
    b.axvline(0.5, color=INK, lw=0.8)
    dmed = df.delay.median()
    b.axvline(dmed + 0.5, color=INK, lw=0.8, ls="--")
    b.set_ylim(0, counts.max() * 1.3)
    b.text(dmed - 0.3, counts.max() * 1.27, f"trung vị: {vn(abs(dmed), 0)} ngày\ntrước hạn",
           fontsize=8.5, color=INK, ha="right", va="top", linespacing=1.2)
    late = (df.delay > 0).mean() * 100
    b.text(3, counts.max() * 0.5, r"\textbf{Trễ hạn: " + pct(late, 2) + "}", color=ORANGE, fontsize=8.5)
    b.text(-44, counts.max() * 0.45, "Sớm hoặc\nđúng hạn", color=INK2, fontsize=8.5, va="top")
    style_axis(b)
    b.set_xlabel("Ngày nhận $-$ ngày giao dự kiến (ngày)")
    b.yaxis.set_major_formatter(VN_INT)
    panel_title(b, "(b) So với ngày giao dự kiến")
    save(fig, "fig-thoi-gian-giao-hang")


def fig_review_distribution():
    df = q("SELECT review_score AS s, COUNT(*) AS n FROM staging.stg_reviews GROUP BY 1 ORDER BY 1")
    share = df.n / df.n.sum() * 100
    fig, ax = plt.subplots(figsize=(FULL * 0.62, 2.25))
    colors = [ORANGE, ORANGE, SOFT, SOFT, BLUE]
    ax.bar([f"{s} sao" for s in df.s], share, width=0.6, color=colors)
    for x, p, n in zip(range(len(df)), share, df.n):
        ax.text(x, p + 1.5, r"\textbf{" + pct(p, 1) + "}\n" + f"{vn(n)} đơn", ha="center", fontsize=8,
                color=INK2, linespacing=1.2)
    ax.set_ylim(0, 72)
    style_axis(ax)
    ax.set_yticks([])
    ax.spines["bottom"].set_color(AXIS)
    save(fig, "fig-phan-bo-danh-gia")


def fig_geolocation():
    df = q("""SELECT DISTINCT geolocation_lat::float AS lat, geolocation_lng::float AS lng
              FROM staging.raw_geolocation""")
    inside = df.lat.between(-33.75, 5.27) & df.lng.between(-73.99, -34.79)
    out = df[~inside]
    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL, 2.9), gridspec_kw={"width_ratios": [1.45, 1]})
    a.hexbin(df[inside].lng, df[inside].lat, gridsize=45, bins="log", cmap=SEQ, mincnt=1, linewidths=0.1)
    a.scatter(out.lng, out.lat, s=16, color=ORANGE, edgecolor="white", linewidth=0.7, zorder=3)
    a.add_patch(plt.Rectangle((-73.99, -33.75), 73.99 - 34.79, 33.75 + 5.27, fill=False, ec=INK2, lw=0.7, ls="-"))
    a.text(-72, 8, "khung lãnh thổ Brazil", fontsize=8, color=INK2)
    a.text(20, -33, f"{len(out)} điểm phân biệt\n(42 dòng) nằm ngoài\nlãnh thổ Brazil", fontsize=8,
           color=ORANGE, linespacing=1.25)
    a.set_xlabel("Kinh độ")
    a.set_ylabel("Vĩ độ")
    a.grid(True)
    panel_title(a, "(a) Toàn bộ tọa độ phân biệt")
    hb = b.hexbin(df[inside].lng, df[inside].lat, gridsize=38, bins="log", cmap=SEQ, mincnt=1, linewidths=0.1)
    b.set_xlim(-74, -34)
    b.set_ylim(-34, 6)
    b.set_aspect("equal")
    b.set_xlabel("Kinh độ")
    b.grid(True)
    panel_title(b, "(b) Mật độ trong lãnh thổ")
    cb = fig.colorbar(hb, ax=b, fraction=0.05, pad=0.03)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.5)
    cb.set_label("Số điểm (thang log)", fontsize=8)
    save(fig, "fig-toa-do-geolocation")


# =============================================================================================
# Part 2 - exploratory data analysis (src/eda/run_eda.py)
# =============================================================================================
def fig_eda_missing():
    # every column with missing values on its own bar (no grouping), largest share on top
    m = pd.read_csv(EDA / "missing.csv")
    m = m[m.missing > 0].sort_values("share", ascending=False, kind="stable").reset_index(drop=True)
    color = {"order_reviews": ORANGE, "orders": BLUE, "products": AQUA}
    fig, ax = plt.subplots(figsize=(FULL, 3.7))
    y = np.arange(len(m))[::-1]           # first row on top; ties keep the column order of the file
    vals = m.share * 100
    ax.barh(y, vals, height=0.62, color=[color[f] for f in m.file])
    for yi, n, v in zip(y, m.missing, vals):
        d = 1 if v >= 1 else 2 if v >= 0.1 else 3
        ax.text(v * 1.18, yi, f"{vn(n)} dòng ({pct(v, d)})", va="center", fontsize=7.8, color=INK2)
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_xlim(0.003, 900)
    ax.set_ylim(-0.6, len(m) - 0.4)
    ax.set_xticks([0.01, 0.1, 1, 10, 100], ["0,01\\%", "0,1\\%", "1\\%", "10\\%", "100\\%"])
    ax.set_yticks(y, [tt(c) for c in m.column], fontsize=7.8)
    ax.set_xlabel("Tỷ lệ giá trị thiếu trên số dòng của tập tin (thang log)")
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    handles = [plt.Rectangle((0, 0), 1, 1, color=color[k]) for k in ["orders", "order_reviews", "products"]]
    legend_top(ax, 3, handles=handles, labels=[tt("orders"), tt("order_reviews"), tt("products")])
    save(fig, "fig-eda-gia-tri-thieu")


def fig_eda_outliers():
    items, products = load_raw("order_items"), load_raw("products")
    o = pd.read_csv(EDA / "outliers.csv").set_index("measure")
    series = [("price", pd.to_numeric(items.price), "(a) Giá bán một sản phẩm (BRL)", True),
              ("freight_value", pd.to_numeric(items.freight_value), "(b) Phí vận chuyển một dòng (BRL)", False),
              ("product_weight_g", pd.to_numeric(products.product_weight_g).dropna(), "(c) Khối lượng sản phẩm (g)", True),
              ("delivery_days", raw_delivery_days(load_raw("orders")), "(d) Thời gian giao hàng (ngày)", False)]
    fig, axes = plt.subplots(2, 2, figsize=(FULL, 2.9))
    for ax, (key, s, title, log) in zip(axes.flat, series):
        r = o.loc[key]
        data = s[s > 0] if log else s
        ax.boxplot(data, orientation="horizontal", widths=0.5, whis=1.5, patch_artist=True, showfliers=False,
                   boxprops=dict(facecolor="#dbe9fa", edgecolor=BLUE, lw=0.8),
                   medianprops=dict(color=BLUE, lw=1.4), whiskerprops=dict(color=BLUE, lw=0.8),
                   capprops=dict(color=BLUE, lw=0.8))
        # tens of thousands of outliers would overflow TeX: draw a sample of 300 plus the maximum
        out = data[data > r.upper_fence]
        pts = pd.concat([out.sample(min(300, len(out)), random_state=1), out.nlargest(1)])
        jitter = np.random.default_rng(1).uniform(-0.12, 0.12, len(pts))
        ax.scatter(pts, 1 + jitter, s=4, color=ORANGE, alpha=0.35, lw=0)
        if log:
            ax.set_xscale("log")
            ax.minorticks_off()
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: vn(v)))
        ax.set_yticks([])
        style_axis(ax, "x")
        ax.spines["left"].set_visible(False)
        ax.text(0.99, 0.93, f"trung vị {vn(r['median'], 1)}; lớn nhất {vn(r['max'], 1)}\n"
                + r"\textcolor[HTML]{eb6834}{" + f"{vn(r.n_above_fence)} giá trị ngoại lai ({pct(r.share_above_fence * 100, 1)})" + "}",
                transform=ax.transAxes, ha="right", va="top", fontsize=7.5, color=INK2, linespacing=1.3)
        ax.set_ylim(0.5, 1.75)
        ax.tick_params(axis="x", labelsize=7.8)
        panel_title(ax, title)
    save(fig, "fig-eda-ngoai-lai")


CORR_VI = {"approval_days": "Thời gian duyệt", "handling_days": "Thời gian chuẩn bị", "shipping_days": "Thời gian vận chuyển",
           "delivery_days": "Thời gian giao hàng", "promised_days": "Số ngày hứa giao", "order_value": "Giá trị đơn",
           "order_freight": "Phí vận chuyển", "weight_g": "Khối lượng", "distance_km": "Khoảng cách",
           "is_late": "Giao trễ", "review_score": "Điểm đánh giá"}


def fig_eda_correlation():
    c = pd.read_csv(EDA / "correlation.csv", index_col=0)
    labels = [CORR_VI[k] for k in c.index]
    fig, ax = plt.subplots(figsize=(FULL, 4.15))
    data = c.values.copy()
    data[np.triu_indices_from(data, k=1)] = np.nan
    m = ax.pcolormesh(np.ma.masked_invalid(data), cmap=DIV, vmin=-1, vmax=1, edgecolors="white", linewidth=1.2)
    for i in range(len(c)):
        for j in range(i + 1):
            v = data[i, j]
            ax.text(j + 0.5, i + 0.5, vn(v, 2), ha="center", va="center", fontsize=7.2,
                    color="white" if abs(v) > 0.55 else INK)
    ax.invert_yaxis()
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(len(c)) + 0.5, labels, rotation=40, ha="right", rotation_mode="anchor", fontsize=7.8)
    ax.set_yticks(np.arange(len(c)) + 0.5, labels, fontsize=7.8)
    ax.set_aspect("equal")
    cb = fig.colorbar(m, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.5)
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: vn(v, 1)))
    cb.set_label("Hệ số tương quan Spearman", fontsize=8)
    save(fig, "fig-eda-tuong-quan")


def fig_eda_late_by_bin():
    b = pd.read_csv(EDA / "late_by_bin.csv")
    panels = [("distance_km", "(a) Khoảng cách giao", "nghìn km", ["<0,1", "0,1-0,5", "0,5-1", "1-2", ">2"]),
              ("promised_days", "(b) Số ngày hứa giao", "ngày", [r"$\leq$15", "16-20", "21-25", "26-30", ">30"]),
              ("handling_days", "(c) Chuẩn bị hàng", "ngày", [r"$\leq$1", "1-3", "3-5", "5-10", ">10"])]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.6), sharey=True)
    fig.get_layout_engine().set(wspace=0.08)
    for ax, (attr, title, unit, labels) in zip(axes, panels):
        g = b[b.attribute == attr]
        vals = g.late_rate * 100
        ax.axhline(6.77, color=INK2, lw=0.6, ls=(0, (3, 2)), zorder=1)
        ax.bar(range(len(g)), vals, width=0.62, color=np.where(vals == vals.max(), ORANGE, BLUE), zorder=2)
        for i, v in enumerate(vals):
            ax.text(i, v + 0.7, vn(v, 1), ha="center", fontsize=7.5, color=INK2,
                    bbox=dict(fc="white", ec="none", pad=0.4))
        ax.set_xticks(range(len(g)), labels, fontsize=7.0)
        style_axis(ax)
        ax.yaxis.set_major_formatter(VN_PCT)
        ax.tick_params(axis="y", labelleft=True)
        ax.set_xlabel(unit, fontsize=8)
        ax.set_title(title, loc="center", fontsize=8.8, fontweight="bold", pad=6)
    axes[0].set_ylabel("Tỷ lệ giao trễ")
    axes[0].set_ylim(0, 33)
    save(fig, "fig-eda-ty-le-tre-theo-nhom")


# =============================================================================================
# Part 3 - OLAP on the Data Mart
# =============================================================================================
def fig_rollup_month():
    df = q("""SELECT d.year, d.month, SUM(f.price) AS revenue
              FROM dm.fact_sales f JOIN dm.dim_date d ON d.date_key = f.purchase_date_key
              WHERE f.order_status NOT IN ('canceled', 'unavailable')
                AND d.full_date BETWEEN '2017-01-01' AND '2018-08-31'
              GROUP BY d.year, d.month ORDER BY 1, 2""")
    x = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
    y = df.revenue / 1e6
    fig, ax = plt.subplots(figsize=(FULL, 2.35))
    ax.fill_between(x, y, color=BLUE, alpha=0.08, lw=0)
    ax.plot(x, y, color=BLUE, lw=1.8, marker="o", ms=4, mec="white", mew=0.8)
    style_axis(ax)
    ax.set_ylabel("Doanh thu (triệu BRL)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: vn(v, 1)))
    ax.set_ylim(0, 1.2)
    ax.set_xticks(x[::3], [t.strftime("%m/%Y") for t in x[::3]])
    peak = int(y.idxmax())
    ax.annotate(r"\textbf{11/2017: " + vn(y[peak], 2) + r" triệu BRL}", (x[peak], y[peak]),
                xytext=(pd.Timestamp("2017-04-01"), 1.08), fontsize=8.5, color=INK2, va="center",
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.6))
    ax.text(x.iloc[-1], y.iloc[-1] + 0.07, vn(y.iloc[-1], 2), ha="center", fontsize=8, color=INK2)
    ax.text(x.iloc[0], y.iloc[0] + 0.07, vn(y.iloc[0], 2), ha="center", fontsize=8, color=INK2)
    save(fig, "fig-olap-rollup-thang")


def fig_drilldown_state():
    df = q("""SELECT st.region, st.state_code, COUNT(*) AS n, AVG(o.is_late) * 100 AS late
              FROM dm.v_order o
              JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
              JOIN dm.dim_city ci ON ci.city_key = cu.city_key
              JOIN dm.dim_state st ON st.state_key = ci.state_key
              WHERE o.is_late IS NOT NULL GROUP BY 1, 2 ORDER BY late""")
    fig, ax = plt.subplots(figsize=(FULL, 4.3))
    y = np.arange(len(df))
    ax.barh(y, df.late, height=0.68, color=df.region.map(REGION_COLOR), edgecolor="white", linewidth=0.5)
    ax.set_yticks(y, [rf"\textbf{{{s}}} \color[HTML]{{898781}}{{{vn(n)}}}" for s, n in zip(df.state_code, df.n)],
                  fontsize=8)
    ax.axvline(6.77, color=INK, lw=0.7)
    ax.text(6.95, -1.15, "trung bình toàn quốc 6,77\\%", fontsize=8, color=INK, va="center")
    for yi, v in zip(y, df.late):
        ax.text(v + 0.25, yi, pct(v, 1), va="center", fontsize=7.5, color=INK2)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.set_ylim(-1.7, len(df) - 0.3)
    ax.set_xlim(0, 24)
    ax.xaxis.set_major_formatter(VN_PCT)
    ax.set_xlabel("Tỷ lệ giao trễ của đơn đã giao (số xám: số đơn đã giao)")
    handles = [plt.Rectangle((0, 0), 1, 1, color=REGION_COLOR[r]) for r in REGIONS]
    ax.legend(handles, REGIONS, loc="lower right", bbox_to_anchor=(1, 0.04), title="Vùng", title_fontsize=8.5,
              alignment="left")
    save(fig, "fig-olap-drilldown-bang")


def fig_dice():
    df = pd.read_csv(OLAP / "q05_dice_q4_2017.csv")
    piv = df.pivot(index="category_name_en", columns="state_code", values="revenue")[["SP", "RJ", "MG"]]
    piv = piv.loc[piv.sum(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(FULL, 2.7))
    y = np.arange(len(piv))
    h = 0.27
    for i, (st, col) in enumerate(zip(piv.columns, [BLUE, ORANGE, AQUA])):
        ax.barh(y + (1 - i) * h, piv[st] / 1000, height=h, color=col, label=st, edgecolor="white", linewidth=0.6)
    for yi, v in zip(y, piv.SP / 1000):
        ax.text(v + 1, yi + h, vn(v, 1), va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [tt(c) for c in piv.index], fontsize=8)
    ax.set_xlabel("Doanh thu quý 4/2017 (nghìn BRL)")
    ax.xaxis.set_major_formatter(VN_INT)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 98)
    legend_top(ax, 3, title=None)
    save(fig, "fig-olap-dice")


def heatmap(ax, data, vmin, vmax, fmt, light_threshold, fontsize=8):
    m = ax.pcolormesh(data, cmap=SEQ, vmin=vmin, vmax=vmax, edgecolors="white", linewidth=1.2)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            if not np.isnan(v):
                ax.text(j + 0.5, i + 0.5, fmt(v), ha="center", va="center", fontsize=fontsize,
                        color="white" if v > light_threshold else INK)
    ax.invert_yaxis()
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    return m


def fig_pivot():
    df = pd.read_csv(OLAP / "q06_pivot_review_category_region.csv").set_index("category")
    df = df[["sudeste", "sul", "centro_oeste", "nordeste", "norte"]]
    fig, ax = plt.subplots(figsize=(FULL * 0.86, 3.3))
    m = heatmap(ax, df.values, 3.6, 4.45, lambda v: vn(v, 2), 4.12)
    ax.set_xticks(np.arange(5) + 0.5, REGIONS)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(df)) + 0.5, [tt(c) for c in df.index], fontsize=8)
    cb = fig.colorbar(m, ax=ax, fraction=0.035, pad=0.02)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.5)
    cb.ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: vn(v, 1)))
    cb.set_label("Điểm đánh giá trung bình", fontsize=8)
    save(fig, "fig-olap-pivot")


def fig_late_vs_review():
    df = q("""SELECT is_late, review_score AS s, COUNT(*) AS n FROM dm.v_order
              WHERE is_late IS NOT NULL AND review_score IS NOT NULL GROUP BY 1, 2""")
    df["share"] = df.n / df.groupby("is_late").n.transform("sum") * 100
    piv = df.pivot(index="s", columns="is_late", values="share")
    fig, ax = plt.subplots(figsize=(FULL * 0.8, 2.5))
    x = np.arange(5)
    ax.bar(x - 0.2, piv[0], width=0.38, color=BLUE, label="Giao đúng hạn (trung bình 4,29 điểm)")
    ax.bar(x + 0.2, piv[1], width=0.38, color=ORANGE, label="Giao trễ (trung bình 2,27 điểm)")
    for xi, v0, v1 in zip(x, piv[0], piv[1]):
        ax.text(xi - 0.2, v0 + 1.2, pct(v0, 1), ha="center", fontsize=7.5, color=INK2)
        ax.text(xi + 0.2, v1 + 1.2, pct(v1, 1), ha="center", fontsize=7.5, color=INK2)
    ax.set_xticks(x, [f"{i} sao" for i in range(1, 6)])
    ax.set_yticks([])
    style_axis(ax)
    ax.set_ylim(0, 70)
    legend_top(ax, 2)
    save(fig, "fig-tre-va-danh-gia")


def fig_stage_durations():
    df = pd.read_csv(OLAP / "q09_stage_durations_region.csv").dropna(subset=["region"])
    df = df.sort_values("avg_delivery_days")
    fig, ax = plt.subplots(figsize=(FULL, 2.2))
    y = np.arange(len(df))
    left = np.zeros(len(df))
    for col, lab, colr in [("avg_approval_days", "Duyệt đơn", INK2), ("avg_handling_days", "Người bán chuẩn bị hàng", AQUA),
                           ("avg_shipping_days", "Vận chuyển", BLUE)]:
        ax.barh(y, df[col], left=left, height=0.6, color=colr, label=lab, edgecolor="white", linewidth=1)
        left += df[col].to_numpy()
    for yi, (tot, ship) in enumerate(zip(df.avg_delivery_days, df.avg_shipping_days)):
        ax.text(left[yi] + 0.35, yi, r"\textbf{" + vn(tot, 1) + "} ngày", va="center", fontsize=8, color=INK)
    ax.set_yticks(y, df.region)
    ax.set_xlabel("Số ngày trung bình")
    ax.set_xlim(0, 26)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    legend_top(ax, 3)
    save(fig, "fig-olap-cong-doan")


def fig_route_heatmap():
    df = pd.read_csv(OLAP / "q08_route_matrix.csv")
    rows = df.groupby("seller_state").lots.sum().sort_values(ascending=False).index
    cols = df.groupby("customer_state").lots.sum().sort_values(ascending=False).index
    piv = df.pivot(index="seller_state", columns="customer_state", values="late_pct").loc[rows, cols]
    fig, ax = plt.subplots(figsize=(FULL, 2.45))
    m = heatmap(ax, piv.values, 0, 24, lambda v: vn(v, 0), 11, fontsize=7.2)
    ax.set_xticks(np.arange(len(cols)) + 0.5, cols, fontsize=7.8)
    ax.set_yticks(np.arange(len(rows)) + 0.5, rows, fontsize=7.8)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.set_xlabel("Bang của khách hàng (sắp theo số lô hàng giảm dần)", labelpad=6)
    ax.set_ylabel("Bang của người bán")
    cb = fig.colorbar(m, ax=ax, fraction=0.025, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7.5)
    cb.ax.yaxis.set_major_formatter(VN_PCT)
    cb.set_label("Tỷ lệ trễ", fontsize=8)
    save(fig, "fig-olap-tuyen-giao")


def fig_black_friday():
    df = q("""SELECT d.full_date AS day, COUNT(*) AS orders, AVG(o.is_late) * 100 AS late
              FROM dm.v_order o JOIN dm.dim_date d ON d.date_key = o.purchase_date_key
              WHERE d.full_date BETWEEN '2017-11-01' AND '2017-12-31' GROUP BY 1 ORDER BY 1""")
    df["day"] = pd.to_datetime(df.day)
    bf, bf_end = pd.Timestamp("2017-11-24"), pd.Timestamp("2017-11-29")
    fig, (a, b) = plt.subplots(2, 1, figsize=(FULL, 3.3), sharex=True, gridspec_kw={"height_ratios": [1.25, 1]})
    for ax in (a, b):
        ax.axvspan(bf - pd.Timedelta(hours=12), bf_end + pd.Timedelta(hours=12), color="#fdeee6", zorder=0, lw=0)
    a.bar(df.day, df.orders, width=0.75, color=np.where(df.day == bf, ORANGE, BLUE))
    a.annotate(r"\textbf{24/11/2017: 1.166 đơn}", (bf, 1166), xytext=(10, -4), textcoords="offset points",
               fontsize=8.5, color=INK2, va="top")
    a.set_ylabel("Số đơn mỗi ngày")
    a.yaxis.set_major_formatter(VN_INT)
    style_axis(a)
    panel_title(a, "(a) Số đơn hàng theo ngày đặt")
    b.plot(df.day, df.late, color=ORANGE, lw=1.6)
    b.axhline(6.77, color=MUTED, lw=0.7)
    b.text(df.day.iloc[-1], 7.7, "trung bình toàn kỳ 6,77\\%", ha="right", fontsize=8, color=MUTED)
    b.set_ylabel("Tỷ lệ trễ")
    b.yaxis.set_major_formatter(VN_PCT)
    style_axis(b)
    panel_title(b, "(b) Tỷ lệ trễ của đơn đặt trong ngày")
    ticks = pd.date_range("2017-11-01", "2017-12-31", freq="7D")
    b.set_xticks(ticks, [t.strftime("%d/%m") for t in ticks])
    save(fig, "fig-olap-black-friday")


def fig_category_growth():
    df = pd.read_csv(OLAP / "q12_category_growth.csv").sort_values("growth_pct")
    fig, ax = plt.subplots(figsize=(FULL, 3.2))
    y = np.arange(len(df))
    colors = np.where(df.growth_pct >= 200, BLUE, SOFT)
    ax.barh(y, df.growth_pct, height=0.66, color=colors)
    for yi, v in zip(y, df.growth_pct):
        ax.text(v + 3, yi, "+" + pct(v, 1), va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [tt(c) for c in df.category_name_en], fontsize=7.8)
    ax.xaxis.set_major_formatter(VN_PCT)
    ax.set_xlabel("Tăng trưởng doanh thu 01-08/2018 so với cùng kỳ 2017 (xanh: tăng hơn gấp ba)")
    ax.set_xlim(0, 300)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    save(fig, "fig-olap-tang-truong-nganh")


def fig_seller_vs_orders():
    df = pd.read_csv(OLAP / "q11_sellers_vs_customers_by_state.csv").head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(FULL, 2.8))
    y = np.arange(len(df))
    ax.barh(y + 0.2, df.order_share_pct, height=0.38, color=BLUE, label="Tỷ trọng đơn hàng")
    ax.barh(y - 0.2, df.seller_share_pct, height=0.38, color=ORANGE, label="Tỷ trọng người bán")
    for yi, v1, v2 in zip(y, df.order_share_pct, df.seller_share_pct):
        ax.text(v1 + 0.6, yi + 0.2, pct(v1, 1), va="center", fontsize=7.3, color=INK2)
        ax.text(v2 + 0.6, yi - 0.2, pct(v2, 1), va="center", fontsize=7.3, color=INK2)
    ax.set_yticks(y, df.state_code)
    ax.xaxis.set_major_formatter(VN_PCT)
    ax.set_xlim(0, 66)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    legend_top(ax, 2)
    save(fig, "fig-olap-nguoi-ban-khach-hang")


# =============================================================================================
# Part 4 - decision support system
# =============================================================================================
TEST = "2018-06"


def fig_dss_model_compare():
    s = pd.read_csv(DSS / "improved_summary.csv")
    s = s[s.period.str.startswith("test") & (s.stage == "handover")].set_index("model")
    names = [("random", "Chọn ngẫu nhiên"), ("rule_route_history", "Luật: tỷ lệ trễ lịch sử của tuyến"),
             ("rule_days_left", "Luật: số ngày còn lại tới hạn"),
             ("hgb_base_features", "Gradient Boosting, chỉ đặc trưng tĩnh và lịch sử"),
             ("logistic_regression", "Logistic Regression"),
             ("lr_tuned_backlog", "TK mở rộng: Logistic Regression + tồn đọng"),
             ("hgb_tuned", "TK mở rộng: Gradient Boosting"),
             ("hgb_tuned_backlog", "TK mở rộng: Gradient Boosting + tồn đọng"),
             ("ensemble", "TK mở rộng: kết hợp ba mô hình"),
             ("hgb_v1", r"\textbf{Gradient Boosting (mô hình được chọn)}")]
    fig, ax = plt.subplots(figsize=(FULL, 3.3))
    vals = [10.0 if k == "random" else s.loc[k, "recall_top10"] * 100 for k, _ in names]
    y = np.arange(len(names))
    ax.barh(y, vals, height=0.62, color=[BLUE if k == "hgb_v1" else SOFT for k, _ in names])
    ax.axvline(40, color=ORANGE, lw=0.9, ls=(0, (3, 2)), zorder=1)
    for yi, v in zip(y, vals):
        ax.text(v + 0.6, yi, pct(v, 1), va="center", fontsize=8, color=INK2, bbox=dict(fc="white", ec="none", pad=0.5))
    ax.text(40.6, -0.62, "chỉ tiêu 40\\%", fontsize=8, color=ORANGE, va="center")
    ax.set_yticks(y, [n for _, n in names], fontsize=8)
    ax.set_xlim(0, 50)
    ax.set_ylim(-0.95, len(names) - 0.5)
    ax.xaxis.set_major_formatter(VN_PCT)
    ax.set_xlabel("Đơn trễ bắt được khi cảnh báo 10\\% đơn rủi ro nhất")
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    save(fig, "fig-dss-so-sanh-mo-hinh")


def fig_dss_by_month():
    wf = pd.read_csv(DSS / "walkforward.csv")
    wf = wf[wf.stage == "handover"]
    months = sorted(wf.month.unique())
    x = np.arange(len(months))
    fig, (a, b) = plt.subplots(2, 1, figsize=(FULL, 3.4), sharex=True, gridspec_kw={"height_ratios": [1, 1.5]})
    test = [i for i, m in enumerate(months) if m >= TEST]
    for ax in (a, b):
        ax.axvspan(test[0] - 0.5, test[-1] + 0.5, color="#eef5fd", lw=0, zorder=0)
    prev = wf[wf.model == "hgb_v1"].set_index("month").loc[months, "prevalence"] * 100
    a.bar(x, prev, width=0.62, color=SOFT)
    a.yaxis.set_major_formatter(VN_PCT)
    a.set_ylabel("Tỷ lệ trễ")
    style_axis(a)
    panel_title(a, "(a) Tỷ lệ trễ của các đơn bàn giao trong tháng")
    for model, col, lab, lw in [("hgb_v1", BLUE, "Gradient Boosting (được chọn)", 1.8),
                                ("ensemble", AQUA, "Kết hợp ba mô hình", 1.1),
                                ("rule_route_history", MUTED, "Luật: tỷ lệ trễ của tuyến", 1.1)]:
        g = wf[wf.model == model].set_index("month").loc[months]
        b.plot(x, g.recall_top10 * 100, color=col, lw=lw, marker="o", ms=3.4 if lw > 1.5 else 2.6, mec="white",
               mew=0.6, label=lab, zorder=3 if lw > 1.5 else 2)
    b.axhline(10, color=MUTED, lw=0.6, ls=(0, (3, 2)))
    b.text(0, 11.5, "chọn ngẫu nhiên: 10\\%", fontsize=7.8, color=MUTED)
    b.yaxis.set_major_formatter(VN_PCT)
    b.set_ylabel("Đơn trễ bắt được")
    style_axis(b)
    panel_title(b, "(b) Tỷ lệ đơn trễ bắt được khi cảnh báo 10\\% đơn, huấn luyện lại mỗi tháng")
    b.legend(loc="upper left", ncol=3, bbox_to_anchor=(0, 1.0))
    b.set_ylim(0, 62)
    a.text(test[0] - 0.35, a.get_ylim()[1] * 0.97, "tập test", fontsize=8, color=BLUE, va="top")
    b.set_xticks(x, [pd.Period(m, "M").strftime("%m/%y") for m in months], fontsize=8)
    save(fig, "fig-dss-theo-thang")


def fig_dss_capacity():
    g = pd.read_csv(DSS / "capacity_curve.csv")
    fig, ax = plt.subplots(figsize=(FULL * 0.78, 2.6))
    ax.plot(g.capacity_pct, g.recall * 100, color=BLUE, lw=1.8, label="DSS (mô hình + luật đã quá hạn)")
    for k in (5, 10, 15):
        r = g[g.capacity_pct == k].iloc[0]
        ax.plot(k, r.recall * 100, "o", color=BLUE, ms=4.5, mec="white", mew=0.8)
        ax.text(k - 0.5, r.recall * 100 + 3.5, r"\textbf{" + pct(r.recall * 100, 0) + "}", fontsize=8, color=BLUE,
                ha="right")
    ax.plot([0, 30], [0, 30], color=MUTED, lw=0.8, label="Chọn ngẫu nhiên")
    for k, lab in [(5, "ĐỎ"), (15, "ĐỎ + VÀNG")]:
        ax.axvline(k, color=GRID, lw=0.9, zorder=0)
        ax.text(k, 76, lab, ha="center", fontsize=7.5, color=INK2)
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 80)
    ax.xaxis.set_major_formatter(VN_PCT)
    ax.yaxis.set_major_formatter(VN_PCT)
    ax.set_xlabel("Tỷ lệ đơn được cảnh báo mỗi ngày (năng lực xử lý)")
    ax.set_ylabel("Đơn trễ bắt được")
    ax.grid(True)
    ax.legend(loc="lower right")
    save(fig, "fig-dss-nang-luc")


def fig_dss_risk_levels():
    s = pd.read_csv(DSS / "scores.csv")
    g = s.groupby("risk_level").label.agg(["mean", "size"])
    levels = [("GREEN", "XANH", "#9fd8c2"), ("YELLOW", "VÀNG", YELLOW), ("RED", "ĐỎ", ORANGE)]
    fig, ax = plt.subplots(figsize=(FULL * 0.6, 2.2))
    vals = [g.loc[k, "mean"] * 100 for k, _, _ in levels]
    ax.bar([lab for _, lab, _ in levels], vals, width=0.58, color=[c for _, _, c in levels])
    for i, (k, _, _) in enumerate(levels):
        ax.text(i, vals[i] + 1, r"\textbf{" + pct(vals[i], 1) + "}\n" + f"{vn(g.loc[k, 'size'])} đơn",
                ha="center", fontsize=8, color=INK2, linespacing=1.2)
    ax.set_ylim(0, 42)
    ax.set_yticks([])
    style_axis(ax)
    ax.set_ylabel("Tỷ lệ thực sự trễ")
    save(fig, "fig-dss-muc-rui-ro")


def fig_dss_confusion():
    c = pd.read_csv(DSS / "confusion.csv")
    titles = ["(a) Mức ĐỎ: 5\\% đơn mỗi ngày", "(b) ĐỎ + VÀNG: 15\\% đơn mỗi ngày"]
    fig, axes = plt.subplots(1, 2, figsize=(FULL, 2.45))
    for ax, (_, r), title in zip(axes, c.iterrows(), titles):
        cells = [[(r.tp, BLUE, "white"), (r.fn, ORANGE, "white")], [(r.fp, "#fbe0d3", INK), (r.tn, "#dbe9fa", INK)]]
        for i, row in enumerate(cells):
            for j, (v, fc, tc) in enumerate(row):
                ax.add_patch(plt.Rectangle((j, i), 1, 1, fc=fc, ec="white", lw=2))
                ax.text(j + 0.5, i + 0.5, r"\textbf{" + vn(v) + "}", ha="center", va="center", fontsize=10, color=tc)
        ax.set_xlim(0, 2)
        ax.set_ylim(2, 0)
        ax.set_aspect("equal")
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks([0.5, 1.5], ["Cảnh báo", "Không cảnh báo"], fontsize=8)
        ax.set_yticks([0.5, 1.5], ["Thực tế trễ", "Thực tế\nđúng hạn"], fontsize=8)
        ax.xaxis.tick_top()
        ax.text(1, 2.18, f"Precision {vn(r.precision * 100, 1)}\\%\\quad Recall {vn(r.recall * 100, 1)}\\%\n"
                f"F1 {vn(r.f1, 3)}\\quad Accuracy {vn(r.accuracy * 100, 1)}\\%", ha="center", va="top", fontsize=7.8,
                color=INK2, linespacing=1.35)
        ax.set_title(title, loc="center", fontsize=9.5, fontweight="bold", pad=6)
    save(fig, "fig-dss-ma-tran-nham-lan")


FEATURE_VI = {
    "promised_days": "Số ngày hứa giao", "distance_km": "Khoảng cách", "is_cross_state": "Giao liên bang",
    "n_items": "Số sản phẩm", "n_sellers": "Số người bán", "order_value": "Giá trị đơn",
    "order_freight": "Phí vận chuyển", "freight_ratio": "Tỷ lệ phí vận chuyển", "total_weight_g": "Khối lượng",
    "total_volume_cm3": "Thể tích", "approval_days": "Thời gian duyệt", "purchase_month": "Tháng đặt hàng",
    "purchase_dow": "Thứ trong tuần", "days_to_black_friday": "Số ngày tới Black Friday",
    "seller_hist_n": "Số đơn trước đó của người bán", "seller_hist_late": "Tỷ lệ trễ lịch sử của người bán",
    "route_hist_n": "Số đơn trước đó của tuyến", "route_hist_late": "Tỷ lệ trễ lịch sử của tuyến",
    "cstate_hist_late": "Tỷ lệ trễ lịch sử của bang khách", "global_late_7d": "Tỷ lệ trễ toàn sàn 7 ngày",
    "global_late_30d": "Tỷ lệ trễ toàn sàn 30 ngày", "route_late_90d": "Tỷ lệ trễ của tuyến 90 ngày",
    "seller_late_90d": "Tỷ lệ trễ của người bán 90 ngày", "cstate_late_30d": "Tỷ lệ trễ bang khách 30 ngày",
    "route_mean_delivery": "Thời gian giao thường lệ của tuyến", "slack_days": "Số ngày dư so với thường lệ",
    "seller_mean_handling": "Thời gian chuẩn bị TB của người bán", "seller_orders_7d": "Tải đơn của người bán",
    "platform_orders_7d": "Tải đơn toàn sàn 7 ngày", "platform_load_ratio": "Tải đơn so với bình thường",
    "handling_days": "Thời gian chuẩn bị thực tế", "days_left_at_handover": "Số ngày còn lại khi bàn giao",
    "handover_dow": "Thứ bàn giao", "handling_vs_seller": "Chuẩn bị chậm hơn thường lệ",
    "global_late_7d_at_handover": "Tỷ lệ trễ toàn sàn lúc bàn giao", "customer_state": "Bang khách hàng",
    "seller_state": "Bang người bán", "customer_region": "Vùng khách hàng", "main_category": "Ngành hàng chính",
    "global_backlog": "Đơn tồn đọng quá hạn toàn sàn", "cstate_backlog": "Đơn tồn đọng quá hạn tới bang khách",
    "route_backlog": "Đơn tồn đọng quá hạn trên tuyến",
}


def fig_dss_importance():
    imp = pd.read_csv(DSS / "importance.csv")
    g = imp[imp.stage == "handover"].sort_values("importance", ascending=False).head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(FULL * 0.8, 2.5))
    y = np.arange(len(g))
    vals = g.importance * 100
    ax.barh(y, vals, height=0.62, color=BLUE)
    for yi, v in zip(y, vals):
        ax.text(v + 0.4, yi, vn(v, 2), va="center", fontsize=7.5, color=INK2)
    ax.set_yticks(y, [FEATURE_VI.get(f, f) for f in g.feature], fontsize=7.8)
    ax.set_xlim(0, vals.max() * 1.15)
    style_axis(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: vn(v, 0)))
    ax.set_xlabel("Mức giảm PR-AUC khi xáo trộn đặc trưng (điểm \\%)", fontsize=8)
    save(fig, "fig-dss-dac-trung")


FIGURES = [fig_orders_by_month, fig_delivery_time, fig_review_distribution, fig_geolocation,
           fig_eda_missing, fig_eda_outliers, fig_eda_correlation, fig_eda_late_by_bin,
           fig_rollup_month, fig_drilldown_state, fig_dice, fig_pivot, fig_late_vs_review,
           fig_stage_durations, fig_route_heatmap, fig_black_friday, fig_category_growth, fig_seller_vs_orders,
           fig_dss_model_compare, fig_dss_by_month, fig_dss_capacity, fig_dss_risk_levels, fig_dss_confusion,
           fig_dss_importance]


def main(argv=None):
    pattern = (argv or sys.argv[1:] or [""])[0]
    OUT.mkdir(parents=True, exist_ok=True)
    for f in FIGURES:
        if pattern in f.__name__:
            f()


if __name__ == "__main__":
    main()
