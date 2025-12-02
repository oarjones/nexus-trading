-- Hypertable: ohlcv
CREATE TABLE IF NOT EXISTS market_data.ohlcv (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open DECIMAL(18,8),
    high DECIMAL(18,8),
    low DECIMAL(18,8),
    close DECIMAL(18,8),
    volume DECIMAL(24,8),
    source VARCHAR(20),
    PRIMARY KEY (time, symbol, timeframe)
);

-- Convertir a hypertable (TimescaleDB)
SELECT create_hypertable(
    'market_data.ohlcv', 
    'time',
    if_not_exists => TRUE
);

-- Hypertable: indicators
CREATE TABLE IF NOT EXISTS market_data.indicators (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    indicator VARCHAR(30) NOT NULL,
    value DECIMAL(18,8),
    PRIMARY KEY (time, symbol, timeframe, indicator)
);

SELECT create_hypertable(
    'market_data.indicators', 
    'time',
    if_not_exists => TRUE
);

-- Índices adicionales
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol 
    ON market_data.ohlcv(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_indicators_symbol 
    ON market_data.indicators(symbol, indicator, time DESC);
