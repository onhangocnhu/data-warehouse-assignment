"""Mức độ hài lòng (Chăm sóc khách hàng): review scores, late vs on time, pivot category x region.
OLAP: q07 (late vs review), q06 (pivot)."""
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import query
from src.dashboard.filters import REGIONS, items_cte, orders_cte, sidebar_filters
from src.dashboard.ui import SEQ_BLUE, chart, kpis, num, pct, pct_col, series

st.title("Mức độ hài lòng của khách hàng")
f = sidebar_filters()
p = f.params

k = query(f"""WITH {orders_cte()}
SELECT COUNT(review_score) AS reviews, AVG(review_score) AS avg_review,
       100.0 * AVG((review_score <= 2)::int) FILTER (WHERE review_score IS NOT NULL) AS low_pct,
       100.0 * AVG((review_score = 5)::int)  FILTER (WHERE review_score IS NOT NULL) AS five_pct
FROM orders""", p).iloc[0]
lv = query(f"""WITH {orders_cte()}
SELECT is_late, COUNT(*) AS orders, ROUND(AVG(review_score), 2) AS avg_review,
       ROUND(100.0 * AVG((review_score <= 2)::int), 1) AS low_review_pct,
       ROUND(100.0 * AVG((review_score = 5)::int), 1)  AS five_star_pct
FROM orders WHERE is_late IS NOT NULL AND review_score IS NOT NULL
GROUP BY is_late ORDER BY is_late""", p)
on_time = lv[lv.is_late == 0].avg_review
late = lv[lv.is_late == 1].avg_review
kpis([("Số đánh giá", num(k.reviews)), ("Điểm TB", num(k.avg_review, 2)),
      ("Tỷ lệ 1-2 sao", pct(k.low_pct, 1))])
kpis([("Tỷ lệ 5 sao", pct(k.five_pct, 1)),
      ("Điểm TB đơn giao đúng hạn", num(on_time.iloc[0], 2) if len(on_time) else "–",
       "Đơn có cả trạng thái giao hàng và đánh giá (báo cáo: 4,29)"),
      ("Điểm TB đơn giao trễ", num(late.iloc[0], 2) if len(late) else "–",
       "Đơn có cả trạng thái giao hàng và đánh giá (báo cáo: 2,27)")])

# ---- distribution of stars, on time vs late ----
dist = query(f"""WITH {orders_cte()}
SELECT is_late, review_score, COUNT(*) AS n
FROM orders WHERE is_late IS NOT NULL AND review_score IS NOT NULL
GROUP BY is_late, review_score""", p)
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure()
    for flag, name, i in [(0, "Đúng hạn", 0), (1, "Giao trễ", 1)]:
        d = dist[dist.is_late == flag].sort_values("review_score")
        share = 100 * d.n / d.n.sum() if len(d) else d.n
        fig.add_bar(x=d.review_score.astype(str) + " sao", y=share, name=name, marker_color=series(i),
                    hovertemplate=name + " · %{x}<br>%{y:.1f}% số đơn<extra></extra>")
    fig.update_layout(title="Phân bố điểm đánh giá (% số đơn trong nhóm)", barmode="group", yaxis_ticksuffix="%")
    chart(fig, lv.assign(is_late=lv.is_late.map({0: "Đúng hạn", 1: "Giao trễ"})).rename(columns={
        "is_late": "Giao hàng", "orders": "Số đơn", "avg_review": "Điểm TB", "low_review_pct": "Tỷ lệ 1-2 sao",
        "five_star_pct": "Tỷ lệ 5 sao"}),
        column_config={"Tỷ lệ 1-2 sao": pct_col("Tỷ lệ 1-2 sao", 1), "Tỷ lệ 5 sao": pct_col("Tỷ lệ 5 sao", 1)})

# ---- low-review rate by category ----
with c2:
    cat = query(f"""WITH {items_cte('all')},
ord AS (SELECT order_id, MIN(category) AS category, MIN(review_score) AS score
        FROM items WHERE review_score IS NOT NULL GROUP BY order_id)
SELECT category, COUNT(*) AS orders, ROUND(AVG(score), 2) AS avg_review,
       ROUND(100.0 * AVG((score <= 2)::int), 1) AS low_pct
FROM ord GROUP BY category HAVING COUNT(*) >= 300 ORDER BY low_pct DESC LIMIT 12""", p)
    fig = go.Figure(go.Bar(x=cat.low_pct, y=cat.category, orientation="h", marker_color=series(1),
                           customdata=cat[["orders", "avg_review"]],
                           hovertemplate="%{y}<br>1-2 sao: %{x:.1f}%<br>Điểm TB %{customdata[1]:.2f} · %{customdata[0]:,} đơn<extra></extra>"))
    fig.update_layout(title="Ngành hàng có tỷ lệ đánh giá 1-2 sao cao nhất (≥ 300 đơn)",
                      yaxis_autorange="reversed", xaxis_ticksuffix="%")
    chart(fig, cat.rename(columns={"category": "Ngành hàng", "orders": "Số đơn", "avg_review": "Điểm TB",
                                   "low_pct": "Tỷ lệ 1-2 sao"}),
          column_config={"Tỷ lệ 1-2 sao": pct_col("Tỷ lệ 1-2 sao", 1)})

# ---- pivot: category (rows) x region (columns), with a "swap axes" toggle ----
st.subheader("Pivot: điểm đánh giá trung bình theo ngành hàng và vùng")
top_n = st.slider("Số ngành hàng nhiều đơn nhất", 5, 20, 10, key="sat_topn")
piv = query(f"""WITH {items_cte('all')},
ord AS (SELECT order_id, MIN(category) AS category, MIN(region) AS region, MIN(review_score) AS score
        FROM items WHERE review_score IS NOT NULL GROUP BY order_id),
top AS (SELECT category FROM ord GROUP BY category ORDER BY COUNT(*) DESC LIMIT :n)
SELECT category, region, ROUND(AVG(score), 2) AS avg_review, COUNT(*) AS orders
FROM ord WHERE category IN (SELECT category FROM top)
GROUP BY category, region""", {**p, "n": top_n})
if piv.empty:
    st.info("Không có dữ liệu với bộ lọc hiện tại.")
else:
    swap = st.toggle("Hoán đổi trục (pivot)", key="sat_swap")
    m = piv.pivot(index="category", columns="region", values="avg_review")
    n = piv.pivot(index="category", columns="region", values="orders")
    overall = piv.assign(w=piv.avg_review * piv.orders).groupby("category").w.sum() / n.sum(axis=1)
    m = m.loc[overall.sort_values().index, [r for r in REGIONS if r in m.columns]]
    n = n.loc[m.index, m.columns]
    if swap:
        m, n = m.T, n.T
    fig = go.Figure(go.Heatmap(z=m.values, x=m.columns, y=m.index, customdata=n.values, colorscale=SEQ_BLUE,
                               xgap=2, ygap=2, colorbar=dict(title="điểm"),
                               text=[[num(v, 2) for v in row] for row in m.values], texttemplate="%{text}",
                               hovertemplate="%{y} · %{x}<br>Điểm TB %{z:.2f}<br>%{customdata:,} đơn<extra></extra>"))
    fig.update_layout(title="Điểm TB (màu đậm hơn = điểm cao hơn)")
    chart(fig, m.reset_index().rename(columns={"index": "", "category": "Ngành hàng", "region": "Vùng"}),
          height=max(340, 34 * len(m) + 100))
    st.caption("Ô ít đơn (xem số đơn khi rê chuột) không đủ để kết luận, ví dụ housewares ở Norte (~60 đơn).")
