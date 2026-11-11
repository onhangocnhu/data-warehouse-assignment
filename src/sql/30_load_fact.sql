-- 30_load_fact.sql
-- Load dm.fact_sales: one row per product in an order (order_id, order_item_id).
-- Surrogate keys are looked up from the dimensions; anything not found -> -1 (unknown member).
-- Order-level measures (the 4 durations, is_late, review_score) are repeated on every item row
-- of the order; aggregate them over DISTINCT order_id (view dm.v_order).

SET client_min_messages = warning;

INSERT INTO dm.fact_sales
SELECT i.order_id,
       i.order_item_id,
       COALESCE(p.product_key, -1),
       COALESCE(s.seller_key, -1),
       COALESCE(c.customer_key, -1),
       COALESCE(TO_CHAR(o.purchase_ts,          'YYYYMMDD')::int, -1),
       COALESCE(TO_CHAR(o.approved_ts,          'YYYYMMDD')::int, -1),
       COALESCE(TO_CHAR(o.carrier_ts,           'YYYYMMDD')::int, -1),
       COALESCE(TO_CHAR(o.delivered_ts,         'YYYYMMDD')::int, -1),
       COALESCE(TO_CHAR(o.estimated_ts,         'YYYYMMDD')::int, -1),
       COALESCE(TO_CHAR(r.review_creation_ts,   'YYYYMMDD')::int, -1),
       o.order_status,
       i.price,
       i.freight_value,
       o.approval_days,
       o.handling_days,
       o.shipping_days,
       o.delivery_days,
       o.is_late,
       r.review_score
FROM staging.stg_order_items i
JOIN staging.stg_orders o       ON o.order_id = i.order_id
LEFT JOIN staging.stg_reviews r ON r.order_id = i.order_id
LEFT JOIN dm.dim_product  p ON p.product_id = i.product_id
LEFT JOIN dm.dim_seller   s ON s.seller_id = i.seller_id
LEFT JOIN dm.dim_customer c ON c.customer_unique_id = o.customer_unique_id;

ANALYZE dm.fact_sales;
