"""Sidebar filters shared by the analysis pages, and the two base CTEs every analysis query starts from.

    items   grain = one product in one order (dm.fact_sales).
            Use it for ADDITIVE measures: revenue (price), freight, number of distinct orders / sellers.
    orders  grain = one order (dm.v_order).
            Use it for ORDER-LEVEL measures: delivery durations, late rate, review score. These values are
            repeated on every item of an order, so averaging them over fact_sales rows would count an order
            with three items three times (report section 3.2.4).

Both CTEs walk the snowflake schema: date, product -> category, customer -> city -> state (-> region).
Filters are passed as bound parameters, so the SQL text never changes and query results cache well.
A filter left empty means "all" (:all_regions / :all_cats = TRUE).
"""
from dataclasses import dataclass

import streamlit as st

from .db import query


def _month_list() -> list[str]:
    out, y, m = [], 2016, 9
    while (y, m) <= (2018, 10):          # purchase dates in the data: 04/9/2016 - 17/10/2018
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


MONTHS = _month_list()
REGIONS = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]

# Which orders count. Revenue excludes canceled / unavailable orders (src/dashboard/README.md);
# some report queries (route matrix, pivot) use every order, seller ranking only delivered ones.
STATUS = {
    "sales": "f.order_status NOT IN ('canceled', 'unavailable')",
    "delivered": "f.order_status = 'delivered'",
    "all": "TRUE",
}


def vn_month(ym: str) -> str:
    return f"{ym[5:]}/{ym[:4]}"


@dataclass(frozen=True)
class Filters:
    months: tuple[str, str]
    regions: tuple[str, ...] = ()
    cats: tuple[str, ...] = ()

    @property
    def params(self) -> dict:
        start, end = self.months
        return {
            "d_start": int(start.replace("-", "") + "01"),   # date_key is YYYYMMDD
            "d_end": int(end.replace("-", "") + "31"),
            "all_regions": not self.regions, "regions": list(self.regions),
            "all_cats": not self.cats, "cats": list(self.cats),
        }

    @property
    def is_default(self) -> bool:
        return self.months == (MONTHS[0], MONTHS[-1]) and not self.regions and not self.cats


def items_cte(status: str = "sales") -> str:
    return f"""items AS (
    SELECT f.order_id, f.order_item_id, f.seller_key, f.customer_key,
           f.price, f.freight_value, f.order_status, f.is_late, f.delivery_days, f.review_score,
           d.full_date, d.year, d.quarter, d.month,
           cat.category_name_en AS category,
           st.region, st.state_code, ci.city_name
    FROM dm.fact_sales f
    JOIN dm.dim_date d       ON d.date_key = f.purchase_date_key
    JOIN dm.dim_product p    ON p.product_key = f.product_key
    JOIN dm.dim_category cat ON cat.category_key = p.category_key
    JOIN dm.dim_customer cu  ON cu.customer_key = f.customer_key
    JOIN dm.dim_city ci      ON ci.city_key = cu.city_key
    JOIN dm.dim_state st     ON st.state_key = ci.state_key
    WHERE {STATUS[status]}
      AND f.purchase_date_key BETWEEN :d_start AND :d_end
      AND (:all_regions OR st.region = ANY(CAST(:regions AS text[])))
      AND (:all_cats OR cat.category_name_en = ANY(CAST(:cats AS text[])))
)"""


def orders_cte() -> str:
    # The category filter keeps an order if ANY of its items is in the chosen categories.
    return """orders AS (
    SELECT o.order_id, o.customer_key, o.order_status, o.order_value, o.order_freight,
           o.approval_days, o.handling_days, o.shipping_days, o.delivery_days,
           o.is_late, o.review_score,
           d.full_date, d.year, d.quarter, d.month,
           st.region, st.state_code, ci.city_name
    FROM dm.v_order o
    JOIN dm.dim_date d      ON d.date_key = o.purchase_date_key
    JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
    JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
    JOIN dm.dim_state st    ON st.state_key = ci.state_key
    WHERE o.purchase_date_key BETWEEN :d_start AND :d_end
      AND (:all_regions OR st.region = ANY(CAST(:regions AS text[])))
      AND (:all_cats OR EXISTS (
            SELECT 1
            FROM dm.fact_sales f2
            JOIN dm.dim_product p2  ON p2.product_key = f2.product_key
            JOIN dm.dim_category c2 ON c2.category_key = p2.category_key
            WHERE f2.order_id = o.order_id
              AND c2.category_name_en = ANY(CAST(:cats AS text[]))))
)"""


# ---------- sidebar ----------
# Streamlit forgets a widget's value when the user opens a page that does not show it, so the
# chosen values are kept in their own session keys (f_*). The multiselects are seeded through their
# widget keys (w_f_*). The month slider is NOT: a select_slider is a range slider only when `value`
# is a tuple, so it gets value=ss.f_months and no key (its value is read back after each run).
_DEFAULTS = {"f_months": (MONTHS[0], MONTHS[-1]), "f_regions": [], "f_cats": []}


def _month_range(v) -> tuple[str, str]:
    """Always a (start, end) pair of valid months, whatever shape the widget handed back."""
    vals = [v] if isinstance(v, str) else list(v or [])
    vals = sorted(m for m in vals if m in MONTHS)
    return (vals[0], vals[-1]) if vals else (MONTHS[0], MONTHS[-1])


def _keep(name: str) -> None:
    st.session_state[name] = st.session_state["w_" + name]


def _reset() -> None:
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.f_months_ver = st.session_state.get("f_months_ver", 0) + 1   # rebuild the slider


def sidebar_filters() -> Filters:
    ss = st.session_state
    for k, v in _DEFAULTS.items():
        ss.setdefault(k, v)
    ss.f_months = _month_range(ss.f_months)
    for k in ("f_regions", "f_cats"):
        ss["w_" + k] = ss[k]
    cats = query("SELECT category_name_en FROM dm.dim_category WHERE category_key <> -1 ORDER BY 1")
    with st.sidebar:
        st.subheader("Bộ lọc")
        picked = st.select_slider("Tháng đặt hàng", options=MONTHS, value=ss.f_months, format_func=vn_month,
                                  key=f"w_f_months_{ss.get('f_months_ver', 0)}")
        ss.f_months = _month_range(picked)
        st.multiselect("Vùng của khách hàng", REGIONS, key="w_f_regions", placeholder="Tất cả các vùng",
                       on_change=_keep, args=("f_regions",))
        st.multiselect("Ngành hàng", cats.category_name_en.tolist(), key="w_f_cats",
                       placeholder="Tất cả ngành hàng", on_change=_keep, args=("f_cats",))
        st.button("Xóa bộ lọc", on_click=_reset, width="stretch")
    return Filters(_month_range(ss.f_months), tuple(ss.f_regions), tuple(ss.f_cats))
