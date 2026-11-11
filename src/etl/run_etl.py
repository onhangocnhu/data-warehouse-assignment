"""Full ETL run: extract -> transform -> load (one transaction) -> data-quality checks.

Usage (from the repository root):
    python -m src.etl.run_etl --init     # first time: create schemas and tables
    python -m src.etl.run_etl            # full load
Exit code 0 when every reconciliation check passes, 1 otherwise.
"""
import argparse
import sys
import time

from .config import INIT_SQL
from .db import connect, log_step, new_run_id, run_sql_file
from .extract import extract_all

LOAD_SQL = ["02_datamart_ddl.sql", "20_load_dims.sql", "30_load_fact.sql", "05_metadata_seed.sql"]


def init_db() -> None:
    with connect(autocommit=True) as conn:
        for f in INIT_SQL:
            run_sql_file(conn, f)
    print("schemas and tables created")


def count(conn, sql: str) -> int:
    return conn.execute(sql).fetchone()[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--init", action="store_true", help="create schemas and tables before loading")
    args = ap.parse_args(argv)
    if args.init:
        init_db()

    t0 = time.perf_counter()
    run_id = new_run_id()
    print(f"ETL run {run_id}")
    with connect() as conn:
        conn.execute("SELECT set_config('etl.run_id', %s, false)", (str(run_id),))

        # 1. Extract
        extract_all(conn, run_id)

        # 2. Transform
        with log_step(run_id, "transform") as st:
            run_sql_file(conn, "10_transform.sql")
            st["rows_in"] = count(conn, "SELECT COUNT(*) FROM staging.raw_order_items")
            st["rows_out"] = count(conn, "SELECT COUNT(*) FROM staging.stg_order_items")
            st["rows_rejected"] = count(
                conn, f"SELECT COUNT(*) FROM meta.rejected_record WHERE run_id = {run_id} AND action = 'DROPPED'")
            conn.commit()

        # 3. Load: drop/recreate the Data Mart and reload it in ONE transaction.
        #    Any error rolls everything back and the previous Data Mart stays untouched.
        with log_step(run_id, "load") as st:
            try:
                for f in LOAD_SQL:
                    run_sql_file(conn, f)
                st["rows_in"] = count(conn, "SELECT COUNT(*) FROM staging.stg_order_items")
                st["rows_out"] = count(conn, "SELECT COUNT(*) FROM dm.fact_sales")
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        # 4. Data-quality / reconciliation checks
        with log_step(run_id, "dq_check") as st:
            run_sql_file(conn, "40_dq_checks.sql")
            conn.commit()
            rows = conn.execute(
                "SELECT check_name, expected, actual, passed FROM meta.dq_result WHERE run_id = %s ORDER BY check_name",
                (run_id,)).fetchall()
            failed = [r for r in rows if not r[3]]
            st["rows_in"], st["rows_out"], st["rows_rejected"] = len(rows), len(rows) - len(failed), len(failed)

    for name, exp, act, ok in rows:
        print(f"  [{'OK' if ok else 'FAIL'}] {name}: expected {exp}, actual {act}")
    print(f"ETL run {run_id} finished in {time.perf_counter() - t0:.1f}s, failed checks: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
