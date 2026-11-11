"""Database helpers: connections, running SQL files, and step logging into meta.etl_run_log."""
import time
from contextlib import contextmanager

import psycopg

from .config import DSN, SQL_DIR


def connect(autocommit: bool = False) -> psycopg.Connection:
    return psycopg.connect(DSN, autocommit=autocommit)


def run_sql_file(conn: psycopg.Connection, name: str) -> None:
    """Execute a whole SQL file (several statements, no parameters) on the given connection."""
    conn.execute((SQL_DIR / name).read_text(encoding="utf-8"))


def new_run_id() -> int:
    with connect(autocommit=True) as c:
        return c.execute("SELECT nextval('meta.etl_run_seq')").fetchone()[0]


@contextmanager
def log_step(run_id: int, step: str):
    """Record one ETL step. The log uses its own autocommit connection, so a failed step
    is still logged as FAILED even when the work itself is rolled back."""
    t0 = time.perf_counter()
    stats = {"rows_in": None, "rows_out": None, "rows_rejected": None}
    with connect(autocommit=True) as log:
        log.execute(
            "INSERT INTO meta.etl_run_log (run_id, step, started_at, status) VALUES (%s, %s, clock_timestamp(), 'RUNNING')",
            (run_id, step),
        )
        try:
            yield stats
        except Exception as exc:
            log.execute(
                "UPDATE meta.etl_run_log SET finished_at = clock_timestamp(), status = 'FAILED', message = %s "
                "WHERE run_id = %s AND step = %s",
                (str(exc)[:2000], run_id, step),
            )
            raise
        log.execute(
            "UPDATE meta.etl_run_log SET finished_at = clock_timestamp(), status = 'SUCCESS', "
            "rows_in = %s, rows_out = %s, rows_rejected = %s WHERE run_id = %s AND step = %s",
            (stats["rows_in"], stats["rows_out"], stats["rows_rejected"], run_id, step),
        )
    print(f"  {step:<34} {time.perf_counter() - t0:7.2f}s  out={stats['rows_out']}")
