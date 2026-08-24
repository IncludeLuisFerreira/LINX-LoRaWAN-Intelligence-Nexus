CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS telemetry (
  id BIGSERIAL,
  device_eui TEXT NOT NULL,
  device_name TEXT NOT NULL,
  application_id TEXT NOT NULL DEFAULT '',
  temperature DOUBLE PRECISION,
  humidity DOUBLE PRECISION,
  battery_level DOUBLE PRECISION,
  rssi INTEGER,
  snr DOUBLE PRECISION,
  fcnt BIGINT,
  payload JSONB,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('telemetry', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry (device_eui, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry (timestamp DESC);

CREATE TABLE IF NOT EXISTS devices (
  device_eui TEXT PRIMARY KEY,
  device_name TEXT NOT NULL,
  application_id TEXT NOT NULL DEFAULT '',
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_rssi INTEGER,
  last_snr DOUBLE PRECISION,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS alerts (
  id BIGSERIAL PRIMARY KEY,
  device_eui TEXT NOT NULL,
  metric TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  threshold DOUBLE PRECISION NOT NULL,
  channel TEXT NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  cooldown_until TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alerts_sent_at ON alerts (sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_device_metric ON alerts (device_eui, metric);
