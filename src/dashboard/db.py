"""Database access for the dashboard.

The dashboard connects with its own login role `dashboard_app` (created by setup_role.py):
it inherits SELECT on dm / meta / dss from the read-only role `analyst_ro`, and may only INSERT
into dss.decision_log (report: Security -- Tính bảo mật). If DASHBOARD_DB_USER is not set in .env,
it falls back to the ETL admin account and the sidebar shows a warning.
"""
import os

import pandas as pd
import sqlalchemy as sa
import streamlit as st

from src.etl.config import DB  # also loads .env


def using_admin() -> bool:
    return not os.getenv("DASHBOARD_DB_USER")


@st.cache_resource
def engine() -> sa.Engine:
    if using_admin():
        user, password = DB["user"], DB["password"]
    else:
        user, password = os.getenv("DASHBOARD_DB_USER"), os.getenv("DASHBOARD_DB_PASSWORD", "")
    url = sa.engine.URL.create("postgresql+psycopg", username=user, password=password,
                               host=DB["host"], port=int(DB["port"]), database=DB["dbname"])
    return sa.create_engine(url, pool_pre_ping=True)


def _run(sql: str, params: dict | None) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(sa.text(sql), conn, params=params or {})


@st.cache_data(ttl=600, show_spinner=False)
def query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Read-only query, cached for 10 minutes (the Data Mart only changes when the ETL runs)."""
    return _run(sql, params)


def query_live(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Uncached query, for data the dashboard itself writes (the decision log)."""
    return _run(sql, params)


def log_decision(order_id: str, recommendation: str, decision: str, decided_by: str, note: str) -> None:
    """The only write of the dashboard: an operator approves or rejects a DSS recommendation."""
    with engine().begin() as conn:
        conn.execute(
            sa.text("INSERT INTO dss.decision_log (module, object_id, recommendation, decision, decided_by, note) "
                    "VALUES ('delay_risk', :order_id, :rec, :decision, :by, :note)"),
            {"order_id": order_id, "rec": recommendation, "decision": decision,
             "by": decided_by or None, "note": note or None},
        )
