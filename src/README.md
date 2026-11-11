# src/

Source code submitted with the report (assignment rule 5.1: "Mã nguồn (thư mục src/)").

```
src/
├── sql/                     Run in numeric order on an empty database
│   ├── 00_schemas.sql       staging, dm, meta, dss + read-only role
│   ├── 01_staging_raw.sql   raw_* landing tables (all TEXT)
│   ├── 02_datamart_ddl.sql  fact_sales + 7 dimensions + unknown members + dm.v_order
│   ├── 03_meta_ddl.sql      data dictionary, lineage, ETL run log, DQ results, rejected records
│   ├── 04_dss_ddl.sql       DSS output tables
│   ├── 05_metadata_seed.sql data dictionary + lineage (re-run by every load)
│   ├── 10_transform.sql     staging.raw_* -> staging.stg_*
│   ├── 20_load_dims.sql     stg_* -> dm.dim_*
│   ├── 30_load_fact.sql     stg_* -> dm.fact_sales
│   ├── 40_dq_checks.sql     20 reconciliation checks -> meta.dq_result
│   └── 50_olap_queries.sql  14 OLAP queries (roll-up, drill-down, slice, dice, pivot, cube, business)
├── eda/                     run_eda.py: raw-file EDA (structure, missing values, outliers) and EDA after
│                            preprocessing (before/after counts, correlation, late rate by bins) -> results/
├── etl/                     run_etl.py (entry point), extract.py (COPY), db.py (logging), verify_rollback.py
├── olap/                    run_olap.py -> results/<query>.csv + results/timings.csv
├── dss/                     features.py (point-in-time features, labels), evaluate_baseline.py (first
│                            baseline), evaluate_models.py (walk-forward + tuning), score_delay.py
│                            (scores at carrier handover, policies, backtest -> dss.*) -> results/
├── report/                  make_figures.py -> latex-report/Pictures/fig-*.png (24 data figures, 300 dpi)
└── dashboard/               (Bảo) web dashboard
```

Quick start (repository root, Docker running):

```bash
copy .env.example .env                    # set DB_PASSWORD; use DB_PORT=5433 if 5432 is taken
docker compose up -d
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -m src.etl.run_etl --init          # create schemas + full load (about 20 seconds)
python -m src.etl.run_etl                 # later full reloads
python -m src.eda.run_eda                 # EDA results (raw files + cleaned data)
python -m src.olap.run_olap               # OLAP results and timings
python -m src.dss.evaluate_models         # DSS walk-forward evaluation + tuning (~10-15 min)
python -m src.dss.score_delay             # risk scores at carrier handover, policy backtest -> dss.*
python -m src.report.make_figures         # regenerate the report charts (PNG, needs pdflatex + pdftoppm)
```
