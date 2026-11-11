"""Exploratory data analysis (EDA) before and after preprocessing.

Part 1 - raw data, read straight from the CSV files in data/raw (independent of the ETL):
  structure of each file, missing values per column, duplicate rows, outliers of the numeric
  measures (IQR rule).
Part 2 - clean data, read from the staging / Data Mart tables after the ETL has run:
  row counts before and after preprocessing, correlation between order-level attributes and the
  late-delivery rate by binned attributes (distance, promised days, handling time).

Outputs: src/eda/results/{raw_structure, missing, outliers, before_after, correlation, late_by_bin}.csv
Usage:   python -m src.eda.run_eda          (run the ETL first for part 2)
"""
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from src.etl.config import DATA_DIR, ROOT, SQLALCHEMY_URL

OUT = ROOT / "src" / "eda" / "results"
FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}


def load_raw(name: str) -> pd.DataFrame:
    """Every column as text, empty fields as missing - the way the ETL sees the files."""
    return pd.read_csv(DATA_DIR / FILES[name], dtype=str, encoding="utf-8-sig")


def raw_delivery_days(orders: pd.DataFrame) -> pd.Series:
    bought = pd.to_datetime(orders.order_purchase_timestamp)
    got = pd.to_datetime(orders.order_delivered_customer_date)
    return ((got - bought).dt.total_seconds() / 86400).dropna()


def iqr_row(name, s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    q1, med, q3 = s.quantile([0.25, 0.5, 0.75])
    upper = q3 + 1.5 * (q3 - q1)
    return {"measure": name, "n": len(s), "min": s.min(), "q1": q1, "median": med, "q3": q3, "max": s.max(),
            "mean": s.mean(), "upper_fence": upper, "n_above_fence": int((s > upper).sum()),
            "share_above_fence": (s > upper).mean()}


def raw_part():
    structure, missing = [], []
    for name in FILES:
        df = load_raw(name)
        miss = df.isna().sum()
        structure.append({"file": name, "rows": len(df), "columns": df.shape[1],
                          "missing_cells": int(miss.sum()), "rows_with_missing": int(df.isna().any(axis=1).sum()),
                          "duplicate_rows": int(df.duplicated().sum())})
        for col, n in miss[miss > 0].items():
            missing.append({"file": name, "column": col, "missing": int(n), "share": n / len(df)})
    items, products, orders = load_raw("order_items"), load_raw("products"), load_raw("orders")
    outliers = [iqr_row("price", items.price), iqr_row("freight_value", items.freight_value),
                iqr_row("product_weight_g", products.product_weight_g),
                iqr_row("delivery_days", raw_delivery_days(orders))]
    return pd.DataFrame(structure), pd.DataFrame(missing), pd.DataFrame(outliers)


BEFORE_AFTER = [
    ("Đơn hàng", "SELECT COUNT(*) FROM staging.raw_orders", "SELECT COUNT(*) FROM staging.stg_orders",
     "SELECT COUNT(DISTINCT order_id) FROM dm.fact_sales"),
    ("Dòng sản phẩm trong đơn", "SELECT COUNT(*) FROM staging.raw_order_items",
     "SELECT COUNT(*) FROM staging.stg_order_items", "SELECT COUNT(*) FROM dm.fact_sales"),
    ("Đánh giá", "SELECT COUNT(*) FROM staging.raw_order_reviews", "SELECT COUNT(*) FROM staging.stg_reviews",
     "SELECT COUNT(review_score) FROM dm.v_order"),
    ("Khách hàng", "SELECT COUNT(*) FROM staging.raw_customers", "SELECT COUNT(*) FROM staging.stg_customers",
     "SELECT COUNT(*) - 1 FROM dm.dim_customer"),
    ("Sản phẩm", "SELECT COUNT(*) FROM staging.raw_products", "SELECT COUNT(*) FROM staging.stg_products",
     "SELECT COUNT(*) - 1 FROM dm.dim_product"),
    ("Dòng tọa độ geolocation", "SELECT COUNT(*) FROM staging.raw_geolocation", "SELECT COUNT(*) FROM staging.stg_geo",
     None),
    ("Mã bưu chính có tọa độ", "SELECT COUNT(DISTINCT geolocation_zip_code_prefix) FROM staging.raw_geolocation",
     "SELECT COUNT(*) FROM staging.stg_zip", None),
    ("Cách viết (thành phố, bang) của người bán",
     "SELECT COUNT(DISTINCT (seller_city, seller_state)) FROM staging.raw_sellers",
     "SELECT COUNT(DISTINCT (city, state)) FROM staging.stg_sellers",
     "SELECT COUNT(DISTINCT city_key) FROM dm.dim_seller WHERE seller_key > 0"),
    ("Cách viết (thành phố, bang) của khách hàng",
     "SELECT COUNT(DISTINCT (customer_city, customer_state)) FROM staging.raw_customers",
     "SELECT COUNT(DISTINCT (city, state)) FROM staging.stg_customers",
     "SELECT COUNT(DISTINCT city_key) FROM dm.dim_customer WHERE customer_key > 0"),
    ("Thành phố (khách hàng và người bán)", None, "SELECT COUNT(*) FROM staging.stg_city",
     "SELECT COUNT(*) - 1 FROM dm.dim_city"),
]

# One row per delivered order: order-level measures plus the distance between seller and customer
# cities (first seller of the order) and the promised delivery time.
ORDER_LEVEL = """
WITH first_seller AS (
    SELECT DISTINCT ON (order_id) order_id, seller_key FROM dm.fact_sales ORDER BY order_id, order_item_id),
weight AS (
    SELECT f.order_id, SUM(p.weight_g) AS weight_g
    FROM dm.fact_sales f JOIN dm.dim_product p ON p.product_key = f.product_key GROUP BY f.order_id)
SELECT o.order_id, o.approval_days::float, o.handling_days::float, o.shipping_days::float,
       o.delivery_days::float, (de.full_date - dp.full_date)::float AS promised_days,
       o.order_value::float, o.order_freight::float, w.weight_g::float, o.n_items::float,
       2 * 6371 * asin(sqrt(power(sin(radians(cc.latitude - sc.latitude) / 2), 2)
           + cos(radians(sc.latitude)) * cos(radians(cc.latitude))
             * power(sin(radians(cc.longitude - sc.longitude) / 2), 2)))::float AS distance_km,
       o.is_late::float, o.review_score::float
FROM dm.v_order o
JOIN dm.dim_date dp ON dp.date_key = o.purchase_date_key
JOIN dm.dim_date de ON de.date_key = o.estimated_date_key
JOIN first_seller fs ON fs.order_id = o.order_id
JOIN dm.dim_seller s ON s.seller_key = fs.seller_key
JOIN dm.dim_city sc ON sc.city_key = s.city_key
JOIN dm.dim_customer c ON c.customer_key = o.customer_key
JOIN dm.dim_city cc ON cc.city_key = c.city_key
JOIN weight w ON w.order_id = o.order_id
WHERE o.is_late IS NOT NULL
"""
CORR_COLS = ["approval_days", "handling_days", "shipping_days", "delivery_days", "promised_days", "order_value",
             "order_freight", "weight_g", "distance_km", "is_late", "review_score"]
BINS = {
    "distance_km": ([0, 100, 500, 1000, 2000, np.inf], ["< 100", "100-500", "500-1.000", "1.000-2.000", "> 2.000"]),
    "promised_days": ([0, 15, 20, 25, 30, np.inf], ["≤ 15", "16-20", "21-25", "26-30", "> 30"]),
    "handling_days": ([-np.inf, 1, 3, 5, 10, np.inf], ["≤ 1", "1-3", "3-5", "5-10", "> 10"]),
}


def clean_part():
    eng = create_engine(SQLALCHEMY_URL)
    with eng.connect() as c:
        def one(sql):
            return None if sql is None else c.execute(text(sql)).scalar()
        ba = pd.DataFrame([{"object": o, "raw": one(r), "after_cleaning": one(s), "data_mart": one(d)}
                           for o, r, s, d in BEFORE_AFTER])
        od = pd.read_sql(text(ORDER_LEVEL), c)
    corr = od[CORR_COLS].corr(method="spearman")
    rows = []
    for col, (edges, labels) in BINS.items():
        b = pd.cut(od[col], edges, labels=labels, right=True)
        g = od.groupby(b, observed=False).agg(orders=("is_late", "size"), late_rate=("is_late", "mean"),
                                              avg_review=("review_score", "mean"))
        rows += [{"attribute": col, "bin": k, **v} for k, v in g.to_dict("index").items()]
    print(f"order-level rows: {len(od)}, distance missing: {od.distance_km.isna().sum()}")
    return ba, corr, pd.DataFrame(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    structure, missing, outliers = raw_part()
    structure.to_csv(OUT / "raw_structure.csv", index=False)
    missing.to_csv(OUT / "missing.csv", index=False)
    outliers.to_csv(OUT / "outliers.csv", index=False)
    ba, corr, bins = clean_part()
    ba.to_csv(OUT / "before_after.csv", index=False)
    corr.to_csv(OUT / "correlation.csv")
    bins.to_csv(OUT / "late_by_bin.csv", index=False)
    pd.set_option("display.width", 200)
    for name, df in [("structure", structure), ("missing", missing), ("outliers", outliers.round(2)),
                     ("before/after", ba), ("late by bin", bins.round(4))]:
        print(f"\n== {name}\n{df.to_string(index=False)}")
    print("\n== spearman correlation\n", corr.round(2).to_string())


if __name__ == "__main__":
    main()
