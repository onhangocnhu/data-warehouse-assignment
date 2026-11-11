# src/etl/

Planned modules (see `docs/ke_hoach_hien_thuc_chi_tiet.md`, phase GĐ3):

| File | Role |
|---|---|
| `config.py` | Read `.env` (DB host, port, name, user, password, `DATA_DIR=data/raw`) |
| `db.py` | Connection helper, `run_sql_file()`, transaction context, `log_step()` writing `meta.etl_run_log` |
| `extract.py` | Check the 9 files and their headers, `TRUNCATE` + `COPY` into `staging.raw_*`, compare row counts with `data/README.md` |
| `reference.py` | Load `data/reference/*.csv` into `staging.ref_state_region` and `staging.ref_category_patch` |
| `dim_date.py` | Generate `dm.dim_date` for 01/1/2016-31/12/2018 |
| `run_etl.py` | Entry point: extract -> transform -> load (one transaction) -> DQ checks; exits non-zero on failure |
