"""Demonstrate that a failing load leaves the Data Mart untouched (Reliability requirement).

Runs the real load scripts in one transaction, injects an error before COMMIT, and compares
row counts and sum(price) of dm.fact_sales before and after.
Usage: python -m src.etl.verify_rollback
"""
from .db import connect, run_sql_file

SNAPSHOT = "SELECT COUNT(*), SUM(price) FROM dm.fact_sales"


def main() -> None:
    with connect() as conn:
        before = conn.execute(SNAPSHOT).fetchone()
        conn.commit()
        try:
            run_sql_file(conn, "02_datamart_ddl.sql")     # drops and recreates the Data Mart
            run_sql_file(conn, "20_load_dims.sql")
            mid = conn.execute(SNAPSHOT).fetchone()      # fact is empty inside the transaction
            conn.execute("SELECT 1 / 0")                  # simulated failure before 30_load_fact.sql
        except Exception as exc:
            conn.rollback()
            print(f"injected failure: {type(exc).__name__}: {exc}".strip())
        after = conn.execute(SNAPSHOT).fetchone()
    print(f"before load      : rows={before[0]}, sum(price)={before[1]}")
    print(f"inside load (tx) : rows={mid[0]}, sum(price)={mid[1]}")
    print(f"after rollback   : rows={after[0]}, sum(price)={after[1]}")
    print("Data Mart unchanged:", before == after)


if __name__ == "__main__":
    main()
