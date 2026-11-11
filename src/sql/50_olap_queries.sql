-- 50_olap_queries.sql
-- OLAP query library on the Data Mart (ROLAP: SQL over fact_sales + dimensions).
-- Each query starts with "-- name: <id>" so src/olap/run_olap.py can run them one by one,
-- save the result to src/olap/results/<id>.csv and time them with EXPLAIN ANALYZE.
-- Order-level measures (durations, is_late, review_score) are always taken from dm.v_order
-- so that orders with several items are counted once.

-- name: q01_rollup_time
-- Roll-up Ngày -> Tháng -> Quý -> Năm: doanh thu hàng hóa và số đơn (loại đơn hủy / không khả dụng).
-- Dòng có month/quarter/year NULL là dòng tổng hợp của ROLLUP.
SELECT d.year, d.quarter, d.month,
       SUM(f.price)               AS revenue,
       COUNT(DISTINCT f.order_id) AS orders,
       ROUND(SUM(f.price) / COUNT(DISTINCT f.order_id), 2) AS avg_order_value
FROM dm.fact_sales f
JOIN dm.dim_date d ON d.date_key = f.purchase_date_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY ROLLUP (d.year, d.quarter, d.month)
ORDER BY d.year, d.quarter, d.month;

-- name: q02_drilldown_region_state
-- Drill-down Vùng -> Bang: tỷ lệ giao trễ và thời gian giao trên đơn phân biệt (theo vị trí khách hàng).
SELECT st.region, st.state_code,
       COUNT(*)                                AS delivered_orders,
       ROUND(100.0 * AVG(o.is_late), 2)        AS late_pct,
       ROUND(AVG(o.delivery_days), 1)          AS avg_delivery_days
FROM dm.v_order o
JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
JOIN dm.dim_state st    ON st.state_key = ci.state_key
WHERE o.is_late IS NOT NULL
GROUP BY ROLLUP (st.region, st.state_code)
ORDER BY st.region NULLS LAST, late_pct DESC;

-- name: q03_drilldown_city_rj
-- Drill-down tiếp xuống Thành phố trong bang RJ (bang lớn có tỷ lệ trễ cao).
SELECT ci.city_name,
       COUNT(*)                         AS delivered_orders,
       ROUND(100.0 * AVG(o.is_late), 2) AS late_pct,
       ROUND(AVG(o.delivery_days), 1)   AS avg_delivery_days
FROM dm.v_order o
JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
JOIN dm.dim_state st    ON st.state_key = ci.state_key
WHERE o.is_late IS NOT NULL AND st.state_code = 'RJ'
GROUP BY ci.city_name
HAVING COUNT(*) >= 300
ORDER BY late_pct DESC;

-- name: q04_slice_2018
-- Slice: cố định Năm = 2018, xem doanh thu và số đơn theo vùng của khách hàng.
SELECT st.region,
       SUM(f.price)               AS revenue,
       COUNT(DISTINCT f.order_id) AS orders,
       ROUND(100.0 * SUM(f.price) / SUM(SUM(f.price)) OVER (), 1) AS revenue_share_pct
FROM dm.fact_sales f
JOIN dm.dim_date d      ON d.date_key = f.purchase_date_key
JOIN dm.dim_customer cu ON cu.customer_key = f.customer_key
JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
JOIN dm.dim_state st    ON st.state_key = ci.state_key
WHERE d.year = 2018 AND f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY st.region
ORDER BY revenue DESC;

-- name: q05_dice_q4_2017
-- Dice: Quý 4/2017 x bang SP, RJ, MG x 5 ngành hàng có doanh thu cao nhất cả năm 2017.
WITH top_cat AS (
    SELECT p.category_key
    FROM dm.fact_sales f
    JOIN dm.dim_product p ON p.product_key = f.product_key
    JOIN dm.dim_date d    ON d.date_key = f.purchase_date_key
    WHERE d.year = 2017
    GROUP BY p.category_key
    ORDER BY SUM(f.price) DESC
    LIMIT 5
)
SELECT cat.category_name_en, st.state_code,
       SUM(f.price)               AS revenue,
       COUNT(DISTINCT f.order_id) AS orders
FROM dm.fact_sales f
JOIN dm.dim_date d       ON d.date_key = f.purchase_date_key
JOIN dm.dim_product p    ON p.product_key = f.product_key
JOIN dm.dim_category cat ON cat.category_key = p.category_key
JOIN dm.dim_customer cu  ON cu.customer_key = f.customer_key
JOIN dm.dim_city ci      ON ci.city_key = cu.city_key
JOIN dm.dim_state st     ON st.state_key = ci.state_key
WHERE d.year = 2017 AND d.quarter = 4
  AND st.state_code IN ('SP', 'RJ', 'MG')
  AND p.category_key IN (SELECT category_key FROM top_cat)
  AND f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY cat.category_name_en, st.state_code
ORDER BY cat.category_name_en, revenue DESC;

-- name: q06_pivot_review_category_region
-- Pivot: điểm đánh giá trung bình, ngành hàng (dòng) x vùng (cột); 10 ngành hàng nhiều đơn nhất.
WITH ord AS (
    SELECT f.order_id, MIN(f.review_score) AS score,
           MIN(cat.category_name_en) AS category, MIN(st.region) AS region
    FROM dm.fact_sales f
    JOIN dm.dim_product p    ON p.product_key = f.product_key
    JOIN dm.dim_category cat ON cat.category_key = p.category_key
    JOIN dm.dim_customer cu  ON cu.customer_key = f.customer_key
    JOIN dm.dim_city ci      ON ci.city_key = cu.city_key
    JOIN dm.dim_state st     ON st.state_key = ci.state_key
    WHERE f.review_score IS NOT NULL
    GROUP BY f.order_id
), top AS (
    SELECT category FROM ord GROUP BY category ORDER BY COUNT(*) DESC LIMIT 10
)
SELECT category,
       ROUND(AVG(score) FILTER (WHERE region = 'Sudeste'), 2)      AS sudeste,
       ROUND(AVG(score) FILTER (WHERE region = 'Sul'), 2)          AS sul,
       ROUND(AVG(score) FILTER (WHERE region = 'Centro-Oeste'), 2) AS centro_oeste,
       ROUND(AVG(score) FILTER (WHERE region = 'Nordeste'), 2)     AS nordeste,
       ROUND(AVG(score) FILTER (WHERE region = 'Norte'), 2)        AS norte,
       ROUND(AVG(score), 2)                                        AS all_regions
FROM ord
WHERE category IN (SELECT category FROM top)
GROUP BY category
ORDER BY all_regions;

-- name: q07_late_vs_review
-- Ảnh hưởng của giao trễ đến mức độ hài lòng (đơn phân biệt có cả trạng thái giao và đánh giá).
SELECT CASE o.is_late WHEN 1 THEN 'late' ELSE 'on_time' END AS delivery,
       COUNT(*)                                             AS orders,
       ROUND(AVG(o.review_score), 2)                        AS avg_review,
       ROUND(100.0 * AVG((o.review_score <= 2)::int), 1)    AS low_review_pct,
       ROUND(100.0 * AVG((o.review_score = 5)::int), 1)     AS five_star_pct
FROM dm.v_order o
WHERE o.is_late IS NOT NULL AND o.review_score IS NOT NULL
GROUP BY o.is_late
ORDER BY o.is_late;

-- name: q08_route_matrix
-- Tuyến giao hàng (bang người bán -> bang khách hàng), cấp lô = đơn x người bán, tuyến có >= 200 lô.
WITH lot AS (
    SELECT DISTINCT f.order_id, f.seller_key, f.customer_key, f.is_late, f.delivery_days
    FROM dm.fact_sales f
    WHERE f.is_late IS NOT NULL
)
SELECT ss.state_code AS seller_state, cs.state_code AS customer_state,
       COUNT(*)                          AS lots,
       ROUND(100.0 * AVG(l.is_late), 1)  AS late_pct,
       ROUND(AVG(l.delivery_days), 1)    AS avg_delivery_days
FROM lot l
JOIN dm.dim_seller se   ON se.seller_key = l.seller_key
JOIN dm.dim_city sc     ON sc.city_key = se.city_key
JOIN dm.dim_state ss    ON ss.state_key = sc.state_key
JOIN dm.dim_customer cu ON cu.customer_key = l.customer_key
JOIN dm.dim_city cc     ON cc.city_key = cu.city_key
JOIN dm.dim_state cs    ON cs.state_key = cc.state_key
GROUP BY ss.state_code, cs.state_code
HAVING COUNT(*) >= 200
ORDER BY late_pct DESC;

-- name: q09_stage_durations_region
-- Thời gian từng công đoạn (duyệt, chuẩn bị hàng, vận chuyển) theo vùng của khách hàng.
SELECT st.region,
       COUNT(*)                       AS delivered_orders,
       ROUND(AVG(o.approval_days), 2) AS avg_approval_days,
       ROUND(AVG(o.handling_days), 2) AS avg_handling_days,
       ROUND(AVG(o.shipping_days), 2) AS avg_shipping_days,
       ROUND(AVG(o.delivery_days), 2) AS avg_delivery_days
FROM dm.v_order o
JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
JOIN dm.dim_state st    ON st.state_key = ci.state_key
WHERE o.order_status = 'delivered' AND o.delivery_days IS NOT NULL
GROUP BY ROLLUP (st.region)
ORDER BY avg_delivery_days;

-- name: q10_seller_high_revenue_low_quality
-- Người bán thuộc 20% doanh thu cao nhất nhưng tỷ lệ đánh giá 1-2 sao > 20% (tối thiểu 30 đơn).
WITH s AS (
    SELECT f.seller_key, f.order_id,
           SUM(f.price) AS revenue, MIN(f.is_late) AS is_late, MIN(f.review_score) AS score
    FROM dm.fact_sales f
    WHERE f.order_status = 'delivered'
    GROUP BY f.seller_key, f.order_id
), agg AS (
    SELECT seller_key, COUNT(*) AS orders, SUM(revenue) AS revenue,
           ROUND(100.0 * AVG(is_late), 1)          AS late_pct,
           ROUND(AVG(score), 2)                    AS avg_review,
           ROUND(100.0 * AVG((score <= 2)::int), 1) AS low_review_pct
    FROM s GROUP BY seller_key HAVING COUNT(*) >= 30
)
SELECT a.seller_key, LEFT(se.seller_id, 8) AS seller_id_prefix, st.state_code,
       a.orders, a.revenue, a.late_pct, a.avg_review, a.low_review_pct
FROM agg a
JOIN dm.dim_seller se ON se.seller_key = a.seller_key
JOIN dm.dim_city ci   ON ci.city_key = se.city_key
JOIN dm.dim_state st  ON st.state_key = ci.state_key
WHERE a.revenue >= (SELECT PERCENTILE_CONT(0.8) WITHIN GROUP (ORDER BY revenue) FROM agg)
  AND a.low_review_pct > 20
ORDER BY a.revenue DESC;

-- name: q11_sellers_vs_customers_by_state
-- Phân bố người bán so với nơi tập trung khách hàng (đơn hàng) theo bang.
WITH sel AS (
    SELECT st.state_code, COUNT(*) AS sellers
    FROM dm.dim_seller se JOIN dm.dim_city ci USING (city_key) JOIN dm.dim_state st USING (state_key)
    WHERE se.seller_key <> -1 GROUP BY st.state_code
), ord AS (
    SELECT st.state_code, COUNT(*) AS orders
    FROM dm.v_order o
    JOIN dm.dim_customer cu ON cu.customer_key = o.customer_key
    JOIN dm.dim_city ci ON ci.city_key = cu.city_key
    JOIN dm.dim_state st ON st.state_key = ci.state_key
    GROUP BY st.state_code
)
SELECT o.state_code,
       COALESCE(s.sellers, 0) AS sellers,
       ROUND(100.0 * COALESCE(s.sellers, 0) / SUM(COALESCE(s.sellers, 0)) OVER (), 1) AS seller_share_pct,
       o.orders,
       ROUND(100.0 * o.orders / SUM(o.orders) OVER (), 1) AS order_share_pct
FROM ord o LEFT JOIN sel s USING (state_code)
ORDER BY o.orders DESC;

-- name: q12_category_growth
-- Ngành hàng tăng trưởng: so sánh doanh thu tháng 01-08 năm 2018 với cùng kỳ 2017 (ngành có >= 50.000 BRL năm 2017).
SELECT cat.category_name_en,
       SUM(f.price) FILTER (WHERE d.year = 2017) AS revenue_2017_jan_aug,
       SUM(f.price) FILTER (WHERE d.year = 2018) AS revenue_2018_jan_aug,
       ROUND(100.0 * (SUM(f.price) FILTER (WHERE d.year = 2018) / NULLIF(SUM(f.price) FILTER (WHERE d.year = 2017), 0) - 1), 1)
           AS growth_pct
FROM dm.fact_sales f
JOIN dm.dim_date d       ON d.date_key = f.purchase_date_key
JOIN dm.dim_product p    ON p.product_key = f.product_key
JOIN dm.dim_category cat ON cat.category_key = p.category_key
WHERE d.month BETWEEN 1 AND 8 AND d.year IN (2017, 2018)
  AND f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY cat.category_name_en
HAVING SUM(f.price) FILTER (WHERE d.year = 2017) >= 50000
ORDER BY growth_pct DESC;

-- name: q13_cube_region_year
-- CUBE: mọi tổ hợp Vùng x Năm (các dòng NULL là tổng theo một hoặc cả hai chiều).
SELECT COALESCE(st.region, '(tất cả vùng)') AS region,
       COALESCE(d.year::text, '(tất cả năm)') AS year,
       SUM(f.price)               AS revenue,
       COUNT(DISTINCT f.order_id) AS orders
FROM dm.fact_sales f
JOIN dm.dim_date d      ON d.date_key = f.purchase_date_key
JOIN dm.dim_customer cu ON cu.customer_key = f.customer_key
JOIN dm.dim_city ci     ON ci.city_key = cu.city_key
JOIN dm.dim_state st    ON st.state_key = ci.state_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY CUBE (st.region, d.year)
ORDER BY 1, 2;

-- name: q14_black_friday
-- Black Friday 24/11/2017: số đơn, doanh thu và tỷ lệ trễ theo ngày trong cửa sổ 17/11-01/12/2017.
SELECT d.full_date, d.day_of_week,
       COUNT(*)                         AS orders,
       SUM(o.order_value)               AS revenue,
       ROUND(100.0 * AVG(o.is_late), 1) AS late_pct
FROM dm.v_order o
JOIN dm.dim_date d ON d.date_key = o.purchase_date_key
WHERE d.full_date BETWEEN '2017-11-17' AND '2017-12-01'
GROUP BY d.full_date, d.day_of_week
ORDER BY d.full_date;
