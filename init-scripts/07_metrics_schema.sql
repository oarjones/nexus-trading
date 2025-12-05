-- ============================================================================
-- FASE A1.1: ESQUEMA DE MÉTRICAS
-- ============================================================================
-- Propósito: Tablas para capturar métricas de trades, estrategias y modelos ML
-- Dependencias: Esquemas base de Fase 0 (trading, config, audit)
-- ============================================================================

-- Crear esquema
CREATE SCHEMA IF NOT EXISTS metrics;

-- ============================================================================
-- TIPOS ENUM
-- ============================================================================

DO $$ BEGIN
    CREATE TYPE metrics.trade_direction AS ENUM ('LONG', 'SHORT');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE metrics.trade_status AS ENUM ('OPEN', 'CLOSED', 'CANCELLED');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE metrics.regime_type AS ENUM ('BULL', 'BEAR', 'SIDEWAYS', 'VOLATILE', 'UNKNOWN');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE metrics.experiment_status AS ENUM ('DRAFT', 'RUNNING', 'COMPLETED', 'ABORTED');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- ============================================================================
-- TABLA: metrics.trades
-- ============================================================================
-- Registro detallado de cada trade ejecutado
-- Esta es la tabla central del sistema de métricas

CREATE TABLE IF NOT EXISTS metrics.trades (
    -- Identificadores
    trade_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Contexto de origen
    strategy_id VARCHAR(50) NOT NULL,           -- 'etf_momentum', 'ai_agent_swing'
    model_id VARCHAR(50),                        -- 'hmm_v1', 'rules_baseline', NULL si no usa ML
    agent_id VARCHAR(50),                        -- 'claude_moderate', NULL si no es AI agent
    experiment_id UUID,                          -- FK a experiments, NULL si no es experimento
    
    -- Datos del trade
    symbol VARCHAR(20) NOT NULL,
    direction metrics.trade_direction NOT NULL,
    status metrics.trade_status NOT NULL DEFAULT 'OPEN',
    
    -- Precios y tamaño
    entry_price DECIMAL(18,8) NOT NULL,
    exit_price DECIMAL(18,8),                    -- NULL si OPEN
    stop_loss DECIMAL(18,8),
    take_profit DECIMAL(18,8),
    size_shares DECIMAL(18,8) NOT NULL,
    size_value_eur DECIMAL(18,2) NOT NULL,
    
    -- PnL (calculado al cerrar)
    pnl_eur DECIMAL(18,2),                       -- NULL si OPEN
    pnl_pct DECIMAL(8,4),                        -- Porcentaje, ej: 2.68 = 2.68%
    pnl_r_multiple DECIMAL(8,4),                 -- PnL en múltiplos de riesgo inicial
    
    -- Costes
    commission_eur DECIMAL(10,2) DEFAULT 0,
    slippage_eur DECIMAL(10,2) DEFAULT 0,
    
    -- Contexto de mercado al momento del trade
    regime_at_entry metrics.regime_type,
    regime_confidence DECIMAL(5,4),              -- 0.0000 - 1.0000
    market_volatility_at_entry DECIMAL(8,4),     -- ATR o volatilidad del momento
    
    -- Timestamps
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_timestamp TIMESTAMPTZ,
    holding_duration_hours DECIMAL(10,2),        -- Calculado al cerrar
    
    -- Metadata adicional
    reasoning TEXT,                              -- Explicación del AI agent si aplica
    signals_at_entry JSONB,                      -- Snapshot de señales: {rsi: 35, macd: -0.5, ...}
    metadata JSONB,                              -- Cualquier dato adicional
    
    -- Auditoría
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger para updated_at
CREATE OR REPLACE FUNCTION metrics.update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trades_updated_at ON metrics.trades;
CREATE TRIGGER trades_updated_at
    BEFORE UPDATE ON metrics.trades
    FOR EACH ROW EXECUTE FUNCTION metrics.update_timestamp();

-- ============================================================================
-- TABLA: metrics.strategy_performance
-- ============================================================================
-- Métricas agregadas por estrategia y período
-- Se actualiza periódicamente (ej: cada hora, cada día)

CREATE TABLE IF NOT EXISTS metrics.strategy_performance (
    id SERIAL PRIMARY KEY,
    
    -- Identificadores
    strategy_id VARCHAR(50) NOT NULL,
    period_type VARCHAR(20) NOT NULL,            -- 'hourly', 'daily', 'weekly', 'monthly', 'all_time'
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    
    -- Contadores
    total_trades INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    
    -- PnL
    total_pnl_eur DECIMAL(18,2) NOT NULL DEFAULT 0,
    avg_pnl_eur DECIMAL(18,2),
    max_win_eur DECIMAL(18,2),
    max_loss_eur DECIMAL(18,2),
    
    -- Ratios
    win_rate DECIMAL(5,4),                       -- 0.0000 - 1.0000
    profit_factor DECIMAL(8,4),                  -- Gross profits / Gross losses
    avg_r_multiple DECIMAL(8,4),
    
    -- Risk metrics
    sharpe_ratio DECIMAL(8,4),
    sortino_ratio DECIMAL(8,4),
    calmar_ratio DECIMAL(8,4),
    max_drawdown_pct DECIMAL(8,4),
    max_drawdown_eur DECIMAL(18,2),
    var_95_pct DECIMAL(8,4),                     -- Value at Risk 95%
    
    -- Timing
    avg_holding_hours DECIMAL(10,2),
    avg_trades_per_day DECIMAL(8,4),
    
    -- Por régimen
    trades_by_regime JSONB,                      -- {"BULL": 45, "BEAR": 12, ...}
    pnl_by_regime JSONB,                         -- {"BULL": 1234.56, "BEAR": -567.89, ...}
    
    -- Metadata
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Unique constraint para evitar duplicados
    UNIQUE(strategy_id, period_type, period_start)
);

-- ============================================================================
-- TABLA: metrics.model_performance
-- ============================================================================
-- Métricas de modelos ML (predicción, calibración, etc.)

CREATE TABLE IF NOT EXISTS metrics.model_performance (
    id SERIAL PRIMARY KEY,
    
    -- Identificadores
    model_id VARCHAR(50) NOT NULL,               -- 'hmm_v1', 'ppo_v1', 'rules_baseline'
    model_version VARCHAR(20),                   -- 'v1.2.3'
    period_type VARCHAR(20) NOT NULL,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    
    -- Métricas de predicción
    total_predictions INTEGER NOT NULL DEFAULT 0,
    
    -- Accuracy por régimen (para clasificación)
    accuracy DECIMAL(5,4),                       -- Overall accuracy
    accuracy_by_regime JSONB,                    -- {"BULL": 0.78, "BEAR": 0.65, ...}
    
    -- Calibración
    ece DECIMAL(5,4),                            -- Expected Calibration Error
    brier_score DECIMAL(5,4),
    
    -- Matriz de confusión (almacenada como JSON)
    confusion_matrix JSONB,                      -- {"BULL": {"BULL": 45, "BEAR": 5, ...}, ...}
    
    -- Timing
    avg_inference_time_ms DECIMAL(10,4),
    p95_inference_time_ms DECIMAL(10,4),
    
    -- Metadata
    training_date TIMESTAMPTZ,
    training_samples INTEGER,
    features_used JSONB,                         -- ["returns_5d", "volatility_20d", ...]
    hyperparameters JSONB,                       -- {"n_states": 4, "covariance_type": "full", ...}
    
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(model_id, model_version, period_type, period_start)
);

-- ============================================================================
-- TABLA: metrics.experiments
-- ============================================================================
-- Configuración de experimentos A/B

CREATE TABLE IF NOT EXISTS metrics.experiments (
    experiment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Metadata
    name VARCHAR(100) NOT NULL,
    description TEXT,
    hypothesis TEXT,                             -- "HMM mejora Sharpe vs rules baseline"
    
    -- Configuración
    experiment_type VARCHAR(50) NOT NULL,        -- 'strategy_comparison', 'model_comparison', 'parameter_tuning'
    
    -- Variantes del experimento
    control_config JSONB NOT NULL,               -- Configuración del control (baseline)
    treatment_config JSONB NOT NULL,             -- Configuración del tratamiento
    
    -- Asignación de tráfico
    traffic_split DECIMAL(5,4) NOT NULL DEFAULT 0.5,  -- % de trades al tratamiento
    
    -- Estado y timing
    status metrics.experiment_status NOT NULL DEFAULT 'DRAFT',
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    min_samples INTEGER DEFAULT 100,             -- Mínimo de trades para significancia
    
    -- Resultados finales
    winner VARCHAR(20),                          -- 'control', 'treatment', 'inconclusive'
    p_value DECIMAL(10,8),
    effect_size DECIMAL(10,6),
    
    -- Auditoría
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS experiments_updated_at ON metrics.experiments;
CREATE TRIGGER experiments_updated_at
    BEFORE UPDATE ON metrics.experiments
    FOR EACH ROW EXECUTE FUNCTION metrics.update_timestamp();

-- ============================================================================
-- TABLA: metrics.experiment_results
-- ============================================================================
-- Resultados parciales/finales de experimentos

CREATE TABLE IF NOT EXISTS metrics.experiment_results (
    id SERIAL PRIMARY KEY,
    
    experiment_id UUID NOT NULL REFERENCES metrics.experiments(experiment_id),
    variant VARCHAR(20) NOT NULL,                -- 'control' o 'treatment'
    
    -- Snapshot de métricas
    snapshot_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Contadores
    total_trades INTEGER NOT NULL DEFAULT 0,
    
    -- Métricas principales
    total_pnl_eur DECIMAL(18,2) NOT NULL DEFAULT 0,
    sharpe_ratio DECIMAL(8,4),
    win_rate DECIMAL(5,4),
    max_drawdown_pct DECIMAL(8,4),
    
    -- Métricas extendidas
    metrics_snapshot JSONB,                      -- Todas las métricas en un snapshot
    
    UNIQUE(experiment_id, variant, snapshot_timestamp)
);

-- ============================================================================
-- ÍNDICES
-- ============================================================================

-- Trades
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON metrics.trades(strategy_id, entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_model ON metrics.trades(model_id, entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON metrics.trades(symbol, entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON metrics.trades(status, entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_regime ON metrics.trades(regime_at_entry, entry_timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_experiment ON metrics.trades(experiment_id) WHERE experiment_id IS NOT NULL;

-- Strategy performance
CREATE INDEX IF NOT EXISTS idx_strategy_perf_lookup ON metrics.strategy_performance(strategy_id, period_type, period_start DESC);

-- Model performance
CREATE INDEX IF NOT EXISTS idx_model_perf_lookup ON metrics.model_performance(model_id, period_type, period_start DESC);

-- Experiments
CREATE INDEX IF NOT EXISTS idx_experiments_status ON metrics.experiments(status, start_date);

-- ============================================================================
-- VISTAS DE AGREGACIÓN
-- ============================================================================

-- Vista: Resumen de estrategias activas
CREATE OR REPLACE VIEW metrics.v_strategy_summary AS
SELECT 
    strategy_id,
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE status = 'CLOSED') as closed_trades,
    SUM(pnl_eur) FILTER (WHERE status = 'CLOSED') as total_pnl_eur,
    AVG(pnl_pct) FILTER (WHERE status = 'CLOSED') as avg_pnl_pct,
    COUNT(*) FILTER (WHERE pnl_eur > 0) as winning_trades,
    COUNT(*) FILTER (WHERE pnl_eur < 0) as losing_trades,
    CASE 
        WHEN COUNT(*) FILTER (WHERE status = 'CLOSED') > 0 
        THEN COUNT(*) FILTER (WHERE pnl_eur > 0)::DECIMAL / COUNT(*) FILTER (WHERE status = 'CLOSED')
        ELSE NULL 
    END as win_rate,
    MIN(entry_timestamp) as first_trade,
    MAX(entry_timestamp) as last_trade
FROM metrics.trades
GROUP BY strategy_id;

-- Vista: Resumen de modelos ML activos
CREATE OR REPLACE VIEW metrics.v_model_summary AS
SELECT 
    model_id,
    COUNT(DISTINCT strategy_id) as strategies_using,
    COUNT(*) as total_trades,
    SUM(pnl_eur) FILTER (WHERE status = 'CLOSED') as total_pnl_eur,
    AVG(regime_confidence) as avg_regime_confidence,
    MIN(entry_timestamp) as first_use,
    MAX(entry_timestamp) as last_use
FROM metrics.trades
WHERE model_id IS NOT NULL
GROUP BY model_id;

-- Vista: Trades recientes con contexto
CREATE OR REPLACE VIEW metrics.v_recent_trades AS
SELECT 
    t.trade_id,
    t.symbol,
    t.direction,
    t.status,
    t.strategy_id,
    t.model_id,
    t.entry_price,
    t.exit_price,
    t.pnl_eur,
    t.pnl_pct,
    t.regime_at_entry,
    t.regime_confidence,
    t.entry_timestamp,
    t.exit_timestamp,
    t.holding_duration_hours,
    t.reasoning
FROM metrics.trades t
ORDER BY t.entry_timestamp DESC
LIMIT 100;

-- ============================================================================
-- FUNCIONES DE UTILIDAD
-- ============================================================================

-- Función: Calcular métricas de una estrategia para un período
CREATE OR REPLACE FUNCTION metrics.calculate_strategy_metrics(
    p_strategy_id VARCHAR(50),
    p_start_date TIMESTAMPTZ,
    p_end_date TIMESTAMPTZ
) RETURNS TABLE (
    total_trades INTEGER,
    winning_trades INTEGER,
    losing_trades INTEGER,
    total_pnl_eur DECIMAL,
    win_rate DECIMAL,
    avg_pnl_eur DECIMAL,
    max_win_eur DECIMAL,
    max_loss_eur DECIMAL,
    profit_factor DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    WITH trade_stats AS (
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE pnl_eur > 0) as wins,
            COUNT(*) FILTER (WHERE pnl_eur < 0) as losses,
            COALESCE(SUM(pnl_eur), 0) as total_pnl,
            AVG(pnl_eur) as avg_pnl,
            MAX(pnl_eur) as max_win,
            MIN(pnl_eur) as max_loss,
            COALESCE(SUM(pnl_eur) FILTER (WHERE pnl_eur > 0), 0) as gross_profit,
            COALESCE(ABS(SUM(pnl_eur) FILTER (WHERE pnl_eur < 0)), 1) as gross_loss
        FROM metrics.trades
        WHERE strategy_id = p_strategy_id
          AND status = 'CLOSED'
          AND exit_timestamp BETWEEN p_start_date AND p_end_date
    )
    SELECT 
        ts.total::INTEGER,
        ts.wins::INTEGER,
        ts.losses::INTEGER,
        ts.total_pnl,
        CASE WHEN ts.total > 0 THEN ts.wins::DECIMAL / ts.total ELSE NULL END,
        ts.avg_pnl,
        ts.max_win,
        ts.max_loss,
        CASE WHEN ts.gross_loss > 0 THEN ts.gross_profit / ts.gross_loss ELSE NULL END
    FROM trade_stats ts;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================

-- Query de verificación (ejecutar después de crear las tablas)
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_schema = 'metrics';
    
    IF table_count >= 5 THEN
        RAISE NOTICE 'VERIFICACIÓN OK: % tablas creadas en esquema metrics', table_count;
    ELSE
        RAISE WARNING 'VERIFICACIÓN FALLIDA: Solo % tablas encontradas', table_count;
    END IF;
END $$;
