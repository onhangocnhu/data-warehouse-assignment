-- 03_meta_ddl.sql
-- Metadata repository (report: thietke/etl.tex, "Quản lý metadata"):
--   data_dictionary : every table/column of the Data Mart with its business meaning and unit
--   data_lineage    : for every target column, the source file/column and the transformation rule
--   etl_run_log     : one row per ETL step per run (Monitoring in the architecture)
--   dq_result       : result of each reconciliation / data-quality check (tab:doisoat)
--   rejected_record : records dropped or modified during transformation, with the reason

CREATE TABLE IF NOT EXISTS meta.data_dictionary (
    table_name   VARCHAR(60) NOT NULL,
    column_name  VARCHAR(60) NOT NULL,
    data_type    VARCHAR(30),
    description  TEXT,
    unit         VARCHAR(20),
    PRIMARY KEY (table_name, column_name)
);

CREATE TABLE IF NOT EXISTS meta.data_lineage (
    target_table   VARCHAR(60) NOT NULL,
    target_column  VARCHAR(60) NOT NULL,
    source_file    VARCHAR(80),
    source_column  VARCHAR(120),
    rule           TEXT,
    PRIMARY KEY (target_table, target_column)
);

CREATE TABLE IF NOT EXISTS meta.etl_run_log (
    run_id         INTEGER     NOT NULL,
    step           VARCHAR(40) NOT NULL,     -- extract | transform | load_dim_* | load_fact | dq_check
    started_at     TIMESTAMP   NOT NULL,
    finished_at    TIMESTAMP,
    rows_in        INTEGER,
    rows_out       INTEGER,
    rows_rejected  INTEGER,
    status         VARCHAR(10) NOT NULL,     -- RUNNING | SUCCESS | FAILED
    message        TEXT,
    PRIMARY KEY (run_id, step)
);
CREATE SEQUENCE IF NOT EXISTS meta.etl_run_seq;

CREATE TABLE IF NOT EXISTS meta.dq_result (
    run_id      INTEGER      NOT NULL,
    check_name  VARCHAR(80)  NOT NULL,
    expected    VARCHAR(40),
    actual      VARCHAR(40),
    passed      BOOLEAN      NOT NULL,
    checked_at  TIMESTAMP    NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, check_name)
);

CREATE TABLE IF NOT EXISTS meta.rejected_record (
    run_id      INTEGER      NOT NULL,
    source      VARCHAR(40)  NOT NULL,      -- e.g. 'orders', 'geolocation'
    record_key  VARCHAR(80),                -- e.g. order_id
    action      VARCHAR(10)  NOT NULL,      -- DROPPED | MODIFIED
    reason      TEXT         NOT NULL
);
