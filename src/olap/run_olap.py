"""Run every query of src/sql/50_olap_queries.sql: save its result and measure its execution time.

Outputs (src/olap/results/):
    <query_id>.csv     result of the query
    timings.csv        query id, result rows, median / min / max execution time over N runs (ms),
                       taken from EXPLAIN (ANALYZE) so client transfer time is excluded
Usage: python -m src.olap.run_olap [--runs 5]
"""
import argparse
import csv
import json
import re
import statistics
from pathlib import Path

from src.etl.config import SQL_DIR
from src.etl.db import connect

RESULTS = Path(__file__).resolve().parent / "results"


def load_queries() -> dict[str, str]:
    text = (SQL_DIR / "50_olap_queries.sql").read_text(encoding="utf-8")
    parts = re.split(r"^-- name: (\w+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    args = ap.parse_args(argv)
    RESULTS.mkdir(exist_ok=True)
    timings = []
    with connect(autocommit=True) as conn:
        for qid, sql in load_queries().items():
            cur = conn.execute(sql)
            cols = [c.name for c in cur.description]
            rows = cur.fetchall()
            with open(RESULTS / f"{qid}.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(cols)
                w.writerows(rows)
            ms = []
            for _ in range(args.runs):
                plan = conn.execute(f"EXPLAIN (ANALYZE, FORMAT JSON) {sql}").fetchone()[0]
                plan = plan if isinstance(plan, list) else json.loads(plan)
                ms.append(plan[0]["Execution Time"])
            timings.append([qid, len(rows), round(statistics.median(ms), 1), round(min(ms), 1), round(max(ms), 1)])
            print(f"{qid:<38} rows={len(rows):>4}  median={statistics.median(ms):8.1f} ms")
    with open(RESULTS / "timings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["query", "rows", "median_ms", "min_ms", "max_ms"])
        w.writerows(timings)


if __name__ == "__main__":
    main()
