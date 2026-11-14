"""Giao hàng (Quản lý vận hành): late rate with drill-down region -> state -> city, stage durations,
route matrix, Black Friday. OLAP: q02, q03, q08, q09, q14. All order-level measures come from dm.v_order."""
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import query
from src.dashboard.filters import REGIONS, STATUS, filter_caption, items_cte, orders_cte, sidebar_filters
from src.dashboard.ui import SEQ_BLUE, chart, kpis, num, palette, pct, pct_col, region_colors, series

st.header("Giao hàng")
f = sidebar_filters()
filter_caption(f)
p = f.params

k = query(f"""WITH {orders_cte()}
SELECT COUNT(*) FILTER (WHERE is_late IS NOT NULL) AS delivered,
       ROUND(100.0 * AVG(is_late), 2) AS late_pct,
       AVG(delivery_days) FILTER (WHERE order_status = 'delivered') AS delivery_days,
       AVG(handling_days) FILTER (WHERE order_status = 'delivered') AS handling_days,
       AVG(shipping_days) FILTER (WHERE order_status = 'delivered') AS shipping_days
FROM orders""", p).iloc[0]
kpis([("Đơn đã giao", num(k.delivered)), ("Tỷ lệ giao trễ", pct(k.late_pct)),
      ("Thời gian giao TB", num(k.delivery_days, 1) + " ngày"),
      ("Người bán chuẩn bị TB", num(k.handling_days, 1) + " ngày"),
      ("Vận chuyển TB", num(k.shipping_days, 1) + " ngày")])

# ---- drill-down region -> state -> city ----
st.subheader("Tỷ lệ giao trễ theo địa bàn")
c1, c2 = st.columns([1, 2])
with c1:
    region = st.selectbox("Vùng", ["Toàn quốc"] + REGIONS, key="dl_region")
states = query(f"""WITH {orders_cte()}
SELECT region, state_code, COUNT(*) AS delivered_orders,
       ROUND(100.0 * AVG(is_late), 2) AS late_pct, ROUND(AVG(delivery_days), 1) AS avg_delivery_days
FROM orders WHERE is_late IS NOT NULL
GROUP BY region, state_code ORDER BY late_pct DESC""", p)
if region != "Toàn quốc":
    states = states[states.region == region]
with c2:
    state = st.selectbox("Bang", ["Tất cả bang"] + states.state_code.tolist(), key="dl_state")

overall = float(k.late_pct) if k.late_pct is not None else None
colors = region_colors()
if state == "Tất cả bang":
    d = states
    fig = go.Figure()
    for reg_name, color in colors.items():          # one trace per region -> legend explains the colors
        g = d[d.region == reg_name]
        if len(g):
            fig.add_bar(x=g.state_code, y=g.late_pct, name=reg_name, marker_color=color,
                        customdata=g[["region", "delivered_orders"]],
                        hovertemplate="%{x} (%{customdata[0]})<br>Trễ %{y:.2f}%<br>%{customdata[1]:,} đơn<extra></extra>")
    fig.update_layout(barmode="relative", xaxis=dict(categoryorder="array", categoryarray=d.state_code.tolist()),
                      yaxis_ticksuffix="%")
    title = "Tỷ lệ giao trễ theo bang (%)"
    table = d.rename(columns={"region": "Vùng", "state_code": "Bang", "delivered_orders": "Đơn đã giao",
                              "late_pct": "Tỷ lệ trễ", "avg_delivery_days": "Thời gian giao TB (ngày)"})
else:
    min_orders = st.slider("Số đơn tối thiểu mỗi thành phố", 10, 500, 100, 10, key="dl_min")
    d = query(f"""WITH {orders_cte()}
SELECT city_name, COUNT(*) AS delivered_orders, ROUND(100.0 * AVG(is_late), 2) AS late_pct,
       ROUND(AVG(delivery_days), 1) AS avg_delivery_days
FROM orders WHERE is_late IS NOT NULL AND state_code = :state
GROUP BY city_name HAVING COUNT(*) >= :min ORDER BY late_pct DESC LIMIT 25""",
              {**p, "state": state, "min": min_orders})
    fig = go.Figure(go.Bar(x=d.city_name, y=d.late_pct, marker_color=series(0), customdata=d.delivered_orders,
                           hovertemplate="%{x}<br>Trễ %{y:.2f}%<br>%{customdata:,} đơn<extra></extra>"))
    fig.update_layout(yaxis_ticksuffix="%")
    title = f"Tỷ lệ giao trễ theo thành phố, bang {state} (%)"
    table = d.rename(columns={"city_name": "Thành phố", "delivered_orders": "Đơn đã giao", "late_pct": "Tỷ lệ trễ",
                              "avg_delivery_days": "Thời gian giao TB (ngày)"})
if overall is not None:
    fig.add_hline(y=overall, line_dash="dash", line_color=palette()["muted"], line_width=1,
                  annotation_text=f"Trung bình {pct(overall)}", annotation_position="top right")
fig.update_layout(title=title)
chart(fig, table, column_config={"Tỷ lệ trễ": pct_col("Tỷ lệ trễ")})

# ---- stage durations by region ----
_, c_lots = st.columns(2)                          # the slider only filters the route matrix (right)
min_lots = c_lots.select_slider("Số lô tối thiểu mỗi tuyến", list(range(50, 1001, 50)), value=200,
                                format_func=num, key="dl_lots")
c1, c2 = st.columns(2)
with c1:
    stg = query(f"""WITH {orders_cte()}
SELECT region, COUNT(*) AS delivered_orders,
       ROUND(AVG(approval_days), 2) AS approval, ROUND(AVG(handling_days), 2) AS handling,
       ROUND(AVG(shipping_days), 2) AS shipping, ROUND(AVG(delivery_days), 2) AS total
FROM orders WHERE order_status = 'delivered' AND delivery_days IS NOT NULL
GROUP BY region ORDER BY total""", p)
    fig = go.Figure()
    for col, name, i in [("approval", "Duyệt đơn", 3), ("handling", "Người bán chuẩn bị", 1), ("shipping", "Vận chuyển", 0)]:
        fig.add_bar(y=stg.region, x=stg[col], name=name, orientation="h", marker_color=series(i),
                    marker_line_color=palette()["grid"], marker_line_width=0,
                    hovertemplate="%{y}<br>" + name + ": %{x:.2f} ngày<extra></extra>")
    fig.update_layout(title="Thời gian TB từng công đoạn theo vùng (ngày)", barmode="stack")
    chart(fig, stg.rename(columns={"region": "Vùng", "delivered_orders": "Đơn đã giao", "approval": "Duyệt",
                                   "handling": "Chuẩn bị", "shipping": "Vận chuyển", "total": "Tổng"}))

# ---- route matrix: seller state -> customer state, one lot = (order, seller) ----
with c2:
    routes = query(f"""WITH {items_cte('all')},
lot AS (SELECT DISTINCT order_id, seller_key, state_code AS customer_state, is_late FROM items WHERE is_late IS NOT NULL)
SELECT ss.state_code AS seller_state, l.customer_state, COUNT(*) AS lots, ROUND(100.0 * AVG(l.is_late), 1) AS late_pct
FROM lot l
JOIN dm.dim_seller se ON se.seller_key = l.seller_key
JOIN dm.dim_city sc   ON sc.city_key = se.city_key
JOIN dm.dim_state ss  ON ss.state_key = sc.state_key
GROUP BY 1, 2 HAVING COUNT(*) >= :min_lots""", {**p, "min_lots": min_lots})
    if routes.empty:
        st.info("Không có tuyến nào đủ số lô với bộ lọc hiện tại.")
    else:
        m = routes.pivot(index="seller_state", columns="customer_state", values="late_pct")
        n = routes.pivot(index="seller_state", columns="customer_state", values="lots")
        m = m.loc[n.sum(axis=1).sort_values().index]
        n = n.loc[m.index, m.columns]
        fig = go.Figure(go.Heatmap(z=m.values, x=m.columns, y=m.index, customdata=n.values, colorscale=SEQ_BLUE,
                                   xgap=2, ygap=2, colorbar=dict(title="% trễ"),
                                   hovertemplate="%{y} → %{x}<br>Trễ %{z:.1f}%<br>%{customdata:,} lô<extra></extra>"))
        fig.update_layout(title="Tỷ lệ giao trễ theo tuyến (%)",
                          xaxis_title="Bang khách hàng", yaxis_title="Bang người bán")
        chart(fig, routes.sort_values("lots", ascending=False).rename(columns={
            "seller_state": "Bang người bán", "customer_state": "Bang khách hàng", "lots": "Số lô", "late_pct": "Tỷ lệ trễ"}),
            column_config={"Tỷ lệ trễ": pct_col("Tỷ lệ trễ", 1)})

# ---- Black Friday (fixed window) ----
st.subheader("Black Friday 24/11/2017")
bf = query("""SELECT d.full_date, COUNT(*) AS orders, ROUND(100.0 * AVG(o.is_late), 1) AS late_pct
FROM dm.v_order o JOIN dm.dim_date d ON d.date_key = o.purchase_date_key
WHERE d.full_date BETWEEN '2017-11-01' AND '2017-12-31'
GROUP BY d.full_date ORDER BY d.full_date""")
c1, c2 = st.columns(2)
with c1:
    fig = go.Figure(go.Bar(x=bf.full_date, y=bf.orders, marker_color=series(0),
                           hovertemplate="%{x|%d/%m/%Y}<br>%{y:,} đơn<extra></extra>"))
    fig.update_layout(title="Số đơn theo ngày đặt (đơn), 11-12/2017", xaxis_tickformat="%d/%m")
    chart(fig)
with c2:
    fig = go.Figure(go.Scatter(x=bf.full_date, y=bf.late_pct, mode="lines+markers", marker_size=8,
                               line_color=series(1),
                               hovertemplate="%{x|%d/%m/%Y}<br>Trễ %{y:.1f}%<extra></extra>"))
    fig.update_layout(title="Tỷ lệ giao trễ theo ngày đặt (%), 11-12/2017", xaxis_tickformat="%d/%m", hovermode="x")
    chart(fig, bf.rename(columns={"full_date": "Ngày", "orders": "Số đơn", "late_pct": "Tỷ lệ trễ"}),
          column_config={"Tỷ lệ trễ": pct_col("Tỷ lệ trễ", 1)})
