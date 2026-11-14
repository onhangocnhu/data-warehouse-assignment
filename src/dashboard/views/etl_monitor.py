"""Giám sát ETL (Kỹ thuật): last runs, data-quality reconciliation, rejected / modified records
(meta.etl_run_log, meta.dq_result, meta.rejected_record) -- the Monitoring function of the architecture."""
import re

import streamlit as st

from src.dashboard.db import query
from src.dashboard.ui import STATUS, kpis, num, show_table


def vn_text(v: str) -> str:
    """dq_result stores expected / actual as text ("13591643.70", "4.05..4.15"): print the numbers Vietnamese-style."""
    def one(m):
        x = m.group(0)
        return num(float(x), len(x.split(".")[1]) if "." in x else 0)
    return re.sub(r"\d+(?:\.\d+)?", one, v.replace("..", "-")) if isinstance(v, str) else v

st.header("Giám sát ETL")

runs = query("""SELECT run_id, MIN(started_at) AS started_at, MAX(finished_at) AS finished_at,
       ROUND(EXTRACT(EPOCH FROM MAX(finished_at) - MIN(started_at))::numeric, 1) AS seconds,
       COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_steps
FROM meta.etl_run_log GROUP BY run_id ORDER BY run_id DESC""")
if runs.empty:
    st.warning("Chưa có lần chạy ETL nào. Chạy `python -m src.etl.run_etl --init`.")
    st.stop()

run_id = st.selectbox("Lần chạy ETL", runs.run_id.tolist(), key="etl_run",
                      format_func=lambda r: f"#{r} · {runs.loc[runs.run_id == r, 'started_at'].iloc[0]:%d/%m/%Y %H:%M}")
run = runs[runs.run_id == run_id].iloc[0]
dq = query("SELECT check_name, expected, actual, passed FROM meta.dq_result WHERE run_id = :r ORDER BY passed, check_name",
           {"r": int(run_id)})
rej = query("""SELECT source, action, reason, COUNT(*) AS records FROM meta.rejected_record
WHERE run_id = :r GROUP BY source, action, reason ORDER BY records DESC""", {"r": int(run_id)})

n_pass, n_dq = int(dq.passed.sum()), len(dq)
if run.failed_steps == 0 and n_pass == n_dq:
    st.success(f"Lần chạy #{run_id} thành công · {n_pass}/{n_dq} tiêu chí đối soát đạt", icon=":material/check_circle:")
else:
    st.error(f"Lần chạy #{run_id} có lỗi: {num(run.failed_steps)} bước lỗi, {n_dq - n_pass} tiêu chí không đạt",
             icon=":material/error:")

kpis([("Bắt đầu", f"{run.started_at:%H:%M}", f"{run.started_at:%d/%m/%Y %H:%M:%S}"),
      ("Thời gian chạy", num(run.seconds, 1) + " giây"), ("Bước lỗi", num(run.failed_steps)),
      ("Tiêu chí đối soát đạt", f"{n_pass}/{n_dq}"),
      ("Bản ghi bị loại", num(rej[rej.action == "DROPPED"].records.sum())),
      ("Bản ghi bị sửa", num(rej[rej.action == "MODIFIED"].records.sum()))])

OK_COLORS = {"✓ Đạt": STATUS["GREEN"], "✗ Không đạt": STATUS["RED"]}
RUN_COLORS = {"SUCCESS": STATUS["GREEN"], "FAILED": STATUS["RED"]}

st.subheader("Kiểm tra chất lượng dữ liệu")
show_table(dq.assign(passed=dq.passed.map({True: "✓ Đạt", False: "✗ Không đạt"}),
                     expected=dq.expected.map(vn_text), actual=dq.actual.map(vn_text)).rename(columns={
    "check_name": "Tiêu chí", "expected": "Kỳ vọng", "actual": "Thực tế", "passed": "Kết quả"}),
    highlight={"Kết quả": OK_COLORS})

st.subheader("Các bước ETL")
show_table(query("""SELECT step, status, rows_out, rows_rejected,
       ROUND(EXTRACT(EPOCH FROM finished_at - started_at)::numeric, 2) AS seconds, message
FROM meta.etl_run_log WHERE run_id = :r ORDER BY started_at""", {"r": int(run_id)}).rename(columns={
    "step": "Bước", "status": "Trạng thái", "rows_out": "Số dòng ra", "rows_rejected": "Số dòng bị loại",
    "seconds": "Giây", "message": "Ghi chú"}), highlight={"Trạng thái": RUN_COLORS})

st.subheader("Bản ghi bị loại / bị sửa")
show_table(rej.rename(columns={"source": "Nguồn", "action": "Hành động", "reason": "Lý do", "records": "Số bản ghi"}))

st.subheader("Lịch sử chạy")
show_table(runs.rename(columns={"run_id": "Lần chạy", "started_at": "Bắt đầu", "finished_at": "Kết thúc",
                                "seconds": "Giây", "failed_steps": "Bước lỗi"}),
           column_config={"Bắt đầu": st.column_config.DatetimeColumn("Bắt đầu", format="DD/MM/YYYY HH:mm"),
                          "Kết thúc": st.column_config.DatetimeColumn("Kết thúc", format="DD/MM/YYYY HH:mm")})
