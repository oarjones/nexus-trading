-- Tabla: decisions
CREATE TABLE IF NOT EXISTS audit.decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decision_type VARCHAR(50) NOT NULL,
    symbol VARCHAR(20),
    signals JSONB,
    risk_check JSONB,
    final_action VARCHAR(50),
    reasoning TEXT,
    order_id UUID REFERENCES trading.orders(id)
);

CREATE INDEX IF NOT EXISTS idx_decisions_timestamp 
    ON audit.decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_symbol 
    ON audit.decisions(symbol, timestamp);

-- Tabla: system_events
CREATE TABLE IF NOT EXISTS audit.system_events (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    severity audit.severity_level NOT NULL DEFAULT 'info',
    component VARCHAR(50),
    message TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp 
    ON audit.system_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_severity 
    ON audit.system_events(severity);
