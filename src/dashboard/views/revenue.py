"""Doanh thu (Ban điều hành): revenue by region / state / category. OLAP: slice (q04), dice (q05), growth (q12)."""
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import query
from src.dashboard.filters import items_cte, sidebar_filters
from src.dashboard.ui import SEQ_BLUE, chart, money_col, pct_col, region_colors, series

st.title("Doanh thu theo khu vực và ngành hàng")
f = sidebar_filters()
p = f.params

# ---- by region (slice when one year is chosen) ----
c1, c2 = st.columns(2)
with c1:
    reg = query(f"""WITH {items_cte('sales')}
SELECT region, SUM(price) AS revenue, COUNT(DISTINCT order_id) AS orders,
       ROUND(100.0 * SUM(price) / SUM(SUM(price)) OVER (), 1) AS share_pct
FROM items GROUP BY region ORDER BY revenue DESC""", p)
    colors = region_colors()
    fig = go.Figure(go.Bar(x=reg.revenue, y=reg.region, orientation="h",
                           marker_color=[colors.get(r, series(0)) for r in reg.region],
                           text=[f"{s:.1f}%".replace(".", ",") for s in reg.share_pct], textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}<br>%{x:,.2f} BRL<extra></extra>"))
    fig.update_layout(title="Doanh thu theo vùng của khách hàng (nhãn: tỷ trọng)", yaxis_autorange="reversed",
                      xaxis_range=[0, float(reg.revenue.max() or 1) * 1.15])
    chart(fig, reg.rename(columns={"region": "Vùng", "revenue": "Doanh thu (BRL)", "orders": "Số đơn",
                                   "share_pct": "Tỷ trọng"}),
          column_config={"Doanh thu (BRL)": money_col("Doanh thu (BRL)"), "Tỷ trọng": pct_col("Tỷ trọng", 1)})
with c2:
    stt = query(f"""WITH {items_cte('sales')}
SELECT state_code, region, SUM(price) AS revenue, COUNT(DISTINCT order_id) AS orders
FROM items GROUP BY state_code, region ORDER BY revenue DESC LIMIT 10""", p)
    fig = go.Figure(go.Bar(x=stt.revenue, y=stt.state_code, orientation="h", marker_color=series(0),
                           customdata=stt.region,
                           hovertemplate="%{y} (%{customdata})<br>%{x:,.2f} BRL<extra></extra>"))
    fig.update_layout(title="10 bang có doanh thu cao nhất ", yaxis_autorange="reversed")
    chart(fig, stt.rename(columns={"state_code": "Bang", "region": "Vùng", "revenue": "Doanh thu (BRL)",
                                   "orders": "Số đơn"}),
          column_config={"Doanh thu (BRL)": money_col("Doanh thu (BRL)")})

# ---- dice: top categories x states ----
st.subheader("Ngành hàng dẫn đầu tại các bang lớn")
top_n = st.slider("Số ngành hàng", 3, 15, 8, key="rev_topn")
dice = query(f"""WITH {items_cte('sales')},
top_cat AS (SELECT category FROM items GROUP BY category ORDER BY SUM(price) DESC LIMIT :n),
top_state AS (SELECT state_code FROM items GROUP BY state_code ORDER BY SUM(price) DESC LIMIT 6)
SELECT category, state_code, SUM(price) AS revenue
FROM items
WHERE category IN (SELECT category FROM top_cat) AND state_code IN (SELECT state_code FROM top_state)
GROUP BY category, state_code""", {**p, "n": top_n})
if dice.empty:
    st.info("Không có dữ liệu với bộ lọc hiện tại.")
else:
    m = dice.pivot(index="category", columns="state_code", values="revenue").fillna(0)
    m = m.loc[m.sum(axis=1).sort_values().index, m.sum().sort_values(ascending=False).index]
    fig = go.Figure(go.Heatmap(z=m.values, x=m.columns, y=m.index, colorscale=SEQ_BLUE, xgap=2, ygap=2,
                               colorbar=dict(title="BRL"),
                               hovertemplate="%{y} tại %{x}<br>%{z:,.2f} BRL<extra></extra>"))
    fig.update_layout(title="Doanh thu (BRL): ngành hàng × bang của khách hàng")
    chart(fig, m.reset_index().rename(columns={"category": "Ngành hàng"}),
          height=max(320, 34 * len(m) + 90),
          column_config={c: money_col(c) for c in m.columns})

# ---- category growth (fixed comparison, independent of the time filter) ----
st.subheader("Tăng trưởng ngành hàng: 01-08/2018 so với 01-08/2017")
growth = query("""SELECT cat.category_name_en AS category,
       SUM(f.price) FILTER (WHERE d.year = 2017) AS rev_2017,
       SUM(f.price) FILTER (WHERE d.year = 2018) AS rev_2018,
       ROUND(100.0 * (SUM(f.price) FILTER (WHERE d.year = 2018)
             / NULLIF(SUM(f.price) FILTER (WHERE d.year = 2017), 0) - 1), 1) AS growth_pct
FROM dm.fact_sales f
JOIN dm.dim_date d       ON d.date_key = f.purchase_date_key
JOIN dm.dim_product p    ON p.product_key = f.product_key
JOIN dm.dim_category cat ON cat.category_key = p.category_key
WHERE d.month BETWEEN 1 AND 8 AND d.year IN (2017, 2018)
  AND f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY cat.category_name_en
HAVING SUM(f.price) FILTER (WHERE d.year = 2017) >= 50000
ORDER BY growth_pct""")
fig = go.Figure(go.Bar(x=growth.growth_pct, y=growth.category, orientation="h", marker_color=series(0),
                       hovertemplate="%{y}<br>+%{x:.1f}%<extra></extra>"))
fig.update_layout(title="Tăng trưởng doanh thu (%), ngành có từ 50.000 BRL trong 01-08/2017")
chart(fig, growth.sort_values("growth_pct", ascending=False).rename(columns={
    "category": "Ngành hàng", "rev_2017": "01-08/2017 (BRL)", "rev_2018": "01-08/2018 (BRL)", "growth_pct": "Tăng trưởng"}),
    height=max(320, 26 * len(growth) + 90),
    column_config={"01-08/2017 (BRL)": money_col("01-08/2017 (BRL)"), "01-08/2018 (BRL)": money_col("01-08/2018 (BRL)"),
                   "Tăng trưởng": pct_col("Tăng trưởng", 1)})
