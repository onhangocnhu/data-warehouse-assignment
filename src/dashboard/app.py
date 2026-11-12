"""Dashboard of the e-commerce Data Mart (Olist).  Run from the repository root:

    streamlit run src/dashboard/app.py

One page per user group of the report (tab:quyetdinh), plus the DSS page and an ETL monitor.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:                 # so "import src..." works under `streamlit run`
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from src.dashboard.db import using_admin  # noqa: E402
from src.dashboard.ui import theme_watcher  # noqa: E402

st.set_page_config(page_title="Olist Data Mart", page_icon=":material/insights:", layout="wide")

# Folder name is "views", not "pages": Streamlit would treat a "pages/" folder as old-style automatic pages.
PAGES = Path(__file__).resolve().parent / "views"
nav = st.navigation({
    "Ban điều hành": [
        st.Page(PAGES / "overview.py", title="Tổng quan", icon=":material/dashboard:", url_path="overview", default=True),
        st.Page(PAGES / "revenue.py", title="Doanh thu", icon=":material/payments:", url_path="revenue"),
    ],
    "Vận hành": [
        st.Page(PAGES / "delivery.py", title="Giao hàng", icon=":material/local_shipping:", url_path="delivery"),
        st.Page(PAGES / "dss.py", title="Cảnh báo giao trễ (DSS)", icon=":material/notifications_active:",
                url_path="dss"),
    ],
    "Khách hàng & người bán": [
        st.Page(PAGES / "satisfaction.py", title="Mức độ hài lòng", icon=":material/reviews:", url_path="satisfaction"),
        st.Page(PAGES / "sellers.py", title="Người bán", icon=":material/storefront:", url_path="sellers"),
    ],
    "Kỹ thuật": [
        st.Page(PAGES / "etl_monitor.py", title="Giám sát ETL", icon=":material/fact_check:", url_path="etl_monitor"),
    ],
})

with st.sidebar:
    st.markdown("**Kho dữ liệu sàn TMĐT Olist**  \nCO4031 · Nhóm 10")
    if using_admin():
        st.warning("Đang kết nối bằng tài khoản ETL (dw_admin). Chạy `python -m src.dashboard.setup_role` "
                   "để dùng tài khoản chỉ đọc cho dashboard.", icon=":material/lock_open:")
    theme_watcher()

nav.run()
