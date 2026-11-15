-- 10_transform.sql
-- Transformation: staging.raw_* (TEXT, as in the CSV files) -> staging.stg_* (typed, cleaned, integrated).
-- Implements the rules of tab:quytac in report/Sections/thietke/etl.tex.
-- Every table is dropped and rebuilt, so the step can be re-run safely.
-- Expects the session setting etl.run_id (set by run_etl.py) for meta.rejected_record.

SET client_min_messages = warning;

-- ---------------------------------------------------------------------------------------------
-- City-name normalisation: lower case, no accents, keep the part before '/', drop a trailing
-- state code ('- sp', ', rj'), collapse spaces. Returns NULL for empty strings.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.norm_city(t TEXT) RETURNS TEXT
LANGUAGE sql IMMUTABLE AS $$
  SELECT NULLIF(btrim(regexp_replace(regexp_replace(
           split_part(lower(public.unaccent(coalesce(t, ''))), '/', 1),
           '\s*[-,]\s*[a-z]{2}\s*$', ''),
         '\s+', ' ', 'g')), '')
$$;

DELETE FROM meta.rejected_record WHERE run_id = current_setting('etl.run_id')::int;

-- ---------------------------------------------------------------------------------------------
-- Orders: cast timestamps, compute the order-level measures and the late flag
-- ---------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.stg_orders;
CREATE TABLE staging.stg_orders AS
WITH t AS (
    SELECT o.order_id, o.customer_id, c.customer_unique_id, o.order_status,
           o.order_purchase_timestamp::timestamp      AS purchase_ts,
           o.order_approved_at::timestamp             AS approved_ts,
           o.order_delivered_carrier_date::timestamp  AS carrier_ts,
           o.order_delivered_customer_date::timestamp AS delivered_ts,
           o.order_estimated_delivery_date::timestamp AS estimated_ts
    FROM staging.raw_orders o
    JOIN staging.raw_customers c USING (customer_id)
)
SELECT t.*,
       CASE WHEN approved_ts  >= purchase_ts THEN ROUND(EXTRACT(EPOCH FROM approved_ts  - purchase_ts) / 86400.0, 2) END AS approval_days,
       CASE WHEN carrier_ts   >= approved_ts THEN ROUND(EXTRACT(EPOCH FROM carrier_ts   - approved_ts) / 86400.0, 2) END AS handling_days,
       CASE WHEN delivered_ts >= carrier_ts  THEN ROUND(EXTRACT(EPOCH FROM delivered_ts - carrier_ts)  / 86400.0, 2) END AS shipping_days,
       CASE WHEN delivered_ts >= purchase_ts THEN ROUND(EXTRACT(EPOCH FROM delivered_ts - purchase_ts) / 86400.0, 2) END AS delivery_days,
       CASE WHEN order_status = 'delivered' AND delivered_ts IS NOT NULL
            THEN (delivered_ts::date > estimated_ts::date)::int::smallint END AS is_late
FROM t;
CREATE UNIQUE INDEX ON staging.stg_orders (order_id);

INSERT INTO meta.rejected_record (run_id, source, record_key, action, reason)
SELECT current_setting('etl.run_id')::int, 'orders', order_id, 'MODIFIED',
       'Thời điểm bàn giao vận chuyển trước thời điểm duyệt: handling_days để trống'
FROM staging.stg_orders WHERE carrier_ts < approved_ts
UNION ALL
SELECT current_setting('etl.run_id')::int, 'orders', order_id, 'MODIFIED',
       'Thời điểm bàn giao vận chuyển sau thời điểm nhận hàng: shipping_days để trống'
FROM staging.stg_orders WHERE carrier_ts > delivered_ts
UNION ALL
SELECT current_setting('etl.run_id')::int, 'orders', order_id, 'MODIFIED',
       'Trạng thái delivered nhưng thiếu thời điểm nhận hàng: không tính chỉ số giao hàng'
FROM staging.stg_orders WHERE order_status = 'delivered' AND delivered_ts IS NULL;

-- ---------------------------------------------------------------------------------------------
-- Order items
-- ---------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.stg_order_items;
CREATE TABLE staging.stg_order_items AS
SELECT order_id, order_item_id::smallint AS order_item_id, product_id, seller_id,
       shipping_limit_date::timestamp AS shipping_limit_ts,
       price::numeric(10,2) AS price, freight_value::numeric(10,2) AS freight_value
FROM staging.raw_order_items;

INSERT INTO meta.rejected_record (run_id, source, record_key, action, reason)
SELECT current_setting('etl.run_id')::int, 'orders', o.order_id, 'DROPPED',
       'Đơn hàng không có dòng sản phẩm: không nạp vào bảng fact'
FROM staging.stg_orders o
WHERE NOT EXISTS (SELECT 1 FROM staging.stg_order_items i WHERE i.order_id = o.order_id);

-- ---------------------------------------------------------------------------------------------
-- Reviews: one official review per order = the one answered last
-- ---------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.stg_reviews;
CREATE TABLE staging.stg_reviews AS
SELECT order_id, review_id, review_score::smallint AS review_score,
       review_creation_date::timestamp AS review_creation_ts,
       review_answer_timestamp::timestamp AS review_answer_ts
FROM (
    SELECT r.*, ROW_NUMBER() OVER (PARTITION BY order_id
                                   ORDER BY review_answer_timestamp::timestamp DESC, review_id) AS rn
    FROM staging.raw_order_reviews r
) x
WHERE rn = 1;
CREATE UNIQUE INDEX ON staging.stg_reviews (order_id);

-- ---------------------------------------------------------------------------------------------
-- Geography
-- ---------------------------------------------------------------------------------------------
-- (a) geolocation: drop exact duplicates and points outside Brazil, normalise names
DROP TABLE IF EXISTS staging.stg_geo;
CREATE TABLE staging.stg_geo AS
SELECT geolocation_zip_code_prefix AS zip,
       geolocation_lat::numeric AS lat, geolocation_lng::numeric AS lng,
       staging.norm_city(geolocation_city) AS city, upper(geolocation_state) AS state
FROM (SELECT DISTINCT * FROM staging.raw_geolocation) g
WHERE geolocation_lat::numeric BETWEEN -33.75 AND 5.27
  AND geolocation_lng::numeric BETWEEN -73.99 AND -34.79;
CREATE INDEX ON staging.stg_geo (city, state);

-- (b) one state and one city per zip prefix: the most frequent value
DROP TABLE IF EXISTS staging.stg_zip;
CREATE TABLE staging.stg_zip AS
SELECT zip,
       MODE() WITHIN GROUP (ORDER BY state) AS state,
       MODE() WITHIN GROUP (ORDER BY city)  AS city
FROM staging.stg_geo
GROUP BY zip;
CREATE UNIQUE INDEX ON staging.stg_zip (zip);

-- Known (city, state) pairs of the geolocation set, used to validate names given by customers/sellers
DROP TABLE IF EXISTS staging.stg_geo_city;
CREATE TABLE staging.stg_geo_city AS SELECT DISTINCT city, state FROM staging.stg_geo;
CREATE UNIQUE INDEX ON staging.stg_geo_city (city, state);

-- City resolution rule for customers and sellers:
--   1. normalised name, if it exists in geolocation for that state;
--   2. otherwise the city of the zip prefix (covers digits-only names such as '04482255',
--      abbreviations such as 'sbc/sp' or 'sp / sp');
--   3. otherwise the normalised name as given; 4. otherwise 'unknown'.

-- (c) customers: one row per real customer, address of the most recent order (SCD type 1)
DROP TABLE IF EXISTS staging.stg_customers;
CREATE TABLE staging.stg_customers AS
SELECT DISTINCT ON (c.customer_unique_id)
       c.customer_unique_id, c.customer_zip_code_prefix AS zip,
       COALESCE(gc.city, z.city, staging.norm_city(c.customer_city), 'unknown') AS city,
       upper(c.customer_state) AS state
FROM staging.raw_customers c
JOIN staging.raw_orders o USING (customer_id)
LEFT JOIN staging.stg_geo_city gc
       ON gc.city = staging.norm_city(c.customer_city) AND gc.state = upper(c.customer_state)
LEFT JOIN staging.stg_zip z ON z.zip = c.customer_zip_code_prefix AND z.state = upper(c.customer_state)
ORDER BY c.customer_unique_id, o.order_purchase_timestamp::timestamp DESC;

-- (d) sellers: same rule; digits-only names are never accepted as a city
DROP TABLE IF EXISTS staging.stg_sellers;
CREATE TABLE staging.stg_sellers AS
SELECT s.seller_id, s.seller_zip_code_prefix AS zip,
       COALESCE(gc.city, z.city,
                CASE WHEN staging.norm_city(s.seller_city) ~ '^[0-9 ]+$' THEN NULL
                     ELSE staging.norm_city(s.seller_city) END,
                'unknown') AS city,
       upper(s.seller_state) AS state
FROM staging.raw_sellers s
LEFT JOIN staging.stg_geo_city gc
       ON gc.city = staging.norm_city(s.seller_city) AND gc.state = upper(s.seller_state)
LEFT JOIN staging.stg_zip z ON z.zip = s.seller_zip_code_prefix AND z.state = upper(s.seller_state);

INSERT INTO meta.rejected_record (run_id, source, record_key, action, reason)
SELECT current_setting('etl.run_id')::int, 'sellers', s.seller_id, 'MODIFIED',
       'Tên thành phố không chuẩn (' || s.seller_city || ') được chuẩn hóa thành ' || t.city
FROM staging.raw_sellers s JOIN staging.stg_sellers t USING (seller_id)
WHERE s.seller_city <> t.city;

-- (e) cities = union of customer and seller cities; coordinates = mean of the matching geolocation points
DROP TABLE IF EXISTS staging.stg_city;
CREATE TABLE staging.stg_city AS
WITH c AS (
    SELECT city, state FROM staging.stg_customers
    UNION
    SELECT city, state FROM staging.stg_sellers
)
SELECT c.city, c.state, ROUND(AVG(g.lat), 6) AS lat, ROUND(AVG(g.lng), 6) AS lng
FROM c
LEFT JOIN staging.stg_geo g ON g.city = c.city AND g.state = c.state
GROUP BY c.city, c.state;

-- ---------------------------------------------------------------------------------------------
-- Products and categories
-- ---------------------------------------------------------------------------------------------
DROP TABLE IF EXISTS staging.stg_category;
CREATE TABLE staging.stg_category AS
SELECT DISTINCT
       COALESCE(p.product_category_name, 'unknown') AS category_name_pt,
       COALESCE(t.product_category_name_english, r.product_category_name_english,
                p.product_category_name, 'unknown') AS category_name_en
FROM staging.raw_products p
LEFT JOIN staging.raw_category_translation t USING (product_category_name)
LEFT JOIN staging.ref_category_patch r USING (product_category_name);

DROP TABLE IF EXISTS staging.stg_products;
CREATE TABLE staging.stg_products AS
SELECT product_id,
       COALESCE(product_category_name, 'unknown')            AS category_name_pt,
       NULLIF(NULLIF(product_weight_g, '')::numeric, 0)::int AS weight_g,
       NULLIF(NULLIF(product_length_cm, '')::numeric, 0)::int AS length_cm,
       NULLIF(NULLIF(product_height_cm, '')::numeric, 0)::int AS height_cm,
       NULLIF(NULLIF(product_width_cm, '')::numeric, 0)::int  AS width_cm,
       NULLIF(product_photos_qty, '')::numeric::smallint      AS photos_qty
FROM staging.raw_products;
