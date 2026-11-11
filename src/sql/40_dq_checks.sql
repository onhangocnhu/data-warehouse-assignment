-- 40_dq_checks.sql
-- Reconciliation after each load (tab:doisoat in thietke/etl.tex). Expected values were computed
-- directly from the 9 CSV files. Results go to meta.dq_result; run_etl.py fails the run if any
-- check does not pass. Requires the session setting etl.run_id.

SET client_min_messages = warning;

DELETE FROM meta.dq_result WHERE run_id = current_setting('etl.run_id')::int;

INSERT INTO meta.dq_result (run_id, check_name, expected, actual, passed)
SELECT current_setting('etl.run_id')::int, check_name, expected, actual,
       CASE WHEN expected LIKE '%..%'                                    -- range check 'low..high'
            THEN actual::numeric BETWEEN split_part(expected, '..', 1)::numeric
                                     AND split_part(expected, '..', 2)::numeric
            ELSE expected = actual END
FROM (VALUES
    ('fact_rows = source order items',        '112650',      (SELECT COUNT(*)::text FROM dm.fact_sales)),
    ('distinct orders in fact',               '98666',       (SELECT COUNT(DISTINCT order_id)::text FROM dm.fact_sales)),
    ('sum(price)',                            '13591643.70', (SELECT SUM(price)::text FROM dm.fact_sales)),
    ('sum(freight_value)',                    '2251909.54',  (SELECT SUM(freight_value)::text FROM dm.fact_sales)),
    ('late rate % over distinct orders',      '6.77',        (SELECT ROUND(100 * AVG(is_late), 2)::text FROM dm.v_order)),
    ('avg review over distinct orders',       '4.05..4.15',  (SELECT ROUND(AVG(review_score), 3)::text FROM dm.v_order)),
    ('dim_customer rows (incl. unknown)',     '96097',       (SELECT COUNT(*)::text FROM dm.dim_customer)),
    ('dim_product rows (incl. unknown)',      '32952',       (SELECT COUNT(*)::text FROM dm.dim_product)),
    ('dim_seller rows (incl. unknown)',       '3096',        (SELECT COUNT(*)::text FROM dm.dim_seller)),
    ('dim_category rows (incl. unknown)',     '74',          (SELECT COUNT(*)::text FROM dm.dim_category)),
    ('dim_state rows (incl. unknown)',        '28',          (SELECT COUNT(*)::text FROM dm.dim_state)),
    ('dim_date rows (incl. unknown)',         '1097',        (SELECT COUNT(*)::text FROM dm.dim_date)),
    ('fact rows with unknown product',        '0',           (SELECT COUNT(*)::text FROM dm.fact_sales WHERE product_key = -1)),
    ('fact rows with unknown seller',         '0',           (SELECT COUNT(*)::text FROM dm.fact_sales WHERE seller_key = -1)),
    ('fact rows with unknown customer',       '0',           (SELECT COUNT(*)::text FROM dm.fact_sales WHERE customer_key = -1)),
    ('fact rows with unknown purchase date',  '0',           (SELECT COUNT(*)::text FROM dm.fact_sales WHERE purchase_date_key = -1)),
    ('fact rows with unknown estimated date', '0',           (SELECT COUNT(*)::text FROM dm.fact_sales WHERE estimated_date_key = -1)),
    ('customers with unknown city',           '0',           (SELECT COUNT(*)::text FROM dm.dim_customer WHERE city_key = -1 AND customer_key <> -1)),
    ('sellers with unknown city',             '0',           (SELECT COUNT(*)::text FROM dm.dim_seller WHERE city_key = -1 AND seller_key <> -1)),
    ('cities with unknown state',             '0',           (SELECT COUNT(*)::text FROM dm.dim_city WHERE state_key = -1 AND city_key <> -1))
) AS t(check_name, expected, actual);
