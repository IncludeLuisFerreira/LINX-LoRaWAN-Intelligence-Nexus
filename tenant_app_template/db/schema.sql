CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry (
    time TIMESTAMPTZ NOT NULL,
    dev_eui TEXT NOT NULL,
    payload JSONB NOT NULL,
    rssi INT,
    snr FLOAT
);

SELECT create_hypertable('telemetry', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS telemetry_dev_eui_time_idx
    ON telemetry (dev_eui, time DESC);
