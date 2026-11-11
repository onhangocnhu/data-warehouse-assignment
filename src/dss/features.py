"""Point-in-time features for DSS module 1 (late-delivery early warning), read from the Data Mart.

Two decision moments:
  * approval  - the order has just been approved (early warning, most time to act);
  * handover  - the seller has just handed the parcel to the carrier (more information, less time).
Every feature must be known at its decision moment. Historical rates only use outcomes that were
KNOWN strictly before the moment (pandas.merge_asof with allow_exact_matches=False).

Label: is_late of delivered orders; orders still open at the data cut-off whose estimated date has
already passed are certainly late, so they are labelled 1 (otherwise the most recent months would
lose their late orders). Each label has a `label_time`, the day it became known.
"""
import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from src.etl.config import SQLALCHEMY_URL

ORDER_SQL = """
WITH lot AS (
    SELECT order_id, seller_key, SUM(price) AS lot_value
    FROM dm.fact_sales GROUP BY order_id, seller_key
), main_seller AS (
    SELECT DISTINCT ON (order_id) order_id, seller_key
    FROM lot ORDER BY order_id, lot_value DESC, seller_key
)
SELECT f.order_id,
       MIN(f.purchase_date_key)            AS purchase_date_key,
       MIN(f.estimated_date_key)           AS estimated_date_key,
       MIN(f.carrier_date_key)             AS carrier_date_key,     -- handover stage only
       MIN(f.delivered_date_key)           AS delivered_date_key,   -- label side only, never a feature
       MIN(f.order_status)                 AS order_status,         -- label side only, never a feature
       MIN(f.is_late)                      AS is_late,              -- label
       MIN(f.approval_days)::float         AS approval_days,
       MIN(f.handling_days)::float         AS handling_days,        -- handover stage only
       MIN(f.delivery_days)::float         AS delivery_days,        -- history only (outcome of past orders)
       COUNT(*)                            AS n_items,
       COUNT(DISTINCT f.seller_key)        AS n_sellers,
       SUM(f.price)::float                 AS order_value,
       SUM(f.freight_value)::float         AS order_freight,
       SUM(p.weight_g)::float              AS total_weight_g,
       SUM(p.length_cm * p.height_cm * p.width_cm)::float AS total_volume_cm3,
       MODE() WITHIN GROUP (ORDER BY cat.category_name_en) AS main_category,
       MIN(ms.seller_key)                  AS main_seller_key,
       MIN(cs.state_code)                  AS customer_state,
       MIN(cs.region)                      AS customer_region,
       MIN(cc.latitude)::float             AS c_lat,
       MIN(cc.longitude)::float            AS c_lng
FROM dm.fact_sales f
JOIN main_seller ms      ON ms.order_id = f.order_id
JOIN dm.dim_product p    ON p.product_key = f.product_key
JOIN dm.dim_category cat ON cat.category_key = p.category_key
JOIN dm.dim_customer cu  ON cu.customer_key = f.customer_key
JOIN dm.dim_city cc      ON cc.city_key = cu.city_key
JOIN dm.dim_state cs     ON cs.state_key = cc.state_key
GROUP BY f.order_id
"""

SELLER_SQL = """
SELECT se.seller_key AS main_seller_key, st.state_code AS seller_state, st.region AS seller_region,
       ci.latitude::float AS s_lat, ci.longitude::float AS s_lng
FROM dm.dim_seller se
JOIN dm.dim_city ci  ON ci.city_key = se.city_key
JOIN dm.dim_state st ON st.state_key = ci.state_key
"""

# ---- feature sets ------------------------------------------------------------------------------
STATIC = ["promised_days", "distance_km", "is_cross_state", "n_items", "n_sellers", "order_value",
          "order_freight", "freight_ratio", "total_weight_g", "total_volume_cm3", "approval_days",
          "purchase_month", "purchase_dow", "days_to_black_friday"]
HISTORY = ["seller_hist_n", "seller_hist_late", "route_hist_n", "route_hist_late", "cstate_hist_late"]
RECENT = ["global_late_7d", "global_late_30d", "route_late_90d", "seller_late_90d", "cstate_late_30d",
          "route_mean_delivery", "slack_days", "seller_mean_handling", "seller_orders_7d",
          "platform_orders_7d", "platform_load_ratio"]
HANDOVER = ["handling_days", "days_left_at_handover", "handover_dow", "handling_vs_seller",
            "global_late_7d_at_handover"]
CAT = ["customer_state", "seller_state", "customer_region", "main_category"]

NUM_BASE = STATIC + HISTORY                       # first version (evaluate_baseline.py)
NUM = NUM_BASE                                    # kept for backward compatibility
NUM_APPROVAL = STATIC + HISTORY + RECENT
NUM_HANDOVER = NUM_APPROVAL + HANDOVER
# carrier backlog at handover: share of recent handovers already overdue and still not delivered
BACKLOG = ["global_backlog", "cstate_backlog", "route_backlog"]
NUM_HANDOVER_BL = NUM_HANDOVER + BACKLOG

LEAKY = ["delivered_date_key", "delivered_date", "order_status", "is_late", "label", "label_time",
         "delivery_days", "review_score", "review_date_key"]
for _cols in (NUM_APPROVAL, NUM_HANDOVER, NUM_HANDOVER_BL):
    assert not set(LEAKY) & set(_cols + CAT), "leaky column used as a feature"

TRAIN_END = "2018-04-01"   # p0 used for smoothing is computed only from orders before this date
DAY = pd.Timedelta(days=1)


def key_to_date(s: pd.Series) -> pd.Series:
    """20171124 -> Timestamp, -1 -> NaT."""
    return pd.to_datetime(s.where(s > 0).astype("Int64").astype("string"), format="%Y%m%d", errors="coerce")


def haversine_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = (np.radians(x) for x in (lat1, lng1, lat2, lng2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(a))


def load_orders(engine=None) -> pd.DataFrame:
    engine = engine or create_engine(SQLALCHEMY_URL)
    orders = pd.read_sql(ORDER_SQL, engine)
    sellers = pd.read_sql(SELLER_SQL, engine)
    return orders.merge(sellers, on="main_seller_key", how="left")


# ---- labels ------------------------------------------------------------------------------------
def add_labels(df: pd.DataFrame) -> pd.DataFrame:
    cutoff = df[["purchase_date", "delivered_date", "carrier_date"]].max().max()
    delivered = df.order_status.eq("delivered") & df.delivered_date.notna()
    still_open = ~df.order_status.isin(["delivered", "canceled", "unavailable"]) & df.delivered_date.isna()
    censored_late = still_open & (df.estimated_date < cutoff)
    df["label"] = np.where(delivered, df.is_late, np.where(censored_late, 1.0, np.nan))
    # When the outcome becomes known to the platform: lateness is known the day after the estimated
    # date (the parcel has not arrived), an on-time delivery is known on the delivery day.
    late_known = df.estimated_date + DAY
    df["label_time"] = pd.Series(pd.NaT, index=df.index, dtype=df.delivered_date.dtype)
    df.loc[df.label == 1, "label_time"] = late_known[df.label == 1]
    df.loc[df.label == 0, "label_time"] = df.delivered_date[df.label == 0]
    df["censored_late"] = censored_late.astype(int)
    df.attrs["cutoff"] = cutoff
    return df


# ---- point-in-time helpers ---------------------------------------------------------------------
def cum_before(events: pd.DataFrame, key: str, time_col: str, values: list[str],
               query: pd.DataFrame, qtime: str) -> pd.DataFrame:
    """For each query row, cumulative sums of `values` over events of the same key with
    event time strictly before the query time. Returns a frame aligned on query.index."""
    ev = events[[key, time_col] + values].dropna(subset=[time_col]).sort_values(time_col).copy()
    cum_cols = [f"_c_{v}" for v in values]
    ev[cum_cols] = ev.groupby(key)[values].cumsum().to_numpy()
    q = query[[key, qtime]].reset_index().rename(columns={"index": "_row"}).sort_values(qtime)
    q = q[q[qtime].notna()]
    out = pd.merge_asof(q, ev[[key, time_col] + cum_cols], left_on=qtime, right_on=time_col, by=key,
                        allow_exact_matches=False, direction="backward")
    out = out.set_index("_row").reindex(query.index)[cum_cols].fillna(0)
    out.columns = values
    return out


def rate_window(events, key, time_col, query, qtime, window_days=None, m=20.0, p0=0.08):
    """Smoothed late rate of `key` over events known before qtime (optionally only the last N days)."""
    now = cum_before(events, key, time_col, ["n", "late"], query, qtime)
    if window_days:
        q2 = query[[key, qtime]].copy()
        q2[qtime] = q2[qtime] - pd.Timedelta(days=window_days)
        past = cum_before(events, key, time_col, ["n", "late"], q2, qtime)
        now = now - past
    return now["n"], (now["late"] + m * p0) / (now["n"] + m)


def _day(s: pd.Series) -> np.ndarray:
    return s.values.astype("datetime64[D]").astype("int64").astype(float)


def backlog_counts(df, ev, key, qtime, window=45):
    """For each row: number of orders of the same key handed to the carrier in the `window` days before
    qtime, and how many of them were already past their estimated date and not delivered on day qtime.
    Only carrier, estimated and delivered dates strictly before qtime are used (point-in-time)."""
    q = df[[key, qtime]].dropna()
    qd = _day(q[qtime])
    c_all = _day(ev.carrier_date)
    e_all = _day(ev.estimated_date)
    l_all = np.where(ev.delivered_date.isna(), 1e12, _day(ev.delivered_date.fillna(pd.Timestamp("2100-01-01"))))
    ev_key = ev[key].to_numpy()
    res = {}
    for k, qdays in pd.Series(qd, index=q.index).groupby(q[key].to_numpy()):
        sel = ev_key == k
        if not sel.any():
            continue
        c, e, dl = c_all[sel], e_all[sel], l_all[sel]
        tdays = np.unique(qdays.to_numpy())
        for chunk in np.array_split(tdays, max(1, len(tdays) // 200)):
            t = chunk[:, None]
            inwin = (c >= t - window) & (c < t)
            over = inwin & (e < t) & (dl >= t)
            for ti, n, o in zip(chunk, inwin.sum(1), over.sum(1)):
                res[(k, ti)] = (n, o)
    pairs = [res.get(kk, (0, 0)) for kk in zip(q[key], qd)]
    n = pd.Series(0.0, index=df.index)
    o = pd.Series(0.0, index=df.index)
    n.loc[q.index] = [p[0] for p in pairs]
    o.loc[q.index] = [p[1] for p in pairs]
    return n, o


def static_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["purchase_date"] = key_to_date(df.purchase_date_key)
    df["estimated_date"] = key_to_date(df.estimated_date_key)
    df["delivered_date"] = key_to_date(df.delivered_date_key)
    df["carrier_date"] = key_to_date(df.carrier_date_key)
    df["promised_days"] = (df.estimated_date - df.purchase_date).dt.days
    df["distance_km"] = haversine_km(df.s_lat, df.s_lng, df.c_lat, df.c_lng)
    df["is_cross_state"] = (df.seller_state != df.customer_state).astype(int)
    df["freight_ratio"] = df.order_freight / df.order_value.replace(0, np.nan)
    df["purchase_month"] = df.purchase_date.dt.month
    df["purchase_dow"] = df.purchase_date.dt.dayofweek
    bf = pd.to_datetime(np.where(df.purchase_date <= "2017-11-24", "2017-11-24", "2018-11-23"))
    df["days_to_black_friday"] = (bf - df.purchase_date).dt.days.clip(upper=60)
    df["route"] = df.seller_state.fillna("??") + "->" + df.customer_state.fillna("??")
    df["all"] = "all"
    return df


def build_features(df: pd.DataFrame | None = None) -> pd.DataFrame:
    df = add_labels(static_features(load_orders() if df is None else df))
    p0 = df.loc[df.purchase_date < TRAIN_END, "label"].mean()
    df.attrs["p0"] = p0

    # outcome events: one per labelled order, known at label_time
    ev = df.loc[df.label.notna(), ["main_seller_key", "route", "customer_state", "all", "label_time",
                                   "label", "delivery_days", "delivered_date"]].rename(columns={"label": "late"})
    ev["n"] = 1.0
    t = "purchase_date"

    # all-time history (first version of the features)
    for key, name in [("main_seller_key", "seller"), ("route", "route"), ("customer_state", "cstate")]:
        n, rate = rate_window(ev, key, "label_time", df, t, None, 20, p0)
        df[f"{name}_hist_n"], df[f"{name}_hist_late"] = n, rate

    # recent windows: capture drift (strikes, peak season) that all-time rates average away
    _, df["global_late_7d"] = rate_window(ev, "all", "label_time", df, t, 7, 1, p0)
    _, df["global_late_30d"] = rate_window(ev, "all", "label_time", df, t, 30, 1, p0)
    _, df["route_late_90d"] = rate_window(ev, "route", "label_time", df, t, 90, 10, p0)
    _, df["seller_late_90d"] = rate_window(ev, "main_seller_key", "label_time", df, t, 90, 10, p0)
    _, df["cstate_late_30d"] = rate_window(ev, "customer_state", "label_time", df, t, 30, 10, p0)

    # promised time versus what the route actually needed in the past
    dev = ev[ev.delivery_days.notna() & ev.delivered_date.notna()].copy()   # known on the delivery day
    c = cum_before(dev, "route", "delivered_date", ["n", "delivery_days"], df, t)
    glob = cum_before(dev, "all", "delivered_date", ["n", "delivery_days"], df, t)
    glob_mean = glob.delivery_days / glob.n.replace(0, np.nan)
    df["route_mean_delivery"] = (c.delivery_days + 10 * glob_mean) / (c.n + 10)
    df["slack_days"] = df.promised_days - df.route_mean_delivery

    # seller operations: average handling time known before the purchase, and current load
    hev = df.loc[df.handling_days.notna() & df.carrier_date.notna(),
                 ["main_seller_key", "carrier_date", "handling_days"]].copy()
    hev["n"] = 1.0
    h = cum_before(hev, "main_seller_key", "carrier_date", ["n", "handling_days"], df, t)
    hall = cum_before(hev.assign(all="all"), "all", "carrier_date", ["n", "handling_days"], df, t)
    df["seller_mean_handling"] = (h.handling_days + 5 * hall.handling_days / hall.n.replace(0, np.nan)) / (h.n + 5)

    pev = df[["main_seller_key", "all", "purchase_date"]].copy()
    pev["n"] = 1.0
    for key, col in [("main_seller_key", "seller_orders_7d"), ("all", "platform_orders_7d")]:
        now = cum_before(pev, key, "purchase_date", ["n"], df, t)
        back = cum_before(pev, key, "purchase_date", ["n"], df.assign(**{t: df[t] - pd.Timedelta(days=7)}), t)
        df[col] = now.n - back.n
    back90 = cum_before(pev, "all", "purchase_date", ["n"], df.assign(**{t: df[t] - pd.Timedelta(days=90)}), t)
    now_all = cum_before(pev, "all", "purchase_date", ["n"], df, t)
    df["platform_load_ratio"] = df.platform_orders_7d / ((now_all.n - back90.n) / 90 * 7).replace(0, np.nan)

    # handover-stage features (known when the parcel reaches the carrier)
    df["days_left_at_handover"] = (df.estimated_date - df.carrier_date).dt.days
    df["handover_dow"] = df.carrier_date.dt.dayofweek
    df["handling_vs_seller"] = df.handling_days - df.seller_mean_handling
    _, df["global_late_7d_at_handover"] = rate_window(ev, "all", "label_time", df, "carrier_date", 7, 1, p0)

    # carrier backlog on the handover day (an early sign of a carrier-wide problem)
    bev = df.loc[df.carrier_date.notna() & df.estimated_date.notna() & df.order_status.ne("canceled"),
                 ["route", "customer_state", "all", "carrier_date", "estimated_date", "delivered_date"]]
    n, o = backlog_counts(df, bev, "all", "carrier_date")
    df["global_backlog"] = o / n.replace(0, np.nan)
    for key, col in [("customer_state", "cstate_backlog"), ("route", "route_backlog")]:
        n, o = backlog_counts(df, bev, key, "carrier_date")
        df[col] = (o + 20 * df.global_backlog.fillna(0)) / (n + 20)
    return df
