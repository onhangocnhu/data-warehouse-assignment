"""Create the dashboard's database login (report: Security -- Tính bảo mật).

    dashboard_app : LOGIN, member of analyst_ro (SELECT on dm / meta / dss)
                    + INSERT on dss.decision_log only (approve / reject buttons of the DSS page).

Run once after the ETL (python -m src.etl.run_etl --init), from the repository root:
    python -m src.dashboard.setup_role
then add the two lines it prints to .env. Re-running is safe (it only resets the password and grants).
"""
import os
import secrets

import psycopg
from psycopg import sql

from src.etl.config import DSN

ROLE = "dashboard_app"


def main() -> None:
    password = os.getenv("DASHBOARD_DB_PASSWORD") or secrets.token_urlsafe(18)
    with psycopg.connect(DSN, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()
        verb = "ALTER" if exists else "CREATE"
        conn.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(ROLE), sql.Literal(password)))
        conn.execute(sql.SQL("GRANT analyst_ro TO {}").format(sql.Identifier(ROLE)))
        # analyst_ro only receives default privileges on tables created after 00_schemas.sql ran;
        # grant explicitly so the role works whatever the creation order was.
        conn.execute("GRANT USAGE ON SCHEMA dm, meta, dss TO analyst_ro")
        conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA dm, meta, dss TO analyst_ro")
        conn.execute(sql.SQL("GRANT INSERT ON dss.decision_log TO {}").format(sql.Identifier(ROLE)))
        conn.execute(sql.SQL("GRANT USAGE ON SEQUENCE dss.decision_log_decision_id_seq TO {}").format(sql.Identifier(ROLE)))
    print(f"Role {ROLE} ready. Add to .env:\n\nDASHBOARD_DB_USER={ROLE}\nDASHBOARD_DB_PASSWORD={password}")


if __name__ == "__main__":
    main()
