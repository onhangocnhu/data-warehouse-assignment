-- 04_dss_ddl.sql
-- Outputs of the decision support component, written back into the database so the dashboard
-- reads them like any other table. Rebuilt by the DSS scripts (src/dss/*).
--   model_registry   : every model version with its evaluation metrics
--   delay_risk_score : late-delivery risk of each order when it is handed over to the carrier
--   decision_log     : what the human operator decided for each recommendation
-- (seller_alert was an earlier prototype, moved to future work; it is only dropped here.)

DROP TABLE IF EXISTS dss.delay_risk_score, dss.model_registry, dss.seller_alert CASCADE;

CREATE TABLE dss.model_registry (
    model_version  VARCHAR(60) PRIMARY KEY,     -- e.g. 'handover_hist_gradient_boosting_2018-08'
    stage          VARCHAR(10) NOT NULL,        -- handover
    algorithm      VARCHAR(40) NOT NULL,
    train_rows     INTEGER,
    train_until    DATE,                        -- only orders whose estimated date is before this day
    params         TEXT,
    test_month     CHAR(7),
    pr_auc         NUMERIC(6,4),
    roc_auc        NUMERIC(6,4),
    recall_top10   NUMERIC(6,4),               -- share of late orders caught in the riskiest 10%
    created_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE dss.delay_risk_score (
    order_id            VARCHAR(32) NOT NULL,
    stage               VARCHAR(10) NOT NULL,   -- handover
    model_version       VARCHAR(60) NOT NULL REFERENCES dss.model_registry (model_version),
    decision_date       DATE        NOT NULL,   -- day the seller handed the order over to the carrier
    p_late              NUMERIC(6,4) NOT NULL,  -- calibrated probability
    risk_rank_pct       NUMERIC(6,4),           -- rank among the orders of the same day, 0 = riskiest
    risk_level          VARCHAR(6)  NOT NULL,   -- RED | YELLOW | GREEN
    reason_1            VARCHAR(160),
    reason_2            VARCHAR(160),
    reason_3            VARCHAR(160),
    recommended_action  TEXT,
    actual_is_late      SMALLINT,               -- known outcome, kept for backtesting
    PRIMARY KEY (order_id, stage)
);

CREATE TABLE IF NOT EXISTS dss.decision_log (
    decision_id    BIGSERIAL PRIMARY KEY,
    module         VARCHAR(20) NOT NULL,        -- 'delay_risk'
    object_id      VARCHAR(40) NOT NULL,        -- order_id
    recommendation TEXT,
    decision       VARCHAR(10) NOT NULL,        -- APPROVED | REJECTED
    decided_by     VARCHAR(40),
    note           TEXT,
    decided_at     TIMESTAMP NOT NULL DEFAULT now()
);
