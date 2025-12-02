-- Tabla: strategies
CREATE TABLE IF NOT EXISTS config.strategies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT false,
    params JSONB NOT NULL DEFAULT '{}',
    allowed_symbols TEXT[],
    regime_filter TEXT[],
    max_positions INTEGER DEFAULT 5,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Tabla: risk_limits
CREATE TABLE IF NOT EXISTS config.risk_limits (
    key VARCHAR(50) PRIMARY KEY,
    value DECIMAL(18,8) NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(50)
);

-- Insertar límites por defecto (Doc 6 sec 2)
INSERT INTO config.risk_limits (key, value, description) VALUES
    ('max_position_pct', 0.20, 'Máximo % por posición individual'),
    ('max_sector_pct', 0.40, 'Máximo % por sector'),
    ('max_correlation', 0.70, 'Máxima correlación entre posiciones'),
    ('max_drawdown', 0.15, 'Drawdown máximo antes de STOP'),
    ('min_cash_pct', 0.10, 'Mínimo % en cash'),
    ('max_daily_loss', 0.03, 'Pérdida máxima diaria'),
    ('max_weekly_loss', 0.05, 'Pérdida máxima semanal')
ON CONFLICT (key) DO NOTHING;
