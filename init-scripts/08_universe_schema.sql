-- Universe Schema
-- Persistencia del universo de símbolos activos
-- 
-- El UniverseManager guarda aquí el resultado del screening diario
-- para análisis histórico y debugging.

CREATE SCHEMA IF NOT EXISTS universe;

-- Tabla principal: universo activo por día
CREATE TABLE IF NOT EXISTS universe.daily_universe (
    id SERIAL PRIMARY KEY,
    
    -- Fecha del screening (única por día)
    screening_date DATE NOT NULL UNIQUE,
    
    -- Símbolos activos para el día
    active_symbols TEXT[] NOT NULL DEFAULT '{}',
    
    -- Régimen de mercado al momento del screening
    regime VARCHAR(20) NOT NULL,
    
    -- Métricas del funnel de filtrado
    master_universe_size INTEGER NOT NULL DEFAULT 0,
    passed_liquidity INTEGER NOT NULL DEFAULT 0,
    passed_trend INTEGER NOT NULL DEFAULT 0,
    
    -- Sugerencias del AI (JSON array)
    ai_suggestions JSONB NOT NULL DEFAULT '[]',
    
    -- Símbolos añadidos/quitados por AI
    ai_additions TEXT[] NOT NULL DEFAULT '{}',
    ai_removals TEXT[] NOT NULL DEFAULT '{}',
    
    -- Timestamps
    screened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_daily_universe_date 
    ON universe.daily_universe(screening_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_universe_regime 
    ON universe.daily_universe(regime);

-- GIN index para búsqueda en arrays
CREATE INDEX IF NOT EXISTS idx_daily_universe_symbols 
    ON universe.daily_universe USING GIN(active_symbols);


-- Tabla de historial de sugerencias del AI
-- Guarda todas las sugerencias para análisis de efectividad
CREATE TABLE IF NOT EXISTS universe.ai_suggestion_history (
    id SERIAL PRIMARY KEY,
    
    -- Símbolo sugerido
    symbol VARCHAR(20) NOT NULL,
    
    -- Tipo de sugerencia
    suggestion_type VARCHAR(10) NOT NULL CHECK (
        suggestion_type IN ('add', 'remove', 'watch')
    ),
    
    -- Razón del AI
    reason TEXT NOT NULL,
    
    -- Confianza del AI (0-1)
    confidence DECIMAL(3,2) NOT NULL CHECK (
        confidence >= 0 AND confidence <= 1
    ),
    
    -- Estado final
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'approved', 'rejected', 'expired')
    ),
    
    -- Notas de validación
    validation_notes TEXT,
    
    -- Timestamps
    suggested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    
    -- Referencia al día
    screening_date DATE REFERENCES universe.daily_universe(screening_date)
);

-- Índices para análisis
CREATE INDEX IF NOT EXISTS idx_ai_suggestions_symbol 
    ON universe.ai_suggestion_history(symbol);

CREATE INDEX IF NOT EXISTS idx_ai_suggestions_date 
    ON universe.ai_suggestion_history(screening_date DESC);

CREATE INDEX IF NOT EXISTS idx_ai_suggestions_status 
    ON universe.ai_suggestion_history(status);


-- Vista: resumen de efectividad del AI
CREATE OR REPLACE VIEW universe.ai_suggestion_effectiveness AS
SELECT 
    symbol,
    suggestion_type,
    COUNT(*) as total_suggestions,
    COUNT(*) FILTER (WHERE status = 'approved') as approved,
    COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
    AVG(confidence) as avg_confidence,
    AVG(confidence) FILTER (WHERE status = 'approved') as avg_approved_confidence
FROM universe.ai_suggestion_history
GROUP BY symbol, suggestion_type
ORDER BY total_suggestions DESC;


-- Vista: universos recientes con estadísticas
CREATE OR REPLACE VIEW universe.recent_universes AS
SELECT 
    screening_date,
    regime,
    array_length(active_symbols, 1) as active_count,
    master_universe_size,
    passed_liquidity,
    passed_trend,
    array_length(ai_additions, 1) as ai_additions_count,
    array_length(ai_removals, 1) as ai_removals_count,
    screened_at
FROM universe.daily_universe
ORDER BY screening_date DESC
LIMIT 30;


-- Función: obtener símbolos activos para una fecha
CREATE OR REPLACE FUNCTION universe.get_active_symbols(target_date DATE DEFAULT CURRENT_DATE)
RETURNS TEXT[] AS $$
DECLARE
    result TEXT[];
BEGIN
    SELECT active_symbols INTO result
    FROM universe.daily_universe
    WHERE screening_date = target_date;
    
    -- Si no hay datos para hoy, buscar el día anterior más reciente
    IF result IS NULL THEN
        SELECT active_symbols INTO result
        FROM universe.daily_universe
        WHERE screening_date < target_date
        ORDER BY screening_date DESC
        LIMIT 1;
    END IF;
    
    RETURN COALESCE(result, '{}');
END;
$$ LANGUAGE plpgsql;


-- Función: verificar si un símbolo está activo
CREATE OR REPLACE FUNCTION universe.is_symbol_active(
    check_symbol VARCHAR,
    target_date DATE DEFAULT CURRENT_DATE
)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN check_symbol = ANY(universe.get_active_symbols(target_date));
END;
$$ LANGUAGE plpgsql;


-- Comentarios de documentación
COMMENT ON TABLE universe.daily_universe IS 
    'Universo de símbolos activos para cada día de trading';

COMMENT ON TABLE universe.ai_suggestion_history IS 
    'Historial de sugerencias del AI Agent para análisis de efectividad';

COMMENT ON VIEW universe.ai_suggestion_effectiveness IS 
    'Resumen de efectividad de las sugerencias del AI por símbolo';

COMMENT ON FUNCTION universe.get_active_symbols IS 
    'Obtiene los símbolos activos para una fecha dada';
