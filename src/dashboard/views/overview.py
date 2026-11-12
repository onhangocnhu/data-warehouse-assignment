"""Tổng quan (Ban điều hành): headline KPIs and the monthly trend. OLAP: roll-up (q01) and CUBE (q13)."""
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import query
from src.dashboard.filters import items_cte, orders_cte, sidebar_filters
from src.dashboard.ui import chart, kpis, money, money_col, num, pct, ratio, region_colors, series

st.title("Tổng quan kinh doanh")
f = sidebar_filters()
p = f.params

sales = query(f"""WITH {items_cte('sales')}
SELECT SUM(price) AS revenue, SUM(freight_value) AS freight,
       COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT seller_key) AS sellers
FROM items""", p).iloc[0]
ops = query(f"""WITH {orders_cte()}
SELECT ROUND(100.0 * AVG(is_late), 2) AS late_pct,
       AVG(review_score)              AS avg_review
FROM orders""", p).iloc[0]

kpis([
    ("Doanh thu hàng hóa", money(sales.revenue), "Tổng giá bán, không gồm phí vận chuyển, loại đơn bị hủy / không khả dụng"),
    ("Số đơn hàng", num(sales.orders)),
    ("Giá trị đơn trung bình", money(ratio(sales.revenue, sales.orders))),
])
kpis([
    ("Tỷ lệ giao trễ", pct(ops.late_pct), "Trên các đơn đã giao (tính theo đơn, không theo dòng sản phẩm)"),
    ("Điểm đánh giá TB", num(ops.avg_review, 2)),
    ("Người bán hoạt động", num(sales.sellers)),
])
if f.is_default:
    st.caption("Đối soát với báo cáo: doanh thu 13.494.400,74 BRL trên 98.199 đơn; tỷ lệ giao trễ 6,77%.")

# ---- roll-up: month -> quarter -> year ----
st.subheader("Doanh thu theo thời gian")
level = st.segmented_control("Mức tổng hợp (roll-up / drill-down)", ["Tháng", "Quý", "Năm"],
                             default="Tháng", required=True, key="ov_level")
period = {"Tháng": "to_char(full_date, 'MM/YYYY')", "Quý": "'Q' || quarter || '/' || year",
          "Năm": "year::text"}[level]
order = {"Tháng": "MIN(full_date)", "Quý": "MIN(year * 10 + quarter)", "Năm": "MIN(year)"}[level]
trend = query(f"""WITH {items_cte('sales')}
SELECT {period} AS period, SUM(price) AS revenue, COUNT(DISTINCT order_id) AS orders,
       ROUND(SUM(price) / COUNT(DISTINCT order_id), 2) AS avg_order_value
FROM items GROUP BY 1 ORDER BY {order}""", p)

c1, c2 = st.columns(2)
with c1:
    fig = go.Figure(go.Bar(x=trend.period, y=trend.revenue, marker_color=series(0), name="Doanh thu",
                           hovertemplate="%{x}<br>%{y:,.2f} BRL<extra></extra>"))
    fig.update_layout(title="Doanh thu hàng hóa (BRL)", hovermode="x")
    chart(fig, trend.rename(columns={"period": "Kỳ", "revenue": "Doanh thu (BRL)", "orders": "Số đơn",
                                     "avg_order_value": "Giá trị đơn TB (BRL)"}),
          column_config={"Doanh thu (BRL)": money_col("Doanh thu (BRL)")})
with c2:
    fig = go.Figure(go.Scatter(x=trend.period, y=trend.orders, mode="lines+markers", name="Số đơn",
                               line_color=series(0), marker_size=8,
                               hovertemplate="%{x}<br>%{y:,} đơn<extra></extra>"))
    fig.update_layout(title="Số đơn hàng", hovermode="x unified")
    chart(fig)
if level == "Tháng":
    st.caption("Các tháng 09-12/2016 và 09-10/2018 chỉ có vài đơn (dữ liệu chưa đủ / đã dừng), không phải sụt giảm thật.")

# ---- CUBE: region x year ----
st.subheader("Doanh thu theo vùng và năm")
cube = query(f"""WITH {items_cte('sales')}
SELECT COALESCE(region, 'Tất cả vùng') AS region, COALESCE(year::text, 'Tất cả năm') AS year,
       SUM(price) AS revenue, COUNT(DISTINCT order_id) AS orders
FROM items GROUP BY CUBE (region, year) ORDER BY region, year""", p)
detail = cube[(cube.region != "Tất cả vùng") & (cube.year != "Tất cả năm")]
fig = go.Figure()
for region, color in region_colors().items():
    d = detail[detail.region == region]
    if len(d):
        fig.add_bar(x=d.year, y=d.revenue, name=region, marker_color=color,
                    hovertemplate=region + " %{x}<br>%{y:,.2f} BRL<extra></extra>")
fig.update_layout(title="Doanh thu theo vùng của khách hàng (BRL)", barmode="group")
pivot = cube.pivot(index="region", columns="year", values="revenue").reset_index()
chart(fig, pivot.rename(columns={"region": "Vùng"}),
      column_config={c: money_col(c) for c in pivot.columns if c != "region"})
st.caption("Bảng số liệu dùng GROUP BY CUBE: dòng / cột \"Tất cả\" là tổng theo một hoặc cả hai chiều.")
