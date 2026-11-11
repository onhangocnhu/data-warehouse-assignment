"""Extract: load the CSV files as-is (all TEXT) into staging.raw_* / staging.ref_* with COPY."""
import csv

import psycopg

from .config import SOURCES
from .db import log_step


def staging_columns(conn: psycopg.Connection, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'staging' AND table_name = %s ORDER BY ordinal_position",
        (table,),
    ).fetchall()
    return [r[0] for r in rows]


def copy_csv(conn: psycopg.Connection, path, table: str) -> int:
    # utf-8-sig strips the byte-order mark of product_category_name_translation.csv
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader([f.readline()]))
        expected = staging_columns(conn, table)
        if header != expected:
            raise ValueError(f"{path.name}: header {header} does not match staging.{table} {expected}")
        f.seek(0)
        with conn.cursor() as cur:
            cur.execute(f"TRUNCATE staging.{table}")
            with cur.copy(f"COPY staging.{table} FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
            return cur.execute(f"SELECT COUNT(*) FROM staging.{table}").fetchone()[0]


def extract_all(conn: psycopg.Connection, run_id: int) -> int:
    total = 0
    for (folder, file), (table, expected) in SOURCES.items():
        with log_step(run_id, f"extract_{table}") as st:
            n = copy_csv(conn, folder / file, table)
            st["rows_in"] = st["rows_out"] = n
            if n != expected:
                raise ValueError(f"staging.{table}: {n} rows loaded, expected {expected}")
            conn.commit()
        total += n
    return total
