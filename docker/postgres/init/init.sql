CREATE TABLE IF NOT EXISTS tb_metrics_snapshots(
    id SERIAL,
    metric_at TIMESTAMP NOT NULL,
    source_alias TEXT,
    cost NUMERIC(12,2) DEFAULT 0,
    profit NUMERIC(12,2) DEFAULT 0,
    roi NUMERIC(8,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT pk_tb_metrics_id PRIMARY KEY(id)
);
