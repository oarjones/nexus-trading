-- ============================================================================
-- FASE A1.2: CONFIGURACIÓN DE FUENTES DE DATOS
-- ============================================================================

-- Tabla para almacenar configuración de fuentes (puede sobrescribir YAML)
CREATE TABLE IF NOT EXISTS config.data_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL UNIQUE,     -- 'ibkr', 'yahoo', 'kraken'
    source_type VARCHAR(30) NOT NULL,            -- 'broker', 'free_api', 'crypto_exchange'
    is_primary BOOLEAN DEFAULT FALSE,
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 100,                 -- Menor = mayor prioridad
    
    -- Configuración específica
    config JSONB NOT NULL DEFAULT '{}',
    
    -- Capacidades
    supports_realtime BOOLEAN DEFAULT FALSE,
    supports_historical BOOLEAN DEFAULT TRUE,
    supports_intraday BOOLEAN DEFAULT FALSE,
    max_symbols_per_request INTEGER DEFAULT 1,
    rate_limit_per_minute INTEGER DEFAULT 60,
    
    -- Estado
    last_successful_request TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    is_healthy BOOLEAN DEFAULT TRUE,
    
    -- Auditoría
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger para updated_at
DROP TRIGGER IF EXISTS data_sources_updated_at ON config.data_sources;
CREATE TRIGGER data_sources_updated_at
    BEFORE UPDATE ON config.data_sources
    FOR EACH ROW EXECUTE FUNCTION metrics.update_timestamp();

-- Insertar configuraciones por defecto
INSERT INTO config.data_sources (source_name, source_type, is_primary, priority, config, supports_realtime, supports_intraday)
VALUES 
    ('ibkr', 'broker', TRUE, 10, '{
        "host": "127.0.0.1",
        "port": 7497,
        "client_id": 1,
        "timeout_seconds": 30,
        "delayed_data_ok": true
    }', TRUE, TRUE),
    
    ('yahoo', 'free_api', FALSE, 20, '{
        "rate_limit_seconds": 0.5,
        "max_retries": 3,
        "retry_delay_seconds": 5
    }', FALSE, FALSE),
    
    ('kraken', 'crypto_exchange', FALSE, 30, '{
        "api_key_env": "KRAKEN_API_KEY",
        "api_secret_env": "KRAKEN_API_SECRET"
    }', TRUE, TRUE)
ON CONFLICT (source_name) DO NOTHING;

-- Índice para búsqueda por prioridad
CREATE INDEX IF NOT EXISTS idx_data_sources_priority 
ON config.data_sources(priority, is_enabled, is_healthy);
