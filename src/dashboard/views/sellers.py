"""Người bán (Quản lý ngành hàng và người bán): seller scorecard, high-revenue / low-quality sellers,
seller share vs order share by state. OLAP: q10, q11."""
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import query
from src.dashboard.filters import items_cte, orders_cte, sidebar_filters
from src.dashboard.ui import chart, kpis, money_col, num, pct_col, series, show_table

st.title("Hiệu quả người bán")
f = sidebar_filters()
p = f.params

c1, c2, c3 = st.columns(3)
min_orders = c1.number_input("Số đơn tối thiểu của người bán", 1, 500, 30, 5, key="sel_min")
top_share = c2.slider("Nhóm doanh thu cao nhất (%)", 5, 50, 20, 5, key="sel_top")
low_limit = c3.slider("Ngưỡng tỷ lệ 1-2 sao (%)", 5, 50, 20, 5, key="sel_low")

# one row per (seller, order) on delivered orders, then aggregate per seller (same logic as q10)
sellers = query(f"""WITH {items_cte('delivered')},
so AS (SELECT seller_key, order_id, SUM(price) AS revenue, MIN(is_late) AS is_late, MIN(review_score) AS score
       FROM items GROUP BY seller_key, order_id),
agg AS (SELECT seller_key, COUNT(*) AS orders, SUM(revenue) AS revenue,
               ROUND(100.0 * AVG(is_late), 1) AS late_pct, ROUND(AVG(score), 2) AS avg_review,
               ROUND(100.0 * AVG((score <= 2)::int), 1) AS low_review_pct
        FROM so GROUP BY seller_key HAVING COUNT(*) >= :min_orders)
SELECT a.*, LEFT(se.seller_id, 8) AS seller_id, st.state_code,
       PERCENT_RANK() OVER (ORDER BY a.revenue DESC) AS revenue_rank
FROM agg a
JOIN dm.dim_seller se ON se.seller_key = a.seller_key
JOIN dm.dim_city ci   ON ci.city_key = se.city_key
JOIN dm.dim_state st  ON st.state_key = ci.state_key
ORDER BY a.revenue DESC""", {**p, "min_orders": min_orders})

if sellers.empty:
    st.info("Không có người bán nào thỏa điều kiện với bộ lọc hiện tại.")
    st.stop()

sellers["top"] = sellers.revenue_rank < top_share / 100
sellers["flag"] = sellers.top & (sellers.low_review_pct > low_limit)
flagged = sellers[sellers.flag]
kpis([("Người bán được xét", num(len(sellers)), f"Có từ {min_orders} đơn đã giao trong kỳ"),
      (f"Thuộc nhóm {top_share}% doanh thu cao nhất", num(sellers.top.sum())),
      ("Cần làm việc trước", num(len(flagged)), f"Nhóm doanh thu cao nhưng hơn {low_limit}% đánh giá 1-2 sao")])

st.subheader("Doanh thu và chất lượng của từng người bán")
fig = go.Figure()
for is_flag, name, i in [(False, "Người bán khác", 0), (True, "Doanh thu cao, đánh giá thấp", 1)]:
    d = sellers[sellers.flag == is_flag]
    fig.add_scatter(x=d.revenue, y=d.low_review_pct, mode="markers", name=name,
                    marker=dict(size=9, color=series(i), opacity=0.75,
                                line=dict(width=1, color="rgba(255,255,255,0.8)")),
                    customdata=d[["seller_id", "state_code", "orders", "late_pct", "avg_review"]],
                    hovertemplate="Người bán %{customdata[0]}… (%{customdata[1]})<br>Doanh thu %{x:,.2f} BRL"
                                  "<br>1-2 sao %{y:.1f}% · Điểm TB %{customdata[4]:.2f}"
                                  "<br>%{customdata[2]:,} đơn · trễ %{customdata[3]:.1f}%<extra></extra>")
fig.add_hline(y=low_limit, line_dash="dash", line_width=1, line_color="#898781",
              annotation_text=f"{low_limit}% đánh giá 1-2 sao", annotation_position="top left")
fig.update_layout(title="Mỗi điểm là một người bán (trục ngang theo thang log)", xaxis_type="log",
                  xaxis_title="doanh thu (BRL)", yaxis_title="tỷ lệ đánh giá 1-2 sao (%)")
chart(fig, height=420)

cols = {"seller_id": "Mã người bán", "state_code": "Bang", "orders": "Số đơn", "revenue": "Doanh thu (BRL)",
        "late_pct": "Tỷ lệ trễ", "avg_review": "Điểm TB", "low_review_pct": "Tỷ lệ 1-2 sao"}
cfg = {"Doanh thu (BRL)": money_col("Doanh thu (BRL)"), "Tỷ lệ trễ": pct_col("Tỷ lệ trễ", 1),
       "Tỷ lệ 1-2 sao": pct_col("Tỷ lệ 1-2 sao", 1)}
st.markdown(f"**Người bán cần làm việc trước** ({len(flagged)}): thuộc nhóm {top_share}% doanh thu cao nhất "
            f"nhưng có hơn {low_limit}% đánh giá 1-2 sao.")
show_table(flagged[list(cols)].rename(columns=cols), column_config=cfg)
with st.expander("Bảng xếp hạng toàn bộ người bán"):
    show_table(sellers[list(cols)].rename(columns=cols), column_config=cfg)

# ---- seller share vs order share by state ----
st.subheader("Phân bố người bán so với nơi tập trung đơn hàng")
dist = query(f"""WITH {orders_cte()},
ord AS (SELECT state_code, COUNT(*) AS orders FROM orders GROUP BY state_code),
sel AS (SELECT st.state_code, COUNT(*) AS sellers
        FROM dm.dim_seller se JOIN dm.dim_city ci USING (city_key) JOIN dm.dim_state st USING (state_key)
        WHERE se.seller_key <> -1 GROUP BY st.state_code)
SELECT o.state_code, COALESCE(s.sellers, 0) AS sellers,
       ROUND(100.0 * COALESCE(s.sellers, 0) / SUM(COALESCE(s.sellers, 0)) OVER (), 1) AS seller_share,
       o.orders, ROUND(100.0 * o.orders / SUM(o.orders) OVER (), 1) AS order_share
FROM ord o LEFT JOIN sel s USING (state_code)
ORDER BY o.orders DESC""", p)
top10 = dist.head(10)
fig = go.Figure()
fig.add_bar(x=top10.state_code, y=top10.seller_share, name="Tỷ trọng người bán", marker_color=series(0),
            hovertemplate="%{x}<br>%{y:.1f}% người bán<extra></extra>")
fig.add_bar(x=top10.state_code, y=top10.order_share, name="Tỷ trọng đơn hàng", marker_color=series(1),
            hovertemplate="%{x}<br>%{y:.1f}% đơn hàng<extra></extra>")
fig.update_layout(title="10 bang có nhiều đơn nhất (%)", barmode="group", yaxis_ticksuffix="%")
chart(fig, dist.rename(columns={"state_code": "Bang", "sellers": "Người bán", "seller_share": "Tỷ trọng người bán",
                                "orders": "Đơn hàng", "order_share": "Tỷ trọng đơn hàng"}),
      column_config={"Tỷ trọng người bán": pct_col("Tỷ trọng người bán", 1),
                     "Tỷ trọng đơn hàng": pct_col("Tỷ trọng đơn hàng", 1)})
st.caption("Số người bán theo bang là toàn bộ người bán trong kho (không phụ thuộc bộ lọc), giống truy vấn q11.")
