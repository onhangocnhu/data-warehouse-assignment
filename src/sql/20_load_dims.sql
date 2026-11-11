-- 20_load_dims.sql
-- Load the 7 dimension tables from staging.stg_*, parents before children:
--   dim_date -> dim_state -> dim_city -> dim_category -> dim_product -> dim_customer -> dim_seller
-- Runs inside the load transaction, right after 02_datamart_ddl.sql has recreated empty tables
-- that already contain the unknown members (key -1).
-- Surrogate keys = ROW_NUMBER() over the natural key, so they are stable between full loads.

SET client_min_messages = warning;

-- dim_date: 01/1/2016 - 31/12/2018 (covers every date in the source, up to 12/11/2018)
INSERT INTO dm.dim_date (date_key, full_date, day, month, quarter, year, day_of_week)
SELECT TO_CHAR(d, 'YYYYMMDD')::int, d::date,
       EXTRACT(DAY FROM d), EXTRACT(MONTH FROM d), EXTRACT(QUARTER FROM d), EXTRACT(YEAR FROM d),
       TRIM(TO_CHAR(d, 'FMDay'))
FROM generate_series('2016-01-01'::date, '2018-12-31'::date, interval '1 day') AS d;

-- dim_state: 27 states, region added by the team (data/reference/state_region.csv)
INSERT INTO dm.dim_state (state_key, state_code, state_name, region)
SELECT ROW_NUMBER() OVER (ORDER BY state_code), state_code, state_name, region
FROM staging.ref_state_region;

-- dim_city: union of customer and seller cities, identified by (normalised name, state)
INSERT INTO dm.dim_city (city_key, city_name, latitude, longitude, state_key)
SELECT ROW_NUMBER() OVER (ORDER BY c.state, c.city), c.city, c.lat, c.lng, COALESCE(s.state_key, -1)
FROM staging.stg_city c
LEFT JOIN dm.dim_state s ON s.state_code = c.state;

-- dim_category: 73 categories; products without a category point to the unknown member (-1)
INSERT INTO dm.dim_category (category_key, category_name_pt, category_name_en)
SELECT ROW_NUMBER() OVER (ORDER BY category_name_pt), category_name_pt, category_name_en
FROM staging.stg_category
WHERE category_name_pt <> 'unknown';

-- dim_product
INSERT INTO dm.dim_product (product_key, product_id, category_key, weight_g, length_cm, height_cm, width_cm, photos_qty)
SELECT ROW_NUMBER() OVER (ORDER BY p.product_id), p.product_id, COALESCE(c.category_key, -1),
       p.weight_g, p.length_cm, p.height_cm, p.width_cm, p.photos_qty
FROM staging.stg_products p
LEFT JOIN dm.dim_category c ON c.category_name_pt = p.category_name_pt;

-- dim_customer: one row per customer_unique_id
INSERT INTO dm.dim_customer (customer_key, customer_unique_id, zip_code_prefix, city_key)
SELECT ROW_NUMBER() OVER (ORDER BY cu.customer_unique_id), cu.customer_unique_id, cu.zip,
       COALESCE(ci.city_key, -1)
FROM staging.stg_customers cu
LEFT JOIN dm.dim_state st ON st.state_code = cu.state
LEFT JOIN dm.dim_city ci  ON ci.city_name = cu.city AND ci.state_key = st.state_key;

-- dim_seller
INSERT INTO dm.dim_seller (seller_key, seller_id, zip_code_prefix, city_key)
SELECT ROW_NUMBER() OVER (ORDER BY se.seller_id), se.seller_id, se.zip, COALESCE(ci.city_key, -1)
FROM staging.stg_sellers se
LEFT JOIN dm.dim_state st ON st.state_code = se.state
LEFT JOIN dm.dim_city ci  ON ci.city_name = se.city AND ci.state_key = st.state_key;
