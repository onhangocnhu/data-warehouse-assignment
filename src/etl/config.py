"""Settings shared by the ETL, DSS and dashboard: database connection and file locations."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "src" / ".env")

DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "olist_dw"),
    "user": os.getenv("DB_USER", "dw_admin"),
    "password": os.getenv("DB_PASSWORD", ""),
}
DSN = " ".join(f"{k}={v}" for k, v in DB.items())
SQLALCHEMY_URL = "postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}".format(**DB)

DATA_DIR = ROOT / os.getenv("DATA_DIR", "data/raw")
REF_DIR = ROOT / "data" / "reference"
SQL_DIR = ROOT / "src" / "sql"

# (directory, file) -> (staging table, expected number of data rows)
SOURCES = {
    (DATA_DIR, "olist_orders_dataset.csv"): ("raw_orders", 99441),
    (DATA_DIR, "olist_order_items_dataset.csv"): ("raw_order_items", 112650),
    (DATA_DIR, "olist_order_payments_dataset.csv"): ("raw_order_payments", 103886),
    (DATA_DIR, "olist_order_reviews_dataset.csv"): ("raw_order_reviews", 99224),
    (DATA_DIR, "olist_customers_dataset.csv"): ("raw_customers", 99441),
    (DATA_DIR, "olist_sellers_dataset.csv"): ("raw_sellers", 3095),
    (DATA_DIR, "olist_products_dataset.csv"): ("raw_products", 32951),
    (DATA_DIR, "olist_geolocation_dataset.csv"): ("raw_geolocation", 1000163),
    (DATA_DIR, "product_category_name_translation.csv"): ("raw_category_translation", 71),
    (REF_DIR, "state_region.csv"): ("ref_state_region", 27),
    (REF_DIR, "category_translation_patch.csv"): ("ref_category_patch", 2),
}

# DDL that only needs to exist once (run with --init); 02_datamart_ddl.sql is re-run by every full load.
INIT_SQL = ["00_schemas.sql", "01_staging_raw.sql", "02_datamart_ddl.sql", "03_meta_ddl.sql", "04_dss_ddl.sql"]
