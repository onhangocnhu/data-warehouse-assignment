-- 00_schemas.sql
-- Creates the four schemas of the system (see latex-report/Sections/thietke/khainiem.tex, sec:kientruc).
--   staging : raw copies of the 9 CSV files (raw_*) and cleaned tables (stg_*)
--   dm      : the Data Mart (snowflake schema: fact_sales + 7 dimension tables)
--   meta    : metadata repository (data dictionary, lineage, ETL run log, data-quality results)
--   dss     : outputs of the decision support component (risk scores, alerts, decision log)

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS dm;
CREATE SCHEMA IF NOT EXISTS meta;
CREATE SCHEMA IF NOT EXISTS dss;

-- Removes accents when normalising city names ('são paulo' -> 'sao paulo'). Needs a superuser once.
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Read-only role for analysts and the dashboard (report: Security -- Tính bảo mật).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_ro') THEN
        CREATE ROLE analyst_ro NOLOGIN;
    END IF;
END $$;
GRANT USAGE ON SCHEMA dm, dss, meta TO analyst_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA dm   GRANT SELECT ON TABLES TO analyst_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA meta GRANT SELECT ON TABLES TO analyst_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA dss  GRANT SELECT ON TABLES TO analyst_ro;
