-- 02_datamart_ddl.sql
-- Data Mart in snowflake schema, exactly as designed in report/Sections/thietke/logic.tex
-- (tab:fact, tab:dim) and report/drawio-files/schema-snowflake.mmd.
--   fact_sales  : granularity = one product in one order (order_id, order_item_id), accumulating snapshot
--   dimensions  : dim_date, dim_state, dim_city, dim_category, dim_product, dim_customer, dim_seller (7 tables)
-- Every dimension has an "unknown" member with key -1, so the fact table never holds a NULL foreign key.
-- Full load: the ETL truncates and reloads these tables inside one transaction.

DROP TABLE IF EXISTS dm.fact_sales, dm.dim_customer, dm.dim_seller, dm.dim_product,
    dm.dim_category, dm.dim_city, dm.dim_state, dm.dim_date CASCADE;

-- ---------- Dimensions ----------
CREATE TABLE dm.dim_date (
    date_key     INTEGER PRIMARY KEY,          -- YYYYMMDD, -1 = unknown / not happened yet
    full_date    DATE,
    day          SMALLINT,
    month        SMALLINT,
    quarter      SMALLINT,
    year         SMALLINT,
    day_of_week  VARCHAR(10)                   -- e.g. 'Monday'
);

CREATE TABLE dm.dim_state (
    state_key   INTEGER PRIMARY KEY,
    state_code  CHAR(2) NOT NULL UNIQUE,       -- 'SP', 'RJ', ... ; '??' for unknown
    state_name  VARCHAR(40) NOT NULL,
    region      VARCHAR(20) NOT NULL           -- Norte, Nordeste, Centro-Oeste, Sudeste, Sul
);

CREATE TABLE dm.dim_city (
    city_key    INTEGER PRIMARY KEY,
    city_name   VARCHAR(80) NOT NULL,          -- lower case, accents removed, trimmed
    latitude    NUMERIC(9,6),                  -- mean of the zip-prefix coordinates; NULL when unknown
    longitude   NUMERIC(9,6),
    state_key   INTEGER NOT NULL REFERENCES dm.dim_state (state_key),
    UNIQUE (city_name, state_key)
);

CREATE TABLE dm.dim_category (
    category_key      INTEGER PRIMARY KEY,
    category_name_pt  VARCHAR(80) NOT NULL UNIQUE,   -- 'unknown' for products without a category
    category_name_en  VARCHAR(80) NOT NULL
);

CREATE TABLE dm.dim_product (
    product_key   INTEGER PRIMARY KEY,
    product_id    VARCHAR(32) NOT NULL UNIQUE,
    category_key  INTEGER NOT NULL REFERENCES dm.dim_category (category_key),
    weight_g      INTEGER,                     -- NULL when missing or 0 in the source
    length_cm     INTEGER,
    height_cm     INTEGER,
    width_cm      INTEGER,
    photos_qty    SMALLINT
);

CREATE TABLE dm.dim_customer (
    customer_key        INTEGER PRIMARY KEY,
    customer_unique_id  VARCHAR(32) NOT NULL UNIQUE,  -- one row per real customer (SCD type 1)
    zip_code_prefix     CHAR(5),                      -- address of the customer's most recent order
    city_key            INTEGER NOT NULL REFERENCES dm.dim_city (city_key)
);

CREATE TABLE dm.dim_seller (
    seller_key       INTEGER PRIMARY KEY,
    seller_id        VARCHAR(32) NOT NULL UNIQUE,
    zip_code_prefix  CHAR(5),
    city_key         INTEGER NOT NULL REFERENCES dm.dim_city (city_key)
);

-- ---------- Fact ----------
CREATE TABLE dm.fact_sales (
    order_id            VARCHAR(32) NOT NULL,     -- degenerate dimension
    order_item_id       SMALLINT    NOT NULL,
    product_key         INTEGER NOT NULL REFERENCES dm.dim_product (product_key),
    seller_key          INTEGER NOT NULL REFERENCES dm.dim_seller (seller_key),
    customer_key        INTEGER NOT NULL REFERENCES dm.dim_customer (customer_key),
    purchase_date_key   INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    approved_date_key   INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    carrier_date_key    INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    delivered_date_key  INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    estimated_date_key  INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    review_date_key     INTEGER NOT NULL REFERENCES dm.dim_date (date_key),
    order_status        VARCHAR(12) NOT NULL,
    price               NUMERIC(10,2) NOT NULL,   -- additive
    freight_value       NUMERIC(10,2) NOT NULL,   -- additive
    approval_days       NUMERIC(8,2),             -- order-level, non-additive: aggregate over DISTINCT order_id
    handling_days       NUMERIC(8,2),
    shipping_days       NUMERIC(8,2),
    delivery_days       NUMERIC(8,2),
    is_late             SMALLINT,                 -- 1 late, 0 on time, NULL not delivered
    review_score        SMALLINT,                 -- 1-5, NULL when the order has no review
    PRIMARY KEY (order_id, order_item_id),
    CHECK (review_score IS NULL OR review_score BETWEEN 1 AND 5),
    CHECK (is_late IS NULL OR is_late IN (0, 1))
);

-- Indexes on the fact foreign keys and order_id (report: Load -- Chỉ mục).
CREATE INDEX ix_fact_sales_order     ON dm.fact_sales (order_id);
CREATE INDEX ix_fact_sales_product   ON dm.fact_sales (product_key);
CREATE INDEX ix_fact_sales_seller    ON dm.fact_sales (seller_key);
CREATE INDEX ix_fact_sales_customer  ON dm.fact_sales (customer_key);
CREATE INDEX ix_fact_sales_purchase  ON dm.fact_sales (purchase_date_key);
CREATE INDEX ix_fact_sales_delivered ON dm.fact_sales (delivered_date_key);

-- ---------- Unknown members ----------
INSERT INTO dm.dim_date     VALUES (-1, NULL, NULL, NULL, NULL, NULL, 'Unknown');
INSERT INTO dm.dim_state    VALUES (-1, '??', 'Unknown', 'Unknown');
INSERT INTO dm.dim_city     VALUES (-1, 'unknown', NULL, NULL, -1);
INSERT INTO dm.dim_category VALUES (-1, 'unknown', 'unknown');
INSERT INTO dm.dim_product  VALUES (-1, 'UNKNOWN', -1, NULL, NULL, NULL, NULL, NULL);
INSERT INTO dm.dim_customer VALUES (-1, 'UNKNOWN', NULL, -1);
INSERT INTO dm.dim_seller   VALUES (-1, 'UNKNOWN', NULL, -1);

-- ---------- Order-level view (report: "View theo đơn hàng", logic.tex) ----------
-- One row per order. Use it for every order-level measure (delivery time, late rate, review score)
-- so that orders with several items are not counted several times.
CREATE OR REPLACE VIEW dm.v_order AS
SELECT  f.order_id,
        MIN(f.customer_key)        AS customer_key,
        MIN(f.purchase_date_key)   AS purchase_date_key,
        MIN(f.delivered_date_key)  AS delivered_date_key,
        MIN(f.estimated_date_key)  AS estimated_date_key,
        MIN(f.order_status)        AS order_status,
        COUNT(*)                   AS n_items,
        COUNT(DISTINCT f.seller_key) AS n_sellers,
        SUM(f.price)               AS order_value,
        SUM(f.freight_value)       AS order_freight,
        MIN(f.approval_days)       AS approval_days,
        MIN(f.handling_days)       AS handling_days,
        MIN(f.shipping_days)       AS shipping_days,
        MIN(f.delivery_days)       AS delivery_days,
        MIN(f.is_late)             AS is_late,
        MIN(f.review_score)        AS review_score
FROM dm.fact_sales f
GROUP BY f.order_id;
