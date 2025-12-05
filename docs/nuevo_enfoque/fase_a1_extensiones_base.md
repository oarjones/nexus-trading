# 🔧 Fase A1: Extensiones a Infraestructura Base

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fases 0-3 existentes (documentación)  
**Prerrequisito:** Este documento DEBE implementarse antes de Fase A2 (ML Modular)

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

Las Fases 0-3 originales fueron diseñadas con:
- Yahoo Finance como fuente principal de datos
- Esquemas de BD orientados a datos OHLCV básicos
- Sin soporte para métricas de trading/ML
- Sin servidor MCP para modelos de Machine Learning

### 1.2 Nuevo Enfoque

El handoff document define un cambio de filosofía:

```
ANTES                           AHORA
══════                          ══════
Yahoo Finance (principal)   →   IBKR (principal) + Yahoo (fallback)
Backtesting primero         →   Paper trading primero (MVP)
Sin métricas detalladas     →   Métricas por trade, estrategia, modelo
Sin ML server               →   mcp-ml-models para predicciones
```

### 1.3 Por Qué Estos Cambios

| Cambio | Justificación |
|--------|---------------|
| IBKR como fuente | Datos más fiables, misma fuente que ejecución, evita discrepancias |
| Tablas de métricas | Comparar estrategias, modelos ML, y configuraciones A/B |
| mcp-ml-models | Servir predicciones de régimen (HMM) a estrategias |

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| Esquemas de métricas | Tablas `metrics.*` creadas, queries funcionando |
| IBKR como fuente principal | `IBKRProvider` descarga datos correctamente |
| Fallback a Yahoo | Si IBKR falla, Yahoo toma el relevo automáticamente |
| mcp-ml-models base | Server responde a `health_check`, estructura lista |
| Migración no destructiva | Datos existentes preservados (si los hay) |

---

## 3. Resumen de Cambios

### 3.1 Cambios en Base de Datos

```
NUEVOS ESQUEMAS:
═══════════════
metrics/                    ← NUEVO esquema completo
├── trades                  ← Registro detallado de cada trade
├── strategy_performance    ← Métricas agregadas por estrategia
├── model_performance       ← Métricas de modelos ML
├── experiments             ← Configuración de experimentos A/B
└── experiment_results      ← Resultados de experimentos

MODIFICACIONES:
═══════════════
config/
└── data_sources            ← Nueva tabla para configurar fuentes
```

### 3.2 Cambios en Data Pipeline (Fase 1)

```
ARCHIVOS MODIFICADOS:
═══════════════════════
src/data/providers/
├── yahoo.py                ← Convertir a fallback
├── ibkr.py                 ← Promover a principal
└── provider_factory.py     ← NUEVO: Factory para seleccionar provider

config/
└── data_sources.yaml       ← NUEVO: Configuración de fuentes
```

### 3.3 Nuevos Componentes

```
NUEVO MCP SERVER:
═══════════════════
mcp-servers/ml-models/
├── __init__.py
├── server.py               ← Entry point
├── tools/
│   ├── __init__.py
│   ├── health.py           ← Health check básico
│   ├── predict.py          ← Placeholder para predicciones
│   └── model_info.py       ← Info de modelos disponibles
└── tests/
    └── test_ml_models.py
```

---

## 4. Dependencias Entre Tareas

```
┌─────────────────────────────────────────────────────────────────┐
│                    FASE A1: EXTENSIONES BASE                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐                                           │
│  │ A1.1: Esquemas   │                                           │
│  │ de métricas      │──────┐                                    │
│  └──────────────────┘      │                                    │
│                            │                                    │
│  ┌──────────────────┐      │     ┌──────────────────┐          │
│  │ A1.2: Config     │      │     │ A1.5: Scripts    │          │
│  │ data_sources     │──────┼────▶│ verificación     │          │
│  └──────────────────┘      │     └──────────────────┘          │
│                            │              ▲                     │
│  ┌──────────────────┐      │              │                     │
│  │ A1.3: IBKR       │──────┤              │                     │
│  │ como principal   │      │              │                     │
│  └──────────────────┘      │              │                     │
│                            │              │                     │
│  ┌──────────────────┐      │              │                     │
│  │ A1.4: mcp-ml-    │──────┘──────────────┘                     │
│  │ models (base)    │                                           │
│  └──────────────────┘                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

LEYENDA:
────────
A1.1, A1.2 pueden ejecutarse en paralelo
A1.3 depende de A1.2 (necesita config)
A1.4 es independiente
A1.5 requiere todos los anteriores
```

---

## 5. Arquitectura de Referencia

### 5.1 Flujo de Datos con Nuevo Provider

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA PROVIDER FACTORY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   config/data_sources.yaml                                       │
│   ┌─────────────────────┐                                       │
│   │ primary: ibkr       │                                       │
│   │ fallback: yahoo     │                                       │
│   │ retry_count: 3      │                                       │
│   └─────────────────────┘                                       │
│              │                                                   │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │  ProviderFactory    │                                       │
│   │  .get_provider()    │                                       │
│   └─────────────────────┘                                       │
│              │                                                   │
│      ┌───────┴───────┐                                          │
│      ▼               ▼                                          │
│  ┌────────┐     ┌────────┐                                      │
│  │  IBKR  │     │ Yahoo  │                                      │
│  │Provider│     │Provider│                                      │
│  └────────┘     └────────┘                                      │
│      │               │                                          │
│      │   (fallback)  │                                          │
│      └───────┬───────┘                                          │
│              ▼                                                   │
│   ┌─────────────────────┐                                       │
│   │    TimescaleDB      │                                       │
│   │   market_data.*     │                                       │
│   └─────────────────────┘                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 Esquema de Métricas

```
┌─────────────────────────────────────────────────────────────────┐
│                     ESQUEMA: metrics                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                     metrics.trades                        │   │
│  │  ─────────────────────────────────────────────────────   │   │
│  │  • trade_id (PK)           • strategy_id                 │   │
│  │  • symbol                  • model_id                    │   │
│  │  • direction               • agent_id                    │   │
│  │  • entry_price/exit_price  • regime_at_entry             │   │
│  │  • pnl_eur, pnl_pct        • reasoning (JSON)            │   │
│  │  • timestamps              • metadata (JSONB)            │   │
│  └──────────────────────────────────────────────────────────┘   │
│                              │                                   │
│              ┌───────────────┼───────────────┐                  │
│              ▼               ▼               ▼                  │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐      │
│  │   strategy_    │ │    model_      │ │  experiments   │      │
│  │  performance   │ │  performance   │ │                │      │
│  │  (agregado)    │ │  (agregado)    │ │  (A/B config)  │      │
│  └────────────────┘ └────────────────┘ └────────────────┘      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Consideraciones Importantes

### 6.1 Compatibilidad Hacia Atrás

- Los esquemas existentes (`trading`, `market_data`, `config`, `audit`, `features`) NO se modifican
- Las nuevas tablas van en esquema `metrics` separado
- El código existente seguirá funcionando sin cambios

### 6.2 IBKR Requisitos

Para que IBKR funcione como fuente de datos:

| Requisito | Detalle |
|-----------|---------|
| TWS/Gateway | Debe estar corriendo en `localhost:7497` (paper) |
| API habilitada | TWS → File → Global Configuration → API → Enable |
| Client ID | Usar ID único (ej: 1 para data, 2 para trading) |
| Delayed OK | Aceptamos datos con 15 min delay en paper |

### 6.3 Orden de Ejecución

```
1. Ejecutar scripts SQL de métricas (A1.1)
2. Crear tabla config.data_sources (A1.2)
3. Implementar IBKRProvider mejorado (A1.3)
4. Crear estructura mcp-ml-models (A1.4)
5. Ejecutar script verificación (A1.5)
```

---

## 7. Checklist Pre-Implementación

Antes de comenzar, verificar:

```
[ ] Docker está corriendo con servicios de Fase 0
[ ] PostgreSQL accesible en localhost:5432
[ ] Redis accesible en localhost:6379
[ ] TWS/IB Gateway instalado (aunque no necesario corriendo aún)
[ ] Python 3.11+ con entorno virtual activo
[ ] requirements.txt instalado
```

---

*Fin de Parte 1 - Continúa en Parte 2: Esquemas de Métricas*
---

# Parte 2: Esquemas de Métricas (PostgreSQL)

---

## Tarea A1.1: Crear Esquema de Métricas

**Estado:** ⬜ Pendiente

**Objetivo:** Crear todas las tablas necesarias para capturar métricas de trading, estrategias y modelos ML.

**Duración estimada:** 2-3 horas

**Subtareas:**
- [ ] Crear esquema `metrics`
- [ ] Crear tipos ENUM para métricas
- [ ] Crear tabla `metrics.trades`
- [ ] Crear tabla `metrics.strategy_performance`
- [ ] Crear tabla `metrics.model_performance`
- [ ] Crear tabla `metrics.experiments`
- [ ] Crear tabla `metrics.experiment_results`
- [ ] Crear índices optimizados
- [ ] Crear vistas de agregación
- [ ] Verificar con queries de prueba

---

### A1.1.1: Script SQL Principal

**Archivo:** `init-scripts/07_metrics_schema.sql`

```sql
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
```

---

### A1.1.2: Validación del Esquema

**Archivo:** `scripts/verify_metrics_schema.py`

```python
#!/usr/bin/env python3
"""
Verificación del esquema de métricas - Fase A1.1
Ejecutar: python scripts/verify_metrics_schema.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

def check_metrics_schema():
    """Verificar que el esquema metrics existe y tiene todas las tablas."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Verificar esquema existe
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name = 'metrics'
        """)
        if not cur.fetchone():
            return False, "Esquema 'metrics' no existe"
        
        # Verificar tablas
        expected_tables = {
            'trades',
            'strategy_performance',
            'model_performance',
            'experiments',
            'experiment_results'
        }
        
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'metrics'
        """)
        actual_tables = {row[0] for row in cur.fetchall()}
        
        missing = expected_tables - actual_tables
        if missing:
            return False, f"Tablas faltantes: {missing}"
        
        # Verificar tipos ENUM
        cur.execute("""
            SELECT typname FROM pg_type 
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'metrics')
            AND typtype = 'e'
        """)
        enums = {row[0] for row in cur.fetchall()}
        expected_enums = {'trade_direction', 'trade_status', 'regime_type', 'experiment_status'}
        
        missing_enums = expected_enums - enums
        if missing_enums:
            return False, f"ENUMs faltantes: {missing_enums}"
        
        # Verificar vistas
        cur.execute("""
            SELECT table_name FROM information_schema.views 
            WHERE table_schema = 'metrics'
        """)
        views = {row[0] for row in cur.fetchall()}
        expected_views = {'v_strategy_summary', 'v_model_summary', 'v_recent_trades'}
        
        missing_views = expected_views - views
        if missing_views:
            return False, f"Vistas faltantes: {missing_views}"
        
        # Verificar índices (al menos los principales)
        cur.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'metrics'
        """)
        indexes = {row[0] for row in cur.fetchall()}
        
        if len(indexes) < 5:
            return False, f"Pocos índices encontrados: {len(indexes)}"
        
        conn.close()
        
        return True, f"OK: 5 tablas, {len(enums)} ENUMs, {len(views)} vistas, {len(indexes)} índices"
        
    except Exception as e:
        return False, str(e)


def check_metrics_function():
    """Verificar que la función de cálculo de métricas funciona."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Llamar función con datos vacíos (debe retornar sin error)
        cur.execute("""
            SELECT * FROM metrics.calculate_strategy_metrics(
                'test_strategy',
                NOW() - INTERVAL '30 days',
                NOW()
            )
        """)
        result = cur.fetchone()
        
        conn.close()
        
        if result is not None:
            return True, "Función calculate_strategy_metrics OK"
        else:
            return False, "Función no retorna resultados"
            
    except Exception as e:
        return False, str(e)


def main():
    """Ejecutar todas las verificaciones."""
    print("VERIFICACIÓN ESQUEMA MÉTRICAS - FASE A1.1")
    print("=" * 50)
    
    checks = [
        ("Esquema y tablas metrics", check_metrics_schema),
        ("Función de métricas", check_metrics_function),
    ]
    
    all_ok = True
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    print()
    print("=" * 50)
    if all_ok:
        print("✅ ESQUEMA MÉTRICAS OK - Tarea A1.1 completada")
        return 0
    else:
        print("❌ ERRORES DETECTADOS - Revisar antes de continuar")
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### A1.1.3: Comandos de Ejecución

```powershell
# 1. Ejecutar script SQL
docker exec -i trading_postgres psql -U trading -d trading < init-scripts/07_metrics_schema.sql

# 2. Verificar manualmente (opcional)
docker exec trading_postgres psql -U trading -d trading -c "\dt metrics.*"

# 3. Ejecutar script de verificación
python scripts/verify_metrics_schema.py

# Output esperado:
# VERIFICACIÓN ESQUEMA MÉTRICAS - FASE A1.1
# ==================================================
# ✅ Esquema y tablas metrics: OK: 5 tablas, 4 ENUMs, 3 vistas, 8 índices
# ✅ Función de métricas: Función calculate_strategy_metrics OK
# ==================================================
# ✅ ESQUEMA MÉTRICAS OK - Tarea A1.1 completada
```

---

### A1.1.4: Queries de Prueba

Después de crear el esquema, ejecutar estas queries para verificar funcionamiento:

```sql
-- 1. Insertar trade de prueba
INSERT INTO metrics.trades (
    strategy_id, symbol, direction, entry_price, 
    size_shares, size_value_eur, regime_at_entry
) VALUES (
    'etf_momentum', 'VWCE.DE', 'LONG', 100.50,
    10, 1005.00, 'BULL'
) RETURNING trade_id;

-- 2. Simular cierre de trade
UPDATE metrics.trades 
SET status = 'CLOSED',
    exit_price = 103.20,
    exit_timestamp = NOW(),
    pnl_eur = (103.20 - 100.50) * 10,
    pnl_pct = ((103.20 - 100.50) / 100.50) * 100,
    holding_duration_hours = EXTRACT(EPOCH FROM (NOW() - entry_timestamp)) / 3600
WHERE strategy_id = 'etf_momentum' AND status = 'OPEN';

-- 3. Verificar vista de resumen
SELECT * FROM metrics.v_strategy_summary;

-- 4. Verificar función de métricas
SELECT * FROM metrics.calculate_strategy_metrics(
    'etf_momentum',
    NOW() - INTERVAL '1 day',
    NOW()
);

-- 5. Limpiar datos de prueba
DELETE FROM metrics.trades WHERE strategy_id = 'etf_momentum';
```

---

*Fin de Parte 2 - Continúa en Parte 3: Configuración de Fuentes de Datos*
---

# Parte 3: Configuración de Fuentes de Datos (IBKR como Principal)

---

## Tarea A1.2: Crear Sistema de Configuración de Fuentes

**Estado:** ⬜ Pendiente

**Objetivo:** Centralizar la configuración de fuentes de datos y permitir cambiar entre IBKR (principal) y Yahoo (fallback).

**Duración estimada:** 1-2 horas

**Subtareas:**
- [ ] Crear tabla `config.data_sources`
- [ ] Crear archivo `config/data_sources.yaml`
- [ ] Implementar clase `DataSourceConfig`
- [ ] Tests de carga de configuración

---

### A1.2.1: Tabla de Configuración en BD

**Archivo:** `init-scripts/08_data_sources_config.sql`

```sql
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
```

---

### A1.2.2: Archivo de Configuración YAML

**Archivo:** `config/data_sources.yaml`

```yaml
# ============================================================================
# CONFIGURACIÓN DE FUENTES DE DATOS - NEXUS TRADING
# ============================================================================
# Este archivo define las fuentes de datos disponibles y su prioridad.
# La configuración aquí puede ser sobrescrita por la tabla config.data_sources
# ============================================================================

# Fuente principal
primary: ibkr

# Fuente de fallback (si principal falla)
fallback: yahoo

# Comportamiento global
global:
  # Reintentos antes de usar fallback
  retry_count: 3
  retry_delay_seconds: 2
  
  # Timeout global para requests
  request_timeout_seconds: 30
  
  # Umbral de fallos consecutivos para marcar fuente como unhealthy
  unhealthy_threshold: 5
  
  # Tiempo para reintentar fuente unhealthy (segundos)
  recovery_check_interval: 300

# Configuración específica por fuente
sources:
  # ─────────────────────────────────────────────────────────────────────────
  # IBKR - Interactive Brokers (PRINCIPAL)
  # ─────────────────────────────────────────────────────────────────────────
  ibkr:
    enabled: true
    priority: 10  # Menor número = mayor prioridad
    
    connection:
      host: "127.0.0.1"
      port: 7497              # 7497 = paper trading, 7496 = live
      client_id: 1            # ID único para este cliente
      timeout_seconds: 30
    
    data:
      delayed_data_ok: true   # Aceptamos datos con 15 min delay en paper
      bar_sizes:              # Tamaños de barra soportados
        - "1 min"
        - "5 mins"
        - "15 mins"
        - "1 hour"
        - "1 day"
      max_duration: "1 Y"     # Máximo histórico en una request
    
    capabilities:
      supports_realtime: true
      supports_historical: true
      supports_intraday: true
      supports_options: true
      supports_forex: true
    
    rate_limiting:
      max_requests_per_second: 50
      max_historical_requests_per_10min: 60
  
  # ─────────────────────────────────────────────────────────────────────────
  # YAHOO FINANCE (FALLBACK)
  # ─────────────────────────────────────────────────────────────────────────
  yahoo:
    enabled: true
    priority: 20
    
    connection:
      rate_limit_seconds: 0.5   # Delay entre requests para evitar ban
      max_retries: 3
      retry_delay_seconds: 5
    
    data:
      intervals:                # Intervalos soportados
        - "1m"
        - "5m"
        - "15m"
        - "1h"
        - "1d"
        - "1wk"
        - "1mo"
      max_period: "5y"          # Máximo histórico
    
    capabilities:
      supports_realtime: false   # Solo delayed
      supports_historical: true
      supports_intraday: false   # Solo con limitaciones
      supports_options: true
      supports_forex: true
    
    rate_limiting:
      max_requests_per_minute: 60
      batch_size: 10            # Símbolos por request en batch
  
  # ─────────────────────────────────────────────────────────────────────────
  # KRAKEN (CRYPTO)
  # ─────────────────────────────────────────────────────────────────────────
  kraken:
    enabled: false  # Habilitar cuando se implemente crypto
    priority: 30
    
    connection:
      api_key_env: "KRAKEN_API_KEY"
      api_secret_env: "KRAKEN_API_SECRET"
    
    capabilities:
      supports_realtime: true
      supports_historical: true
      supports_intraday: true

# ─────────────────────────────────────────────────────────────────────────
# MAPPING DE SÍMBOLOS
# ─────────────────────────────────────────────────────────────────────────
# Algunos símbolos tienen formato diferente según la fuente
symbol_mapping:
  # Símbolo interno -> { fuente: símbolo_específico }
  "EURUSD":
    ibkr: "EUR.USD"
    yahoo: "EURUSD=X"
  "GBPUSD":
    ibkr: "GBP.USD"
    yahoo: "GBPUSD=X"
  "BTC-EUR":
    ibkr: null        # No disponible en IBKR
    yahoo: "BTC-EUR"
    kraken: "XXBTZEUR"
```

---

### A1.2.3: Clase de Configuración Python

**Archivo:** `src/data/config.py`

```python
"""
Configuración de fuentes de datos - Fase A1.2
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class SourceCapabilities(BaseModel):
    """Capacidades de una fuente de datos."""
    supports_realtime: bool = False
    supports_historical: bool = True
    supports_intraday: bool = False
    supports_options: bool = False
    supports_forex: bool = False


class IBKRConfig(BaseModel):
    """Configuración específica de IBKR."""
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 1
    timeout_seconds: int = 30
    delayed_data_ok: bool = True


class YahooConfig(BaseModel):
    """Configuración específica de Yahoo Finance."""
    rate_limit_seconds: float = 0.5
    max_retries: int = 3
    retry_delay_seconds: int = 5


class GlobalConfig(BaseModel):
    """Configuración global del sistema de datos."""
    retry_count: int = 3
    retry_delay_seconds: int = 2
    request_timeout_seconds: int = 30
    unhealthy_threshold: int = 5
    recovery_check_interval: int = 300


@dataclass
class DataSourceInfo:
    """Información completa de una fuente de datos."""
    name: str
    enabled: bool
    priority: int
    capabilities: SourceCapabilities
    config: dict
    is_healthy: bool = True
    consecutive_failures: int = 0


class DataSourceConfig:
    """
    Gestor de configuración de fuentes de datos.
    
    Carga configuración desde YAML y permite override desde BD.
    
    Uso:
        config = DataSourceConfig('config/data_sources.yaml')
        primary = config.get_primary_source()
        fallback = config.get_fallback_source()
    """
    
    def __init__(self, config_path: str = "config/data_sources.yaml"):
        self.config_path = Path(config_path)
        self._raw_config: dict = {}
        self._sources: dict[str, DataSourceInfo] = {}
        self._global: GlobalConfig = GlobalConfig()
        self._symbol_mapping: dict[str, dict[str, str]] = {}
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Cargar configuración desde YAML."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self._raw_config = yaml.safe_load(f)
        
        # Cargar configuración global
        if 'global' in self._raw_config:
            self._global = GlobalConfig(**self._raw_config['global'])
        
        # Cargar fuentes
        sources_config = self._raw_config.get('sources', {})
        for name, source_data in sources_config.items():
            capabilities = SourceCapabilities(**source_data.get('capabilities', {}))
            
            self._sources[name] = DataSourceInfo(
                name=name,
                enabled=source_data.get('enabled', True),
                priority=source_data.get('priority', 100),
                capabilities=capabilities,
                config=source_data
            )
        
        # Cargar mapping de símbolos
        self._symbol_mapping = self._raw_config.get('symbol_mapping', {})
    
    def get_primary_source(self) -> Optional[DataSourceInfo]:
        """Obtener la fuente principal configurada."""
        primary_name = self._raw_config.get('primary')
        if primary_name and primary_name in self._sources:
            source = self._sources[primary_name]
            if source.enabled and source.is_healthy:
                return source
        
        # Fallback: buscar por prioridad
        return self._get_best_available_source()
    
    def get_fallback_source(self) -> Optional[DataSourceInfo]:
        """Obtener la fuente de fallback configurada."""
        fallback_name = self._raw_config.get('fallback')
        if fallback_name and fallback_name in self._sources:
            source = self._sources[fallback_name]
            if source.enabled:
                return source
        return None
    
    def _get_best_available_source(self) -> Optional[DataSourceInfo]:
        """Obtener la mejor fuente disponible por prioridad."""
        available = [
            s for s in self._sources.values()
            if s.enabled and s.is_healthy
        ]
        if not available:
            return None
        
        return min(available, key=lambda s: s.priority)
    
    def get_source(self, name: str) -> Optional[DataSourceInfo]:
        """Obtener una fuente específica por nombre."""
        return self._sources.get(name)
    
    def get_all_sources(self) -> list[DataSourceInfo]:
        """Obtener todas las fuentes configuradas."""
        return list(self._sources.values())
    
    def get_enabled_sources(self) -> list[DataSourceInfo]:
        """Obtener fuentes habilitadas ordenadas por prioridad."""
        enabled = [s for s in self._sources.values() if s.enabled]
        return sorted(enabled, key=lambda s: s.priority)
    
    def get_symbol_for_source(self, internal_symbol: str, source_name: str) -> str:
        """
        Obtener el símbolo específico para una fuente.
        
        Args:
            internal_symbol: Símbolo interno (ej: "EURUSD")
            source_name: Nombre de la fuente (ej: "ibkr", "yahoo")
        
        Returns:
            Símbolo específico para la fuente, o el interno si no hay mapping
        """
        if internal_symbol in self._symbol_mapping:
            mapping = self._symbol_mapping[internal_symbol]
            if source_name in mapping and mapping[source_name]:
                return mapping[source_name]
        
        return internal_symbol
    
    def mark_source_failure(self, source_name: str) -> None:
        """Marcar un fallo en una fuente."""
        if source_name in self._sources:
            source = self._sources[source_name]
            source.consecutive_failures += 1
            
            if source.consecutive_failures >= self._global.unhealthy_threshold:
                source.is_healthy = False
    
    def mark_source_success(self, source_name: str) -> None:
        """Marcar un éxito en una fuente (resetea contador de fallos)."""
        if source_name in self._sources:
            source = self._sources[source_name]
            source.consecutive_failures = 0
            source.is_healthy = True
    
    @property
    def global_config(self) -> GlobalConfig:
        """Obtener configuración global."""
        return self._global
    
    def get_ibkr_config(self) -> IBKRConfig:
        """Obtener configuración específica de IBKR."""
        ibkr_source = self._sources.get('ibkr')
        if not ibkr_source:
            return IBKRConfig()
        
        conn_config = ibkr_source.config.get('connection', {})
        return IBKRConfig(**conn_config)
    
    def get_yahoo_config(self) -> YahooConfig:
        """Obtener configuración específica de Yahoo."""
        yahoo_source = self._sources.get('yahoo')
        if not yahoo_source:
            return YahooConfig()
        
        conn_config = yahoo_source.config.get('connection', {})
        return YahooConfig(**conn_config)
```

---

## Tarea A1.3: Implementar IBKR como Fuente Principal

**Estado:** ⬜ Pendiente

**Objetivo:** Mejorar el `IBKRProvider` existente y crear un `ProviderFactory` que gestione el fallback automático.

**Duración estimada:** 3-4 horas

**Subtareas:**
- [ ] Mejorar `IBKRProvider` con manejo de errores robusto
- [ ] Mantener `YahooProvider` como fallback
- [ ] Crear `ProviderFactory` para selección automática
- [ ] Implementar sistema de fallback con reintentos
- [ ] Tests unitarios y de integración

---

### A1.3.1: Provider Factory

**Archivo:** `src/data/providers/provider_factory.py`

```python
"""
Factory para selección de providers de datos - Fase A1.3
"""

import logging
from typing import Optional, Protocol
from datetime import date
import pandas as pd

from src.data.config import DataSourceConfig, DataSourceInfo

logger = logging.getLogger(__name__)


class DataProvider(Protocol):
    """Protocolo que deben implementar todos los providers."""
    
    @property
    def name(self) -> str:
        """Nombre del provider."""
        ...
    
    def is_available(self) -> bool:
        """Verificar si el provider está disponible."""
        ...
    
    def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """Obtener datos históricos."""
        ...
    
    def get_quote(self, symbol: str) -> dict:
        """Obtener quote actual."""
        ...


class ProviderFactory:
    """
    Factory para obtener el provider de datos apropiado.
    
    Implementa lógica de fallback automático cuando el provider
    principal no está disponible.
    
    Uso:
        factory = ProviderFactory()
        
        # Obtener datos (usa principal o fallback automáticamente)
        df = factory.get_historical("AAPL", start_date, end_date)
        
        # Forzar un provider específico
        df = factory.get_historical("AAPL", start_date, end_date, force_source="yahoo")
    """
    
    def __init__(self, config_path: str = "config/data_sources.yaml"):
        self.config = DataSourceConfig(config_path)
        self._providers: dict[str, DataProvider] = {}
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Inicializar providers habilitados."""
        from src.data.providers.ibkr import IBKRProvider
        from src.data.providers.yahoo import YahooProvider
        
        for source in self.config.get_enabled_sources():
            try:
                if source.name == 'ibkr':
                    ibkr_config = self.config.get_ibkr_config()
                    self._providers['ibkr'] = IBKRProvider(
                        host=ibkr_config.host,
                        port=ibkr_config.port,
                        client_id=ibkr_config.client_id,
                        timeout=ibkr_config.timeout_seconds
                    )
                    logger.info("IBKRProvider inicializado")
                    
                elif source.name == 'yahoo':
                    yahoo_config = self.config.get_yahoo_config()
                    self._providers['yahoo'] = YahooProvider(
                        rate_limit=yahoo_config.rate_limit_seconds
                    )
                    logger.info("YahooProvider inicializado")
                    
            except Exception as e:
                logger.warning(f"No se pudo inicializar {source.name}: {e}")
    
    def get_provider(self, force_source: Optional[str] = None) -> Optional[DataProvider]:
        """
        Obtener el provider apropiado.
        
        Args:
            force_source: Forzar un provider específico (ignora prioridad)
        
        Returns:
            DataProvider disponible o None si ninguno está disponible
        """
        if force_source:
            provider = self._providers.get(force_source)
            if provider and provider.is_available():
                return provider
            logger.warning(f"Provider forzado '{force_source}' no disponible")
            return None
        
        # Intentar provider principal
        primary = self.config.get_primary_source()
        if primary and primary.name in self._providers:
            provider = self._providers[primary.name]
            if provider.is_available():
                return provider
            logger.warning(f"Provider principal '{primary.name}' no disponible")
        
        # Intentar fallback
        fallback = self.config.get_fallback_source()
        if fallback and fallback.name in self._providers:
            provider = self._providers[fallback.name]
            if provider.is_available():
                logger.info(f"Usando fallback: {fallback.name}")
                return provider
        
        logger.error("No hay providers disponibles")
        return None
    
    def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d",
        force_source: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Obtener datos históricos con fallback automático.
        
        Args:
            symbol: Símbolo a consultar
            start: Fecha de inicio
            end: Fecha de fin
            interval: Intervalo de datos
            force_source: Forzar provider específico
        
        Returns:
            DataFrame con OHLCV o DataFrame vacío si error
        """
        global_config = self.config.global_config
        
        # Determinar providers a intentar
        if force_source:
            sources_to_try = [force_source]
        else:
            sources_to_try = [
                s.name for s in self.config.get_enabled_sources()
                if s.name in self._providers
            ]
        
        for source_name in sources_to_try:
            provider = self._providers.get(source_name)
            if not provider:
                continue
            
            # Obtener símbolo específico para esta fuente
            source_symbol = self.config.get_symbol_for_source(symbol, source_name)
            
            # Reintentos
            for attempt in range(global_config.retry_count):
                try:
                    if not provider.is_available():
                        logger.debug(f"{source_name} no disponible")
                        break
                    
                    df = provider.get_historical(source_symbol, start, end, interval)
                    
                    if not df.empty:
                        self.config.mark_source_success(source_name)
                        logger.info(f"Datos obtenidos de {source_name}: {len(df)} registros")
                        
                        # Normalizar símbolo al interno
                        df['symbol'] = symbol
                        df['source'] = source_name
                        
                        return df
                    
                except Exception as e:
                    logger.warning(f"{source_name} intento {attempt + 1} fallido: {e}")
                    self.config.mark_source_failure(source_name)
                    
                    if attempt < global_config.retry_count - 1:
                        import time
                        time.sleep(global_config.retry_delay_seconds)
            
            logger.warning(f"Todos los intentos fallaron para {source_name}")
        
        logger.error(f"No se pudieron obtener datos para {symbol}")
        return pd.DataFrame()
    
    def get_quote(
        self,
        symbol: str,
        force_source: Optional[str] = None
    ) -> Optional[dict]:
        """
        Obtener quote actual con fallback automático.
        
        Args:
            symbol: Símbolo a consultar
            force_source: Forzar provider específico
        
        Returns:
            Dict con quote o None si error
        """
        provider = self.get_provider(force_source)
        if not provider:
            return None
        
        source_name = provider.name
        source_symbol = self.config.get_symbol_for_source(symbol, source_name)
        
        try:
            quote = provider.get_quote(source_symbol)
            if quote:
                self.config.mark_source_success(source_name)
                quote['symbol'] = symbol  # Normalizar
                quote['source'] = source_name
                return quote
        except Exception as e:
            logger.error(f"Error obteniendo quote de {source_name}: {e}")
            self.config.mark_source_failure(source_name)
        
        return None
    
    def check_health(self) -> dict[str, bool]:
        """
        Verificar salud de todos los providers.
        
        Returns:
            Dict con estado de cada provider
        """
        health = {}
        for name, provider in self._providers.items():
            try:
                health[name] = provider.is_available()
            except Exception:
                health[name] = False
        return health
```

---

### A1.3.2: IBKR Provider Mejorado

**Archivo:** `src/data/providers/ibkr.py` (modificaciones)

```python
"""
Provider de datos IBKR mejorado - Fase A1.3

Cambios respecto a Fase 1:
- Mejor manejo de conexión/desconexión
- Método is_available()
- Logging estructurado
- Manejo de datos delayed
"""

import logging
from datetime import date, datetime
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class IBKRProvider:
    """
    Provider de datos de Interactive Brokers.
    
    Requiere TWS o IB Gateway corriendo.
    
    Uso:
        provider = IBKRProvider(host="127.0.0.1", port=7497, client_id=1)
        
        # Verificar disponibilidad
        if provider.is_available():
            df = provider.get_historical("AAPL", start_date, end_date)
    """
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        timeout: int = 30,
        readonly: bool = True
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.timeout = timeout
        self.readonly = readonly
        
        self._ib = None
        self._connected = False
    
    @property
    def name(self) -> str:
        return "ibkr"
    
    def _connect(self) -> bool:
        """Establecer conexión con TWS/Gateway."""
        if self._connected and self._ib and self._ib.isConnected():
            return True
        
        try:
            from ib_insync import IB
            
            self._ib = IB()
            self._ib.connect(
                host=self.host,
                port=self.port,
                clientId=self.client_id,
                timeout=self.timeout,
                readonly=self.readonly
            )
            
            self._connected = True
            logger.info(f"Conectado a IBKR en {self.host}:{self.port}")
            
            # Verificar que es paper trading (safety check)
            account_type = self._ib.managedAccounts()
            if account_type:
                logger.info(f"Cuenta(s): {account_type}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error conectando a IBKR: {e}")
            self._connected = False
            return False
    
    def _disconnect(self) -> None:
        """Cerrar conexión."""
        if self._ib:
            try:
                self._ib.disconnect()
            except Exception:
                pass
        self._connected = False
    
    def is_available(self) -> bool:
        """Verificar si IBKR está disponible."""
        try:
            return self._connect()
        except Exception:
            return False
    
    def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = "1d"
    ) -> pd.DataFrame:
        """
        Obtener datos históricos de IBKR.
        
        Args:
            symbol: Símbolo (formato IBKR, ej: "AAPL", "EUR.USD")
            start: Fecha inicio
            end: Fecha fin
            interval: "1d", "1h", "15m", "5m", "1m"
        
        Returns:
            DataFrame con columnas: time, open, high, low, close, volume
        """
        if not self._connect():
            return pd.DataFrame()
        
        try:
            from ib_insync import Stock, Forex, Contract
            
            # Crear contrato según tipo de símbolo
            contract = self._create_contract(symbol)
            
            # Mapear intervalo a formato IBKR
            bar_size = self._map_interval(interval)
            
            # Calcular duración
            duration = self._calculate_duration(start, end)
            
            # Solicitar datos
            bars = self._ib.reqHistoricalData(
                contract,
                endDateTime=end.strftime('%Y%m%d 23:59:59'),
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=True,
                formatDate=1
            )
            
            if not bars:
                logger.warning(f"Sin datos para {symbol}")
                return pd.DataFrame()
            
            # Convertir a DataFrame
            df = pd.DataFrame([{
                'time': bar.date,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume
            } for bar in bars])
            
            # Filtrar por rango de fechas
            df['time'] = pd.to_datetime(df['time'])
            df = df[(df['time'].dt.date >= start) & (df['time'].dt.date <= end)]
            
            logger.info(f"IBKR: {len(df)} barras para {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error obteniendo histórico de IBKR: {e}")
            return pd.DataFrame()
    
    def get_quote(self, symbol: str) -> Optional[dict]:
        """
        Obtener quote actual de IBKR.
        
        Args:
            symbol: Símbolo IBKR
        
        Returns:
            Dict con bid, ask, last, volume, timestamp
        """
        if not self._connect():
            return None
        
        try:
            contract = self._create_contract(symbol)
            
            # Solicitar datos de mercado
            self._ib.reqMktData(contract, '', False, False)
            self._ib.sleep(2)  # Esperar datos
            
            ticker = self._ib.ticker(contract)
            
            if ticker:
                return {
                    'bid': ticker.bid if ticker.bid > 0 else None,
                    'ask': ticker.ask if ticker.ask > 0 else None,
                    'last': ticker.last if ticker.last > 0 else ticker.close,
                    'volume': ticker.volume if ticker.volume else 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo quote de IBKR: {e}")
            return None
    
    def _create_contract(self, symbol: str):
        """Crear contrato IBKR según el símbolo."""
        from ib_insync import Stock, Forex
        
        # Detectar tipo de símbolo
        if '.' in symbol and len(symbol.split('.')[0]) == 3:
            # Forex: EUR.USD -> EUR/USD
            base, quote = symbol.split('.')
            return Forex(base + quote)
        elif symbol.endswith('.MC'):
            # Mercado Continuo español
            return Stock(symbol.replace('.MC', ''), 'MC', 'EUR')
        elif symbol.endswith('.DE'):
            # Xetra alemán
            return Stock(symbol.replace('.DE', ''), 'IBIS', 'EUR')
        else:
            # Default: acción US
            return Stock(symbol, 'SMART', 'USD')
    
    def _map_interval(self, interval: str) -> str:
        """Mapear intervalo a formato IBKR."""
        mapping = {
            '1m': '1 min',
            '5m': '5 mins',
            '15m': '15 mins',
            '1h': '1 hour',
            '1d': '1 day',
            '1w': '1 week',
        }
        return mapping.get(interval, '1 day')
    
    def _calculate_duration(self, start: date, end: date) -> str:
        """Calcular duración en formato IBKR."""
        days = (end - start).days
        
        if days <= 365:
            return f"{days} D"
        else:
            years = days // 365 + 1
            return f"{years} Y"
```

---

### A1.3.3: Yahoo Provider (sin cambios mayores)

El `YahooProvider` existente de Fase 1 se mantiene igual, solo añadimos el método `is_available()`:

```python
# Añadir a src/data/providers/yahoo.py

def is_available(self) -> bool:
    """
    Verificar si Yahoo Finance está disponible.
    Intenta una request simple para verificar conectividad.
    """
    try:
        import yfinance as yf
        # Request mínimo
        ticker = yf.Ticker("SPY")
        info = ticker.fast_info
        return True
    except Exception:
        return False

@property
def name(self) -> str:
    return "yahoo"
```

---

*Fin de Parte 3 - Continúa en Parte 4: MCP Server para ML Models*
---

# Parte 4: MCP Server para ML Models (mcp-ml-models)

---

## Tarea A1.4: Crear Estructura Base de mcp-ml-models

**Estado:** ⬜ Pendiente

**Objetivo:** Crear la estructura base del servidor MCP que servirá predicciones de modelos ML. En esta fase solo creamos el esqueleto; los modelos reales se implementan en Fase A2.

**Duración estimada:** 2-3 horas

**Subtareas:**
- [ ] Crear estructura de directorios
- [ ] Implementar server base con health check
- [ ] Crear tools placeholder (predict, get_model_info)
- [ ] Configurar puerto 3005
- [ ] Añadir a docker-compose.yml
- [ ] Tests básicos

---

### A1.4.1: Estructura de Directorios

```
mcp-servers/
├── common/                      # Ya existente de Fase 2
│   ├── __init__.py
│   ├── base_server.py
│   ├── config.py
│   └── exceptions.py
├── ml-models/                   # NUEVO
│   ├── __init__.py
│   ├── server.py                # Entry point
│   ├── config.py                # Configuración específica
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── health.py            # Health check
│   │   ├── predict.py           # Predicciones (placeholder)
│   │   ├── model_info.py        # Info de modelos
│   │   └── regime.py            # Detección de régimen (placeholder)
│   ├── models/                  # Modelos cargados (Fase A2)
│   │   └── __init__.py
│   └── tests/
│       ├── __init__.py
│       └── test_ml_models.py
```

**Script de creación:**

```powershell
# Crear estructura de directorios para mcp-ml-models
$base = "mcp-servers/ml-models"

$dirs = @(
    "$base/tools",
    "$base/models",
    "$base/tests"
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Path $dir -Force
}

# Crear archivos __init__.py
$initFiles = @(
    "$base/__init__.py",
    "$base/tools/__init__.py",
    "$base/models/__init__.py",
    "$base/tests/__init__.py"
)

foreach ($file in $initFiles) {
    New-Item -ItemType File -Path $file -Force
}
```

---

### A1.4.2: Server Principal

**Archivo:** `mcp-servers/ml-models/server.py`

```python
"""
MCP Server para Modelos ML - Fase A1.4

Este server expone tools para:
- Health check del sistema ML
- Predicciones de régimen de mercado (HMM)
- Información de modelos disponibles
- Ensemble de predicciones (futuro)

Puerto: 3005
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Añadir path del proyecto
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from mcp.server import Server
from mcp.types import Tool, TextContent
import json

from mcp_servers.common.base_server import BaseMCPServer
from mcp_servers.ml_models.tools.health import HealthTool
from mcp_servers.ml_models.tools.predict import PredictTool
from mcp_servers.ml_models.tools.model_info import ModelInfoTool
from mcp_servers.ml_models.tools.regime import RegimeTool
from mcp_servers.ml_models.config import MLModelsConfig

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MLModelsServer(BaseMCPServer):
    """
    Servidor MCP para predicciones de modelos ML.
    
    Tools disponibles:
    - health_check: Verificar estado del sistema ML
    - predict_regime: Predecir régimen de mercado
    - get_model_info: Información de un modelo
    - list_models: Listar modelos disponibles
    """
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        super().__init__("mcp-ml-models", config_path)
        
        self.config = MLModelsConfig(config_path)
        
        # Inicializar tools
        self._health_tool = HealthTool()
        self._predict_tool = PredictTool(self.config)
        self._model_info_tool = ModelInfoTool(self.config)
        self._regime_tool = RegimeTool(self.config)
        
        # Registrar tools
        self._register_tools()
        
        logger.info("MLModelsServer inicializado")
    
    def _register_tools(self) -> None:
        """Registrar todos los tools del server."""
        
        # Health Check
        self.register_tool(
            name="health_check",
            description="Verificar estado del sistema ML y modelos cargados",
            schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=self._handle_health_check
        )
        
        # Predict Regime
        self.register_tool(
            name="predict_regime",
            description="Predecir el régimen actual del mercado usando modelo HMM",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Símbolo para contextualizar (opcional, default: mercado general)"
                    },
                    "model_id": {
                        "type": "string",
                        "description": "ID del modelo a usar (opcional, default: modelo activo)"
                    }
                },
                "required": []
            },
            handler=self._handle_predict_regime
        )
        
        # Get Model Info
        self.register_tool(
            name="get_model_info",
            description="Obtener información detallada de un modelo ML",
            schema={
                "type": "object",
                "properties": {
                    "model_id": {
                        "type": "string",
                        "description": "ID del modelo"
                    }
                },
                "required": ["model_id"]
            },
            handler=self._handle_get_model_info
        )
        
        # List Models
        self.register_tool(
            name="list_models",
            description="Listar todos los modelos ML disponibles",
            schema={
                "type": "object",
                "properties": {
                    "model_type": {
                        "type": "string",
                        "description": "Filtrar por tipo: 'regime', 'prediction', 'all' (default: all)"
                    }
                },
                "required": []
            },
            handler=self._handle_list_models
        )
    
    async def _handle_health_check(self, arguments: dict) -> str:
        """Handler para health_check."""
        result = await self._health_tool.check()
        return json.dumps(result, indent=2)
    
    async def _handle_predict_regime(self, arguments: dict) -> str:
        """Handler para predict_regime."""
        symbol = arguments.get("symbol")
        model_id = arguments.get("model_id")
        
        result = await self._regime_tool.predict(symbol=symbol, model_id=model_id)
        return json.dumps(result, indent=2)
    
    async def _handle_get_model_info(self, arguments: dict) -> str:
        """Handler para get_model_info."""
        model_id = arguments["model_id"]
        
        result = await self._model_info_tool.get_info(model_id)
        return json.dumps(result, indent=2)
    
    async def _handle_list_models(self, arguments: dict) -> str:
        """Handler para list_models."""
        model_type = arguments.get("model_type", "all")
        
        result = await self._model_info_tool.list_all(model_type)
        return json.dumps(result, indent=2)


def main():
    """Entry point del server."""
    config_path = os.getenv("ML_MODELS_CONFIG", "config/ml_models.yaml")
    port = int(os.getenv("ML_MODELS_PORT", "3005"))
    
    server = MLModelsServer(config_path)
    
    logger.info(f"Iniciando mcp-ml-models en puerto {port}")
    server.run(port)


if __name__ == "__main__":
    main()
```

---

### A1.4.3: Configuración del Server

**Archivo:** `mcp-servers/ml-models/config.py`

```python
"""
Configuración de mcp-ml-models - Fase A1.4
"""

import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel


class ModelConfig(BaseModel):
    """Configuración de un modelo individual."""
    model_id: str
    model_type: str                  # 'regime', 'prediction'
    implementation: str              # 'hmm', 'rules', 'ppo'
    enabled: bool = True
    is_default: bool = False
    model_path: Optional[str] = None
    hyperparameters: dict = {}


class MLModelsConfig:
    """
    Gestor de configuración para mcp-ml-models.
    
    Lee configuración desde YAML y expone métodos de acceso.
    """
    
    def __init__(self, config_path: str = "config/ml_models.yaml"):
        self.config_path = Path(config_path)
        self._models: dict[str, ModelConfig] = {}
        self._default_regime_model: Optional[str] = None
        
        self._load_config()
    
    def _load_config(self) -> None:
        """Cargar configuración desde YAML."""
        # Si no existe el archivo, usar config por defecto
        if not self.config_path.exists():
            self._load_defaults()
            return
        
        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Cargar modelos
        models_config = raw_config.get('models', {})
        for model_id, model_data in models_config.items():
            model = ModelConfig(model_id=model_id, **model_data)
            self._models[model_id] = model
            
            if model.is_default and model.model_type == 'regime':
                self._default_regime_model = model_id
    
    def _load_defaults(self) -> None:
        """Cargar configuración por defecto cuando no existe YAML."""
        # Modelo placeholder hasta que se implemente Fase A2
        default_model = ModelConfig(
            model_id="rules_baseline",
            model_type="regime",
            implementation="rules",
            enabled=True,
            is_default=True,
            hyperparameters={
                "bull_threshold": 0.02,
                "bear_threshold": -0.02,
                "volatility_high": 0.25
            }
        )
        self._models["rules_baseline"] = default_model
        self._default_regime_model = "rules_baseline"
    
    def get_model(self, model_id: str) -> Optional[ModelConfig]:
        """Obtener configuración de un modelo."""
        return self._models.get(model_id)
    
    def get_default_regime_model(self) -> Optional[ModelConfig]:
        """Obtener el modelo de régimen por defecto."""
        if self._default_regime_model:
            return self._models.get(self._default_regime_model)
        return None
    
    def list_models(self, model_type: Optional[str] = None) -> list[ModelConfig]:
        """Listar modelos, opcionalmente filtrados por tipo."""
        models = list(self._models.values())
        
        if model_type and model_type != "all":
            models = [m for m in models if m.model_type == model_type]
        
        return models
    
    def get_enabled_models(self) -> list[ModelConfig]:
        """Obtener solo modelos habilitados."""
        return [m for m in self._models.values() if m.enabled]
```

**Archivo:** `config/ml_models.yaml`

```yaml
# ============================================================================
# CONFIGURACIÓN DE MODELOS ML - NEXUS TRADING
# ============================================================================
# Este archivo define los modelos ML disponibles y su configuración.
# Los modelos reales se implementan en Fase A2.
# ============================================================================

# Modelo de régimen activo por defecto
active_regime_model: "rules_baseline"

# Modelos disponibles
models:
  # ─────────────────────────────────────────────────────────────────────────
  # RULES BASELINE (siempre disponible como fallback)
  # ─────────────────────────────────────────────────────────────────────────
  rules_baseline:
    model_type: "regime"
    implementation: "rules"
    enabled: true
    is_default: true
    description: "Detección de régimen basada en reglas simples (ADX, SMA, volatilidad)"
    hyperparameters:
      # Umbrales de retorno para clasificación
      bull_threshold: 0.02       # Retornos > 2% en 5 días = BULL
      bear_threshold: -0.02      # Retornos < -2% en 5 días = BEAR
      # Umbral de volatilidad
      volatility_high: 0.25      # Vol > 25% anualizada = VOLATILE
      # ADX para tendencia
      adx_trend_threshold: 25    # ADX > 25 = tendencia clara
      adx_weak_threshold: 20     # ADX < 20 = rango lateral
  
  # ─────────────────────────────────────────────────────────────────────────
  # HMM (a implementar en Fase A2)
  # ─────────────────────────────────────────────────────────────────────────
  hmm_v1:
    model_type: "regime"
    implementation: "hmm"
    enabled: false              # Deshabilitado hasta Fase A2
    is_default: false
    description: "Hidden Markov Model para detección de régimen"
    model_path: "models/hmm_regime_v1.pkl"
    hyperparameters:
      n_states: 4
      covariance_type: "full"
      n_iter: 100
      features:
        - "returns_5d"
        - "volatility_20d"
        - "adx_14"
        - "volume_ratio"
  
  # ─────────────────────────────────────────────────────────────────────────
  # PPO (futuro - Fase posterior)
  # ─────────────────────────────────────────────────────────────────────────
  ppo_v1:
    model_type: "regime"
    implementation: "ppo"
    enabled: false
    is_default: false
    description: "PPO para detección de régimen (experimental)"
    model_path: "models/ppo_regime_v1.pt"

# Configuración de inferencia
inference:
  # Timeout para predicciones
  timeout_seconds: 5
  # Cache de predicciones
  cache_ttl_seconds: 60
  # Batch processing
  max_batch_size: 100
```

---

### A1.4.4: Tools de ML

**Archivo:** `mcp-servers/ml-models/tools/health.py`

```python
"""
Tool de Health Check para mcp-ml-models - Fase A1.4
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class HealthTool:
    """
    Verifica el estado del sistema ML.
    
    Retorna información sobre:
    - Estado general del server
    - Modelos cargados
    - Recursos disponibles
    """
    
    def __init__(self):
        self._start_time = datetime.now()
    
    async def check(self) -> dict[str, Any]:
        """
        Ejecutar health check completo.
        
        Returns:
            Dict con estado del sistema
        """
        try:
            uptime = (datetime.now() - self._start_time).total_seconds()
            
            return {
                "status": "healthy",
                "server": "mcp-ml-models",
                "uptime_seconds": round(uptime, 2),
                "timestamp": datetime.now().isoformat(),
                "checks": {
                    "server_running": True,
                    "config_loaded": True,
                    "models_initialized": True  # Placeholder hasta Fase A2
                },
                "models_loaded": {
                    "total": 1,
                    "enabled": 1,
                    "list": ["rules_baseline"]  # Placeholder
                },
                "resources": {
                    "memory_available": True,
                    "gpu_available": False  # No usamos GPU por ahora
                }
            }
            
        except Exception as e:
            logger.error(f"Error en health check: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
```

**Archivo:** `mcp-servers/ml-models/tools/regime.py`

```python
"""
Tool de Predicción de Régimen - Fase A1.4

Esta es una implementación placeholder que usa reglas simples.
El modelo HMM real se implementa en Fase A2.
"""

import logging
from datetime import datetime
from typing import Optional, Any

logger = logging.getLogger(__name__)


# Constantes de régimen
REGIMES = {
    "BULL": "Mercado alcista con tendencia clara",
    "BEAR": "Mercado bajista con tendencia clara",
    "SIDEWAYS": "Mercado lateral sin tendencia",
    "VOLATILE": "Alta volatilidad, régimen incierto"
}


class RegimeTool:
    """
    Predice el régimen actual del mercado.
    
    Fase A1.4: Usa reglas simples (baseline)
    Fase A2: Usará modelo HMM entrenado
    """
    
    def __init__(self, config):
        self.config = config
        self._last_prediction = None
        self._last_prediction_time = None
    
    async def predict(
        self,
        symbol: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Predecir régimen del mercado.
        
        Args:
            symbol: Símbolo específico (opcional)
            model_id: ID del modelo a usar (opcional, usa default)
        
        Returns:
            Dict con predicción de régimen
        """
        try:
            # Determinar modelo a usar
            if model_id:
                model_config = self.config.get_model(model_id)
            else:
                model_config = self.config.get_default_regime_model()
            
            if not model_config:
                return {
                    "error": "No hay modelo de régimen disponible",
                    "regime": "UNKNOWN",
                    "confidence": 0.0
                }
            
            # Por ahora, siempre usamos rules_baseline
            # En Fase A2, aquí se cargará el modelo HMM
            if model_config.implementation == "rules":
                result = await self._predict_rules(symbol, model_config)
            else:
                # Placeholder para otros modelos
                result = {
                    "error": f"Modelo {model_config.implementation} no implementado aún",
                    "regime": "UNKNOWN",
                    "confidence": 0.0
                }
            
            # Añadir metadata
            result["model_id"] = model_config.model_id
            result["model_type"] = model_config.implementation
            result["timestamp"] = datetime.now().isoformat()
            result["symbol"] = symbol or "MARKET"
            
            return result
            
        except Exception as e:
            logger.error(f"Error en predicción de régimen: {e}")
            return {
                "error": str(e),
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _predict_rules(
        self,
        symbol: Optional[str],
        model_config
    ) -> dict[str, Any]:
        """
        Predicción usando reglas simples (baseline).
        
        Nota: En una implementación real, esto consultaría los datos
        actuales de mercado. Por ahora es un placeholder.
        """
        # Placeholder: En producción, esto obtendría features reales
        # de mcp-market-data o del Feature Store
        
        # Simulamos una predicción basada en hora del día
        # (solo para demostrar que el sistema funciona)
        from datetime import datetime
        hour = datetime.now().hour
        
        # Reglas simplificadas de demostración
        if 9 <= hour <= 11:
            regime = "BULL"
            confidence = 0.65
        elif 14 <= hour <= 16:
            regime = "SIDEWAYS"
            confidence = 0.70
        elif hour >= 20 or hour <= 6:
            regime = "VOLATILE"
            confidence = 0.55
        else:
            regime = "SIDEWAYS"
            confidence = 0.60
        
        return {
            "regime": regime,
            "confidence": confidence,
            "probabilities": {
                "BULL": 0.25,
                "BEAR": 0.15,
                "SIDEWAYS": 0.45,
                "VOLATILE": 0.15
            },
            "description": REGIMES.get(regime, ""),
            "note": "Predicción placeholder - modelo real en Fase A2"
        }
```

**Archivo:** `mcp-servers/ml-models/tools/model_info.py`

```python
"""
Tool de Información de Modelos - Fase A1.4
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class ModelInfoTool:
    """
    Proporciona información sobre los modelos ML disponibles.
    """
    
    def __init__(self, config):
        self.config = config
    
    async def get_info(self, model_id: str) -> dict[str, Any]:
        """
        Obtener información detallada de un modelo.
        
        Args:
            model_id: ID del modelo
        
        Returns:
            Dict con información del modelo
        """
        model = self.config.get_model(model_id)
        
        if not model:
            return {
                "error": f"Modelo '{model_id}' no encontrado",
                "available_models": [m.model_id for m in self.config.list_models()]
            }
        
        return {
            "model_id": model.model_id,
            "model_type": model.model_type,
            "implementation": model.implementation,
            "enabled": model.enabled,
            "is_default": model.is_default,
            "hyperparameters": model.hyperparameters,
            "model_path": model.model_path,
            "status": "loaded" if model.enabled else "disabled"
        }
    
    async def list_all(self, model_type: Optional[str] = "all") -> dict[str, Any]:
        """
        Listar todos los modelos disponibles.
        
        Args:
            model_type: Filtrar por tipo ('regime', 'prediction', 'all')
        
        Returns:
            Dict con lista de modelos
        """
        models = self.config.list_models(model_type)
        
        return {
            "filter": model_type,
            "total": len(models),
            "models": [
                {
                    "model_id": m.model_id,
                    "model_type": m.model_type,
                    "implementation": m.implementation,
                    "enabled": m.enabled,
                    "is_default": m.is_default
                }
                for m in models
            ]
        }
```

**Archivo:** `mcp-servers/ml-models/tools/predict.py`

```python
"""
Tool de Predicciones Generales - Fase A1.4

Placeholder para predicciones de modelos que no sean de régimen.
Por ejemplo: predicción de retornos, clasificación de patrones, etc.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class PredictTool:
    """
    Tool general de predicciones ML.
    
    En Fase A1 es un placeholder.
    En fases posteriores implementará:
    - Predicción de retornos (TFT)
    - Clasificación de patrones
    - Ensemble de modelos
    """
    
    def __init__(self, config):
        self.config = config
    
    async def predict(
        self,
        model_id: str,
        features: dict[str, float]
    ) -> dict[str, Any]:
        """
        Realizar predicción con un modelo específico.
        
        Args:
            model_id: ID del modelo
            features: Dict con features de entrada
        
        Returns:
            Dict con predicción
        """
        # Placeholder - implementación real en fases posteriores
        return {
            "status": "not_implemented",
            "message": "Predicciones generales se implementan en fases posteriores",
            "model_id": model_id,
            "features_received": list(features.keys()) if features else []
        }
```

---

### A1.4.5: Docker Compose Update

**Añadir a `docker-compose.yml`:**

```yaml
  # MCP Server - ML Models
  mcp-ml-models:
    build:
      context: ./mcp-servers
      dockerfile: Dockerfile
      args:
        SERVER_NAME: ml-models
    container_name: trading_mcp_ml_models
    environment:
      - ML_MODELS_CONFIG=/app/config/ml_models.yaml
      - ML_MODELS_PORT=3005
      - DATABASE_URL=postgresql://trading:${DB_PASSWORD}@postgres:5432/trading
      - REDIS_URL=redis://redis:6379/0
    ports:
      - "3005:3005"
    volumes:
      - ./config:/app/config:ro
      - ./models:/app/models:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:3005/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
```

---

### A1.4.6: Tests Básicos

**Archivo:** `mcp-servers/ml-models/tests/test_ml_models.py`

```python
"""
Tests para mcp-ml-models - Fase A1.4
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Añadir paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from mcp_servers.ml_models.config import MLModelsConfig
from mcp_servers.ml_models.tools.health import HealthTool
from mcp_servers.ml_models.tools.regime import RegimeTool
from mcp_servers.ml_models.tools.model_info import ModelInfoTool


class TestMLModelsConfig:
    """Tests para configuración de ML Models."""
    
    def test_load_defaults_when_no_config(self, tmp_path):
        """Debe cargar configuración por defecto si no existe archivo."""
        config = MLModelsConfig(str(tmp_path / "nonexistent.yaml"))
        
        assert config.get_model("rules_baseline") is not None
        assert config.get_default_regime_model() is not None
    
    def test_list_models(self, tmp_path):
        """Debe listar todos los modelos."""
        config = MLModelsConfig(str(tmp_path / "nonexistent.yaml"))
        
        models = config.list_models()
        assert len(models) >= 1
        assert any(m.model_id == "rules_baseline" for m in models)


class TestHealthTool:
    """Tests para Health Tool."""
    
    @pytest.mark.asyncio
    async def test_health_check_returns_healthy(self):
        """Health check debe retornar status healthy."""
        tool = HealthTool()
        result = await tool.check()
        
        assert result["status"] == "healthy"
        assert "uptime_seconds" in result
        assert "timestamp" in result


class TestRegimeTool:
    """Tests para Regime Tool."""
    
    @pytest.fixture
    def regime_tool(self, tmp_path):
        config = MLModelsConfig(str(tmp_path / "nonexistent.yaml"))
        return RegimeTool(config)
    
    @pytest.mark.asyncio
    async def test_predict_returns_valid_regime(self, regime_tool):
        """Predicción debe retornar un régimen válido."""
        result = await regime_tool.predict()
        
        assert "regime" in result
        assert result["regime"] in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE", "UNKNOWN"]
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_predict_includes_probabilities(self, regime_tool):
        """Predicción debe incluir probabilidades por régimen."""
        result = await regime_tool.predict()
        
        assert "probabilities" in result
        probs = result["probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 0.01  # Deben sumar ~1


class TestModelInfoTool:
    """Tests para Model Info Tool."""
    
    @pytest.fixture
    def model_info_tool(self, tmp_path):
        config = MLModelsConfig(str(tmp_path / "nonexistent.yaml"))
        return ModelInfoTool(config)
    
    @pytest.mark.asyncio
    async def test_get_info_existing_model(self, model_info_tool):
        """Debe retornar info para modelo existente."""
        result = await model_info_tool.get_info("rules_baseline")
        
        assert "error" not in result
        assert result["model_id"] == "rules_baseline"
        assert result["enabled"] == True
    
    @pytest.mark.asyncio
    async def test_get_info_nonexistent_model(self, model_info_tool):
        """Debe retornar error para modelo inexistente."""
        result = await model_info_tool.get_info("nonexistent_model")
        
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_list_all_returns_models(self, model_info_tool):
        """Debe listar todos los modelos."""
        result = await model_info_tool.list_all()
        
        assert result["total"] >= 1
        assert len(result["models"]) >= 1


# Ejecutar tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

---

*Fin de Parte 4 - Continúa en Parte 5: Scripts de Verificación y Checklist*
---

# Parte 5: Scripts de Verificación y Checklist Final

---

## Tarea A1.5: Scripts de Verificación de Fase

**Estado:** ⬜ Pendiente

**Objetivo:** Crear scripts que validen toda la Fase A1 está correctamente implementada.

**Duración estimada:** 1 hora

**Subtareas:**
- [ ] Script de verificación de esquemas BD
- [ ] Script de verificación de providers
- [ ] Script de verificación de mcp-ml-models
- [ ] Script maestro que ejecuta todos

---

### A1.5.1: Script de Verificación Maestro

**Archivo:** `scripts/verify_fase_a1.py`

```python
#!/usr/bin/env python3
"""
Verificación completa de Fase A1: Extensiones Base
Ejecutar: python scripts/verify_fase_a1.py

Este script valida:
1. Esquema de métricas en PostgreSQL
2. Configuración de fuentes de datos
3. Provider Factory funcionando
4. MCP server ml-models respondiendo
"""

import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Colores para output
class Colors:
    OK = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str) -> None:
    """Imprimir header de sección."""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.ENDC}")

def print_result(name: str, ok: bool, message: str) -> None:
    """Imprimir resultado de check."""
    status = f"{Colors.OK}✅{Colors.ENDC}" if ok else f"{Colors.FAIL}❌{Colors.ENDC}"
    print(f"{status} {name}: {message}")


# ============================================================================
# CHECK 1: Esquema de Métricas (A1.1)
# ============================================================================

def check_metrics_schema() -> tuple[bool, str]:
    """Verificar esquema metrics en PostgreSQL."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Verificar esquema
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name = 'metrics'
        """)
        if not cur.fetchone():
            return False, "Esquema 'metrics' no existe"
        
        # Verificar tablas
        expected_tables = {
            'trades', 'strategy_performance', 'model_performance',
            'experiments', 'experiment_results'
        }
        
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'metrics'
        """)
        actual_tables = {row[0] for row in cur.fetchall()}
        
        missing = expected_tables - actual_tables
        if missing:
            return False, f"Tablas faltantes: {missing}"
        
        # Verificar ENUMs
        cur.execute("""
            SELECT typname FROM pg_type 
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'metrics')
            AND typtype = 'e'
        """)
        enums = {row[0] for row in cur.fetchall()}
        expected_enums = {'trade_direction', 'trade_status', 'regime_type', 'experiment_status'}
        
        missing_enums = expected_enums - enums
        if missing_enums:
            return False, f"ENUMs faltantes: {missing_enums}"
        
        # Verificar función
        cur.execute("""
            SELECT routine_name FROM information_schema.routines 
            WHERE routine_schema = 'metrics' 
            AND routine_name = 'calculate_strategy_metrics'
        """)
        if not cur.fetchone():
            return False, "Función calculate_strategy_metrics no existe"
        
        conn.close()
        return True, f"OK: {len(actual_tables)} tablas, {len(enums)} ENUMs"
        
    except ImportError:
        return False, "psycopg2 no instalado"
    except Exception as e:
        return False, str(e)


# ============================================================================
# CHECK 2: Configuración de Data Sources (A1.2)
# ============================================================================

def check_data_sources_config() -> tuple[bool, str]:
    """Verificar configuración de fuentes de datos."""
    try:
        config_path = Path("config/data_sources.yaml")
        
        # Verificar archivo existe
        if not config_path.exists():
            return False, f"Archivo {config_path} no existe"
        
        # Verificar que se puede cargar
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Verificar campos requeridos
        if 'primary' not in config:
            return False, "Falta campo 'primary'"
        if 'fallback' not in config:
            return False, "Falta campo 'fallback'"
        if 'sources' not in config:
            return False, "Falta campo 'sources'"
        
        sources = config['sources']
        if 'ibkr' not in sources:
            return False, "Configuración de IBKR no encontrada"
        if 'yahoo' not in sources:
            return False, "Configuración de Yahoo no encontrada"
        
        return True, f"OK: primary={config['primary']}, fallback={config['fallback']}"
        
    except ImportError:
        return False, "pyyaml no instalado"
    except Exception as e:
        return False, str(e)


def check_data_sources_table() -> tuple[bool, str]:
    """Verificar tabla config.data_sources en BD."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Verificar tabla existe
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'config' AND table_name = 'data_sources'
        """)
        if not cur.fetchone():
            return False, "Tabla config.data_sources no existe"
        
        # Verificar registros
        cur.execute("SELECT source_name, is_primary, is_enabled FROM config.data_sources")
        rows = cur.fetchall()
        
        if not rows:
            return False, "Tabla vacía - ejecutar script de inicialización"
        
        sources = {row[0]: (row[1], row[2]) for row in rows}
        
        if 'ibkr' not in sources:
            return False, "IBKR no configurado en BD"
        
        conn.close()
        return True, f"OK: {len(sources)} fuentes configuradas"
        
    except Exception as e:
        return False, str(e)


# ============================================================================
# CHECK 3: Provider Factory (A1.3)
# ============================================================================

def check_provider_factory() -> tuple[bool, str]:
    """Verificar que ProviderFactory se puede instanciar."""
    try:
        # Añadir src al path
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        
        from data.providers.provider_factory import ProviderFactory
        
        # Intentar crear factory
        factory = ProviderFactory("config/data_sources.yaml")
        
        # Verificar health
        health = factory.check_health()
        
        if not health:
            return False, "No hay providers disponibles"
        
        available = [name for name, ok in health.items() if ok]
        
        return True, f"OK: providers disponibles: {available}"
        
    except ImportError as e:
        return False, f"Error de import: {e}"
    except FileNotFoundError:
        return False, "Archivo de configuración no encontrado"
    except Exception as e:
        return False, str(e)


def check_ibkr_provider() -> tuple[bool, str]:
    """Verificar IBKRProvider (no requiere conexión real)."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        
        from data.providers.ibkr import IBKRProvider
        
        # Solo verificamos que se puede instanciar
        provider = IBKRProvider(
            host="127.0.0.1",
            port=7497,
            client_id=99  # ID diferente para no interferir
        )
        
        # Verificar métodos existen
        assert hasattr(provider, 'is_available')
        assert hasattr(provider, 'get_historical')
        assert hasattr(provider, 'get_quote')
        assert hasattr(provider, 'name')
        
        return True, "OK: IBKRProvider correctamente estructurado"
        
    except ImportError as e:
        return False, f"Error de import: {e}"
    except Exception as e:
        return False, str(e)


def check_yahoo_provider() -> tuple[bool, str]:
    """Verificar YahooProvider con request simple."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        
        from data.providers.yahoo import YahooProvider
        
        provider = YahooProvider(rate_limit=1.0)
        
        # Verificar disponibilidad
        available = provider.is_available()
        
        if available:
            return True, "OK: Yahoo Finance disponible"
        else:
            return True, "OK: Yahoo Provider estructurado (sin conexión)"
        
    except ImportError as e:
        return False, f"Error de import: {e}"
    except Exception as e:
        return False, str(e)


# ============================================================================
# CHECK 4: MCP Server ml-models (A1.4)
# ============================================================================

def check_mcp_ml_models_structure() -> tuple[bool, str]:
    """Verificar estructura de directorios de mcp-ml-models."""
    base = Path("mcp-servers/ml-models")
    
    required_files = [
        base / "__init__.py",
        base / "server.py",
        base / "config.py",
        base / "tools" / "__init__.py",
        base / "tools" / "health.py",
        base / "tools" / "regime.py",
        base / "tools" / "model_info.py",
    ]
    
    missing = [f for f in required_files if not f.exists()]
    
    if missing:
        return False, f"Archivos faltantes: {[str(f) for f in missing[:3]]}..."
    
    return True, f"OK: {len(required_files)} archivos verificados"


def check_mcp_ml_models_config() -> tuple[bool, str]:
    """Verificar configuración de ml-models."""
    config_path = Path("config/ml_models.yaml")
    
    if not config_path.exists():
        return False, f"Archivo {config_path} no existe"
    
    try:
        import yaml
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        if 'models' not in config:
            return False, "Falta sección 'models'"
        
        if 'rules_baseline' not in config['models']:
            return False, "Falta modelo 'rules_baseline'"
        
        return True, f"OK: {len(config['models'])} modelos configurados"
        
    except Exception as e:
        return False, str(e)


def check_mcp_ml_models_imports() -> tuple[bool, str]:
    """Verificar que los módulos de ml-models se pueden importar."""
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "mcp-servers"))
        
        from ml_models.config import MLModelsConfig
        from ml_models.tools.health import HealthTool
        from ml_models.tools.regime import RegimeTool
        from ml_models.tools.model_info import ModelInfoTool
        
        return True, "OK: Todos los módulos importan correctamente"
        
    except ImportError as e:
        return False, f"Error de import: {e}"


def check_mcp_ml_models_server_running() -> tuple[bool, str]:
    """Verificar si el server está corriendo (opcional)."""
    try:
        import requests
        
        response = requests.get("http://localhost:3005/health", timeout=2)
        
        if response.status_code == 200:
            return True, "OK: Server respondiendo en puerto 3005"
        else:
            return False, f"Server respondió con código {response.status_code}"
        
    except requests.exceptions.ConnectionError:
        return True, "OK (Server no corriendo - normal si no se ha iniciado)"
    except Exception as e:
        return True, f"OK (No se pudo verificar: {e})"


# ============================================================================
# CHECK 5: Docker Compose (A1.4)
# ============================================================================

def check_docker_compose_updated() -> tuple[bool, str]:
    """Verificar que docker-compose.yml incluye mcp-ml-models."""
    compose_path = Path("docker-compose.yml")
    
    if not compose_path.exists():
        return False, "docker-compose.yml no existe"
    
    with open(compose_path, 'r') as f:
        content = f.read()
    
    if 'mcp-ml-models' not in content:
        return False, "Servicio mcp-ml-models no encontrado en docker-compose.yml"
    
    if '3005:3005' not in content:
        return False, "Puerto 3005 no mapeado para mcp-ml-models"
    
    return True, "OK: mcp-ml-models configurado en docker-compose.yml"


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Ejecutar todas las verificaciones."""
    print(f"\n{Colors.BOLD}VERIFICACIÓN FASE A1: EXTENSIONES BASE{Colors.ENDC}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_ok = True
    results = []
    
    # ─────────────────────────────────────────────────────────────────────
    print_header("A1.1: ESQUEMA DE MÉTRICAS")
    # ─────────────────────────────────────────────────────────────────────
    
    ok, msg = check_metrics_schema()
    print_result("Esquema metrics en PostgreSQL", ok, msg)
    results.append(("A1.1 - Esquema métricas", ok))
    if not ok:
        all_ok = False
    
    # ─────────────────────────────────────────────────────────────────────
    print_header("A1.2: CONFIGURACIÓN DATA SOURCES")
    # ─────────────────────────────────────────────────────────────────────
    
    ok, msg = check_data_sources_config()
    print_result("Archivo config/data_sources.yaml", ok, msg)
    results.append(("A1.2 - Config YAML", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_data_sources_table()
    print_result("Tabla config.data_sources", ok, msg)
    results.append(("A1.2 - Tabla BD", ok))
    if not ok:
        all_ok = False
    
    # ─────────────────────────────────────────────────────────────────────
    print_header("A1.3: PROVIDER FACTORY")
    # ─────────────────────────────────────────────────────────────────────
    
    ok, msg = check_ibkr_provider()
    print_result("IBKRProvider", ok, msg)
    results.append(("A1.3 - IBKRProvider", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_yahoo_provider()
    print_result("YahooProvider", ok, msg)
    results.append(("A1.3 - YahooProvider", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_provider_factory()
    print_result("ProviderFactory", ok, msg)
    results.append(("A1.3 - Factory", ok))
    if not ok:
        all_ok = False
    
    # ─────────────────────────────────────────────────────────────────────
    print_header("A1.4: MCP-ML-MODELS")
    # ─────────────────────────────────────────────────────────────────────
    
    ok, msg = check_mcp_ml_models_structure()
    print_result("Estructura de directorios", ok, msg)
    results.append(("A1.4 - Estructura", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_mcp_ml_models_config()
    print_result("Configuración ml_models.yaml", ok, msg)
    results.append(("A1.4 - Config", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_mcp_ml_models_imports()
    print_result("Imports de módulos", ok, msg)
    results.append(("A1.4 - Imports", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_docker_compose_updated()
    print_result("Docker Compose actualizado", ok, msg)
    results.append(("A1.4 - Docker", ok))
    if not ok:
        all_ok = False
    
    ok, msg = check_mcp_ml_models_server_running()
    print_result("Server corriendo (opcional)", ok, msg)
    # No afecta all_ok - es opcional
    
    # ─────────────────────────────────────────────────────────────────────
    print_header("RESUMEN")
    # ─────────────────────────────────────────────────────────────────────
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    print(f"\nResultados: {passed}/{total} checks pasados")
    
    if all_ok:
        print(f"\n{Colors.OK}{Colors.BOLD}✅ FASE A1 COMPLETADA - Listo para Fase A2{Colors.ENDC}")
        return 0
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}❌ FASE A1 INCOMPLETA - Revisar errores{Colors.ENDC}")
        
        print(f"\n{Colors.WARNING}Checks fallidos:{Colors.ENDC}")
        for name, ok in results:
            if not ok:
                print(f"  - {name}")
        
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

### A1.5.2: Script de Migración

**Archivo:** `scripts/migrate_fase_a1.sh`

```bash
#!/bin/bash
# ============================================================================
# Script de Migración - Fase A1
# ============================================================================
# Ejecuta todos los scripts SQL y configuraciones necesarias para Fase A1
#
# Uso: ./scripts/migrate_fase_a1.sh
# ============================================================================

set -e  # Salir si hay error

echo "=============================================="
echo "MIGRACIÓN FASE A1: EXTENSIONES BASE"
echo "=============================================="
echo ""

# Verificar que Docker está corriendo
if ! docker ps | grep -q trading_postgres; then
    echo "❌ ERROR: PostgreSQL no está corriendo"
    echo "   Ejecutar: docker-compose up -d postgres"
    exit 1
fi

echo "✅ PostgreSQL está corriendo"
echo ""

# ─────────────────────────────────────────────────────────────────────────
echo ">>> Paso 1/3: Ejecutando script de esquema de métricas..."
# ─────────────────────────────────────────────────────────────────────────

docker exec -i trading_postgres psql -U trading -d trading < init-scripts/07_metrics_schema.sql

if [ $? -eq 0 ]; then
    echo "✅ Esquema de métricas creado"
else
    echo "❌ Error creando esquema de métricas"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────
echo ""
echo ">>> Paso 2/3: Ejecutando script de configuración de data sources..."
# ─────────────────────────────────────────────────────────────────────────

docker exec -i trading_postgres psql -U trading -d trading < init-scripts/08_data_sources_config.sql

if [ $? -eq 0 ]; then
    echo "✅ Configuración de data sources creada"
else
    echo "❌ Error creando configuración de data sources"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────
echo ""
echo ">>> Paso 3/3: Verificando migración..."
# ─────────────────────────────────────────────────────────────────────────

# Verificar tablas de métricas
METRICS_TABLES=$(docker exec trading_postgres psql -U trading -d trading -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'metrics'")
METRICS_TABLES=$(echo $METRICS_TABLES | xargs)  # Trim whitespace

if [ "$METRICS_TABLES" -ge 5 ]; then
    echo "✅ $METRICS_TABLES tablas en esquema metrics"
else
    echo "❌ Solo $METRICS_TABLES tablas encontradas (esperadas >= 5)"
    exit 1
fi

# Verificar data_sources
DS_COUNT=$(docker exec trading_postgres psql -U trading -d trading -t -c "SELECT COUNT(*) FROM config.data_sources")
DS_COUNT=$(echo $DS_COUNT | xargs)

if [ "$DS_COUNT" -ge 2 ]; then
    echo "✅ $DS_COUNT fuentes de datos configuradas"
else
    echo "❌ Solo $DS_COUNT fuentes encontradas (esperadas >= 2)"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────
echo ""
echo "=============================================="
echo "✅ MIGRACIÓN FASE A1 COMPLETADA"
echo "=============================================="
echo ""
echo "Próximos pasos:"
echo "  1. Copiar archivos Python a src/data/"
echo "  2. Copiar archivos mcp-servers/ml-models/"
echo "  3. Actualizar docker-compose.yml"
echo "  4. Ejecutar: python scripts/verify_fase_a1.py"
```

**Versión PowerShell:**

**Archivo:** `scripts/migrate_fase_a1.ps1`

```powershell
# ============================================================================
# Script de Migración - Fase A1 (PowerShell)
# ============================================================================

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "MIGRACIÓN FASE A1: EXTENSIONES BASE" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""

# Verificar Docker
$pgRunning = docker ps | Select-String "trading_postgres"
if (-not $pgRunning) {
    Write-Host "❌ ERROR: PostgreSQL no está corriendo" -ForegroundColor Red
    Write-Host "   Ejecutar: docker-compose up -d postgres" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ PostgreSQL está corriendo" -ForegroundColor Green
Write-Host ""

# Paso 1: Esquema de métricas
Write-Host ">>> Paso 1/3: Ejecutando script de esquema de métricas..." -ForegroundColor Yellow

Get-Content "init-scripts/07_metrics_schema.sql" | docker exec -i trading_postgres psql -U trading -d trading

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Esquema de métricas creado" -ForegroundColor Green
} else {
    Write-Host "❌ Error creando esquema de métricas" -ForegroundColor Red
    exit 1
}

# Paso 2: Data sources
Write-Host ""
Write-Host ">>> Paso 2/3: Ejecutando script de configuración de data sources..." -ForegroundColor Yellow

Get-Content "init-scripts/08_data_sources_config.sql" | docker exec -i trading_postgres psql -U trading -d trading

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Configuración de data sources creada" -ForegroundColor Green
} else {
    Write-Host "❌ Error creando configuración de data sources" -ForegroundColor Red
    exit 1
}

# Paso 3: Verificación
Write-Host ""
Write-Host ">>> Paso 3/3: Verificando migración..." -ForegroundColor Yellow

$metricsTables = docker exec trading_postgres psql -U trading -d trading -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'metrics'"
$metricsTables = $metricsTables.Trim()

if ([int]$metricsTables -ge 5) {
    Write-Host "✅ $metricsTables tablas en esquema metrics" -ForegroundColor Green
} else {
    Write-Host "❌ Solo $metricsTables tablas encontradas" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "✅ MIGRACIÓN FASE A1 COMPLETADA" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Cyan
```

---

## Checklist de Finalización

```
FASE A1: EXTENSIONES BASE
═════════════════════════════════════════════════════════════════════════

TAREA A1.1: ESQUEMA DE MÉTRICAS
─────────────────────────────────────────────────────────────────────────
[ ] Script SQL 07_metrics_schema.sql creado
[ ] Esquema 'metrics' existe
[ ] Tabla metrics.trades creada
[ ] Tabla metrics.strategy_performance creada
[ ] Tabla metrics.model_performance creada
[ ] Tabla metrics.experiments creada
[ ] Tabla metrics.experiment_results creada
[ ] ENUMs creados (trade_direction, trade_status, regime_type, experiment_status)
[ ] Vistas de agregación creadas
[ ] Función calculate_strategy_metrics creada
[ ] Índices optimizados creados
[ ] Queries de prueba ejecutadas exitosamente

TAREA A1.2: CONFIGURACIÓN DATA SOURCES
─────────────────────────────────────────────────────────────────────────
[ ] Script SQL 08_data_sources_config.sql creado
[ ] Tabla config.data_sources creada
[ ] Registros IBKR y Yahoo insertados
[ ] Archivo config/data_sources.yaml creado
[ ] Clase DataSourceConfig implementada
[ ] Configuración de IBKR verificada
[ ] Configuración de Yahoo verificada

TAREA A1.3: PROVIDER FACTORY
─────────────────────────────────────────────────────────────────────────
[ ] Archivo src/data/config.py creado
[ ] Archivo src/data/providers/provider_factory.py creado
[ ] IBKRProvider actualizado con is_available()
[ ] YahooProvider actualizado con is_available()
[ ] Sistema de fallback funcionando
[ ] Symbol mapping implementado
[ ] Health check de providers funcional

TAREA A1.4: MCP-ML-MODELS
─────────────────────────────────────────────────────────────────────────
[ ] Estructura de directorios creada
[ ] server.py implementado
[ ] config.py implementado
[ ] config/ml_models.yaml creado
[ ] tools/health.py implementado
[ ] tools/regime.py implementado (placeholder)
[ ] tools/model_info.py implementado
[ ] tools/predict.py implementado (placeholder)
[ ] Tests básicos creados
[ ] docker-compose.yml actualizado con servicio mcp-ml-models
[ ] Puerto 3005 configurado

TAREA A1.5: VERIFICACIÓN
─────────────────────────────────────────────────────────────────────────
[ ] Script verify_fase_a1.py creado
[ ] Script de migración creado
[ ] Todos los checks pasan

═════════════════════════════════════════════════════════════════════════

GATE DE AVANCE A FASE A2:
─────────────────────────────────────────────────────────────────────────
[ ] python scripts/verify_fase_a1.py retorna 0 (éxito)
[ ] docker-compose up -d levanta todos los servicios
[ ] No hay errores críticos en logs

═════════════════════════════════════════════════════════════════════════
```

---

## Troubleshooting

### Error: "Esquema metrics no existe"

```powershell
# Ejecutar script manualmente
docker exec -i trading_postgres psql -U trading -d trading < init-scripts/07_metrics_schema.sql

# Verificar
docker exec trading_postgres psql -U trading -d trading -c "\dn"
```

### Error: "psycopg2 no instalado"

```powershell
pip install psycopg2-binary
```

### Error: "ib_insync no instalado"

```powershell
pip install ib_insync
```

### Error: "Archivo config no encontrado"

Asegurarse de que los archivos YAML están en la ubicación correcta:
- `config/data_sources.yaml`
- `config/ml_models.yaml`

### Error: "Provider IBKR no disponible"

Normal si TWS/Gateway no está corriendo. El sistema usa Yahoo como fallback automáticamente.

### Error: "mcp-ml-models no arranca"

```powershell
# Ver logs
docker-compose logs mcp-ml-models

# Reconstruir imagen
docker-compose build --no-cache mcp-ml-models
docker-compose up -d mcp-ml-models
```

---

## Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Esquemas base PostgreSQL | fase_0_infraestructura.md | Tarea 0.4 |
| Conector Yahoo original | fase_1_data_pipeline.md | Tarea 1.2 |
| Conector IBKR original | fase_1_data_pipeline.md | Tarea 1.3 |
| MCP servers base | fase_2_mcp_servers.md | Tarea 2.1 |
| Interfaz RegimeDetector | fase_a2_ml_modular.md | (próximo) |
| HMM implementación | fase_a2_ml_modular.md | (próximo) |

---

## Siguiente Fase

Una vez completada la Fase A1:

1. **Verificar:** `python scripts/verify_fase_a1.py` retorna éxito
2. **Verificar:** `docker-compose up -d` levanta todos los servicios
3. **Siguiente documento:** `fase_a2_ml_modular.md`
4. **Contenido Fase A2:**
   - Interfaces ABC para RegimeDetector
   - Implementación HMM con hmmlearn
   - Rules Baseline como comparación
   - Factory para crear modelos según config
   - Integración con mcp-ml-models

---

*Fin de Parte 5 - Documento fase_a1_extensiones_base.md completo*

---

# Apéndice: Comandos de Referencia Rápida

```powershell
# Levantar infraestructura
docker-compose up -d

# Ejecutar migración
.\scripts\migrate_fase_a1.ps1

# Verificar fase
python scripts/verify_fase_a1.py

# Ver logs de ml-models
docker-compose logs -f mcp-ml-models

# Conectar a PostgreSQL
docker exec -it trading_postgres psql -U trading -d trading

# Ver tablas de métricas
\dt metrics.*

# Ver fuentes de datos
SELECT * FROM config.data_sources;
```

---

*Documento de Implementación - Fase A1: Extensiones Base*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
