"""Cảnh báo giao trễ (DSS, Quản lý vận hành): orders scored when the seller hands them over to the carrier
(dss.delay_risk_score, written by src/dss/score_delay.py), what-if on the expected-cost policy,
and approve / reject buttons that write dss.decision_log (report section 5.5-5.6)."""
import datetime as dt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.db import log_decision, query, query_live
from src.dashboard.ui import STATUS, chart, kpis, money, num, pct, pct_col, series, show_table

CERTAIN = "Đã quá ngày giao dự kiến khi bàn giao vận chuyển"   # rule-based RED, p_late = 1
LEVEL_VN = {"RED": "ĐỎ", "YELLOW": "VÀNG", "GREEN": "XANH"}

st.title("Cảnh báo giao trễ lúc bàn giao vận chuyển")

scores = query("""SELECT order_id, decision_date, p_late::float AS p_late, risk_rank_pct::float AS risk_rank_pct,
       risk_level, reason_1, reason_2, reason_3, recommended_action, actual_is_late, model_version
FROM dss.delay_risk_score""")
if scores.empty:
    st.warning("Chưa có kết quả DSS. Chạy `python -m src.dss.score_delay` rồi tải lại trang.")
    st.stop()
scores["decision_date"] = scores.decision_date.astype("datetime64[ns]").dt.date
scores["certain"] = scores.reason_1 == CERTAIN

# ---------------- what-if: expected-cost policy ----------------
st.subheader("Khi nào nên tặng voucher?")
c1, c2, c3 = st.columns(3)
# select_slider instead of slider: a slider can only print numbers as 30.00, not 30,00
c_late = c1.select_slider("Thiệt hại khi một đơn bị trễ, C trễ (BRL)", [float(x) for x in range(5, 101)],
                          value=30.0, format_func=lambda x: num(x, 0), key="dss_late")
c_int = c2.select_slider("Chi phí can thiệp một đơn, C can thiệp (BRL)", [x / 2 for x in range(2, 61)],
                         value=8.0, format_func=lambda x: num(x, 1), key="dss_int")
effect = c3.select_slider("Tỷ lệ thiệt hại tránh được nhờ can thiệp, e", [x / 100 for x in range(5, 101, 5)],
                          value=0.4, format_func=lambda x: num(x, 2), key="dss_eff")
threshold = c_int / (c_late * effect)
st.latex(r"p^* = \frac{C_{\text{can thiệp}}}{C_{\text{trễ}} \cdot e} = "
         + f"\\frac{{{c_int:g}}}{{{c_late:g} \\times {effect:g}}} = {threshold:.3f}".replace(".", "{,}"))

ev = scores.certain | (scores.p_late >= threshold)
caught = int(scores.actual_is_late[ev].sum())
red = scores.risk_level == "RED"
red_yellow = scores.risk_level.isin(["RED", "YELLOW"])


def policy(mask):
    n, c = int(mask.sum()), int(scores.actual_is_late[mask].sum())
    return {"Số đơn can thiệp": n, "Đơn trễ bắt được": c,
            "Precision": 100 * c / n if n else 0.0,
            "Lợi ích ròng (BRL)": c * c_late * effect - n * c_int}


pol = pd.DataFrame([{"Chính sách": "Mức ĐỎ (5%)", **policy(red)},
                    {"Chính sách": "ĐỎ + VÀNG (15%)", **policy(red_yellow)},
                    {"Chính sách": f"Chi phí kỳ vọng (p ≥ {num(threshold, 3)})", **policy(ev)}])
best = pol.iloc[2]
kpis([("Ngưỡng p*", num(threshold, 3) if threshold <= 1 else f"{num(threshold, 3)} (> 1)",
       "Đơn có xác suất trễ từ ngưỡng này được đề xuất voucher"),
      ("Đơn được đề xuất voucher", num(best["Số đơn can thiệp"])),
      ("Precision", pct(best["Precision"], 1)),
      ("Lợi ích ròng ước tính", money(best["Lợi ích ròng (BRL)"], 0))])
show_table(pol, column_config={"Precision": pct_col("Precision", 1)})

# ---------------- risk levels ----------------
c1, c2 = st.columns(2)
with c1:
    lv = scores.groupby("risk_level").agg(orders=("order_id", "size"), late=("actual_is_late", "mean")).reindex(
        ["RED", "YELLOW", "GREEN"]).reset_index()
    lv["late"] = 100 * lv.late
    fig = go.Figure(go.Bar(x=[LEVEL_VN[l] for l in lv.risk_level], y=lv.late,
                           marker_color=[STATUS[l] for l in lv.risk_level],
                           text=[pct(v, 1) for v in lv.late], textposition="outside",
                           customdata=lv.orders,
                           hovertemplate="Mức %{x}<br>%{y:.1f}% đơn thực sự trễ<br>%{customdata:,} đơn<extra></extra>"))
    fig.update_layout(title="Tỷ lệ đơn thực sự trễ trong từng mức rủi ro", yaxis_ticksuffix="%")
    chart(fig, lv.assign(risk_level=lv.risk_level.map(LEVEL_VN)).rename(columns={
        "risk_level": "Mức", "orders": "Số đơn", "late": "Tỷ lệ thực sự trễ"}),
        column_config={"Tỷ lệ thực sự trễ": pct_col("Tỷ lệ thực sự trễ", 1)})
with c2:
    total_late = scores.actual_is_late.sum()
    rows = []
    for k in range(1, 31):
        m = scores.certain | (scores.risk_rank_pct <= k / 100)
        rows.append((k, 100 * scores.actual_is_late[m].sum() / total_late))
    cap = pd.DataFrame(rows, columns=["capacity", "recall"])
    fig = go.Figure(go.Scatter(x=cap.capacity, y=cap.recall, mode="lines", line_color=series(0),
                               hovertemplate="Xử lý %{x}% đơn/ngày<br>bắt được %{y:.1f}% đơn trễ<extra></extra>"))
    fig.update_layout(title="Tỷ lệ đơn trễ bắt được theo năng lực xử lý mỗi ngày", hovermode="x",
                      xaxis_title="năng lực xử lý (% đơn bàn giao mỗi ngày)", xaxis_ticksuffix="%",
                      yaxis_ticksuffix="%")
    chart(fig, cap.rename(columns={"capacity": "Năng lực (%)", "recall": "Đơn trễ bắt được (%)"}))

# ---------------- work queue ----------------
st.subheader("Danh sách đơn cần xử lý")
dates = sorted(scores.decision_date.unique())
c1, c2, c3 = st.columns([1, 1, 2])
day = c1.date_input("Ngày bàn giao", value=dt.date(2018, 7, 16), min_value=dates[0], max_value=dates[-1],
                    format="DD/MM/YYYY", key="dss_day")
levels = c2.pills("Mức rủi ro", ["RED", "YELLOW"], selection_mode="multi", default=["RED", "YELLOW"],
                  format_func=lambda l: LEVEL_VN[l], key="dss_levels")
operator = c3.text_input("Người duyệt", placeholder="Tên người vận hành", key="dss_operator")

queue = scores[(scores.decision_date == day) & scores.risk_level.isin(levels or [])].sort_values("p_late", ascending=False)
decided = query_live("""SELECT DISTINCT ON (object_id) object_id, decision, decided_by, decided_at
FROM dss.decision_log WHERE module = 'delay_risk' ORDER BY object_id, decided_at DESC""")
done = decided.set_index("object_id").to_dict("index")

st.caption(f"{num(len(queue))} đơn cần xử lý")
if queue.empty:
    st.info("Không có đơn ĐỎ / VÀNG nào trong ngày này.")
for r in queue.head(40).itertuples():
    voucher = r.certain or r.p_late >= threshold
    level_md = {"RED": ":red-badge[:material/error: ĐỎ]", "YELLOW": ":orange-badge[:material/warning: VÀNG]"}[r.risk_level]
    with st.container(border=True):
        a, b = st.columns([5, 2])
        with a:
            outcome = ":red[trễ]" if r.actual_is_late else ":green[đúng hạn]"
            st.markdown(f"{level_md} **{r.order_id[:12]}…** · p trễ = **{num(r.p_late, 2)}**"
                        + (" · :violet-badge[:material/redeem: đề xuất voucher]" if voucher else "")
                        + f" · Thực tế: {outcome}")
            reasons = [x for x in (r.reason_1, r.reason_2, r.reason_3) if isinstance(x, str)]
            st.markdown("\n".join(f"- {x}" for x in reasons))
            st.caption(f"Hành động đề xuất: {r.recommended_action}")
        with b:
            prev = done.get(r.order_id)
            if prev:
                verb = "Đã duyệt" if prev["decision"] == "APPROVED" else "Đã từ chối"
                st.markdown(f"**{verb}**  \n{prev['decided_by'] or ''}  \n"
                            f"{prev['decided_at']:%d/%m/%Y %H:%M}")
            else:
                note = st.text_input("Ghi chú", key=f"note_{r.order_id}", label_visibility="collapsed",
                                     placeholder="Ghi chú (không bắt buộc)")
                y, n = st.columns(2)
                rec = r.recommended_action + (" + voucher (p ≥ p*)" if voucher and not r.certain else "")
                if y.button("Duyệt", key=f"ok_{r.order_id}", type="primary", width="stretch",
                            icon=":material/check:"):
                    log_decision(r.order_id, rec, "APPROVED", operator, note)
                    st.rerun()
                if n.button("Từ chối", key=f"no_{r.order_id}", width="stretch", icon=":material/close:"):
                    log_decision(r.order_id, rec, "REJECTED", operator, note)
                    st.rerun()
if len(queue) > 40:
    st.caption(f"Đang hiện 40 / {num(len(queue))} đơn rủi ro nhất.")

with st.expander("Nhật ký quyết định"):
    log = query_live("""SELECT decided_at, object_id AS order_id, decision, decided_by, recommendation, note
FROM dss.decision_log WHERE module = 'delay_risk' ORDER BY decided_at DESC LIMIT 200""")
    show_table(log.rename(columns={"order_id": "Mã đơn", "decision": "Quyết định", "decided_by": "Người duyệt",
                                   "recommendation": "Đề xuất", "note": "Ghi chú"}),
               column_config={"decided_at": st.column_config.DatetimeColumn("Thời điểm", format="DD/MM/YYYY HH:mm")})

with st.expander("Phiên bản mô hình"):
    show_table(query("""SELECT model_version, test_month, train_rows, train_until, roc_auc, pr_auc, recall_top10
FROM dss.model_registry ORDER BY test_month"""))
