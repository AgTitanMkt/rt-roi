CREATE TABLE IF NOT EXISTS tb_metrics_snapshots(
    id TEXT PRIMARY KEY,
    metric_at TIMESTAMPTZ NOT NULL,
    squad TEXT,
    cost NUMERIC(12,2) DEFAULT 0,
    profit NUMERIC(12,2) DEFAULT 0,
    roi NUMERIC(8,4) DEFAULT 0,
    revenue NUMERIC(8,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tb_hourly_metrics(
    campaign_id TEXT NOT NULL,
    metric_at TIMESTAMPTZ NOT NULL,
    checkout_conversion NUMERIC(12,2) DEFAULT 0,
    squad TEXT NOT NULL DEFAULT 'unknown',
    cost NUMERIC(12,2) DEFAULT 0,
    profit NUMERIC(12,2) DEFAULT 0,
    roi NUMERIC(8,4) DEFAULT 0,
    revenue NUMERIC(8,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_tb_hourly_metrics PRIMARY KEY(campaign_id, metric_at)
);

CREATE TABLE IF NOT EXISTS tb_daily_metrics_summary(
    metric_date DATE NOT NULL,
    squad TEXT NOT NULL,
    checkout_conversion NUMERIC(12,2) DEFAULT 0,
    cost NUMERIC(12,2) DEFAULT 0,
    profit NUMERIC(12,2) DEFAULT 0,
    roi NUMERIC(8,4) DEFAULT 0,
    revenue NUMERIC(8,2) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT pk_tb_daily_metrics_summary PRIMARY KEY(metric_date, squad)
);
