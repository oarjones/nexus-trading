-- ============================================================================
-- Phase 4: Trading Engine - Database Schema
-- ============================================================================
-- Creates tables for:
-- - Strategy configuration (config.strategies)
-- - Orders tracking (trading.orders)
-- - Trade history (trading.trades)  
-- - Position management (trading.positions)
-- ============================================================================

-- Create schemas if not exist
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS trading;

-- ============================================================================
-- Drop existing tables (clean slate migration)
-- ============================================================================

DROP TABLE IF EXISTS trading.positions CASCADE;
DROP TABLE IF EXISTS trading.trades CASCADE;
DROP TABLE IF EXISTS trading.orders CASCADE;
DROP TABLE IF EXISTS config.strategies CASCADE;

-- ============================================================================
-- Table: config.strategies
-- Purpose: Store strategy configurations and parameters
-- ============================================================================

CREATE TABLE IF NOT EXISTS config.strategies (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true NOT NULL,
    markets TEXT[] NOT NULL,  -- e.g., ['BME', 'XETRA']
    regime_filter TEXT[] NOT NULL,  -- e.g., ['trending_bull', 'range_bound']
    timeframe VARCHAR(10) NOT NULL,  -- e.g., '1d', '1h'
    params JSONB NOT NULL,  -- Strategy-specific parameters
    risk_params JSONB NOT NULL,  -- Risk management parameters
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_strategies_enabled 
    ON config.strategies(enabled) WHERE enabled = true;

CREATE INDEX IF NOT EXISTS idx_strategies_markets 
    ON config.strategies USING GIN(markets);

CREATE INDEX IF NOT EXISTS idx_strategies_regime 
    ON config.strategies USING GIN(regime_filter);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_strategies_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_strategies_updated
    BEFORE UPDATE ON config.strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_strategies_timestamp();

COMMENT ON TABLE config.strategies IS 'Trading strategy configurations and parameters';
COMMENT ON COLUMN config.strategies.params IS 'Strategy-specific parameters (RSI levels, z-score thresholds, etc.)';
COMMENT ON COLUMN config.strategies.risk_params IS 'Risk management parameters (max positions, drawdown limits, etc.)';

-- ============================================================================
-- Table: trading.orders
-- Purpose: Track all orders sent to broker
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_order_id VARCHAR(100),  -- Order ID from IBKR
    strategy_id VARCHAR(50) REFERENCES config.strategies(id),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market', 'limit', 'stop', 'stop_limit')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    limit_price DECIMAL(12, 4),
    stop_price DECIMAL(12, 4),
    status VARCHAR(20) NOT NULL 
        CHECK (status IN ('pending', 'sent', 'partial', 'filled', 'rejected', 'cancelled')),
    filled_qty INTEGER DEFAULT 0,
    avg_fill_price DECIMAL(12, 4),
    total_commission DECIMAL(10, 4) DEFAULT 0,
    rejection_reason TEXT,
    metadata JSONB,  -- Additional order metadata
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    filled_at TIMESTAMPTZ
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_strategy 
    ON trading.orders(strategy_id);

CREATE INDEX IF NOT EXISTS idx_orders_symbol 
    ON trading.orders(symbol);

CREATE INDEX IF NOT EXISTS idx_orders_status 
    ON trading.orders(status);

CREATE INDEX IF NOT EXISTS idx_orders_created 
    ON trading.orders(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_orders_broker_id 
    ON trading.orders(broker_order_id) WHERE broker_order_id IS NOT NULL;

-- Auto-update timestamp trigger
CREATE TRIGGER trg_orders_updated
    BEFORE UPDATE ON trading.orders
    FOR EACH ROW
    EXECUTE FUNCTION update_strategies_timestamp();

COMMENT ON TABLE trading.orders IS 'Order tracking for all broker submissions';
COMMENT ON COLUMN trading.orders.broker_order_id IS 'Unique order ID from IBKR';
COMMENT ON COLUMN trading.orders.status IS 'Current order status in lifecycle';

-- ============================================================================
-- Table: trading.trades
-- Purpose: Record completed trades (filled orders)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID REFERENCES trading.orders(id),
    strategy_id VARCHAR(50) REFERENCES config.strategies(id),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short', 'close')),
    entry_price DECIMAL(12, 4) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_order_id UUID REFERENCES trading.orders(id),
    exit_price DECIMAL(12, 4),
    exit_time TIMESTAMPTZ,
    exit_order_id UUID REFERENCES trading.orders(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    pnl DECIMAL(12, 4),  -- Profit/Loss in currency
    pnl_pct DECIMAL(8, 4),  -- Profit/Loss percentage
    total_costs DECIMAL(10, 4) DEFAULT 0,  -- Commission + slippage
    holding_period_hours INTEGER,
    stop_loss DECIMAL(12, 4),
    take_profit DECIMAL(12, 4),
    exit_reason VARCHAR(50),  -- 'take_profit', 'stop_loss', 'signal', 'manual'
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_strategy 
    ON trading.trades(strategy_id);

CREATE INDEX IF NOT EXISTS idx_trades_symbol 
    ON trading.trades(symbol);

CREATE INDEX IF NOT EXISTS idx_trades_entry_time 
    ON trading.trades(entry_time DESC);

CREATE INDEX IF NOT EXISTS idx_trades_pnl 
    ON trading.trades(pnl) WHERE pnl IS NOT NULL;

-- Auto-update timestamp trigger
CREATE TRIGGER trg_trades_updated
    BEFORE UPDATE ON trading.trades
    FOR EACH ROW
    EXECUTE FUNCTION update_strategies_timestamp();

-- Auto-calculate PnL trigger
CREATE OR REPLACE FUNCTION calculate_trade_pnl()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.exit_price IS NOT NULL AND NEW.entry_price IS NOT NULL THEN
        IF NEW.direction = 'long' THEN
            NEW.pnl = (NEW.exit_price - NEW.entry_price) * NEW.quantity - NEW.total_costs;
            NEW.pnl_pct = ((NEW.exit_price - NEW.entry_price) / NEW.entry_price) * 100;
        ELSIF NEW.direction = 'short' THEN
            NEW.pnl = (NEW.entry_price - NEW.exit_price) * NEW.quantity - NEW.total_costs;
            NEW.pnl_pct = ((NEW.entry_price - NEW.exit_price) / NEW.entry_price) * 100;
        END IF;
        
        -- Calculate holding period
        IF NEW.exit_time IS NOT NULL AND NEW.entry_time IS NOT NULL THEN
            NEW.holding_period_hours = EXTRACT(EPOCH FROM (NEW.exit_time - NEW.entry_time)) / 3600;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_trades_calculate_pnl
    BEFORE INSERT OR UPDATE ON trading.trades
    FOR EACH ROW
    EXECUTE FUNCTION calculate_trade_pnl();

COMMENT ON TABLE trading.trades IS 'Complete trade records with entry/exit and PnL';
COMMENT ON COLUMN trading.trades.pnl IS 'Profit/Loss in currency after costs';
COMMENT ON COLUMN trading.trades.exit_reason IS 'Reason for trade exit (TP, SL, signal, manual)';

-- ============================================================================
-- Table: trading.positions
-- Purpose: Track current open positions
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id VARCHAR(50) REFERENCES config.strategies(id),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    avg_entry_price DECIMAL(12, 4) NOT NULL,
    current_price DECIMAL(12, 4),
    unrealized_pnl DECIMAL(12, 4),
    unrealized_pnl_pct DECIMAL(8, 4),
    stop_loss DECIMAL(12, 4),
    take_profit DECIMAL(12, 4),
    entry_time TIMESTAMPTZ NOT NULL,
    last_update TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    metadata JSONB,
    UNIQUE(strategy_id, symbol)  -- One position per symbol per strategy
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_positions_strategy 
    ON trading.positions(strategy_id);

CREATE INDEX IF NOT EXISTS idx_positions_symbol 
    ON trading.positions(symbol);

CREATE INDEX IF NOT EXISTS idx_positions_entry_time 
    ON trading.positions(entry_time DESC);

-- Auto-update last_update trigger
CREATE OR REPLACE FUNCTION update_position_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_update = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_positions_updated
    BEFORE UPDATE ON trading.positions
    FOR EACH ROW
    EXECUTE FUNCTION update_position_timestamp();

-- Auto-calculate unrealized PnL trigger
CREATE OR REPLACE FUNCTION calculate_unrealized_pnl()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.current_price IS NOT NULL THEN
        IF NEW.direction = 'long' THEN
            NEW.unrealized_pnl = (NEW.current_price - NEW.avg_entry_price) * NEW.quantity;
            NEW.unrealized_pnl_pct = ((NEW.current_price - NEW.avg_entry_price) / NEW.avg_entry_price) * 100;
        ELSIF NEW.direction = 'short' THEN
            NEW.unrealized_pnl = (NEW.avg_entry_price - NEW.current_price) * NEW.quantity;
            NEW.unrealized_pnl_pct = ((NEW.avg_entry_price - NEW.current_price) / NEW.avg_entry_price) * 100;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_positions_calculate_pnl
    BEFORE INSERT OR UPDATE ON trading.positions
    FOR EACH ROW
    EXECUTE FUNCTION calculate_unrealized_pnl();

COMMENT ON TABLE trading.positions IS 'Current open positions with unrealized PnL';
COMMENT ON COLUMN trading.positions.unrealized_pnl IS 'Unrealized profit/loss based on current_price';

-- ============================================================================
-- Initial Data: Sample Strategies
-- ============================================================================

-- Insert swing momentum strategy
INSERT INTO config.strategies (id, name, enabled, markets, regime_filter, timeframe, params, risk_params, description)
VALUES (
    'swing_momentum_eu',
    'Momentum Swing EU',
    true,
    ARRAY['BME', 'XETRA'],
    ARRAY['trending_bull'],
    '1d',
    '{"rsi_oversold": 35, "rsi_overbought": 65, "sma_filter": 50, "volume_mult": 1.5, "atr_stop_mult": 2.0, "risk_reward": 3.0}'::jsonb,
    '{"max_positions": 5, "max_pct_per_position": 0.15, "max_correlation": 0.7, "max_drawdown": 0.15}'::jsonb,
    'Swing trading strategy using RSI, MACD, and SMA filters for European stocks'
) ON CONFLICT (id) DO NOTHING;

-- Insert mean reversion pairs strategy
INSERT INTO config.strategies (id, name, enabled, markets, regime_filter, timeframe, params, risk_params, description)
VALUES (
    'mean_reversion_pairs',
    'Pairs Mean Reversion',
    true,
    ARRAY['BME', 'XETRA'],
    ARRAY['range_bound'],
    '1h',
    '{"zscore_entry": 2.0, "zscore_exit": 0.5, "lookback": 60, "max_holding_days": 5, "coint_pvalue": 0.05, "coint_lookback": 252, "pairs": [["SAN.MC", "BBVA.MC"], ["SAP.DE", "ASML.AS"]]}'::jsonb,
    '{"max_pairs": 2, "max_pct_per_pair": 0.20, "max_drawdown": 0.10}'::jsonb,
    'Pairs trading strategy using cointegration and z-score signals'
) ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verify strategies table
DO $$
DECLARE
    strategy_count INT;
BEGIN
    SELECT COUNT(*) INTO strategy_count FROM config.strategies WHERE enabled = true;
    RAISE NOTICE 'Loaded % enabled strategies', strategy_count;
END $$;

-- Show created tables
SELECT 
    schemaname, 
    tablename, 
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname IN ('config', 'trading')
    AND tablename IN ('strategies', 'orders', 'trades', 'positions')
ORDER BY schemaname, tablename;
