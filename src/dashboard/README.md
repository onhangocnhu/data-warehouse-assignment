# src/dashboard/  (owner: Đặng Nguyên Bảo)

Web dashboard on top of the Data Mart. Free choice of technology; record it in the report
(`latex-report/Sections/hienthuc/trienkhai.tex`, table `tab:congnghe`, and section 4.4 `hienthuc/dashboard.tex`).
Connect with the read-only role or a dedicated user; only `dss.decision_log` needs write access.

## Data to read

| Page | Users (tab:quyetdinh) | Source | Ready-made SQL |
|---|---|---|---|
| Overview | Executives | `dm.fact_sales` + `dm.dim_date`; order-level KPIs from `dm.v_order` | `src/sql/50_olap_queries.sql`: `q01_rollup_time`, `q13_cube_region_year` |
| Revenue | Executives | fact + `dim_product` -> `dim_category`, `dim_customer` -> `dim_city` -> `dim_state` | `q04_slice_2018`, `q05_dice_q4_2017`, `q12_category_growth` |
| Delivery | Operations | `dm.v_order` (durations, `is_late`), route = seller state -> customer state | `q02_drilldown_region_state`, `q03_drilldown_city_rj`, `q08_route_matrix`, `q09_stage_durations_region`, `q14_black_friday` |
| Satisfaction | Customer care | `dm.v_order.review_score`, `is_late` | `q06_pivot_review_category_region`, `q07_late_vs_review` |
| Sellers | Category / seller managers | fact + `dim_seller` | `q10_seller_high_revenue_low_quality`, `q11_sellers_vs_customers_by_state` |
| DSS - late delivery | Operations | `dss.delay_risk_score` (orders scored when handed over to the carrier; filter `risk_level`, `decision_date`); `dss.model_registry` | columns: `p_late`, `risk_rank_pct`, `reason_1..3`, `recommended_action`, `actual_is_late` (backtest only) |
| ETL monitor | Technical | `meta.etl_run_log`, `meta.dq_result`, `meta.rejected_record` | |

Rules that keep the dashboard consistent with the report:
- Order-level measures (delivery time, late rate, review score) must come from `dm.v_order`, never averaged over `fact_sales` rows.
- Revenue excludes `order_status IN ('canceled', 'unavailable')`.
- Approve / reject buttons on the DSS page insert into `dss.decision_log (module, object_id, recommendation, decision, decided_by)`.
- What-if sliders: expected-cost threshold `p* = C_intervene / (C_late * effect)`; flag orders with `p_late >= p*` (defaults in `src/dss/score_delay.py`, `COST`).

## Numbers the dashboard must reproduce (report check)

| KPI | Expected |
|---|---|
| Revenue 2016-2018 (excl. canceled/unavailable) | 13.494.400,74 BRL, 98.199 orders |
| Late rate (delivered orders) | 6,77 % |
| Average review late vs on time | 2,27 vs 4,29 |
| Late rate RJ / SP | 12,11 % / 4,49 % |
| DSS, RED level, actual late rate | 28,8 % (925 orders, 06-08/2018) |

For the report (section 4.4 and the `\TODO` in `dss.tex`): one screenshot per page with a caption,
and a short check that at least the five numbers above match.
