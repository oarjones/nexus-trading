-- Tabla: orders
CREATE TABLE IF NOT EXISTS trading.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side trading.order_side NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8),
    status trading.order_status NOT NULL DEFAULT 'pending',
    broker trading.broker_type NOT NULL,
    broker_order_id VARCHAR(50),
    strategy_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    filled_qty DECIMAL(18,8) DEFAULT 0,
    avg_fill_price DECIMAL(18,8),
    commission DECIMAL(18,8) DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol_created 
    ON trading.orders(symbol, created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status 
    ON trading.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_strategy 
    ON trading.orders(strategy_id, created_at);

-- Tabla: trades (fills)
CREATE TABLE IF NOT EXISTS trading.trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES trading.orders(id),
    symbol VARCHAR(20) NOT NULL,
    side trading.order_side NOT NULL,
    quantity DECIMAL(18,8) NOT NULL,
    price DECIMAL(18,8) NOT NULL,
    commission DECIMAL(18,8) DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    broker trading.broker_type NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trades_order 
    ON trading.trades(order_id);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_executed 
    ON trading.trades(symbol, executed_at);

-- Tabla: positions
CREATE TABLE IF NOT EXISTS trading.positions (
    symbol VARCHAR(20) PRIMARY KEY,
    quantity DECIMAL(18,8) NOT NULL DEFAULT 0,
    avg_entry_price DECIMAL(18,8),
    current_price DECIMAL(18,8),
    unrealized_pnl DECIMAL(18,8) DEFAULT 0,
    realized_pnl DECIMAL(18,8) DEFAULT 0,
    opened_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
