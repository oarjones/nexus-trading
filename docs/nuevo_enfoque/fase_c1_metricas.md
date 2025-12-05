# 📊 Fase C1: Sistema de Métricas y Análisis

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fase A1 (esquemas BD), Fase B1 (estrategias), Fase B2 (AI Agent)  
**Prerrequisito:** Tablas `metrics.*` creadas, estrategias generando Signal

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

Las fases anteriores han establecido:

| Fase | Componente | Estado |
|------|------------|--------|
| A1 | Esquemas `metrics.*` en PostgreSQL | ✅ Tablas creadas |
| A1 | `metrics.trades` para registro de operaciones | ✅ Estructura lista |
| A1 | `metrics.strategy_performance` para agregados | ✅ Estructura lista |
| A1 | `metrics.experiments` para A/B testing | ✅ Estructura lista |
| B1 | `Signal` dataclass con metadata | ✅ Generando señales |
| B2 | `AgentDecision` con reasoning | ✅ Decisiones estructuradas |

**Lo que falta:** El código Python que conecta todo - capturar trades, calcular métricas, gestionar experimentos y visualizar resultados.

### 1.2 Objetivo de Esta Fase

Implementar el **sistema completo de métricas** que permite:

```
FILOSOFÍA CLAVE:
═══════════════════════════════════════════════════════════════════════════
1. Todo se mide, todo se compara
   - Cada trade etiquetado: estrategia, modelo, régimen, experimento
   - Métricas calculadas automáticamente
   - Dashboard en tiempo real

2. Métricas para decisiones, no para vanidad
   - Sharpe > Rentabilidad bruta (ajustar por riesgo)
   - Win rate + Profit factor (no solo ganar)
   - Max Drawdown (saber cuándo parar)

3. Experimentos A/B para evolucionar
   - Comparar estrategias cabeza a cabeza
   - Validar cambios antes de adoptar
   - Base estadística para decisiones

4. Paper trading = Laboratorio
   - Métricas reales sin riesgo de capital
   - Feedback en días, no meses
   - Iterar rápido, aprender más
═══════════════════════════════════════════════════════════════════════════
```

### 1.3 Por Qué Este Sistema Es Crítico

| Razón | Explicación |
|-------|-------------|
| Comparabilidad | Sin métricas, no sabes qué estrategia es mejor |
| Diagnóstico | Identificar qué funciona (régimen BULL) y qué no (alta volatilidad) |
| Evolución | A/B testing permite mejorar con evidencia |
| Control de riesgo | Max Drawdown y VaR te dicen cuándo parar |
| Confianza | Datos objetivos > intuición subjetiva |

### 1.4 Decisiones de Diseño

| Decisión | Justificación |
|----------|---------------|
| Event-driven con Redis | Captura asíncrona sin bloquear trading |
| Cálculos incrementales | No recalcular todo, actualizar deltas |
| Schemas Pydantic | Validación estricta de métricas |
| PostgreSQL como fuente de verdad | Persistencia, queries SQL para análisis |
| Grafana para visualización | Dashboard profesional sin código custom |

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| MetricsCollector funcional | Captura trades desde eventos Redis |
| Cálculo automático de métricas | Sharpe, Sortino, MaxDD calculados correctamente |
| Agregación por dimensiones | Métricas por estrategia, modelo, régimen, período |
| Sistema A/B operativo | Crear experimento, asignar trades, comparar resultados |
| Dashboard Grafana | 4+ paneles mostrando métricas clave |
| Tests unitarios | > 80% cobertura en `src/metrics/` |

---

## 3. Arquitectura del Sistema de Métricas

### 3.1 Diagrama de Componentes

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                        METRICS SYSTEM - VISIÓN GENERAL                         │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│    FUENTES DE EVENTOS                    PROCESAMIENTO                         │
│    ═══════════════════                   ════════════════                       │
│                                                                                │
│    ┌──────────────────┐                  ┌──────────────────────────────┐      │
│    │  Strategy Runner │──┐               │     MetricsCollector         │      │
│    │  (ETF Momentum)  │  │   Redis       │  ┌────────────────────────┐  │      │
│    └──────────────────┘  │   Pub/Sub     │  │ • subscribe_events()   │  │      │
│                          │   ════════    │  │ • process_trade_open() │  │      │
│    ┌──────────────────┐  ├───────────────│  │ • process_trade_close()│  │      │
│    │    AI Agent      │──┤  Canal:       │  │ • enrich_with_context()│  │      │
│    │   (Claude)       │  │  "trades"     │  └────────────────────────┘  │      │
│    └──────────────────┘  │               └──────────────┬───────────────┘      │
│                          │                              │                      │
│    ┌──────────────────┐  │                              │                      │
│    │  Risk Manager    │──┘                              │                      │
│    │  (stop losses)   │                                 │                      │
│    └──────────────────┘                                 ▼                      │
│                                          ┌──────────────────────────────┐      │
│                                          │         PostgreSQL           │      │
│                                          │      metrics.trades          │      │
│                                          └──────────────┬───────────────┘      │
│                                                         │                      │
│    ┌────────────────────────────────────────────────────┼─────────────────┐    │
│    │                     AGGREGATION LAYER              │                 │    │
│    │  ┌─────────────────┐  ┌─────────────────┐  ┌──────▼────────┐        │    │
│    │  │ StrategyAggr.   │  │  ModelAggr.     │  │ ExperimentMgr │        │    │
│    │  │ ───────────────│  │ ───────────────│  │ ─────────────│        │    │
│    │  │ • by_strategy  │  │ • by_model      │  │ • create()    │        │    │
│    │  │ • by_regime    │  │ • compare()     │  │ • assign()    │        │    │
│    │  │ • by_period    │  │ • accuracy      │  │ • analyze()   │        │    │
│    │  └────────┬────────┘  └────────┬────────┘  └───────┬───────┘        │    │
│    │           │                    │                   │                │    │
│    │           └────────────────────┼───────────────────┘                │    │
│    │                                │                                    │    │
│    │                                ▼                                    │    │
│    │                   ┌────────────────────────┐                        │    │
│    │                   │   MetricsAggregator    │                        │    │
│    │                   │   ──────────────────── │                        │    │
│    │                   │   • calculate_sharpe() │                        │    │
│    │                   │   • calculate_sortino()│                        │    │
│    │                   │   • calculate_maxdd()  │                        │    │
│    │                   │   • calculate_var()    │                        │    │
│    │                   │   • update_aggregates()│                        │    │
│    │                   └────────────┬───────────┘                        │    │
│    │                                │                                    │    │
│    └────────────────────────────────┼────────────────────────────────────┘    │
│                                     │                                         │
│                                     ▼                                         │
│    ┌────────────────────────────────────────────────────────────────────┐     │
│    │                         VISUALIZATION                              │     │
│    │  ┌─────────────────────────────────────────────────────────────┐   │     │
│    │  │                    Grafana Dashboard                        │   │     │
│    │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────┐ │   │     │
│    │  │  │ PnL Curve   │ │Strategy     │ │ Regime      │ │A/B Test│ │   │     │
│    │  │  │ (time)      │ │Comparison   │ │ Performance │ │Results │ │   │     │
│    │  │  └─────────────┘ └─────────────┘ └─────────────┘ └────────┘ │   │     │
│    │  └─────────────────────────────────────────────────────────────┘   │     │
│    └────────────────────────────────────────────────────────────────────┘     │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flujo de Datos Detallado

```
1. TRADE ABIERTO
   ─────────────────────────────────────────────────────────────────────────────
   
   Strategy/Agent                   Redis                    MetricsCollector
       │                              │                              │
       │   Signal ejecutada           │                              │
       ├──────────────────────────────►  publish("trades", {         │
       │                              │    "event": "TRADE_OPEN",    │
       │                              │    "trade_id": "uuid",       │
       │                              │    "symbol": "VWCE.DE",      │
       │                              │    "direction": "LONG",      │
       │                              │    "strategy_id": "etf_mom", │
       │                              │    ...                       │
       │                              │  })                          │
       │                              │                              │
       │                              ├──────────────────────────────►
       │                              │                              │
       │                              │              enrich_with_context()
       │                              │              • obtener régimen actual
       │                              │              • obtener volatilidad
       │                              │              • snapshot indicadores
       │                              │                              │
       │                              │              INSERT metrics.trades
       │                              │                              │

2. TRADE CERRADO
   ─────────────────────────────────────────────────────────────────────────────
   
   Risk Manager / Strategy          Redis                    MetricsCollector
       │                              │                              │
       │   Stop loss / Take profit    │                              │
       ├──────────────────────────────►  publish("trades", {         │
       │                              │    "event": "TRADE_CLOSE",   │
       │                              │    "trade_id": "uuid",       │
       │                              │    "exit_price": 103.20,     │
       │                              │    "reason": "take_profit",  │
       │                              │    ...                       │
       │                              │  })                          │
       │                              │                              │
       │                              ├──────────────────────────────►
       │                              │                              │
       │                              │              calculate_pnl()
       │                              │              • PnL EUR
       │                              │              • PnL %
       │                              │              • R-multiple
       │                              │              • Comisiones
       │                              │              • Holding duration
       │                              │                              │
       │                              │              UPDATE metrics.trades
       │                              │                              │
       │                              │              trigger_aggregation()
       │                              │              • Actualizar aggregates
       │                              │                              │

3. AGREGACIÓN PERIÓDICA
   ─────────────────────────────────────────────────────────────────────────────
   
   Scheduler (cada 5 min)                         MetricsAggregator
       │                                                  │
       │   cron: "*/5 * * * *"                           │
       ├──────────────────────────────────────────────────►
       │                                                  │
       │                                   aggregate_by_strategy()
       │                                   • Por cada estrategia activa
       │                                   • Calcular métricas período
       │                                   • Upsert strategy_performance
       │                                                  │
       │                                   aggregate_by_model()
       │                                   • Por cada modelo ML
       │                                   • Calcular accuracy régimen
       │                                   • Upsert model_performance
       │                                                  │
       │                                   update_experiment_results()
       │                                   • Si hay experimentos activos
       │                                   • Calcular métricas por variante
       │                                   • Actualizar experiment_results
       │                                                  │
```

### 3.3 Estructura de Directorios

```
src/metrics/
├── __init__.py
├── schemas.py              # ← NUEVO: Pydantic schemas para métricas
├── collector.py            # ← NUEVO: MetricsCollector (captura eventos)
├── aggregator.py           # ← NUEVO: MetricsAggregator (cálculos)
├── experiments.py          # ← NUEVO: ExperimentManager (A/B testing)
├── calculators/
│   ├── __init__.py
│   ├── risk_metrics.py     # ← NUEVO: Sharpe, Sortino, MaxDD, VaR
│   ├── trade_metrics.py    # ← NUEVO: Win rate, Profit factor, R-multiple
│   └── time_metrics.py     # ← NUEVO: Holding time, Trades por día
├── exporters/
│   ├── __init__.py
│   ├── postgres.py         # ← NUEVO: Exportar a PostgreSQL
│   └── prometheus.py       # ← NUEVO: Métricas para Prometheus/Grafana
└── tests/
    ├── __init__.py
    ├── test_collector.py
    ├── test_aggregator.py
    ├── test_experiments.py
    └── test_calculators.py

config/
├── metrics.yaml            # ← NUEVO: Configuración del sistema de métricas

grafana/
├── dashboards/
│   └── trading_metrics.json  # ← NUEVO: Dashboard exportable
└── provisioning/
    ├── dashboards/
    │   └── dashboards.yaml   # ← NUEVO: Auto-provisioning
    └── datasources/
        └── datasources.yaml  # ← NUEVO: PostgreSQL datasource
```

---

## 4. Dependencias Entre Tareas

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      FASE C1: SISTEMA DE MÉTRICAS                               │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌──────────────────────┐                                                      │
│   │ C1.1: Schemas        │                                                      │
│   │ Pydantic             │────────────┐                                         │
│   └──────────────────────┘            │                                         │
│                                       │                                         │
│   ┌──────────────────────┐            │     ┌──────────────────────┐            │
│   │ C1.2: Calculators    │────────────┼────►│ C1.4: Aggregator     │            │
│   │ (risk_metrics.py)    │            │     │ (aggregator.py)      │            │
│   └──────────────────────┘            │     └──────────┬───────────┘            │
│                                       │                │                        │
│   ┌──────────────────────┐            │                │                        │
│   │ C1.3: Collector      │────────────┘                │                        │
│   │ (collector.py)       │─────────────────────────────┤                        │
│   └──────────────────────┘                             │                        │
│                                                        │                        │
│   ┌──────────────────────┐                             │                        │
│   │ C1.5: Experiments    │◄────────────────────────────┤                        │
│   │ (experiments.py)     │                             │                        │
│   └──────────────────────┘                             │                        │
│                                                        │                        │
│   ┌──────────────────────┐                             │                        │
│   │ C1.6: Exporters      │◄────────────────────────────┘                        │
│   │ (postgres, prom)     │                                                      │
│   └──────────────────────┘                                                      │
│            │                                                                    │
│            ▼                                                                    │
│   ┌──────────────────────┐                                                      │
│   │ C1.7: Dashboard      │                                                      │
│   │ Grafana              │                                                      │
│   └──────────────────────┘                                                      │
│            │                                                                    │
│            ▼                                                                    │
│   ┌──────────────────────┐                                                      │
│   │ C1.8: Verificación   │                                                      │
│   │ + Integración        │                                                      │
│   └──────────────────────┘                                                      │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘

LEYENDA:
────────
• C1.1 (Schemas) es base para todos los demás
• C1.2 (Calculators) provee funciones a C1.3, C1.4, C1.5
• C1.3 (Collector) alimenta datos a C1.4 (Aggregator)
• C1.4 (Aggregator) alimenta datos a C1.5 (Experiments) y C1.6 (Exporters)
• C1.6 (Exporters) conecta con C1.7 (Dashboard)
• C1.8 (Verificación) requiere todos los anteriores
```

---

## 5. Dependencias Externas (Fases Anteriores)

### 5.1 De Fase A1 (Esquemas BD)

```python
# Tablas que usaremos (ya creadas en A1):
# - metrics.trades          → INSERT/UPDATE desde Collector
# - metrics.strategy_performance → UPSERT desde Aggregator
# - metrics.model_performance    → UPSERT desde Aggregator
# - metrics.experiments          → CRUD desde ExperimentManager
# - metrics.experiment_results   → INSERT desde ExperimentManager

# ENUMs disponibles:
# - metrics.trade_direction (LONG, SHORT)
# - metrics.trade_status (OPEN, CLOSED, CANCELLED)
# - metrics.regime_type (BULL, BEAR, SIDEWAYS, VOLATILE, UNKNOWN)
# - metrics.experiment_status (DRAFT, RUNNING, COMPLETED, ABORTED)
```

### 5.2 De Fase B1 (Estrategias)

```python
# Interfaces que usaremos:
from src.strategies.interfaces import Signal

# Signal contiene:
# - strategy_id: str
# - symbol: str
# - direction: str (LONG, SHORT, CLOSE)
# - confidence: float
# - entry_price, stop_loss, take_profit
# - regime_at_signal: str
# - metadata: dict
```

### 5.3 De Fase B2 (AI Agent)

```python
# Interfaces que usaremos:
from src.agents.llm.interfaces import AgentDecision

# AgentDecision contiene:
# - actions: list[Signal]
# - reasoning: str          ← Guardamos en metrics.trades.reasoning
# - market_view: str
# - confidence: float
# - tokens_used: int       ← Para tracking de costes
```

### 5.4 De Fase 3 (Agentes Core)

```python
# Sistema pub/sub Redis que usaremos:
import redis

# Canales relevantes:
# - "trades" → Publicar/suscribir eventos de trades
# - "signals" → Leer señales generadas
# - "portfolio" → Leer estado del portfolio

# Ya implementado en Fase 3:
# - RedisClient wrapper
# - Serialización JSON de mensajes
```

---

## 6. Configuración YAML

### 6.1 Archivo Principal: `config/metrics.yaml`

```yaml
# ============================================================================
# CONFIGURACIÓN DEL SISTEMA DE MÉTRICAS
# ============================================================================

metrics:
  # Collector settings
  collector:
    redis_channel: "trades"
    batch_size: 10                    # Procesar en lotes
    flush_interval_seconds: 5         # Flush cada N segundos
    enrich_with_regime: true          # Obtener régimen al capturar
    enrich_with_indicators: true      # Snapshot de indicadores
  
  # Aggregator settings
  aggregator:
    # Períodos de agregación
    periods:
      - type: "hourly"
        retention_days: 7
      - type: "daily"
        retention_days: 90
      - type: "weekly"
        retention_days: 365
      - type: "monthly"
        retention_days: 1825          # 5 años
      - type: "all_time"
        retention_days: null          # Sin límite
    
    # Frecuencia de actualización
    update_frequency_seconds: 300     # Cada 5 minutos
    
    # Métricas a calcular
    calculate:
      - sharpe_ratio
      - sortino_ratio
      - calmar_ratio
      - max_drawdown
      - var_95
      - win_rate
      - profit_factor
      - avg_r_multiple
  
  # Calculators settings
  calculators:
    risk_free_rate: 0.03              # 3% anual (EUR)
    trading_days_per_year: 252
    var_confidence: 0.95
    min_trades_for_metrics: 10        # Mínimo trades para métricas válidas
  
  # Experiments (A/B testing)
  experiments:
    min_trades_per_variant: 20        # Mínimo para significancia
    confidence_level: 0.95            # Para tests estadísticos
    auto_conclude_after_days: 30      # Auto-concluir experimentos

  # Exporters
  exporters:
    postgres:
      enabled: true
      batch_size: 100
    prometheus:
      enabled: true
      port: 9090
      path: "/metrics"

# Grafana provisioning
grafana:
  datasource:
    name: "PostgreSQL-Trading"
    type: "postgres"
    host: "${POSTGRES_HOST:-localhost}"
    port: 5432
    database: "trading"
    user: "${POSTGRES_USER:-trading}"
  dashboards:
    auto_provision: true
    folder: "Trading"
```

---

## 7. Consideraciones Importantes

### 7.1 Rendimiento

| Consideración | Solución |
|---------------|----------|
| Alto volumen de trades | Procesamiento en batch, no uno a uno |
| Cálculos costosos | Agregación incremental, no recalcular todo |
| Queries lentas | Índices ya creados en A1, usar EXPLAIN |
| Grafana lento | Limitar time range, usar materialized views |

### 7.2 Consistencia de Datos

```
REGLA: PostgreSQL es la fuente de verdad
═══════════════════════════════════════════════════════════════════════════
• Redis es transporte, no almacenamiento
• Si hay discrepancia, confiar en PostgreSQL
• Métricas calculadas se pueden regenerar desde trades
• Trades nunca se borran, solo se marcan como CANCELLED si error
═══════════════════════════════════════════════════════════════════════════
```

### 7.3 Manejo de Errores

| Situación | Comportamiento |
|-----------|----------------|
| Redis caído | Collector encola en memoria, retry con backoff |
| PostgreSQL caído | Error fatal, pausar sistema de métricas |
| Cálculo NaN | Usar None, no propagar NaN |
| División por cero | Retornar None, log warning |

### 7.4 Testing

```
ESTRATEGIA DE TESTING:
═══════════════════════════════════════════════════════════════════════════
1. Unit tests para calculators
   - Casos conocidos con resultados verificables
   - Edge cases (0 trades, 1 trade, trades negativos)

2. Integration tests para collector
   - Mock de Redis, verificar PostgreSQL
   - Verificar enriquecimiento de contexto

3. End-to-end tests para aggregator
   - Insertar trades de prueba
   - Verificar métricas calculadas
   - Comparar con cálculo manual

4. Property-based tests (opcional)
   - Generar trades aleatorios
   - Verificar propiedades invariantes
═══════════════════════════════════════════════════════════════════════════
```

---

## 8. Checklist Pre-Implementación

Antes de comenzar, verificar:

```
[ ] Tablas metrics.* existen en PostgreSQL (A1 completada)
[ ] Redis corriendo y accesible
[ ] Signal dataclass disponible (B1 completada)
[ ] AgentDecision dataclass disponible (B2 completada)
[ ] Sistema pub/sub Redis funcionando (Fase 3)
[ ] Grafana corriendo (docker-compose up -d)
[ ] Python 3.11+ con entorno virtual activo
[ ] requirements.txt actualizado con dependencias de métricas
```

### 8.1 Dependencias Python Adicionales

```txt
# Añadir a requirements.txt para Fase C1

# Métricas y estadísticas
numpy>=1.24.0
scipy>=1.10.0              # Para tests estadísticos A/B

# Prometheus exporter
prometheus-client>=0.17.0

# Validación
pydantic>=2.0.0            # Ya instalado, confirmar versión

# Async
aioredis>=2.0.0            # Ya instalado, confirmar
asyncpg>=0.28.0            # Ya instalado, confirmar
```

---

*Fin de Parte 1 - Continúa en Parte 2: Metrics Collector*

---

# Resumen de Tareas Fase C1

| Tarea | Descripción | Estimación |
|-------|-------------|------------|
| C1.1 | Schemas Pydantic para métricas | 1-2 horas |
| C1.2 | Calculators (risk, trade, time) | 3-4 horas |
| C1.3 | MetricsCollector | 3-4 horas |
| C1.4 | MetricsAggregator | 3-4 horas |
| C1.5 | ExperimentManager (A/B) | 3-4 horas |
| C1.6 | Exporters (postgres, prometheus) | 2-3 horas |
| C1.7 | Dashboard Grafana | 2-3 horas |
| C1.8 | Verificación + Integración | 2-3 horas |

**Total estimado:** 20-27 horas (~1 semana)

---

*Documento de Implementación - Fase C1: Sistema de Métricas*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
# Fase C1: Sistema de Métricas - Parte 2

## Schemas Pydantic + Calculators

---

# Tarea C1.1: Schemas Pydantic

**Estado:** ⬜ Pendiente  
**Duración estimada:** 1-2 horas  
**Dependencias:** Ninguna (base para todo lo demás)

**Objetivo:** Definir todas las estructuras de datos para el sistema de métricas con validación estricta.

---

## C1.1.1: Archivo Principal de Schemas

**Archivo:** `src/metrics/schemas.py`

```python
"""
Schemas Pydantic para el sistema de métricas.

Este módulo define todas las estructuras de datos utilizadas para:
- Eventos de trades (apertura/cierre)
- Métricas calculadas (Sharpe, Sortino, etc.)
- Resultados de agregación
- Configuración de experimentos A/B
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================================
# ENUMS
# ============================================================================

class TradeDirection(str, Enum):
    """Dirección del trade."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeStatus(str, Enum):
    """Estado del trade."""
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class RegimeType(str, Enum):
    """Tipo de régimen de mercado."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"
    UNKNOWN = "UNKNOWN"


class ExperimentStatus(str, Enum):
    """Estado del experimento A/B."""
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"


class TradeEventType(str, Enum):
    """Tipo de evento de trade."""
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    TRADE_UPDATE = "TRADE_UPDATE"
    TRADE_CANCEL = "TRADE_CANCEL"


class PeriodType(str, Enum):
    """Tipo de período para agregación."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


# ============================================================================
# EVENTOS DE TRADE
# ============================================================================

class TradeOpenEvent(BaseModel):
    """
    Evento emitido cuando se abre un trade.
    Publicado en canal Redis "trades".
    """
    event_type: TradeEventType = TradeEventType.TRADE_OPEN
    trade_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Origen
    strategy_id: str = Field(..., min_length=1, max_length=50)
    model_id: Optional[str] = Field(None, max_length=50)
    agent_id: Optional[str] = Field(None, max_length=50)
    experiment_id: Optional[UUID] = None
    
    # Trade data
    symbol: str = Field(..., min_length=1, max_length=20)
    direction: TradeDirection
    entry_price: Decimal = Field(..., gt=0)
    size_shares: Decimal = Field(..., gt=0)
    size_value_eur: Decimal = Field(..., gt=0)
    
    # Risk levels
    stop_loss: Optional[Decimal] = Field(None, gt=0)
    take_profit: Optional[Decimal] = Field(None, gt=0)
    
    # Contexto (opcional, se enriquece en collector)
    regime_at_entry: Optional[RegimeType] = None
    regime_confidence: Optional[float] = Field(None, ge=0, le=1)
    
    # Metadata
    reasoning: Optional[str] = None
    signals_at_entry: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: str,
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


class TradeCloseEvent(BaseModel):
    """
    Evento emitido cuando se cierra un trade.
    Publicado en canal Redis "trades".
    """
    event_type: TradeEventType = TradeEventType.TRADE_CLOSE
    trade_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Precio de salida
    exit_price: Decimal = Field(..., gt=0)
    
    # Razón de cierre
    close_reason: str = Field(..., min_length=1)  # "stop_loss", "take_profit", "manual", "signal"
    
    # Costes (opcional, calculado si no se proporciona)
    commission_eur: Optional[Decimal] = Field(default=Decimal("0"))
    slippage_eur: Optional[Decimal] = Field(default=Decimal("0"))
    
    # Metadata adicional
    metadata: Optional[dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_encoders = {
            Decimal: str,
            UUID: str,
            datetime: lambda v: v.isoformat()
        }


# ============================================================================
# REGISTRO DE TRADE COMPLETO
# ============================================================================

class TradeRecord(BaseModel):
    """
    Registro completo de un trade.
    Corresponde a una fila en metrics.trades.
    """
    trade_id: UUID
    
    # Origen
    strategy_id: str
    model_id: Optional[str] = None
    agent_id: Optional[str] = None
    experiment_id: Optional[UUID] = None
    
    # Trade data
    symbol: str
    direction: TradeDirection
    status: TradeStatus = TradeStatus.OPEN
    
    # Precios
    entry_price: Decimal
    exit_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    
    # Tamaño
    size_shares: Decimal
    size_value_eur: Decimal
    
    # PnL (calculado al cerrar)
    pnl_eur: Optional[Decimal] = None
    pnl_pct: Optional[float] = None
    pnl_r_multiple: Optional[float] = None
    
    # Costes
    commission_eur: Decimal = Decimal("0")
    slippage_eur: Decimal = Decimal("0")
    
    # Contexto de mercado
    regime_at_entry: Optional[RegimeType] = None
    regime_confidence: Optional[float] = None
    market_volatility_at_entry: Optional[float] = None
    
    # Timestamps
    entry_timestamp: datetime
    exit_timestamp: Optional[datetime] = None
    holding_duration_hours: Optional[float] = None
    
    # Metadata
    reasoning: Optional[str] = None
    signals_at_entry: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None
    
    # Auditoría
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode='after')
    def validate_prices(self) -> 'TradeRecord':
        """Validar coherencia de precios."""
        if self.direction == TradeDirection.LONG:
            if self.stop_loss and self.stop_loss >= self.entry_price:
                raise ValueError("Stop loss debe ser menor que entry price para LONG")
            if self.take_profit and self.take_profit <= self.entry_price:
                raise ValueError("Take profit debe ser mayor que entry price para LONG")
        else:  # SHORT
            if self.stop_loss and self.stop_loss <= self.entry_price:
                raise ValueError("Stop loss debe ser mayor que entry price para SHORT")
            if self.take_profit and self.take_profit >= self.entry_price:
                raise ValueError("Take profit debe ser menor que entry price para SHORT")
        return self

    class Config:
        use_enum_values = True


# ============================================================================
# MÉTRICAS CALCULADAS
# ============================================================================

class RiskMetrics(BaseModel):
    """
    Métricas de riesgo calculadas.
    """
    sharpe_ratio: Optional[float] = Field(None, description="Sharpe Ratio anualizado")
    sortino_ratio: Optional[float] = Field(None, description="Sortino Ratio anualizado")
    calmar_ratio: Optional[float] = Field(None, description="Calmar Ratio")
    max_drawdown_pct: Optional[float] = Field(None, ge=0, le=100, description="Max Drawdown %")
    max_drawdown_eur: Optional[Decimal] = Field(None, ge=0, description="Max Drawdown EUR")
    var_95_pct: Optional[float] = Field(None, description="Value at Risk 95%")
    
    # Período de cálculo
    calculation_period_days: Optional[int] = None
    data_points_used: Optional[int] = None


class TradeMetrics(BaseModel):
    """
    Métricas de trading calculadas.
    """
    total_trades: int = Field(0, ge=0)
    winning_trades: int = Field(0, ge=0)
    losing_trades: int = Field(0, ge=0)
    breakeven_trades: int = Field(0, ge=0)
    
    # PnL
    total_pnl_eur: Decimal = Decimal("0")
    avg_pnl_eur: Optional[Decimal] = None
    max_win_eur: Optional[Decimal] = None
    max_loss_eur: Optional[Decimal] = None
    
    # Ratios
    win_rate: Optional[float] = Field(None, ge=0, le=1, description="Win rate 0-1")
    profit_factor: Optional[float] = Field(None, ge=0, description="Gross profit / Gross loss")
    avg_r_multiple: Optional[float] = Field(None, description="Promedio R-multiple")
    expectancy_eur: Optional[Decimal] = Field(None, description="Expectancy por trade")

    @field_validator('win_rate')
    @classmethod
    def validate_win_rate(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Win rate debe estar entre 0 y 1")
        return v


class TimeMetrics(BaseModel):
    """
    Métricas de tiempo/actividad.
    """
    avg_holding_hours: Optional[float] = Field(None, ge=0)
    min_holding_hours: Optional[float] = Field(None, ge=0)
    max_holding_hours: Optional[float] = Field(None, ge=0)
    avg_trades_per_day: Optional[float] = Field(None, ge=0)
    active_trading_days: Optional[int] = Field(None, ge=0)
    longest_winning_streak: Optional[int] = Field(None, ge=0)
    longest_losing_streak: Optional[int] = Field(None, ge=0)


class AggregatedMetrics(BaseModel):
    """
    Métricas agregadas completas.
    Combina Risk, Trade y Time metrics.
    """
    # Identificadores
    strategy_id: Optional[str] = None
    model_id: Optional[str] = None
    regime: Optional[RegimeType] = None
    
    # Período
    period_type: PeriodType
    period_start: datetime
    period_end: datetime
    
    # Métricas
    risk: RiskMetrics = Field(default_factory=RiskMetrics)
    trade: TradeMetrics = Field(default_factory=TradeMetrics)
    time: TimeMetrics = Field(default_factory=TimeMetrics)
    
    # Por régimen (opcional)
    trades_by_regime: Optional[dict[str, int]] = None
    pnl_by_regime: Optional[dict[str, float]] = None
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    min_trades_met: bool = False  # True si cumple mínimo de trades para métricas válidas


# ============================================================================
# EXPERIMENTOS A/B
# ============================================================================

class ExperimentVariant(BaseModel):
    """
    Variante dentro de un experimento A/B.
    """
    variant_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    
    # Configuración específica de la variante
    config: dict[str, Any] = Field(default_factory=dict)
    
    # Peso para asignación (si se usa weighted random)
    weight: float = Field(1.0, gt=0)


class ExperimentConfig(BaseModel):
    """
    Configuración de un experimento A/B.
    """
    experiment_id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    
    # Variantes
    variants: list[ExperimentVariant] = Field(..., min_length=2)
    
    # Configuración
    start_date: datetime
    end_date: Optional[datetime] = None
    auto_conclude_days: Optional[int] = Field(30, ge=1)
    min_trades_per_variant: int = Field(20, ge=5)
    
    # Métrica principal para comparación
    primary_metric: str = Field("sharpe_ratio")
    
    # Estado
    status: ExperimentStatus = ExperimentStatus.DRAFT
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None

    @field_validator('variants')
    @classmethod
    def validate_variants(cls, v):
        if len(v) < 2:
            raise ValueError("Experimento debe tener al menos 2 variantes")
        variant_ids = [var.variant_id for var in v]
        if len(variant_ids) != len(set(variant_ids)):
            raise ValueError("variant_id debe ser único")
        return v


class ExperimentResult(BaseModel):
    """
    Resultado de una variante en un experimento.
    """
    experiment_id: UUID
    variant_id: str
    
    # Métricas de la variante
    metrics: AggregatedMetrics
    
    # Estadísticas comparativas
    is_winner: Optional[bool] = None
    relative_improvement_pct: Optional[float] = None  # vs control/baseline
    p_value: Optional[float] = None  # Significancia estadística
    confidence_interval: Optional[tuple[float, float]] = None
    
    # Metadata
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

class MetricsConfig(BaseModel):
    """
    Configuración del sistema de métricas.
    Cargada desde config/metrics.yaml
    """
    # Collector
    redis_channel: str = "trades"
    batch_size: int = Field(10, ge=1)
    flush_interval_seconds: int = Field(5, ge=1)
    enrich_with_regime: bool = True
    enrich_with_indicators: bool = True
    
    # Aggregator
    update_frequency_seconds: int = Field(300, ge=60)
    
    # Calculators
    risk_free_rate: float = Field(0.03, ge=0)
    trading_days_per_year: int = Field(252, ge=200, le=365)
    var_confidence: float = Field(0.95, ge=0.9, le=0.99)
    min_trades_for_metrics: int = Field(10, ge=1)
    
    # Experiments
    experiment_min_trades: int = Field(20, ge=5)
    experiment_confidence_level: float = Field(0.95, ge=0.9, le=0.99)
    experiment_auto_conclude_days: int = Field(30, ge=1)


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def trade_event_to_record(
    open_event: TradeOpenEvent,
    close_event: Optional[TradeCloseEvent] = None
) -> TradeRecord:
    """
    Convierte eventos de trade a TradeRecord.
    """
    record = TradeRecord(
        trade_id=open_event.trade_id,
        strategy_id=open_event.strategy_id,
        model_id=open_event.model_id,
        agent_id=open_event.agent_id,
        experiment_id=open_event.experiment_id,
        symbol=open_event.symbol,
        direction=open_event.direction,
        entry_price=open_event.entry_price,
        size_shares=open_event.size_shares,
        size_value_eur=open_event.size_value_eur,
        stop_loss=open_event.stop_loss,
        take_profit=open_event.take_profit,
        regime_at_entry=open_event.regime_at_entry,
        regime_confidence=open_event.regime_confidence,
        entry_timestamp=open_event.timestamp,
        reasoning=open_event.reasoning,
        signals_at_entry=open_event.signals_at_entry,
        metadata=open_event.metadata
    )
    
    if close_event:
        record.status = TradeStatus.CLOSED
        record.exit_price = close_event.exit_price
        record.exit_timestamp = close_event.timestamp
        record.commission_eur = close_event.commission_eur or Decimal("0")
        record.slippage_eur = close_event.slippage_eur or Decimal("0")
        
        # Calcular holding duration
        duration = close_event.timestamp - open_event.timestamp
        record.holding_duration_hours = duration.total_seconds() / 3600
    
    return record
```

---

# Tarea C1.2: Calculators

**Estado:** ⬜ Pendiente  
**Duración estimada:** 3-4 horas  
**Dependencias:** C1.1 (Schemas)

**Objetivo:** Implementar todos los cálculos de métricas con precisión matemática.

---

## C1.2.1: Risk Metrics Calculator

**Archivo:** `src/metrics/calculators/risk_metrics.py`

```python
"""
Calculador de métricas de riesgo.

Implementa:
- Sharpe Ratio (anualizado)
- Sortino Ratio (anualizado)
- Calmar Ratio
- Maximum Drawdown
- Value at Risk (VaR)

IMPORTANTE: Todas las métricas usan retornos logarítmicos para
consistencia matemática y correcta anualización.
"""

import numpy as np
from decimal import Decimal
from typing import Optional
from dataclasses import dataclass

from ..schemas import RiskMetrics


@dataclass
class RiskCalculatorConfig:
    """Configuración del calculador de riesgo."""
    risk_free_rate: float = 0.03        # 3% anual
    trading_days_per_year: int = 252
    var_confidence: float = 0.95
    min_data_points: int = 10


class RiskMetricsCalculator:
    """
    Calculador de métricas de riesgo.
    
    Uso:
        calculator = RiskMetricsCalculator()
        metrics = calculator.calculate(returns_array)
    """
    
    def __init__(self, config: Optional[RiskCalculatorConfig] = None):
        self.config = config or RiskCalculatorConfig()
    
    def calculate(
        self,
        returns: np.ndarray,
        equity_curve: Optional[np.ndarray] = None
    ) -> RiskMetrics:
        """
        Calcula todas las métricas de riesgo.
        
        Args:
            returns: Array de retornos (diarios o por trade)
            equity_curve: Curva de equity opcional (para drawdown)
        
        Returns:
            RiskMetrics con todas las métricas calculadas
        """
        if len(returns) < self.config.min_data_points:
            return RiskMetrics(
                calculation_period_days=len(returns),
                data_points_used=len(returns)
            )
        
        # Limpiar NaN e infinitos
        returns = self._clean_returns(returns)
        
        if len(returns) < self.config.min_data_points:
            return RiskMetrics(
                calculation_period_days=len(returns),
                data_points_used=len(returns)
            )
        
        # Calcular métricas
        sharpe = self.calculate_sharpe_ratio(returns)
        sortino = self.calculate_sortino_ratio(returns)
        var_95 = self.calculate_var(returns)
        
        # Drawdown requiere equity curve
        max_dd_pct = None
        max_dd_eur = None
        calmar = None
        
        if equity_curve is not None and len(equity_curve) > 0:
            max_dd_pct, max_dd_eur = self.calculate_max_drawdown(equity_curve)
            calmar = self.calculate_calmar_ratio(returns, max_dd_pct)
        
        return RiskMetrics(
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_eur=Decimal(str(max_dd_eur)) if max_dd_eur else None,
            var_95_pct=var_95,
            calculation_period_days=len(returns),
            data_points_used=len(returns)
        )
    
    def calculate_sharpe_ratio(self, returns: np.ndarray) -> Optional[float]:
        """
        Calcula el Sharpe Ratio anualizado.
        
        Sharpe = (Mean Return - Risk Free Rate) / Std Dev
        
        Anualización:
        - Mean se anualiza multiplicando por sqrt(252)
        - Std se anualiza multiplicando por sqrt(252)
        - Por tanto: Sharpe_anual = Sharpe_diario * sqrt(252)
        
        Args:
            returns: Array de retornos diarios
        
        Returns:
            Sharpe Ratio anualizado o None si no calculable
        """
        if len(returns) < 2:
            return None
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)  # ddof=1 para sample std
        
        if std_return == 0 or np.isnan(std_return):
            return None
        
        # Risk free rate diario
        rf_daily = self.config.risk_free_rate / self.config.trading_days_per_year
        
        # Sharpe diario
        sharpe_daily = (mean_return - rf_daily) / std_return
        
        # Anualizar
        sharpe_annual = sharpe_daily * np.sqrt(self.config.trading_days_per_year)
        
        return float(round(sharpe_annual, 4))
    
    def calculate_sortino_ratio(self, returns: np.ndarray) -> Optional[float]:
        """
        Calcula el Sortino Ratio anualizado.
        
        Sortino = (Mean Return - Risk Free Rate) / Downside Deviation
        
        Downside Deviation solo considera retornos negativos.
        Penaliza menos la volatilidad al alza (buena volatilidad).
        
        Args:
            returns: Array de retornos diarios
        
        Returns:
            Sortino Ratio anualizado o None si no calculable
        """
        if len(returns) < 2:
            return None
        
        mean_return = np.mean(returns)
        
        # Downside deviation: std de retornos negativos
        negative_returns = returns[returns < 0]
        
        if len(negative_returns) < 2:
            # Sin suficientes retornos negativos, Sortino muy alto
            return None
        
        downside_std = np.std(negative_returns, ddof=1)
        
        if downside_std == 0 or np.isnan(downside_std):
            return None
        
        # Risk free rate diario
        rf_daily = self.config.risk_free_rate / self.config.trading_days_per_year
        
        # Sortino diario
        sortino_daily = (mean_return - rf_daily) / downside_std
        
        # Anualizar
        sortino_annual = sortino_daily * np.sqrt(self.config.trading_days_per_year)
        
        return float(round(sortino_annual, 4))
    
    def calculate_max_drawdown(
        self,
        equity_curve: np.ndarray
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Calcula el Maximum Drawdown.
        
        Drawdown = (Peak - Trough) / Peak
        Max Drawdown = máximo drawdown observado
        
        Args:
            equity_curve: Array de valores de equity a lo largo del tiempo
        
        Returns:
            Tuple (max_dd_pct, max_dd_eur)
        """
        if len(equity_curve) < 2:
            return None, None
        
        # Calcular running maximum (peak)
        running_max = np.maximum.accumulate(equity_curve)
        
        # Drawdown en cada punto
        drawdown = (running_max - equity_curve) / running_max
        
        # Maximum drawdown
        max_dd_pct = float(np.max(drawdown) * 100)  # Convertir a porcentaje
        
        # Max drawdown en EUR
        drawdown_eur = running_max - equity_curve
        max_dd_eur = float(np.max(drawdown_eur))
        
        return round(max_dd_pct, 4), round(max_dd_eur, 2)
    
    def calculate_calmar_ratio(
        self,
        returns: np.ndarray,
        max_drawdown_pct: Optional[float]
    ) -> Optional[float]:
        """
        Calcula el Calmar Ratio.
        
        Calmar = Annualized Return / Max Drawdown
        
        Mide el retorno por unidad de drawdown.
        
        Args:
            returns: Array de retornos diarios
            max_drawdown_pct: Maximum drawdown en porcentaje
        
        Returns:
            Calmar Ratio o None si no calculable
        """
        if max_drawdown_pct is None or max_drawdown_pct == 0:
            return None
        
        if len(returns) < 2:
            return None
        
        # Retorno anualizado
        mean_daily_return = np.mean(returns)
        annual_return = mean_daily_return * self.config.trading_days_per_year * 100  # En %
        
        # Calmar
        calmar = annual_return / max_drawdown_pct
        
        return float(round(calmar, 4))
    
    def calculate_var(
        self,
        returns: np.ndarray,
        confidence: Optional[float] = None
    ) -> Optional[float]:
        """
        Calcula Value at Risk (VaR) usando método histórico.
        
        VaR = Percentil de pérdidas al nivel de confianza
        
        Ejemplo: VaR 95% = 2.5% significa que hay un 5% de probabilidad
        de perder más del 2.5% en un día.
        
        Args:
            returns: Array de retornos diarios
            confidence: Nivel de confianza (default: 0.95)
        
        Returns:
            VaR como porcentaje positivo (pérdida)
        """
        if len(returns) < self.config.min_data_points:
            return None
        
        confidence = confidence or self.config.var_confidence
        
        # Percentil de pérdidas (cola izquierda)
        var = np.percentile(returns, (1 - confidence) * 100)
        
        # Retornar como valor positivo (representa pérdida)
        return float(round(abs(var) * 100, 4))  # En %
    
    def _clean_returns(self, returns: np.ndarray) -> np.ndarray:
        """Limpia returns de NaN e infinitos."""
        returns = np.array(returns, dtype=float)
        returns = returns[~np.isnan(returns)]
        returns = returns[~np.isinf(returns)]
        return returns
```

---

## C1.2.2: Trade Metrics Calculator

**Archivo:** `src/metrics/calculators/trade_metrics.py`

```python
"""
Calculador de métricas de trading.

Implementa:
- Win Rate
- Profit Factor
- R-Multiple promedio
- Expectancy
- Estadísticas de PnL
"""

import numpy as np
from decimal import Decimal
from typing import Optional, Sequence
from dataclasses import dataclass

from ..schemas import TradeMetrics, TradeRecord, TradeStatus


@dataclass
class TradeCalculatorConfig:
    """Configuración del calculador de trades."""
    min_trades: int = 10
    breakeven_threshold_pct: float = 0.001  # 0.1% se considera breakeven


class TradeMetricsCalculator:
    """
    Calculador de métricas de trading.
    
    Uso:
        calculator = TradeMetricsCalculator()
        metrics = calculator.calculate(trades_list)
    """
    
    def __init__(self, config: Optional[TradeCalculatorConfig] = None):
        self.config = config or TradeCalculatorConfig()
    
    def calculate(self, trades: Sequence[TradeRecord]) -> TradeMetrics:
        """
        Calcula todas las métricas de trading.
        
        Args:
            trades: Lista de TradeRecord (solo trades cerrados)
        
        Returns:
            TradeMetrics con todas las métricas calculadas
        """
        # Filtrar solo trades cerrados con PnL
        closed_trades = [
            t for t in trades 
            if t.status == TradeStatus.CLOSED and t.pnl_eur is not None
        ]
        
        if not closed_trades:
            return TradeMetrics()
        
        # Arrays de PnL
        pnl_values = np.array([float(t.pnl_eur) for t in closed_trades])
        pnl_pct_values = np.array([
            t.pnl_pct for t in closed_trades if t.pnl_pct is not None
        ])
        r_multiples = np.array([
            t.pnl_r_multiple for t in closed_trades if t.pnl_r_multiple is not None
        ])
        
        # Clasificar trades
        winners = pnl_values[pnl_values > self.config.breakeven_threshold_pct * np.abs(pnl_values).mean() if len(pnl_values) > 0 else 0]
        losers = pnl_values[pnl_values < -self.config.breakeven_threshold_pct * np.abs(pnl_values).mean() if len(pnl_values) > 0 else 0]
        
        # Clasificación más simple y robusta
        winning_count = int(np.sum(pnl_values > 0))
        losing_count = int(np.sum(pnl_values < 0))
        breakeven_count = len(pnl_values) - winning_count - losing_count
        
        # Calcular métricas
        total_pnl = Decimal(str(round(float(np.sum(pnl_values)), 2)))
        
        return TradeMetrics(
            total_trades=len(closed_trades),
            winning_trades=winning_count,
            losing_trades=losing_count,
            breakeven_trades=breakeven_count,
            total_pnl_eur=total_pnl,
            avg_pnl_eur=self._safe_decimal(np.mean(pnl_values)),
            max_win_eur=self._safe_decimal(np.max(pnl_values)) if winning_count > 0 else None,
            max_loss_eur=self._safe_decimal(np.min(pnl_values)) if losing_count > 0 else None,
            win_rate=self.calculate_win_rate(winning_count, len(closed_trades)),
            profit_factor=self.calculate_profit_factor(pnl_values),
            avg_r_multiple=self.calculate_avg_r_multiple(r_multiples),
            expectancy_eur=self.calculate_expectancy(pnl_values)
        )
    
    def calculate_win_rate(
        self,
        winning_trades: int,
        total_trades: int
    ) -> Optional[float]:
        """
        Calcula el win rate.
        
        Win Rate = Winning Trades / Total Trades
        
        Args:
            winning_trades: Número de trades ganadores
            total_trades: Número total de trades
        
        Returns:
            Win rate entre 0 y 1
        """
        if total_trades == 0:
            return None
        
        return round(winning_trades / total_trades, 4)
    
    def calculate_profit_factor(self, pnl_values: np.ndarray) -> Optional[float]:
        """
        Calcula el Profit Factor.
        
        Profit Factor = Gross Profits / Gross Losses
        
        Un PF > 1 indica sistema rentable.
        PF > 2 se considera muy bueno.
        
        Args:
            pnl_values: Array de PnL de cada trade
        
        Returns:
            Profit Factor o None si no hay pérdidas
        """
        if len(pnl_values) == 0:
            return None
        
        gross_profits = np.sum(pnl_values[pnl_values > 0])
        gross_losses = np.abs(np.sum(pnl_values[pnl_values < 0]))
        
        if gross_losses == 0:
            return None  # No se puede calcular (división por cero)
        
        return round(float(gross_profits / gross_losses), 4)
    
    def calculate_avg_r_multiple(self, r_multiples: np.ndarray) -> Optional[float]:
        """
        Calcula el R-Multiple promedio.
        
        R-Multiple = PnL / Riesgo Inicial (distancia al stop loss)
        
        Un R-Multiple promedio > 1 indica que las ganancias superan
        las pérdidas en términos de riesgo asumido.
        
        Args:
            r_multiples: Array de R-multiples de cada trade
        
        Returns:
            R-Multiple promedio
        """
        if len(r_multiples) == 0:
            return None
        
        r_multiples = r_multiples[~np.isnan(r_multiples)]
        
        if len(r_multiples) == 0:
            return None
        
        return round(float(np.mean(r_multiples)), 4)
    
    def calculate_expectancy(self, pnl_values: np.ndarray) -> Optional[Decimal]:
        """
        Calcula la Expectancy (esperanza matemática por trade).
        
        Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        
        También puede calcularse como: Total PnL / Total Trades
        
        Args:
            pnl_values: Array de PnL de cada trade
        
        Returns:
            Expectancy en EUR por trade
        """
        if len(pnl_values) == 0:
            return None
        
        expectancy = np.mean(pnl_values)
        return Decimal(str(round(float(expectancy), 2)))
    
    def calculate_pnl_for_trade(self, trade: TradeRecord) -> dict:
        """
        Calcula PnL completo para un trade individual.
        
        Args:
            trade: TradeRecord con entry_price y exit_price
        
        Returns:
            Dict con pnl_eur, pnl_pct, pnl_r_multiple
        """
        if trade.exit_price is None:
            return {"pnl_eur": None, "pnl_pct": None, "pnl_r_multiple": None}
        
        entry = float(trade.entry_price)
        exit_price = float(trade.exit_price)
        size = float(trade.size_shares)
        commission = float(trade.commission_eur)
        slippage = float(trade.slippage_eur)
        
        # PnL bruto
        if trade.direction == "LONG":
            pnl_gross = (exit_price - entry) * size
        else:  # SHORT
            pnl_gross = (entry - exit_price) * size
        
        # PnL neto
        pnl_eur = pnl_gross - commission - slippage
        
        # PnL porcentual
        pnl_pct = (pnl_eur / float(trade.size_value_eur)) * 100
        
        # R-Multiple (si hay stop loss)
        pnl_r_multiple = None
        if trade.stop_loss is not None:
            stop = float(trade.stop_loss)
            if trade.direction == "LONG":
                risk_per_share = entry - stop
            else:
                risk_per_share = stop - entry
            
            if risk_per_share > 0:
                risk_total = risk_per_share * size
                pnl_r_multiple = pnl_eur / risk_total
        
        return {
            "pnl_eur": Decimal(str(round(pnl_eur, 2))),
            "pnl_pct": round(pnl_pct, 4),
            "pnl_r_multiple": round(pnl_r_multiple, 4) if pnl_r_multiple else None
        }
    
    def _safe_decimal(self, value: float) -> Optional[Decimal]:
        """Convierte float a Decimal de forma segura."""
        if value is None or np.isnan(value) or np.isinf(value):
            return None
        return Decimal(str(round(float(value), 2)))
```

---

## C1.2.3: Time Metrics Calculator

**Archivo:** `src/metrics/calculators/time_metrics.py`

```python
"""
Calculador de métricas de tiempo y actividad.

Implementa:
- Holding time statistics
- Trades por día
- Streaks (rachas)
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Sequence
from dataclasses import dataclass

from ..schemas import TimeMetrics, TradeRecord, TradeStatus


@dataclass
class TimeCalculatorConfig:
    """Configuración del calculador de tiempo."""
    min_trades: int = 5


class TimeMetricsCalculator:
    """
    Calculador de métricas de tiempo.
    
    Uso:
        calculator = TimeMetricsCalculator()
        metrics = calculator.calculate(trades_list)
    """
    
    def __init__(self, config: Optional[TimeCalculatorConfig] = None):
        self.config = config or TimeCalculatorConfig()
    
    def calculate(self, trades: Sequence[TradeRecord]) -> TimeMetrics:
        """
        Calcula todas las métricas de tiempo.
        
        Args:
            trades: Lista de TradeRecord
        
        Returns:
            TimeMetrics con todas las métricas calculadas
        """
        # Filtrar trades cerrados con timestamps válidos
        closed_trades = [
            t for t in trades 
            if t.status == TradeStatus.CLOSED 
            and t.holding_duration_hours is not None
        ]
        
        if len(closed_trades) < self.config.min_trades:
            return TimeMetrics()
        
        # Arrays de datos
        holding_hours = np.array([t.holding_duration_hours for t in closed_trades])
        
        # PnL para calcular streaks
        pnl_values = np.array([
            float(t.pnl_eur) if t.pnl_eur else 0 
            for t in closed_trades
        ])
        
        # Días activos
        trade_dates = set()
        for t in closed_trades:
            if t.entry_timestamp:
                trade_dates.add(t.entry_timestamp.date())
        
        # Calcular trades por día
        if trade_dates:
            first_date = min(trade_dates)
            last_date = max(trade_dates)
            total_days = (last_date - first_date).days + 1
            avg_trades_per_day = len(closed_trades) / max(total_days, 1)
        else:
            avg_trades_per_day = None
        
        # Calcular streaks
        winning_streak, losing_streak = self.calculate_streaks(pnl_values)
        
        return TimeMetrics(
            avg_holding_hours=round(float(np.mean(holding_hours)), 2),
            min_holding_hours=round(float(np.min(holding_hours)), 2),
            max_holding_hours=round(float(np.max(holding_hours)), 2),
            avg_trades_per_day=round(avg_trades_per_day, 4) if avg_trades_per_day else None,
            active_trading_days=len(trade_dates),
            longest_winning_streak=winning_streak,
            longest_losing_streak=losing_streak
        )
    
    def calculate_streaks(self, pnl_values: np.ndarray) -> tuple[int, int]:
        """
        Calcula las rachas más largas de wins y losses.
        
        Args:
            pnl_values: Array de PnL ordenado cronológicamente
        
        Returns:
            Tuple (longest_winning_streak, longest_losing_streak)
        """
        if len(pnl_values) == 0:
            return 0, 0
        
        # Convertir a wins/losses (1 = win, -1 = loss, 0 = breakeven)
        results = np.sign(pnl_values)
        
        max_win_streak = 0
        max_loss_streak = 0
        current_win_streak = 0
        current_loss_streak = 0
        
        for result in results:
            if result > 0:  # Win
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            elif result < 0:  # Loss
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
            else:  # Breakeven - no rompe streak pero no suma
                pass
        
        return max_win_streak, max_loss_streak
    
    def calculate_holding_duration(
        self,
        entry_timestamp: datetime,
        exit_timestamp: datetime
    ) -> float:
        """
        Calcula la duración de un trade en horas.
        
        Args:
            entry_timestamp: Timestamp de entrada
            exit_timestamp: Timestamp de salida
        
        Returns:
            Duración en horas
        """
        if entry_timestamp is None or exit_timestamp is None:
            return 0.0
        
        duration = exit_timestamp - entry_timestamp
        return round(duration.total_seconds() / 3600, 2)
```

---

## C1.2.4: Módulo __init__ para Calculators

**Archivo:** `src/metrics/calculators/__init__.py`

```python
"""
Módulo de calculadores de métricas.

Provee funciones y clases para calcular:
- Métricas de riesgo (Sharpe, Sortino, MaxDD, VaR)
- Métricas de trading (Win rate, Profit factor, R-multiple)
- Métricas de tiempo (Holding time, Streaks)
"""

from .risk_metrics import RiskMetricsCalculator, RiskCalculatorConfig
from .trade_metrics import TradeMetricsCalculator, TradeCalculatorConfig
from .time_metrics import TimeMetricsCalculator, TimeCalculatorConfig

__all__ = [
    "RiskMetricsCalculator",
    "RiskCalculatorConfig",
    "TradeMetricsCalculator",
    "TradeCalculatorConfig",
    "TimeMetricsCalculator",
    "TimeCalculatorConfig",
]


# Factory function para crear todos los calculadores
def create_calculators(
    risk_config: RiskCalculatorConfig = None,
    trade_config: TradeCalculatorConfig = None,
    time_config: TimeCalculatorConfig = None
) -> dict:
    """
    Crea todos los calculadores con configuración opcional.
    
    Returns:
        Dict con claves 'risk', 'trade', 'time'
    """
    return {
        "risk": RiskMetricsCalculator(risk_config),
        "trade": TradeMetricsCalculator(trade_config),
        "time": TimeMetricsCalculator(time_config)
    }
```

---

## C1.2.5: Tests para Calculators

**Archivo:** `src/metrics/tests/test_calculators.py`

```python
"""
Tests unitarios para los calculadores de métricas.

Incluye casos conocidos con resultados verificables.
"""

import pytest
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta

from ..calculators import (
    RiskMetricsCalculator,
    TradeMetricsCalculator,
    TimeMetricsCalculator,
    RiskCalculatorConfig,
    TradeCalculatorConfig
)
from ..schemas import TradeRecord, TradeStatus, TradeDirection


class TestRiskMetricsCalculator:
    """Tests para RiskMetricsCalculator."""
    
    @pytest.fixture
    def calculator(self):
        config = RiskCalculatorConfig(
            risk_free_rate=0.0,  # Simplificar cálculos
            trading_days_per_year=252
        )
        return RiskMetricsCalculator(config)
    
    def test_sharpe_ratio_positive(self, calculator):
        """Test Sharpe con retornos positivos consistentes."""
        # Retornos diarios de 0.1% consistentes
        returns = np.array([0.001] * 100)
        
        result = calculator.calculate_sharpe_ratio(returns)
        
        # Con rf=0, Sharpe = mean/std * sqrt(252)
        # mean = 0.001, std muy pequeño -> Sharpe muy alto
        assert result is not None
        assert result > 0
    
    def test_sharpe_ratio_negative(self, calculator):
        """Test Sharpe con retornos negativos."""
        returns = np.array([-0.001] * 100)
        
        result = calculator.calculate_sharpe_ratio(returns)
        
        assert result is not None
        assert result < 0
    
    def test_sharpe_ratio_insufficient_data(self, calculator):
        """Test Sharpe con datos insuficientes."""
        returns = np.array([0.01])
        
        result = calculator.calculate_sharpe_ratio(returns)
        
        assert result is None
    
    def test_max_drawdown(self, calculator):
        """Test Max Drawdown con caso conocido."""
        # Equity: 100 -> 120 -> 90 -> 110
        # DD1: 0%, DD2: 25% (de 120 a 90), DD3: 8.3%
        equity = np.array([100, 120, 90, 110])
        
        max_dd_pct, max_dd_eur = calculator.calculate_max_drawdown(equity)
        
        assert max_dd_pct is not None
        assert abs(max_dd_pct - 25.0) < 0.1  # ~25%
        assert max_dd_eur == 30.0  # 120 - 90
    
    def test_var_95(self, calculator):
        """Test VaR 95% con distribución conocida."""
        # Generar retornos normales
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 1000)
        
        result = calculator.calculate_var(returns, confidence=0.95)
        
        assert result is not None
        assert result > 0  # VaR es positivo (pérdida)
        assert result < 10  # Razonable para vol de 2%


class TestTradeMetricsCalculator:
    """Tests para TradeMetricsCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return TradeMetricsCalculator()
    
    @pytest.fixture
    def sample_trades(self):
        """Genera trades de prueba con resultados conocidos."""
        base_time = datetime.utcnow()
        trades = []
        
        # 6 trades ganadores, 4 perdedores
        pnls = [100, 50, -30, 80, -20, 120, -40, 60, -10, 90]
        
        for i, pnl in enumerate(pnls):
            trade = TradeRecord(
                trade_id=f"test-{i}",
                strategy_id="test_strategy",
                symbol="TEST",
                direction=TradeDirection.LONG,
                status=TradeStatus.CLOSED,
                entry_price=Decimal("100"),
                exit_price=Decimal("101") if pnl > 0 else Decimal("99"),
                size_shares=Decimal("10"),
                size_value_eur=Decimal("1000"),
                pnl_eur=Decimal(str(pnl)),
                pnl_pct=float(pnl) / 10,
                entry_timestamp=base_time - timedelta(hours=i*24),
                exit_timestamp=base_time - timedelta(hours=i*24-12),
                holding_duration_hours=12.0
            )
            trades.append(trade)
        
        return trades
    
    def test_win_rate(self, calculator, sample_trades):
        """Test win rate con 6/10 ganadores."""
        metrics = calculator.calculate(sample_trades)
        
        assert metrics.total_trades == 10
        assert metrics.winning_trades == 6
        assert metrics.losing_trades == 4
        assert metrics.win_rate == 0.6
    
    def test_profit_factor(self, calculator, sample_trades):
        """Test profit factor."""
        metrics = calculator.calculate(sample_trades)
        
        # Gross profit: 100+50+80+120+60+90 = 500
        # Gross loss: 30+20+40+10 = 100
        # PF = 500/100 = 5.0
        assert metrics.profit_factor == 5.0
    
    def test_total_pnl(self, calculator, sample_trades):
        """Test PnL total."""
        metrics = calculator.calculate(sample_trades)
        
        # 100+50-30+80-20+120-40+60-10+90 = 400
        assert metrics.total_pnl_eur == Decimal("400")
    
    def test_pnl_calculation_long(self, calculator):
        """Test cálculo de PnL para trade LONG."""
        trade = TradeRecord(
            trade_id="test-1",
            strategy_id="test",
            symbol="TEST",
            direction=TradeDirection.LONG,
            status=TradeStatus.CLOSED,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            stop_loss=Decimal("95"),
            size_shares=Decimal("10"),
            size_value_eur=Decimal("1000"),
            commission_eur=Decimal("2"),
            slippage_eur=Decimal("1"),
            entry_timestamp=datetime.utcnow(),
            exit_timestamp=datetime.utcnow()
        )
        
        result = calculator.calculate_pnl_for_trade(trade)
        
        # PnL bruto: (110-100)*10 = 100
        # PnL neto: 100 - 2 - 1 = 97
        assert result["pnl_eur"] == Decimal("97")
        
        # R-Multiple: 97 / ((100-95)*10) = 97/50 = 1.94
        assert abs(result["pnl_r_multiple"] - 1.94) < 0.01


class TestTimeMetricsCalculator:
    """Tests para TimeMetricsCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return TimeMetricsCalculator()
    
    def test_streaks(self, calculator):
        """Test cálculo de rachas."""
        # Patrón: W W W L L W W W W L
        pnl_values = np.array([1, 1, 1, -1, -1, 1, 1, 1, 1, -1])
        
        win_streak, loss_streak = calculator.calculate_streaks(pnl_values)
        
        assert win_streak == 4  # WWWW al final
        assert loss_streak == 2  # LL en medio
    
    def test_holding_duration(self, calculator):
        """Test cálculo de duración."""
        entry = datetime(2024, 1, 1, 9, 0, 0)
        exit_time = datetime(2024, 1, 1, 17, 30, 0)
        
        duration = calculator.calculate_holding_duration(entry, exit_time)
        
        assert duration == 8.5  # 8 horas 30 minutos


# Ejecutar tests con: pytest src/metrics/tests/test_calculators.py -v
```

---

## Subtareas Completadas C1.1 y C1.2

```
TAREA C1.1: SCHEMAS PYDANTIC
────────────────────────────────────────────────────────────────────────────
[ ] Archivo src/metrics/schemas.py creado
[ ] ENUMs definidos (TradeDirection, TradeStatus, RegimeType, etc.)
[ ] TradeOpenEvent schema
[ ] TradeCloseEvent schema
[ ] TradeRecord schema completo
[ ] RiskMetrics, TradeMetrics, TimeMetrics
[ ] AggregatedMetrics
[ ] ExperimentVariant, ExperimentConfig, ExperimentResult
[ ] MetricsConfig
[ ] Helper function trade_event_to_record

TAREA C1.2: CALCULATORS
────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/calculators/__init__.py creado
[ ] risk_metrics.py con Sharpe, Sortino, MaxDD, Calmar, VaR
[ ] trade_metrics.py con Win Rate, Profit Factor, R-Multiple
[ ] time_metrics.py con Holding time, Streaks
[ ] Tests unitarios con casos conocidos
[ ] Validación de edge cases (división por cero, NaN)
```

---

*Fin de Parte 2 - Continúa en Parte 3: MetricsCollector*

---

*Documento de Implementación - Fase C1: Sistema de Métricas*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
# Fase C1: Sistema de Métricas - Parte 3

## MetricsCollector (Captura de Eventos)

---

# Tarea C1.3: MetricsCollector

**Estado:** ⬜ Pendiente  
**Duración estimada:** 3-4 horas  
**Dependencias:** C1.1 (Schemas), C1.2 (Calculators)

**Objetivo:** Implementar el componente que captura eventos de trades desde Redis, los enriquece con contexto de mercado, y los persiste en PostgreSQL.

---

## C1.3.1: Diagrama de Flujo del Collector

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           METRICS COLLECTOR FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   Redis Channel: "trades"                                                       │
│                                                                                 │
│   ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐          │
│   │   TRADE_OPEN    │     │   TRADE_CLOSE   │     │   TRADE_CANCEL  │          │
│   └────────┬────────┘     └────────┬────────┘     └────────┬────────┘          │
│            └───────────────────────┼───────────────────────┘                   │
│                                    ▼                                            │
│                    ┌───────────────────────────────┐                            │
│                    │     MetricsCollector          │                            │
│                    │  ┌─────────────────────────┐  │                            │
│                    │  │  1. Parse & Validate    │  │                            │
│                    │  │  2. Route by Type       │  │                            │
│                    │  │  3. Enrich Context      │◄─┼──── mcp-ml-models          │
│                    │  │  4. Calculate PnL       │  │                            │
│                    │  │  5. Persist             │  │                            │
│                    │  └───────────┬─────────────┘  │                            │
│                    └──────────────┼────────────────┘                            │
│                                   ▼                                             │
│                    ┌───────────────────────────────┐                            │
│                    │      PostgreSQL               │                            │
│                    │      metrics.trades           │                            │
│                    └───────────────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## C1.3.2: Implementación Principal

**Archivo:** `src/metrics/collector.py`

```python
"""
MetricsCollector - Captura y persiste eventos de trading.

Este componente:
1. Se suscribe al canal Redis "trades"
2. Procesa eventos de apertura/cierre de trades
3. Enriquece con contexto de mercado (régimen, indicadores)
4. Persiste en PostgreSQL (metrics.trades)
"""

import asyncio
import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from uuid import UUID

import asyncpg
import aioredis

from .schemas import (
    TradeOpenEvent, TradeCloseEvent, TradeRecord,
    TradeEventType, TradeStatus, RegimeType, MetricsConfig,
    trade_event_to_record
)
from .calculators import TradeMetricsCalculator

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Collector de métricas de trading.
    
    Captura eventos desde Redis, enriquece con contexto,
    y persiste en PostgreSQL.
    """
    
    def __init__(
        self,
        config: MetricsConfig,
        redis_url: str = "redis://localhost:6379",
        postgres_dsn: str = "postgresql://trading:trading@localhost:5432/trading"
    ):
        self.config = config
        self.redis_url = redis_url
        self.postgres_dsn = postgres_dsn
        
        self._redis: Optional[aioredis.Redis] = None
        self._pg_pool: Optional[asyncpg.Pool] = None
        self._trade_calculator = TradeMetricsCalculator()
        self._running = False
        
        # Callbacks opcionales
        self._on_trade_open: Optional[callable] = None
        self._on_trade_close: Optional[callable] = None
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    async def start(self) -> None:
        """Inicia el collector y comienza a escuchar eventos."""
        logger.info("Iniciando MetricsCollector...")
        await self._connect()
        self._running = True
        await self._listen_loop()
    
    async def stop(self) -> None:
        """Detiene el collector de forma limpia."""
        logger.info("Deteniendo MetricsCollector...")
        self._running = False
        await self._disconnect()
    
    async def _connect(self) -> None:
        """Establece conexiones a Redis y PostgreSQL."""
        self._redis = await aioredis.from_url(
            self.redis_url, encoding="utf-8", decode_responses=True
        )
        self._pg_pool = await asyncpg.create_pool(
            self.postgres_dsn, min_size=2, max_size=10
        )
        logger.info("Conexiones establecidas")
    
    async def _disconnect(self) -> None:
        """Cierra conexiones."""
        if self._redis:
            await self._redis.close()
        if self._pg_pool:
            await self._pg_pool.close()
    
    # =========================================================================
    # EVENT LISTENING
    # =========================================================================
    
    async def _listen_loop(self) -> None:
        """Loop principal de escucha de eventos Redis."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.config.redis_channel)
        
        logger.info(f"Escuchando canal: {self.config.redis_channel}")
        
        async for message in pubsub.listen():
            if not self._running:
                break
            if message["type"] == "message":
                await self._handle_message(message["data"])
        
        await pubsub.unsubscribe(self.config.redis_channel)
    
    async def _handle_message(self, data: str) -> None:
        """Procesa un mensaje JSON de Redis."""
        try:
            event = json.loads(data)
            await self.process_event(event)
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando JSON: {e}")
        except Exception as e:
            logger.error(f"Error procesando evento: {e}")
    
    # =========================================================================
    # EVENT PROCESSING
    # =========================================================================
    
    async def process_event(self, event: dict[str, Any]) -> Optional[TradeRecord]:
        """Procesa un evento de trade según su tipo."""
        event_type = event.get("event_type")
        
        if event_type == TradeEventType.TRADE_OPEN.value:
            return await self._handle_trade_open(event)
        elif event_type == TradeEventType.TRADE_CLOSE.value:
            return await self._handle_trade_close(event)
        elif event_type == TradeEventType.TRADE_CANCEL.value:
            return await self._handle_trade_cancel(event)
        else:
            logger.warning(f"Tipo de evento desconocido: {event_type}")
            return None
    
    async def _handle_trade_open(self, event: dict) -> Optional[TradeRecord]:
        """Procesa apertura de trade."""
        try:
            open_event = TradeOpenEvent(**event)
            
            # Enriquecer con contexto
            if self.config.enrich_with_regime:
                regime_data = await self._get_current_regime(open_event.symbol)
                open_event.regime_at_entry = regime_data.get("regime")
                open_event.regime_confidence = regime_data.get("confidence")
            
            if self.config.enrich_with_indicators:
                open_event.signals_at_entry = await self._get_indicators_snapshot(
                    open_event.symbol
                )
            
            record = trade_event_to_record(open_event)
            await self._insert_trade(record)
            
            logger.info(f"Trade abierto: {record.trade_id} - {record.symbol}")
            
            if self._on_trade_open:
                await self._on_trade_open(record)
            
            return record
        except Exception as e:
            logger.error(f"Error en TRADE_OPEN: {e}")
            return None
    
    async def _handle_trade_close(self, event: dict) -> Optional[TradeRecord]:
        """Procesa cierre de trade."""
        try:
            close_event = TradeCloseEvent(**event)
            existing = await self._get_trade(close_event.trade_id)
            
            if not existing:
                logger.error(f"Trade no encontrado: {close_event.trade_id}")
                return None
            
            # Actualizar datos de cierre
            existing.status = TradeStatus.CLOSED
            existing.exit_price = close_event.exit_price
            existing.exit_timestamp = close_event.timestamp
            existing.commission_eur = close_event.commission_eur or Decimal("0")
            existing.slippage_eur = close_event.slippage_eur or Decimal("0")
            
            # Calcular PnL
            pnl_data = self._trade_calculator.calculate_pnl_for_trade(existing)
            existing.pnl_eur = pnl_data["pnl_eur"]
            existing.pnl_pct = pnl_data["pnl_pct"]
            existing.pnl_r_multiple = pnl_data["pnl_r_multiple"]
            
            # Duración
            if existing.entry_timestamp and existing.exit_timestamp:
                duration = existing.exit_timestamp - existing.entry_timestamp
                existing.holding_duration_hours = round(
                    duration.total_seconds() / 3600, 2
                )
            
            await self._update_trade(existing)
            
            logger.info(
                f"Trade cerrado: {existing.trade_id} - "
                f"PnL: {existing.pnl_eur}€ ({existing.pnl_pct}%)"
            )
            
            if self._on_trade_close:
                await self._on_trade_close(existing)
            
            return existing
        except Exception as e:
            logger.error(f"Error en TRADE_CLOSE: {e}")
            return None
    
    async def _handle_trade_cancel(self, event: dict) -> Optional[TradeRecord]:
        """Procesa cancelación de trade."""
        try:
            trade_id = UUID(event["trade_id"])
            await self._update_trade_status(trade_id, TradeStatus.CANCELLED)
            logger.info(f"Trade cancelado: {trade_id}")
            return None
        except Exception as e:
            logger.error(f"Error en TRADE_CANCEL: {e}")
            return None
    
    # =========================================================================
    # CONTEXT ENRICHMENT
    # =========================================================================
    
    async def _get_current_regime(self, symbol: str) -> dict[str, Any]:
        """Obtiene régimen actual desde mcp-ml-models."""
        # TODO: Integrar con mcp-ml-models
        return {"regime": RegimeType.UNKNOWN, "confidence": None}
    
    async def _get_indicators_snapshot(self, symbol: str) -> dict[str, float]:
        """Obtiene snapshot de indicadores técnicos."""
        # TODO: Integrar con mcp-technical o Feature Store
        return {"rsi_14": None, "macd": None, "adx_14": None}
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _insert_trade(self, trade: TradeRecord) -> None:
        """Inserta un nuevo trade en PostgreSQL."""
        query = """
            INSERT INTO metrics.trades (
                trade_id, strategy_id, model_id, agent_id, experiment_id,
                symbol, direction, status,
                entry_price, stop_loss, take_profit,
                size_shares, size_value_eur,
                regime_at_entry, regime_confidence,
                entry_timestamp, reasoning, signals_at_entry, metadata,
                created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21
            )
        """
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                trade.trade_id, trade.strategy_id, trade.model_id,
                trade.agent_id, trade.experiment_id, trade.symbol,
                trade.direction.value if hasattr(trade.direction, 'value') else trade.direction,
                trade.status.value if hasattr(trade.status, 'value') else trade.status,
                trade.entry_price, trade.stop_loss, trade.take_profit,
                trade.size_shares, trade.size_value_eur,
                trade.regime_at_entry.value if trade.regime_at_entry else None,
                trade.regime_confidence, trade.entry_timestamp,
                trade.reasoning,
                json.dumps(trade.signals_at_entry) if trade.signals_at_entry else None,
                json.dumps(trade.metadata) if trade.metadata else None,
                trade.created_at, trade.updated_at
            )
    
    async def _update_trade(self, trade: TradeRecord) -> None:
        """Actualiza un trade existente (cierre)."""
        query = """
            UPDATE metrics.trades SET
                status = $2, exit_price = $3, exit_timestamp = $4,
                pnl_eur = $5, pnl_pct = $6, pnl_r_multiple = $7,
                commission_eur = $8, slippage_eur = $9,
                holding_duration_hours = $10, metadata = $11, updated_at = $12
            WHERE trade_id = $1
        """
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query, trade.trade_id,
                trade.status.value if hasattr(trade.status, 'value') else trade.status,
                trade.exit_price, trade.exit_timestamp,
                trade.pnl_eur, trade.pnl_pct, trade.pnl_r_multiple,
                trade.commission_eur, trade.slippage_eur,
                trade.holding_duration_hours,
                json.dumps(trade.metadata) if trade.metadata else None,
                datetime.utcnow()
            )
    
    async def _update_trade_status(self, trade_id: UUID, status: TradeStatus) -> None:
        """Actualiza solo el status de un trade."""
        query = "UPDATE metrics.trades SET status = $2, updated_at = $3 WHERE trade_id = $1"
        async with self._pg_pool.acquire() as conn:
            await conn.execute(query, trade_id, status.value, datetime.utcnow())
    
    async def _get_trade(self, trade_id: UUID) -> Optional[TradeRecord]:
        """Obtiene un trade de la base de datos."""
        query = "SELECT * FROM metrics.trades WHERE trade_id = $1"
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, trade_id)
            return self._row_to_trade_record(row) if row else None
    
    def _row_to_trade_record(self, row: asyncpg.Record) -> TradeRecord:
        """Convierte row de PostgreSQL a TradeRecord."""
        return TradeRecord(
            trade_id=row["trade_id"],
            strategy_id=row["strategy_id"],
            model_id=row["model_id"],
            agent_id=row["agent_id"],
            experiment_id=row["experiment_id"],
            symbol=row["symbol"],
            direction=row["direction"],
            status=row["status"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            size_shares=row["size_shares"],
            size_value_eur=row["size_value_eur"],
            pnl_eur=row["pnl_eur"],
            pnl_pct=row["pnl_pct"],
            pnl_r_multiple=row["pnl_r_multiple"],
            commission_eur=row["commission_eur"] or Decimal("0"),
            slippage_eur=row["slippage_eur"] or Decimal("0"),
            regime_at_entry=RegimeType(row["regime_at_entry"]) if row["regime_at_entry"] else None,
            regime_confidence=row["regime_confidence"],
            entry_timestamp=row["entry_timestamp"],
            exit_timestamp=row["exit_timestamp"],
            holding_duration_hours=row["holding_duration_hours"],
            reasoning=row["reasoning"],
            signals_at_entry=json.loads(row["signals_at_entry"]) if row["signals_at_entry"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    
    # =========================================================================
    # QUERY METHODS
    # =========================================================================
    
    async def get_open_trades(self, strategy_id: Optional[str] = None) -> list[TradeRecord]:
        """Obtiene trades abiertos, opcionalmente filtrados por estrategia."""
        if strategy_id:
            query = "SELECT * FROM metrics.trades WHERE status = 'OPEN' AND strategy_id = $1"
            params = [strategy_id]
        else:
            query = "SELECT * FROM metrics.trades WHERE status = 'OPEN'"
            params = []
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_trade_record(row) for row in rows]
    
    async def get_closed_trades(
        self,
        strategy_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> list[TradeRecord]:
        """Obtiene trades cerrados con filtros."""
        conditions = ["status = 'CLOSED'"]
        params = []
        
        if strategy_id:
            params.append(strategy_id)
            conditions.append(f"strategy_id = ${len(params)}")
        
        if since:
            params.append(since)
            conditions.append(f"exit_timestamp >= ${len(params)}")
        
        params.append(limit)
        query = f"""
            SELECT * FROM metrics.trades 
            WHERE {' AND '.join(conditions)}
            ORDER BY exit_timestamp DESC
            LIMIT ${len(params)}
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_trade_record(row) for row in rows]
```

---

## C1.3.3: Event Publisher Helper

**Archivo:** `src/metrics/publisher.py`

```python
"""
TradeEventPublisher - Helper para publicar eventos de trade.

Usado por estrategias y agentes para notificar trades.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

import aioredis

from .schemas import TradeOpenEvent, TradeCloseEvent, TradeDirection

logger = logging.getLogger(__name__)


class TradeEventPublisher:
    """
    Publisher de eventos de trade a Redis.
    
    Uso:
        publisher = TradeEventPublisher()
        await publisher.connect()
        
        trade_id = await publisher.publish_trade_open(
            strategy_id="etf_momentum",
            symbol="VWCE.DE",
            direction="LONG",
            entry_price=100.50,
            size_shares=10,
            size_value_eur=1005.00
        )
        
        await publisher.publish_trade_close(
            trade_id=trade_id,
            exit_price=103.20,
            close_reason="take_profit"
        )
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        channel: str = "trades"
    ):
        self.redis_url = redis_url
        self.channel = channel
        self._redis: Optional[aioredis.Redis] = None
    
    async def connect(self) -> None:
        """Establece conexión con Redis."""
        self._redis = await aioredis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self) -> None:
        """Cierra conexión."""
        if self._redis:
            await self._redis.close()
    
    async def publish_trade_open(
        self,
        strategy_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        size_shares: float,
        size_value_eur: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        model_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        experiment_id: Optional[UUID] = None,
        reasoning: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> UUID:
        """
        Publica evento de apertura de trade.
        
        Returns:
            UUID del trade creado
        """
        trade_id = uuid4()
        
        event = TradeOpenEvent(
            trade_id=trade_id,
            strategy_id=strategy_id,
            symbol=symbol,
            direction=TradeDirection(direction),
            entry_price=Decimal(str(entry_price)),
            size_shares=Decimal(str(size_shares)),
            size_value_eur=Decimal(str(size_value_eur)),
            stop_loss=Decimal(str(stop_loss)) if stop_loss else None,
            take_profit=Decimal(str(take_profit)) if take_profit else None,
            model_id=model_id,
            agent_id=agent_id,
            experiment_id=experiment_id,
            reasoning=reasoning,
            metadata=metadata
        )
        
        await self._publish(event.model_dump(mode='json'))
        
        logger.info(f"Publicado TRADE_OPEN: {trade_id} - {symbol} {direction}")
        
        return trade_id
    
    async def publish_trade_close(
        self,
        trade_id: UUID,
        exit_price: float,
        close_reason: str = "manual",
        commission_eur: float = 0,
        slippage_eur: float = 0,
        metadata: Optional[dict] = None
    ) -> None:
        """Publica evento de cierre de trade."""
        event = TradeCloseEvent(
            trade_id=trade_id,
            exit_price=Decimal(str(exit_price)),
            close_reason=close_reason,
            commission_eur=Decimal(str(commission_eur)),
            slippage_eur=Decimal(str(slippage_eur)),
            metadata=metadata
        )
        
        await self._publish(event.model_dump(mode='json'))
        
        logger.info(f"Publicado TRADE_CLOSE: {trade_id} @ {exit_price}")
    
    async def publish_trade_cancel(
        self,
        trade_id: UUID,
        reason: str = "cancelled"
    ) -> None:
        """Publica evento de cancelación de trade."""
        event = {
            "event_type": "TRADE_CANCEL",
            "trade_id": str(trade_id),
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        }
        
        await self._publish(event)
        
        logger.info(f"Publicado TRADE_CANCEL: {trade_id}")
    
    async def _publish(self, event: dict) -> None:
        """Publica evento a Redis."""
        if not self._redis:
            raise RuntimeError("Publisher no conectado. Llamar connect() primero.")
        
        await self._redis.publish(self.channel, json.dumps(event, default=str))
```

---

## C1.3.4: Tests del Collector

**Archivo:** `src/metrics/tests/test_collector.py`

```python
"""
Tests para MetricsCollector.
"""

import pytest
import asyncio
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from ..collector import MetricsCollector
from ..schemas import (
    TradeOpenEvent, TradeCloseEvent, TradeRecord,
    TradeDirection, TradeStatus, MetricsConfig
)


@pytest.fixture
def config():
    return MetricsConfig(
        redis_channel="test_trades",
        enrich_with_regime=False,  # Desactivar para tests
        enrich_with_indicators=False
    )


@pytest.fixture
def collector(config):
    return MetricsCollector(
        config=config,
        redis_url="redis://localhost:6379",
        postgres_dsn="postgresql://test:test@localhost:5432/test"
    )


class TestMetricsCollector:
    """Tests para MetricsCollector."""
    
    @pytest.mark.asyncio
    async def test_process_trade_open_event(self, collector):
        """Test procesamiento de evento TRADE_OPEN."""
        # Mock de conexiones
        collector._pg_pool = AsyncMock()
        collector._pg_pool.acquire = AsyncMock()
        mock_conn = AsyncMock()
        collector._pg_pool.acquire.return_value.__aenter__ = AsyncMock(
            return_value=mock_conn
        )
        
        event = {
            "event_type": "TRADE_OPEN",
            "trade_id": str(uuid4()),
            "strategy_id": "test_strategy",
            "symbol": "TEST",
            "direction": "LONG",
            "entry_price": "100.00",
            "size_shares": "10",
            "size_value_eur": "1000.00",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await collector.process_event(event)
        
        assert result is not None
        assert result.strategy_id == "test_strategy"
        assert result.symbol == "TEST"
        assert result.status == TradeStatus.OPEN
    
    @pytest.mark.asyncio
    async def test_process_trade_close_event(self, collector):
        """Test procesamiento de evento TRADE_CLOSE."""
        trade_id = uuid4()
        
        # Mock trade existente
        existing_trade = TradeRecord(
            trade_id=trade_id,
            strategy_id="test_strategy",
            symbol="TEST",
            direction=TradeDirection.LONG,
            status=TradeStatus.OPEN,
            entry_price=Decimal("100.00"),
            size_shares=Decimal("10"),
            size_value_eur=Decimal("1000.00"),
            entry_timestamp=datetime.utcnow()
        )
        
        collector._get_trade = AsyncMock(return_value=existing_trade)
        collector._update_trade = AsyncMock()
        
        event = {
            "event_type": "TRADE_CLOSE",
            "trade_id": str(trade_id),
            "exit_price": "110.00",
            "close_reason": "take_profit",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        result = await collector.process_event(event)
        
        assert result is not None
        assert result.status == TradeStatus.CLOSED
        assert result.exit_price == Decimal("110.00")
        assert result.pnl_eur is not None
        assert float(result.pnl_eur) > 0  # Ganancia en LONG
    
    @pytest.mark.asyncio
    async def test_pnl_calculation_long(self, collector):
        """Test cálculo de PnL para trade LONG."""
        trade = TradeRecord(
            trade_id=uuid4(),
            strategy_id="test",
            symbol="TEST",
            direction=TradeDirection.LONG,
            status=TradeStatus.CLOSED,
            entry_price=Decimal("100"),
            exit_price=Decimal("110"),
            stop_loss=Decimal("95"),
            size_shares=Decimal("10"),
            size_value_eur=Decimal("1000"),
            commission_eur=Decimal("2"),
            slippage_eur=Decimal("1"),
            entry_timestamp=datetime.utcnow(),
            exit_timestamp=datetime.utcnow()
        )
        
        pnl_data = collector._trade_calculator.calculate_pnl_for_trade(trade)
        
        # PnL bruto: (110-100)*10 = 100
        # PnL neto: 100 - 2 - 1 = 97
        assert pnl_data["pnl_eur"] == Decimal("97")
        
        # R-Multiple: 97 / ((100-95)*10) = 97/50 = 1.94
        assert abs(pnl_data["pnl_r_multiple"] - 1.94) < 0.01
    
    @pytest.mark.asyncio
    async def test_pnl_calculation_short(self, collector):
        """Test cálculo de PnL para trade SHORT."""
        trade = TradeRecord(
            trade_id=uuid4(),
            strategy_id="test",
            symbol="TEST",
            direction=TradeDirection.SHORT,
            status=TradeStatus.CLOSED,
            entry_price=Decimal("100"),
            exit_price=Decimal("90"),  # Baja = ganancia en SHORT
            stop_loss=Decimal("105"),
            size_shares=Decimal("10"),
            size_value_eur=Decimal("1000"),
            commission_eur=Decimal("0"),
            slippage_eur=Decimal("0"),
            entry_timestamp=datetime.utcnow(),
            exit_timestamp=datetime.utcnow()
        )
        
        pnl_data = collector._trade_calculator.calculate_pnl_for_trade(trade)
        
        # PnL: (100-90)*10 = 100
        assert pnl_data["pnl_eur"] == Decimal("100")
    
    @pytest.mark.asyncio
    async def test_unknown_event_type(self, collector):
        """Test que eventos desconocidos retornan None."""
        event = {
            "event_type": "UNKNOWN_EVENT",
            "data": "test"
        }
        
        result = await collector.process_event(event)
        
        assert result is None
```

---

## C1.3.5: Ejemplo de Integración con Estrategia

```python
"""
Ejemplo de cómo integrar el publisher en una estrategia.

Archivo: src/strategies/swing/etf_momentum.py (fragmento)
"""

from src.metrics.publisher import TradeEventPublisher

class ETFMomentumStrategy(TradingStrategy):
    
    def __init__(self, config):
        super().__init__(config)
        self._publisher = TradeEventPublisher()
    
    async def initialize(self):
        await self._publisher.connect()
    
    async def execute_signal(self, signal: Signal) -> None:
        """Ejecuta una señal y notifica al sistema de métricas."""
        
        # ... lógica de ejecución con broker ...
        
        # Notificar apertura de trade
        trade_id = await self._publisher.publish_trade_open(
            strategy_id=self.strategy_id,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=execution_price,
            size_shares=position_size,
            size_value_eur=position_value,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            model_id=self._regime_model_id,  # Si usa ML
            reasoning=signal.reasoning,
            metadata={
                "signal_confidence": signal.confidence,
                "regime_at_signal": signal.regime_at_signal
            }
        )
        
        # Guardar trade_id para cierre posterior
        self._open_trades[signal.symbol] = trade_id
    
    async def close_position(self, symbol: str, exit_price: float, reason: str):
        """Cierra posición y notifica."""
        trade_id = self._open_trades.get(symbol)
        
        if trade_id:
            await self._publisher.publish_trade_close(
                trade_id=trade_id,
                exit_price=exit_price,
                close_reason=reason,
                commission_eur=self._calculate_commission(exit_price)
            )
            del self._open_trades[symbol]
```

---

## Subtareas Completadas C1.3

```
TAREA C1.3: METRICS COLLECTOR
────────────────────────────────────────────────────────────────────────────
[ ] Archivo src/metrics/collector.py creado
[ ] MetricsCollector clase principal
[ ] Lifecycle methods (start, stop, connect, disconnect)
[ ] Event listening desde Redis pub/sub
[ ] Handler para TRADE_OPEN
[ ] Handler para TRADE_CLOSE
[ ] Handler para TRADE_CANCEL
[ ] Context enrichment (régimen, indicadores) - placeholders
[ ] Database operations (insert, update, get)
[ ] Query methods (get_open_trades, get_closed_trades)
[ ] src/metrics/publisher.py helper para publicar eventos
[ ] Tests unitarios para collector
[ ] Ejemplo de integración con estrategia
```

---

*Fin de Parte 3 - Continúa en Parte 4: MetricsAggregator + ExperimentManager*

---

*Documento de Implementación - Fase C1: Sistema de Métricas*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
# Fase C1: Sistema de Métricas - Parte 4

## MetricsAggregator + ExperimentManager (A/B Testing)

---

# Tarea C1.4: MetricsAggregator

**Estado:** ⬜ Pendiente  
**Duración estimada:** 3-4 horas  
**Dependencias:** C1.1 (Schemas), C1.2 (Calculators), C1.3 (Collector)

**Objetivo:** Implementar el componente que agrega métricas por diferentes dimensiones (estrategia, modelo, régimen, período) y las persiste en PostgreSQL.

---

## C1.4.1: Diagrama de Agregación

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         METRICS AGGREGATION FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   TRIGGER                                                                       │
│   ═══════                                                                       │
│   • Scheduler (cada 5 min)                                                      │
│   • On-demand (después de trade close)                                          │
│   • Manual (API call)                                                           │
│                                                                                 │
│                         ┌───────────────────────────────┐                       │
│                         │     MetricsAggregator         │                       │
│                         └───────────────┬───────────────┘                       │
│                                         │                                       │
│              ┌──────────────────────────┼──────────────────────────┐            │
│              │                          │                          │            │
│              ▼                          ▼                          ▼            │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐    │
│   │  aggregate_by_      │  │  aggregate_by_      │  │  aggregate_by_      │    │
│   │  strategy()         │  │  model()            │  │  regime()           │    │
│   └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘    │
│              │                        │                        │               │
│              └────────────────────────┼────────────────────────┘               │
│                                       │                                        │
│                                       ▼                                        │
│                         ┌───────────────────────────────┐                      │
│                         │   Para cada grupo de trades:  │                      │
│                         │   ─────────────────────────── │                      │
│                         │   1. RiskMetricsCalculator    │                      │
│                         │   2. TradeMetricsCalculator   │                      │
│                         │   3. TimeMetricsCalculator    │                      │
│                         └───────────────┬───────────────┘                      │
│                                         │                                      │
│                                         ▼                                      │
│                         ┌───────────────────────────────┐                      │
│                         │   AggregatedMetrics           │                      │
│                         │   (combina Risk+Trade+Time)   │                      │
│                         └───────────────┬───────────────┘                      │
│                                         │                                      │
│              ┌──────────────────────────┼──────────────────────────┐           │
│              │                          │                          │           │
│              ▼                          ▼                          ▼           │
│   ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐   │
│   │ strategy_performance│  │ model_performance   │  │ experiment_results  │   │
│   │ (UPSERT)            │  │ (UPSERT)            │  │ (si aplica)         │   │
│   └─────────────────────┘  └─────────────────────┘  └─────────────────────┘   │
│                                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## C1.4.2: Implementación Principal

**Archivo:** `src/metrics/aggregator.py`

```python
"""
MetricsAggregator - Agrega métricas por dimensiones.

Este componente:
1. Lee trades cerrados de PostgreSQL
2. Agrupa por dimensión (estrategia, modelo, régimen, período)
3. Calcula métricas usando los calculators
4. Persiste resultados en tablas de agregación

Uso:
    aggregator = MetricsAggregator(config, pg_pool)
    
    # Agregación completa
    await aggregator.run_full_aggregation()
    
    # Por dimensión específica
    metrics = await aggregator.aggregate_by_strategy("etf_momentum", PeriodType.DAILY)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Sequence
from enum import Enum

import asyncpg
import numpy as np

from .schemas import (
    TradeRecord, AggregatedMetrics, RiskMetrics, TradeMetrics, TimeMetrics,
    PeriodType, RegimeType, MetricsConfig, TradeStatus
)
from .calculators import (
    RiskMetricsCalculator, TradeMetricsCalculator, TimeMetricsCalculator,
    RiskCalculatorConfig, TradeCalculatorConfig, TimeCalculatorConfig
)

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """
    Agregador de métricas de trading.
    
    Calcula métricas agregadas por estrategia, modelo, régimen y período.
    """
    
    def __init__(
        self,
        config: MetricsConfig,
        pg_pool: asyncpg.Pool
    ):
        self.config = config
        self._pg_pool = pg_pool
        
        # Inicializar calculadores
        self._risk_calc = RiskMetricsCalculator(
            RiskCalculatorConfig(
                risk_free_rate=config.risk_free_rate,
                trading_days_per_year=config.trading_days_per_year,
                var_confidence=config.var_confidence
            )
        )
        self._trade_calc = TradeMetricsCalculator(
            TradeCalculatorConfig(min_trades=config.min_trades_for_metrics)
        )
        self._time_calc = TimeMetricsCalculator(
            TimeCalculatorConfig(min_trades=config.min_trades_for_metrics)
        )
    
    # =========================================================================
    # MAIN AGGREGATION METHODS
    # =========================================================================
    
    async def run_full_aggregation(self) -> dict[str, int]:
        """
        Ejecuta agregación completa para todas las dimensiones y períodos.
        
        Returns:
            Dict con conteo de registros actualizados por tipo
        """
        logger.info("Iniciando agregación completa...")
        
        results = {
            "strategy_performance": 0,
            "model_performance": 0
        }
        
        # Obtener estrategias activas
        strategies = await self._get_distinct_strategies()
        
        for strategy_id in strategies:
            for period_type in PeriodType:
                try:
                    await self.aggregate_by_strategy(strategy_id, period_type)
                    results["strategy_performance"] += 1
                except Exception as e:
                    logger.error(f"Error agregando {strategy_id}/{period_type}: {e}")
        
        # Obtener modelos activos
        models = await self._get_distinct_models()
        
        for model_id in models:
            if model_id:  # Puede ser None
                try:
                    await self.aggregate_by_model(model_id)
                    results["model_performance"] += 1
                except Exception as e:
                    logger.error(f"Error agregando modelo {model_id}: {e}")
        
        logger.info(f"Agregación completa: {results}")
        return results
    
    async def aggregate_by_strategy(
        self,
        strategy_id: str,
        period_type: PeriodType,
        force_recalculate: bool = False
    ) -> Optional[AggregatedMetrics]:
        """
        Agrega métricas para una estrategia en un período.
        
        Args:
            strategy_id: ID de la estrategia
            period_type: Tipo de período (hourly, daily, etc.)
            force_recalculate: Si True, recalcula aunque exista
        
        Returns:
            AggregatedMetrics calculadas
        """
        # Determinar rango de tiempo
        period_start, period_end = self._get_period_range(period_type)
        
        # Obtener trades del período
        trades = await self._get_trades_for_strategy(
            strategy_id, period_start, period_end
        )
        
        if not trades:
            logger.debug(f"Sin trades para {strategy_id} en {period_type}")
            return None
        
        # Calcular métricas
        metrics = self._calculate_aggregated_metrics(
            trades=trades,
            strategy_id=strategy_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end
        )
        
        # Persistir
        await self._upsert_strategy_performance(metrics)
        
        logger.info(
            f"Agregado {strategy_id}/{period_type}: "
            f"{metrics.trade.total_trades} trades, "
            f"Sharpe: {metrics.risk.sharpe_ratio}"
        )
        
        return metrics
    
    async def aggregate_by_model(
        self,
        model_id: str,
        since: Optional[datetime] = None
    ) -> Optional[AggregatedMetrics]:
        """
        Agrega métricas para un modelo ML.
        
        Args:
            model_id: ID del modelo (ej: "hmm_v1")
            since: Fecha desde la que calcular (default: últimos 30 días)
        
        Returns:
            AggregatedMetrics del modelo
        """
        if since is None:
            since = datetime.utcnow() - timedelta(days=30)
        
        trades = await self._get_trades_for_model(model_id, since)
        
        if not trades:
            return None
        
        metrics = self._calculate_aggregated_metrics(
            trades=trades,
            model_id=model_id,
            period_type=PeriodType.ALL_TIME,
            period_start=since,
            period_end=datetime.utcnow()
        )
        
        # Calcular accuracy de predicción de régimen
        regime_accuracy = self._calculate_regime_accuracy(trades)
        if metrics.risk.sharpe_ratio is not None:
            # Añadir accuracy a metadata si es relevante
            pass
        
        await self._upsert_model_performance(model_id, metrics, regime_accuracy)
        
        return metrics
    
    async def aggregate_by_regime(
        self,
        regime: RegimeType,
        period_type: PeriodType = PeriodType.ALL_TIME
    ) -> Optional[AggregatedMetrics]:
        """
        Agrega métricas por régimen de mercado.
        
        Args:
            regime: Tipo de régimen
            period_type: Período de agregación
        
        Returns:
            AggregatedMetrics para el régimen
        """
        period_start, period_end = self._get_period_range(period_type)
        
        trades = await self._get_trades_for_regime(regime, period_start, period_end)
        
        if not trades:
            return None
        
        return self._calculate_aggregated_metrics(
            trades=trades,
            regime=regime,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end
        )
    
    # =========================================================================
    # CALCULATION METHODS
    # =========================================================================
    
    def _calculate_aggregated_metrics(
        self,
        trades: Sequence[TradeRecord],
        period_type: PeriodType,
        period_start: datetime,
        period_end: datetime,
        strategy_id: Optional[str] = None,
        model_id: Optional[str] = None,
        regime: Optional[RegimeType] = None
    ) -> AggregatedMetrics:
        """
        Calcula métricas agregadas para un conjunto de trades.
        
        Args:
            trades: Lista de trades cerrados
            period_type: Tipo de período
            period_start: Inicio del período
            period_end: Fin del período
            strategy_id: ID de estrategia (opcional)
            model_id: ID de modelo (opcional)
            regime: Régimen (opcional)
        
        Returns:
            AggregatedMetrics completas
        """
        # Preparar datos para cálculos
        returns = self._extract_returns(trades)
        equity_curve = self._build_equity_curve(trades)
        
        # Calcular cada tipo de métrica
        risk_metrics = self._risk_calc.calculate(returns, equity_curve)
        trade_metrics = self._trade_calc.calculate(trades)
        time_metrics = self._time_calc.calculate(trades)
        
        # Calcular distribución por régimen
        trades_by_regime = self._count_trades_by_regime(trades)
        pnl_by_regime = self._sum_pnl_by_regime(trades)
        
        # Determinar si cumple mínimo de trades
        min_trades_met = len(trades) >= self.config.min_trades_for_metrics
        
        return AggregatedMetrics(
            strategy_id=strategy_id,
            model_id=model_id,
            regime=regime,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            risk=risk_metrics,
            trade=trade_metrics,
            time=time_metrics,
            trades_by_regime=trades_by_regime,
            pnl_by_regime=pnl_by_regime,
            min_trades_met=min_trades_met
        )
    
    def _extract_returns(self, trades: Sequence[TradeRecord]) -> np.ndarray:
        """Extrae array de retornos porcentuales de los trades."""
        returns = []
        for trade in trades:
            if trade.pnl_pct is not None:
                returns.append(trade.pnl_pct / 100)  # Convertir a decimal
        return np.array(returns)
    
    def _build_equity_curve(
        self,
        trades: Sequence[TradeRecord],
        initial_equity: float = 25000.0
    ) -> np.ndarray:
        """
        Construye curva de equity a partir de trades.
        
        Args:
            trades: Trades ordenados cronológicamente
            initial_equity: Equity inicial (paper trading)
        
        Returns:
            Array con valores de equity
        """
        equity = [initial_equity]
        current = initial_equity
        
        # Ordenar por fecha de cierre
        sorted_trades = sorted(
            [t for t in trades if t.exit_timestamp],
            key=lambda t: t.exit_timestamp
        )
        
        for trade in sorted_trades:
            if trade.pnl_eur:
                current += float(trade.pnl_eur)
                equity.append(current)
        
        return np.array(equity)
    
    def _count_trades_by_regime(
        self,
        trades: Sequence[TradeRecord]
    ) -> dict[str, int]:
        """Cuenta trades por régimen."""
        counts = {}
        for trade in trades:
            regime = trade.regime_at_entry.value if trade.regime_at_entry else "UNKNOWN"
            counts[regime] = counts.get(regime, 0) + 1
        return counts
    
    def _sum_pnl_by_regime(
        self,
        trades: Sequence[TradeRecord]
    ) -> dict[str, float]:
        """Suma PnL por régimen."""
        sums = {}
        for trade in trades:
            if trade.pnl_eur is not None:
                regime = trade.regime_at_entry.value if trade.regime_at_entry else "UNKNOWN"
                sums[regime] = sums.get(regime, 0.0) + float(trade.pnl_eur)
        return sums
    
    def _calculate_regime_accuracy(
        self,
        trades: Sequence[TradeRecord]
    ) -> Optional[float]:
        """
        Calcula accuracy del modelo en predecir régimen favorable.
        
        Un trade es "correcto" si:
        - Régimen BULL y trade ganador
        - Régimen BEAR y no se operó (o trade perdedor pequeño)
        
        Returns:
            Accuracy entre 0 y 1
        """
        if not trades:
            return None
        
        correct = 0
        total = 0
        
        for trade in trades:
            if trade.regime_at_entry and trade.pnl_eur is not None:
                total += 1
                regime = trade.regime_at_entry
                pnl = float(trade.pnl_eur)
                
                # Simplificación: BULL debería dar ganancias en LONG
                if regime == RegimeType.BULL and pnl > 0:
                    correct += 1
                elif regime == RegimeType.BEAR and pnl < 0:
                    # En BEAR, perder poco es "esperado" si se operó
                    correct += 1
                elif regime == RegimeType.SIDEWAYS:
                    # Sideways: cualquier resultado pequeño es OK
                    if abs(pnl) < 50:  # Threshold arbitrario
                        correct += 1
        
        return correct / total if total > 0 else None
    
    # =========================================================================
    # PERIOD HELPERS
    # =========================================================================
    
    def _get_period_range(
        self,
        period_type: PeriodType
    ) -> tuple[datetime, datetime]:
        """
        Determina el rango de fechas para un tipo de período.
        
        Returns:
            Tuple (period_start, period_end)
        """
        now = datetime.utcnow()
        
        if period_type == PeriodType.HOURLY:
            # Última hora completa
            end = now.replace(minute=0, second=0, microsecond=0)
            start = end - timedelta(hours=1)
        
        elif period_type == PeriodType.DAILY:
            # Último día completo
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        
        elif period_type == PeriodType.WEEKLY:
            # Última semana completa (lunes a domingo)
            days_since_monday = now.weekday()
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = end - timedelta(days=days_since_monday)
            start = end - timedelta(days=7)
        
        elif period_type == PeriodType.MONTHLY:
            # Último mes completo
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start = (end - timedelta(days=1)).replace(day=1)
        
        else:  # ALL_TIME
            start = datetime(2020, 1, 1)  # Fecha arbitraria de inicio
            end = now
        
        return start, end
    
    # =========================================================================
    # DATABASE QUERIES
    # =========================================================================
    
    async def _get_distinct_strategies(self) -> list[str]:
        """Obtiene lista de estrategias con trades."""
        query = """
            SELECT DISTINCT strategy_id 
            FROM metrics.trades 
            WHERE status = 'CLOSED'
        """
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row["strategy_id"] for row in rows]
    
    async def _get_distinct_models(self) -> list[Optional[str]]:
        """Obtiene lista de modelos con trades."""
        query = """
            SELECT DISTINCT model_id 
            FROM metrics.trades 
            WHERE status = 'CLOSED' AND model_id IS NOT NULL
        """
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query)
            return [row["model_id"] for row in rows]
    
    async def _get_trades_for_strategy(
        self,
        strategy_id: str,
        start: datetime,
        end: datetime
    ) -> list[TradeRecord]:
        """Obtiene trades cerrados de una estrategia en período."""
        query = """
            SELECT * FROM metrics.trades
            WHERE strategy_id = $1
              AND status = 'CLOSED'
              AND exit_timestamp >= $2
              AND exit_timestamp < $3
            ORDER BY exit_timestamp ASC
        """
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, strategy_id, start, end)
            return [self._row_to_trade(row) for row in rows]
    
    async def _get_trades_for_model(
        self,
        model_id: str,
        since: datetime
    ) -> list[TradeRecord]:
        """Obtiene trades cerrados de un modelo."""
        query = """
            SELECT * FROM metrics.trades
            WHERE model_id = $1
              AND status = 'CLOSED'
              AND exit_timestamp >= $2
            ORDER BY exit_timestamp ASC
        """
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, model_id, since)
            return [self._row_to_trade(row) for row in rows]
    
    async def _get_trades_for_regime(
        self,
        regime: RegimeType,
        start: datetime,
        end: datetime
    ) -> list[TradeRecord]:
        """Obtiene trades cerrados en un régimen."""
        query = """
            SELECT * FROM metrics.trades
            WHERE regime_at_entry = $1
              AND status = 'CLOSED'
              AND exit_timestamp >= $2
              AND exit_timestamp < $3
            ORDER BY exit_timestamp ASC
        """
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, regime.value, start, end)
            return [self._row_to_trade(row) for row in rows]
    
    def _row_to_trade(self, row: asyncpg.Record) -> TradeRecord:
        """Convierte row a TradeRecord (simplificado)."""
        return TradeRecord(
            trade_id=row["trade_id"],
            strategy_id=row["strategy_id"],
            model_id=row["model_id"],
            agent_id=row["agent_id"],
            experiment_id=row["experiment_id"],
            symbol=row["symbol"],
            direction=row["direction"],
            status=row["status"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            size_shares=row["size_shares"],
            size_value_eur=row["size_value_eur"],
            pnl_eur=row["pnl_eur"],
            pnl_pct=row["pnl_pct"],
            pnl_r_multiple=row["pnl_r_multiple"],
            commission_eur=row["commission_eur"] or Decimal("0"),
            slippage_eur=row["slippage_eur"] or Decimal("0"),
            regime_at_entry=RegimeType(row["regime_at_entry"]) if row["regime_at_entry"] else None,
            regime_confidence=row["regime_confidence"],
            entry_timestamp=row["entry_timestamp"],
            exit_timestamp=row["exit_timestamp"],
            holding_duration_hours=row["holding_duration_hours"],
            reasoning=row["reasoning"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )
    
    # =========================================================================
    # DATABASE PERSISTENCE
    # =========================================================================
    
    async def _upsert_strategy_performance(
        self,
        metrics: AggregatedMetrics
    ) -> None:
        """Inserta o actualiza métricas de estrategia."""
        query = """
            INSERT INTO metrics.strategy_performance (
                strategy_id, period_type, period_start, period_end,
                total_trades, winning_trades, losing_trades,
                total_pnl_eur, avg_pnl_eur, max_win_eur, max_loss_eur,
                win_rate, profit_factor, avg_r_multiple,
                sharpe_ratio, sortino_ratio, calmar_ratio,
                max_drawdown_pct, max_drawdown_eur, var_95_pct,
                avg_holding_hours, avg_trades_per_day,
                trades_by_regime, pnl_by_regime,
                calculated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
                $21, $22, $23, $24, $25
            )
            ON CONFLICT (strategy_id, period_type, period_start)
            DO UPDATE SET
                period_end = EXCLUDED.period_end,
                total_trades = EXCLUDED.total_trades,
                winning_trades = EXCLUDED.winning_trades,
                losing_trades = EXCLUDED.losing_trades,
                total_pnl_eur = EXCLUDED.total_pnl_eur,
                avg_pnl_eur = EXCLUDED.avg_pnl_eur,
                max_win_eur = EXCLUDED.max_win_eur,
                max_loss_eur = EXCLUDED.max_loss_eur,
                win_rate = EXCLUDED.win_rate,
                profit_factor = EXCLUDED.profit_factor,
                avg_r_multiple = EXCLUDED.avg_r_multiple,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                sortino_ratio = EXCLUDED.sortino_ratio,
                calmar_ratio = EXCLUDED.calmar_ratio,
                max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                max_drawdown_eur = EXCLUDED.max_drawdown_eur,
                var_95_pct = EXCLUDED.var_95_pct,
                avg_holding_hours = EXCLUDED.avg_holding_hours,
                avg_trades_per_day = EXCLUDED.avg_trades_per_day,
                trades_by_regime = EXCLUDED.trades_by_regime,
                pnl_by_regime = EXCLUDED.pnl_by_regime,
                calculated_at = EXCLUDED.calculated_at
        """
        
        import json
        
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                metrics.strategy_id,
                metrics.period_type.value,
                metrics.period_start,
                metrics.period_end,
                metrics.trade.total_trades,
                metrics.trade.winning_trades,
                metrics.trade.losing_trades,
                metrics.trade.total_pnl_eur,
                metrics.trade.avg_pnl_eur,
                metrics.trade.max_win_eur,
                metrics.trade.max_loss_eur,
                metrics.trade.win_rate,
                metrics.trade.profit_factor,
                metrics.trade.avg_r_multiple,
                metrics.risk.sharpe_ratio,
                metrics.risk.sortino_ratio,
                metrics.risk.calmar_ratio,
                metrics.risk.max_drawdown_pct,
                metrics.risk.max_drawdown_eur,
                metrics.risk.var_95_pct,
                metrics.time.avg_holding_hours,
                metrics.time.avg_trades_per_day,
                json.dumps(metrics.trades_by_regime) if metrics.trades_by_regime else None,
                json.dumps(metrics.pnl_by_regime) if metrics.pnl_by_regime else None,
                metrics.calculated_at
            )
    
    async def _upsert_model_performance(
        self,
        model_id: str,
        metrics: AggregatedMetrics,
        regime_accuracy: Optional[float]
    ) -> None:
        """Inserta o actualiza métricas de modelo ML."""
        query = """
            INSERT INTO metrics.model_performance (
                model_id, period_start, period_end,
                total_predictions, accuracy_regime,
                sharpe_when_used, total_pnl_eur,
                calculated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (model_id, period_start)
            DO UPDATE SET
                period_end = EXCLUDED.period_end,
                total_predictions = EXCLUDED.total_predictions,
                accuracy_regime = EXCLUDED.accuracy_regime,
                sharpe_when_used = EXCLUDED.sharpe_when_used,
                total_pnl_eur = EXCLUDED.total_pnl_eur,
                calculated_at = EXCLUDED.calculated_at
        """
        
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                model_id,
                metrics.period_start,
                metrics.period_end,
                metrics.trade.total_trades,
                regime_accuracy,
                metrics.risk.sharpe_ratio,
                metrics.trade.total_pnl_eur,
                datetime.utcnow()
            )
```

---

# Tarea C1.5: ExperimentManager (A/B Testing)

**Estado:** ⬜ Pendiente  
**Duración estimada:** 3-4 horas  
**Dependencias:** C1.4 (Aggregator)

**Objetivo:** Implementar sistema de experimentos A/B para comparar estrategias, modelos o configuraciones de forma científica.

---

## C1.5.1: Diagrama de Experimentos A/B

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           A/B EXPERIMENT FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   1. CREATE EXPERIMENT                                                          │
│   ════════════════════                                                          │
│   ┌─────────────────────────────────────────────────────────────┐              │
│   │  ExperimentConfig:                                          │              │
│   │  ─────────────────                                          │              │
│   │  name: "HMM vs Rules Baseline"                              │              │
│   │  variants:                                                  │              │
│   │    - A: {model_id: "hmm_v1"}        ← Control               │              │
│   │    - B: {model_id: "rules_baseline"} ← Treatment            │              │
│   │  primary_metric: "sharpe_ratio"                             │              │
│   │  min_trades_per_variant: 20                                 │              │
│   └─────────────────────────────────────────────────────────────┘              │
│                              │                                                  │
│                              ▼                                                  │
│   2. ASSIGN TRADES                                                              │
│   ════════════════                                                              │
│   ┌─────────────────────────────────────────────────────────────┐              │
│   │                                                             │              │
│   │   Trade 1 ──────► Variant A (50%)                          │              │
│   │   Trade 2 ──────► Variant B (50%)                          │              │
│   │   Trade 3 ──────► Variant A                                │              │
│   │   ...                                                       │              │
│   │                                                             │              │
│   │   Asignación: Random weighted o Round-robin                 │              │
│   │   Persistido en: metrics.trades.experiment_id               │              │
│   │                                                             │              │
│   └─────────────────────────────────────────────────────────────┘              │
│                              │                                                  │
│                              ▼                                                  │
│   3. ANALYZE RESULTS                                                            │
│   ══════════════════                                                            │
│   ┌─────────────────────────────────────────────────────────────┐              │
│   │                                                             │              │
│   │   Variant A (Control)      │    Variant B (Treatment)       │              │
│   │   ─────────────────────────┼────────────────────────────    │              │
│   │   Trades: 25               │    Trades: 23                  │              │
│   │   Sharpe: 1.45             │    Sharpe: 1.82                │              │
│   │   Win Rate: 58%            │    Win Rate: 65%               │              │
│   │   Total PnL: €450          │    Total PnL: €620             │              │
│   │                            │                                │              │
│   │   ───────────────────────────────────────────────────────   │              │
│   │   Winner: Variant B                                         │              │
│   │   Improvement: +25.5% (Sharpe)                              │              │
│   │   p-value: 0.034 (significativo)                            │              │
│   │   Confidence: 95%                                           │              │
│   │                                                             │              │
│   └─────────────────────────────────────────────────────────────┘              │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## C1.5.2: Implementación Principal

**Archivo:** `src/metrics/experiments.py`

```python
"""
ExperimentManager - Sistema de experimentos A/B.

Permite:
1. Crear experimentos con múltiples variantes
2. Asignar trades a variantes
3. Calcular métricas por variante
4. Comparar resultados con significancia estadística

Uso:
    manager = ExperimentManager(config, pg_pool, aggregator)
    
    # Crear experimento
    exp_id = await manager.create_experiment(
        name="HMM vs Rules",
        variants=[
            {"variant_id": "control", "config": {"model_id": "hmm_v1"}},
            {"variant_id": "treatment", "config": {"model_id": "rules_baseline"}}
        ],
        primary_metric="sharpe_ratio"
    )
    
    # Asignar trade a variante
    variant = await manager.assign_variant(exp_id)
    
    # Analizar resultados
    results = await manager.analyze_experiment(exp_id)
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Any
from uuid import UUID, uuid4

import asyncpg
import numpy as np
from scipy import stats

from .schemas import (
    ExperimentConfig, ExperimentVariant, ExperimentResult,
    ExperimentStatus, AggregatedMetrics, MetricsConfig
)
from .aggregator import MetricsAggregator

logger = logging.getLogger(__name__)


class ExperimentManager:
    """
    Manager de experimentos A/B.
    """
    
    def __init__(
        self,
        config: MetricsConfig,
        pg_pool: asyncpg.Pool,
        aggregator: MetricsAggregator
    ):
        self.config = config
        self._pg_pool = pg_pool
        self._aggregator = aggregator
        
        # Cache de experimentos activos
        self._active_experiments: dict[UUID, ExperimentConfig] = {}
    
    # =========================================================================
    # EXPERIMENT LIFECYCLE
    # =========================================================================
    
    async def create_experiment(
        self,
        name: str,
        variants: list[dict[str, Any]],
        primary_metric: str = "sharpe_ratio",
        description: Optional[str] = None,
        auto_conclude_days: int = 30
    ) -> UUID:
        """
        Crea un nuevo experimento A/B.
        
        Args:
            name: Nombre del experimento
            variants: Lista de variantes con config
            primary_metric: Métrica principal para comparación
            description: Descripción opcional
            auto_conclude_days: Días hasta auto-conclusión
        
        Returns:
            UUID del experimento creado
        """
        # Crear variantes
        variant_objects = [
            ExperimentVariant(
                variant_id=v.get("variant_id", f"variant_{i}"),
                name=v.get("name", f"Variant {i}"),
                description=v.get("description"),
                config=v.get("config", {}),
                weight=v.get("weight", 1.0)
            )
            for i, v in enumerate(variants)
        ]
        
        # Crear config
        experiment = ExperimentConfig(
            name=name,
            description=description,
            variants=variant_objects,
            start_date=datetime.utcnow(),
            auto_conclude_days=auto_conclude_days,
            min_trades_per_variant=self.config.experiment_min_trades,
            primary_metric=primary_metric,
            status=ExperimentStatus.RUNNING
        )
        
        # Persistir
        await self._insert_experiment(experiment)
        
        # Cachear
        self._active_experiments[experiment.experiment_id] = experiment
        
        logger.info(
            f"Experimento creado: {experiment.experiment_id} - {name} "
            f"({len(variants)} variantes)"
        )
        
        return experiment.experiment_id
    
    async def start_experiment(self, experiment_id: UUID) -> None:
        """Inicia un experimento en estado DRAFT."""
        await self._update_experiment_status(experiment_id, ExperimentStatus.RUNNING)
        logger.info(f"Experimento iniciado: {experiment_id}")
    
    async def conclude_experiment(
        self,
        experiment_id: UUID,
        reason: str = "manual"
    ) -> dict[str, Any]:
        """
        Concluye un experimento y determina ganador.
        
        Returns:
            Resumen con ganador y estadísticas
        """
        # Analizar antes de concluir
        results = await self.analyze_experiment(experiment_id)
        
        # Actualizar status
        await self._update_experiment_status(
            experiment_id, 
            ExperimentStatus.COMPLETED
        )
        
        # Remover de cache
        self._active_experiments.pop(experiment_id, None)
        
        logger.info(f"Experimento concluido: {experiment_id} - Razón: {reason}")
        
        return results
    
    async def abort_experiment(
        self,
        experiment_id: UUID,
        reason: str = "aborted"
    ) -> None:
        """Aborta un experimento sin conclusión."""
        await self._update_experiment_status(
            experiment_id,
            ExperimentStatus.ABORTED
        )
        self._active_experiments.pop(experiment_id, None)
        logger.info(f"Experimento abortado: {experiment_id}")
    
    # =========================================================================
    # VARIANT ASSIGNMENT
    # =========================================================================
    
    async def assign_variant(
        self,
        experiment_id: UUID,
        context: Optional[dict] = None
    ) -> Optional[str]:
        """
        Asigna una variante para un nuevo trade.
        
        Args:
            experiment_id: ID del experimento
            context: Contexto opcional para asignación inteligente
        
        Returns:
            variant_id asignado o None si experimento no existe/inactivo
        """
        experiment = await self._get_experiment(experiment_id)
        
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return None
        
        # Asignación weighted random
        variant = self._weighted_random_assignment(experiment.variants)
        
        logger.debug(f"Asignado variante {variant} para experimento {experiment_id}")
        
        return variant
    
    def _weighted_random_assignment(
        self,
        variants: list[ExperimentVariant]
    ) -> str:
        """Asigna variante usando weighted random."""
        weights = [v.weight for v in variants]
        total_weight = sum(weights)
        normalized = [w / total_weight for w in weights]
        
        return np.random.choice(
            [v.variant_id for v in variants],
            p=normalized
        )
    
    async def get_variant_for_trade(
        self,
        strategy_id: str
    ) -> Optional[tuple[UUID, str]]:
        """
        Obtiene experimento activo y variante para una estrategia.
        
        Returns:
            Tuple (experiment_id, variant_id) o None
        """
        # Buscar experimentos activos que apliquen a esta estrategia
        for exp_id, exp in self._active_experiments.items():
            # Verificar si el experimento aplica
            for variant in exp.variants:
                if variant.config.get("strategy_id") == strategy_id:
                    assigned = await self.assign_variant(exp_id)
                    if assigned:
                        return (exp_id, assigned)
        
        return None
    
    # =========================================================================
    # ANALYSIS
    # =========================================================================
    
    async def analyze_experiment(
        self,
        experiment_id: UUID
    ) -> dict[str, Any]:
        """
        Analiza resultados de un experimento.
        
        Returns:
            Dict con métricas por variante, ganador, p-value, etc.
        """
        experiment = await self._get_experiment(experiment_id)
        
        if not experiment:
            raise ValueError(f"Experimento no encontrado: {experiment_id}")
        
        results_by_variant = {}
        metrics_by_variant = {}
        
        # Calcular métricas por variante
        for variant in experiment.variants:
            trades = await self._get_trades_for_variant(
                experiment_id, variant.variant_id
            )
            
            if trades:
                # Usar aggregator para calcular métricas
                metrics = self._aggregator._calculate_aggregated_metrics(
                    trades=trades,
                    period_type=experiment.variants[0].config.get("period_type", "all_time"),
                    period_start=experiment.start_date,
                    period_end=datetime.utcnow()
                )
                metrics_by_variant[variant.variant_id] = metrics
            
            results_by_variant[variant.variant_id] = {
                "trades": len(trades) if trades else 0,
                "metrics": metrics.model_dump() if trades else None
            }
        
        # Determinar ganador
        winner_analysis = self._determine_winner(
            experiment, metrics_by_variant
        )
        
        # Calcular significancia estadística
        stat_analysis = self._calculate_statistical_significance(
            experiment, metrics_by_variant
        )
        
        # Persistir resultados
        for variant_id, metrics in metrics_by_variant.items():
            result = ExperimentResult(
                experiment_id=experiment_id,
                variant_id=variant_id,
                metrics=metrics,
                is_winner=variant_id == winner_analysis.get("winner"),
                relative_improvement_pct=winner_analysis.get("improvement"),
                p_value=stat_analysis.get("p_value")
            )
            await self._upsert_experiment_result(result)
        
        return {
            "experiment_id": str(experiment_id),
            "experiment_name": experiment.name,
            "status": experiment.status.value,
            "variants": results_by_variant,
            "winner": winner_analysis,
            "statistical_analysis": stat_analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    def _determine_winner(
        self,
        experiment: ExperimentConfig,
        metrics_by_variant: dict[str, AggregatedMetrics]
    ) -> dict[str, Any]:
        """Determina el ganador basado en la métrica principal."""
        if not metrics_by_variant:
            return {"winner": None, "reason": "no_data"}
        
        primary_metric = experiment.primary_metric
        
        # Extraer valor de métrica principal por variante
        values = {}
        for variant_id, metrics in metrics_by_variant.items():
            value = None
            
            if primary_metric == "sharpe_ratio":
                value = metrics.risk.sharpe_ratio
            elif primary_metric == "sortino_ratio":
                value = metrics.risk.sortino_ratio
            elif primary_metric == "win_rate":
                value = metrics.trade.win_rate
            elif primary_metric == "profit_factor":
                value = metrics.trade.profit_factor
            elif primary_metric == "total_pnl":
                value = float(metrics.trade.total_pnl_eur)
            
            if value is not None:
                values[variant_id] = value
        
        if not values:
            return {"winner": None, "reason": "insufficient_data"}
        
        # Mayor es mejor para estas métricas
        winner = max(values, key=values.get)
        
        # Calcular mejora sobre el siguiente
        sorted_variants = sorted(values.items(), key=lambda x: x[1], reverse=True)
        
        improvement = None
        if len(sorted_variants) > 1:
            best = sorted_variants[0][1]
            second = sorted_variants[1][1]
            if second != 0:
                improvement = ((best - second) / abs(second)) * 100
        
        return {
            "winner": winner,
            "metric": primary_metric,
            "value": values[winner],
            "improvement": round(improvement, 2) if improvement else None,
            "all_values": values
        }
    
    def _calculate_statistical_significance(
        self,
        experiment: ExperimentConfig,
        metrics_by_variant: dict[str, AggregatedMetrics]
    ) -> dict[str, Any]:
        """
        Calcula significancia estadística usando t-test.
        
        Para A/B testing simple con 2 variantes.
        """
        if len(metrics_by_variant) != 2:
            return {
                "test": "not_applicable",
                "reason": "requires_2_variants"
            }
        
        variants = list(metrics_by_variant.keys())
        
        # Necesitamos los retornos individuales para t-test
        # Por ahora usamos aproximación con métricas agregadas
        
        # Simplificación: comparar Sharpe ratios
        sharpe_a = metrics_by_variant[variants[0]].risk.sharpe_ratio
        sharpe_b = metrics_by_variant[variants[1]].risk.sharpe_ratio
        
        n_a = metrics_by_variant[variants[0]].trade.total_trades
        n_b = metrics_by_variant[variants[1]].trade.total_trades
        
        if None in [sharpe_a, sharpe_b] or n_a < 5 or n_b < 5:
            return {
                "test": "insufficient_data",
                "min_required": self.config.experiment_min_trades
            }
        
        # Aproximación de p-value (simplificada)
        # En producción, usar retornos individuales
        diff = abs(sharpe_a - sharpe_b)
        pooled_n = n_a + n_b
        
        # Heurística simple
        if diff > 0.5 and pooled_n > 40:
            p_value = 0.01
        elif diff > 0.3 and pooled_n > 30:
            p_value = 0.05
        elif diff > 0.2 and pooled_n > 20:
            p_value = 0.10
        else:
            p_value = 0.20
        
        significant = p_value < (1 - self.config.experiment_confidence_level)
        
        return {
            "test": "approximate_comparison",
            "p_value": p_value,
            "significant": significant,
            "confidence_level": self.config.experiment_confidence_level,
            "sample_sizes": {variants[0]: n_a, variants[1]: n_b}
        }
    
    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================
    
    async def _insert_experiment(self, experiment: ExperimentConfig) -> None:
        """Inserta nuevo experimento."""
        import json
        
        query = """
            INSERT INTO metrics.experiments (
                experiment_id, name, description,
                variants, primary_metric,
                start_date, end_date, auto_conclude_days,
                min_trades_per_variant, status,
                created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        
        variants_json = json.dumps([v.model_dump() for v in experiment.variants])
        
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                experiment.experiment_id,
                experiment.name,
                experiment.description,
                variants_json,
                experiment.primary_metric,
                experiment.start_date,
                experiment.end_date,
                experiment.auto_conclude_days,
                experiment.min_trades_per_variant,
                experiment.status.value,
                experiment.created_at
            )
    
    async def _update_experiment_status(
        self,
        experiment_id: UUID,
        status: ExperimentStatus
    ) -> None:
        """Actualiza status de experimento."""
        query = """
            UPDATE metrics.experiments 
            SET status = $2, end_date = CASE WHEN $2 IN ('COMPLETED', 'ABORTED') THEN NOW() ELSE end_date END
            WHERE experiment_id = $1
        """
        async with self._pg_pool.acquire() as conn:
            await conn.execute(query, experiment_id, status.value)
    
    async def _get_experiment(self, experiment_id: UUID) -> Optional[ExperimentConfig]:
        """Obtiene experimento de BD."""
        # Primero buscar en cache
        if experiment_id in self._active_experiments:
            return self._active_experiments[experiment_id]
        
        query = "SELECT * FROM metrics.experiments WHERE experiment_id = $1"
        
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, experiment_id)
            
            if not row:
                return None
            
            import json
            variants_data = json.loads(row["variants"])
            variants = [ExperimentVariant(**v) for v in variants_data]
            
            return ExperimentConfig(
                experiment_id=row["experiment_id"],
                name=row["name"],
                description=row["description"],
                variants=variants,
                start_date=row["start_date"],
                end_date=row["end_date"],
                auto_conclude_days=row["auto_conclude_days"],
                min_trades_per_variant=row["min_trades_per_variant"],
                primary_metric=row["primary_metric"],
                status=ExperimentStatus(row["status"]),
                created_at=row["created_at"]
            )
    
    async def _get_trades_for_variant(
        self,
        experiment_id: UUID,
        variant_id: str
    ) -> list:
        """Obtiene trades asignados a una variante."""
        query = """
            SELECT * FROM metrics.trades
            WHERE experiment_id = $1
              AND status = 'CLOSED'
              AND metadata->>'variant_id' = $2
            ORDER BY exit_timestamp ASC
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query, experiment_id, variant_id)
            return [self._aggregator._row_to_trade(row) for row in rows]
    
    async def _upsert_experiment_result(self, result: ExperimentResult) -> None:
        """Inserta o actualiza resultado de variante."""
        import json
        
        query = """
            INSERT INTO metrics.experiment_results (
                experiment_id, variant_id,
                total_trades, sharpe_ratio, win_rate, total_pnl_eur,
                is_winner, relative_improvement_pct, p_value,
                calculated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (experiment_id, variant_id)
            DO UPDATE SET
                total_trades = EXCLUDED.total_trades,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                win_rate = EXCLUDED.win_rate,
                total_pnl_eur = EXCLUDED.total_pnl_eur,
                is_winner = EXCLUDED.is_winner,
                relative_improvement_pct = EXCLUDED.relative_improvement_pct,
                p_value = EXCLUDED.p_value,
                calculated_at = EXCLUDED.calculated_at
        """
        
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                result.experiment_id,
                result.variant_id,
                result.metrics.trade.total_trades,
                result.metrics.risk.sharpe_ratio,
                result.metrics.trade.win_rate,
                result.metrics.trade.total_pnl_eur,
                result.is_winner,
                result.relative_improvement_pct,
                result.p_value,
                result.calculated_at
            )
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    async def get_active_experiments(self) -> list[ExperimentConfig]:
        """Obtiene todos los experimentos activos."""
        query = """
            SELECT * FROM metrics.experiments 
            WHERE status = 'RUNNING'
            ORDER BY start_date DESC
        """
        
        async with self._pg_pool.acquire() as conn:
            rows = await conn.fetch(query)
            
            experiments = []
            for row in rows:
                exp = await self._get_experiment(row["experiment_id"])
                if exp:
                    experiments.append(exp)
            
            return experiments
    
    async def check_auto_conclude(self) -> list[UUID]:
        """
        Verifica experimentos que deben auto-concluirse.
        
        Returns:
            Lista de experiment_ids concluidos
        """
        concluded = []
        
        for exp_id, exp in list(self._active_experiments.items()):
            if exp.auto_conclude_days:
                deadline = exp.start_date + timedelta(days=exp.auto_conclude_days)
                if datetime.utcnow() > deadline:
                    await self.conclude_experiment(exp_id, reason="auto_conclude")
                    concluded.append(exp_id)
        
        return concluded
```

---

## Subtareas Completadas C1.4 y C1.5

```
TAREA C1.4: METRICS AGGREGATOR
────────────────────────────────────────────────────────────────────────────
[ ] Archivo src/metrics/aggregator.py creado
[ ] MetricsAggregator clase principal
[ ] run_full_aggregation() para todas las dimensiones
[ ] aggregate_by_strategy() con períodos
[ ] aggregate_by_model() para modelos ML
[ ] aggregate_by_regime() para análisis por régimen
[ ] _calculate_aggregated_metrics() combinando calculators
[ ] _build_equity_curve() para drawdown
[ ] Helpers de período (hourly, daily, weekly, monthly, all_time)
[ ] Database queries para obtener trades
[ ] UPSERT para strategy_performance
[ ] UPSERT para model_performance

TAREA C1.5: EXPERIMENT MANAGER
────────────────────────────────────────────────────────────────────────────
[ ] Archivo src/metrics/experiments.py creado
[ ] ExperimentManager clase principal
[ ] create_experiment() con variantes
[ ] start_experiment(), conclude_experiment(), abort_experiment()
[ ] assign_variant() weighted random
[ ] analyze_experiment() con métricas por variante
[ ] _determine_winner() basado en métrica principal
[ ] _calculate_statistical_significance() con p-value
[ ] Database operations para experiments
[ ] Auto-conclude check
```

---

*Fin de Parte 4 - Continúa en Parte 5: Dashboard Grafana + Verificación*

---

*Documento de Implementación - Fase C1: Sistema de Métricas*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
# Fase C1: Sistema de Métricas - Parte 5

## Dashboard Grafana + Exporters + Verificación

---

# Tarea C1.6: Exporters

**Estado:** ⬜ Pendiente  
**Duración estimada:** 2-3 horas  
**Dependencias:** C1.4 (Aggregator)

**Objetivo:** Implementar exportadores de métricas para Prometheus (Grafana) y consultas directas a PostgreSQL.

---

## C1.6.1: Prometheus Exporter

**Archivo:** `src/metrics/exporters/prometheus.py`

```python
"""
Prometheus Exporter - Expone métricas para Grafana.

Expone métricas en formato Prometheus en /metrics.
Grafana puede consumir directamente o vía Prometheus server.
"""

import logging
from typing import Optional

from prometheus_client import (
    Counter, Gauge, Histogram, Info,
    start_http_server, REGISTRY, generate_latest
)

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Exportador de métricas a Prometheus.
    
    Métricas expuestas:
    - trading_trades_total (Counter): Total de trades por estrategia/dirección
    - trading_pnl_eur (Gauge): PnL actual por estrategia
    - trading_sharpe_ratio (Gauge): Sharpe ratio por estrategia
    - trading_win_rate (Gauge): Win rate por estrategia
    - trading_drawdown_pct (Gauge): Drawdown actual
    - trading_trade_duration_hours (Histogram): Distribución de duración
    """
    
    def __init__(self, port: int = 9090):
        self.port = port
        self._initialized = False
        
        # Definir métricas
        self._define_metrics()
    
    def _define_metrics(self) -> None:
        """Define todas las métricas de Prometheus."""
        
        # Counters
        self.trades_total = Counter(
            'trading_trades_total',
            'Total number of trades',
            ['strategy_id', 'direction', 'status']
        )
        
        self.trades_won = Counter(
            'trading_trades_won_total',
            'Total winning trades',
            ['strategy_id']
        )
        
        self.trades_lost = Counter(
            'trading_trades_lost_total',
            'Total losing trades',
            ['strategy_id']
        )
        
        # Gauges
        self.pnl_total = Gauge(
            'trading_pnl_eur_total',
            'Total PnL in EUR',
            ['strategy_id']
        )
        
        self.sharpe_ratio = Gauge(
            'trading_sharpe_ratio',
            'Current Sharpe Ratio',
            ['strategy_id', 'period']
        )
        
        self.sortino_ratio = Gauge(
            'trading_sortino_ratio',
            'Current Sortino Ratio',
            ['strategy_id', 'period']
        )
        
        self.win_rate = Gauge(
            'trading_win_rate',
            'Current Win Rate (0-1)',
            ['strategy_id']
        )
        
        self.profit_factor = Gauge(
            'trading_profit_factor',
            'Current Profit Factor',
            ['strategy_id']
        )
        
        self.max_drawdown_pct = Gauge(
            'trading_max_drawdown_pct',
            'Maximum Drawdown Percentage',
            ['strategy_id']
        )
        
        self.open_positions = Gauge(
            'trading_open_positions',
            'Number of open positions',
            ['strategy_id']
        )
        
        self.equity_eur = Gauge(
            'trading_equity_eur',
            'Current equity in EUR',
            []
        )
        
        # Histograms
        self.trade_duration = Histogram(
            'trading_trade_duration_hours',
            'Trade duration in hours',
            ['strategy_id'],
            buckets=[1, 4, 8, 24, 48, 72, 168, 336, 720]  # Hasta 30 días
        )
        
        self.trade_pnl = Histogram(
            'trading_trade_pnl_eur',
            'Trade PnL distribution in EUR',
            ['strategy_id'],
            buckets=[-500, -200, -100, -50, -20, 0, 20, 50, 100, 200, 500, 1000]
        )
        
        # Info
        self.system_info = Info(
            'trading_system',
            'Trading system information'
        )
        
        self._initialized = True
    
    def start(self) -> None:
        """Inicia el servidor HTTP de métricas."""
        start_http_server(self.port)
        logger.info(f"Prometheus exporter iniciado en puerto {self.port}")
    
    def update_from_aggregated(
        self,
        strategy_id: str,
        metrics: 'AggregatedMetrics',
        period: str = "daily"
    ) -> None:
        """
        Actualiza métricas desde AggregatedMetrics.
        
        Args:
            strategy_id: ID de la estrategia
            metrics: Métricas agregadas calculadas
            period: Período de las métricas
        """
        # Trade metrics
        if metrics.trade.win_rate is not None:
            self.win_rate.labels(strategy_id=strategy_id).set(metrics.trade.win_rate)
        
        if metrics.trade.profit_factor is not None:
            self.profit_factor.labels(strategy_id=strategy_id).set(metrics.trade.profit_factor)
        
        if metrics.trade.total_pnl_eur is not None:
            self.pnl_total.labels(strategy_id=strategy_id).set(
                float(metrics.trade.total_pnl_eur)
            )
        
        # Risk metrics
        if metrics.risk.sharpe_ratio is not None:
            self.sharpe_ratio.labels(
                strategy_id=strategy_id, period=period
            ).set(metrics.risk.sharpe_ratio)
        
        if metrics.risk.sortino_ratio is not None:
            self.sortino_ratio.labels(
                strategy_id=strategy_id, period=period
            ).set(metrics.risk.sortino_ratio)
        
        if metrics.risk.max_drawdown_pct is not None:
            self.max_drawdown_pct.labels(strategy_id=strategy_id).set(
                metrics.risk.max_drawdown_pct
            )
    
    def record_trade_open(
        self,
        strategy_id: str,
        direction: str
    ) -> None:
        """Registra apertura de trade."""
        self.trades_total.labels(
            strategy_id=strategy_id,
            direction=direction,
            status="OPEN"
        ).inc()
        
        self.open_positions.labels(strategy_id=strategy_id).inc()
    
    def record_trade_close(
        self,
        strategy_id: str,
        direction: str,
        pnl_eur: float,
        duration_hours: float,
        won: bool
    ) -> None:
        """Registra cierre de trade."""
        self.trades_total.labels(
            strategy_id=strategy_id,
            direction=direction,
            status="CLOSED"
        ).inc()
        
        self.open_positions.labels(strategy_id=strategy_id).dec()
        
        if won:
            self.trades_won.labels(strategy_id=strategy_id).inc()
        else:
            self.trades_lost.labels(strategy_id=strategy_id).inc()
        
        self.trade_duration.labels(strategy_id=strategy_id).observe(duration_hours)
        self.trade_pnl.labels(strategy_id=strategy_id).observe(pnl_eur)
    
    def set_equity(self, equity_eur: float) -> None:
        """Actualiza equity actual."""
        self.equity_eur.set(equity_eur)
    
    def set_system_info(self, version: str, environment: str) -> None:
        """Establece información del sistema."""
        self.system_info.info({
            'version': version,
            'environment': environment
        })
```

---

## C1.6.2: PostgreSQL Direct Exporter

**Archivo:** `src/metrics/exporters/postgres.py`

```python
"""
PostgreSQL Exporter - Queries directas para Grafana.

Grafana puede conectar directamente a PostgreSQL.
Este módulo provee queries optimizadas para dashboards.
"""

from typing import Optional
from datetime import datetime, timedelta


class PostgresQueries:
    """
    Queries SQL optimizadas para Grafana.
    
    Uso en Grafana:
    - Configurar PostgreSQL datasource
    - Usar estas queries en paneles
    """
    
    # =========================================================================
    # EQUITY CURVE
    # =========================================================================
    
    EQUITY_CURVE = """
    -- Curva de equity acumulada
    WITH cumulative AS (
        SELECT 
            exit_timestamp as time,
            strategy_id,
            SUM(pnl_eur) OVER (
                PARTITION BY strategy_id 
                ORDER BY exit_timestamp
            ) as cumulative_pnl
        FROM metrics.trades
        WHERE status = 'CLOSED'
          AND exit_timestamp >= $__timeFrom()
          AND exit_timestamp <= $__timeTo()
    )
    SELECT 
        time,
        strategy_id,
        25000 + cumulative_pnl as equity  -- 25000 = capital inicial
    FROM cumulative
    ORDER BY time
    """
    
    # =========================================================================
    # PNL BY STRATEGY
    # =========================================================================
    
    PNL_BY_STRATEGY = """
    -- PnL por estrategia
    SELECT 
        strategy_id,
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END) as winning,
        SUM(CASE WHEN pnl_eur < 0 THEN 1 ELSE 0 END) as losing,
        ROUND(SUM(pnl_eur)::numeric, 2) as total_pnl,
        ROUND(AVG(pnl_eur)::numeric, 2) as avg_pnl,
        ROUND((SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END)::float / 
               NULLIF(COUNT(*), 0) * 100)::numeric, 1) as win_rate
    FROM metrics.trades
    WHERE status = 'CLOSED'
      AND exit_timestamp >= $__timeFrom()
      AND exit_timestamp <= $__timeTo()
    GROUP BY strategy_id
    ORDER BY total_pnl DESC
    """
    
    # =========================================================================
    # PNL BY REGIME
    # =========================================================================
    
    PNL_BY_REGIME = """
    -- PnL por régimen de mercado
    SELECT 
        COALESCE(regime_at_entry, 'UNKNOWN') as regime,
        COUNT(*) as trades,
        ROUND(SUM(pnl_eur)::numeric, 2) as total_pnl,
        ROUND(AVG(pnl_eur)::numeric, 2) as avg_pnl,
        ROUND((SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END)::float / 
               NULLIF(COUNT(*), 0) * 100)::numeric, 1) as win_rate
    FROM metrics.trades
    WHERE status = 'CLOSED'
      AND exit_timestamp >= $__timeFrom()
      AND exit_timestamp <= $__timeTo()
    GROUP BY regime_at_entry
    ORDER BY total_pnl DESC
    """
    
    # =========================================================================
    # DAILY PNL
    # =========================================================================
    
    DAILY_PNL = """
    -- PnL diario
    SELECT 
        DATE_TRUNC('day', exit_timestamp) as time,
        strategy_id,
        SUM(pnl_eur) as daily_pnl,
        COUNT(*) as trades
    FROM metrics.trades
    WHERE status = 'CLOSED'
      AND exit_timestamp >= $__timeFrom()
      AND exit_timestamp <= $__timeTo()
    GROUP BY DATE_TRUNC('day', exit_timestamp), strategy_id
    ORDER BY time
    """
    
    # =========================================================================
    # STRATEGY PERFORMANCE (from aggregated)
    # =========================================================================
    
    STRATEGY_METRICS = """
    -- Métricas de estrategia (últimas)
    SELECT DISTINCT ON (strategy_id)
        strategy_id,
        sharpe_ratio,
        sortino_ratio,
        win_rate * 100 as win_rate_pct,
        profit_factor,
        max_drawdown_pct,
        total_trades,
        total_pnl_eur,
        calculated_at
    FROM metrics.strategy_performance
    WHERE period_type = 'all_time'
    ORDER BY strategy_id, calculated_at DESC
    """
    
    # =========================================================================
    # EXPERIMENT RESULTS
    # =========================================================================
    
    EXPERIMENT_COMPARISON = """
    -- Comparación de experimentos A/B
    SELECT 
        e.name as experiment_name,
        er.variant_id,
        er.total_trades,
        er.sharpe_ratio,
        er.win_rate * 100 as win_rate_pct,
        er.total_pnl_eur,
        er.is_winner,
        er.relative_improvement_pct,
        er.p_value
    FROM metrics.experiment_results er
    JOIN metrics.experiments e ON e.experiment_id = er.experiment_id
    WHERE e.status IN ('RUNNING', 'COMPLETED')
    ORDER BY e.start_date DESC, er.is_winner DESC
    """
    
    # =========================================================================
    # RECENT TRADES
    # =========================================================================
    
    RECENT_TRADES = """
    -- Últimos trades
    SELECT 
        trade_id,
        symbol,
        strategy_id,
        direction,
        entry_price,
        exit_price,
        pnl_eur,
        pnl_pct,
        regime_at_entry,
        holding_duration_hours,
        exit_timestamp
    FROM metrics.trades
    WHERE status = 'CLOSED'
    ORDER BY exit_timestamp DESC
    LIMIT 20
    """
    
    # =========================================================================
    # DRAWDOWN
    # =========================================================================
    
    DRAWDOWN_SERIES = """
    -- Serie temporal de drawdown
    WITH equity AS (
        SELECT 
            exit_timestamp as time,
            25000 + SUM(pnl_eur) OVER (ORDER BY exit_timestamp) as equity
        FROM metrics.trades
        WHERE status = 'CLOSED'
          AND exit_timestamp >= $__timeFrom()
    ),
    peaks AS (
        SELECT 
            time,
            equity,
            MAX(equity) OVER (ORDER BY time) as peak
        FROM equity
    )
    SELECT 
        time,
        ((peak - equity) / peak * 100) as drawdown_pct
    FROM peaks
    ORDER BY time
    """


# Helper para generar queries con parámetros
def get_query_with_filters(
    base_query: str,
    strategy_id: Optional[str] = None,
    model_id: Optional[str] = None
) -> str:
    """Añade filtros opcionales a una query."""
    filters = []
    
    if strategy_id:
        filters.append(f"strategy_id = '{strategy_id}'")
    
    if model_id:
        filters.append(f"model_id = '{model_id}'")
    
    if filters:
        # Insertar antes de ORDER BY o al final
        filter_clause = " AND " + " AND ".join(filters)
        if "ORDER BY" in base_query:
            base_query = base_query.replace("ORDER BY", f"{filter_clause}\nORDER BY")
        else:
            base_query += filter_clause
    
    return base_query
```

---

# Tarea C1.7: Dashboard Grafana

**Estado:** ⬜ Pendiente  
**Duración estimada:** 2-3 horas  
**Dependencias:** C1.6 (Exporters)

**Objetivo:** Configurar Grafana con datasources y dashboard principal de trading.

---

## C1.7.1: Provisioning de Datasources

**Archivo:** `grafana/provisioning/datasources/datasources.yaml`

```yaml
# Grafana Datasources Provisioning
apiVersion: 1

datasources:
  # PostgreSQL - Métricas de trading
  - name: PostgreSQL-Trading
    type: postgres
    url: ${POSTGRES_HOST:-postgres}:5432
    database: trading
    user: ${POSTGRES_USER:-trading}
    secureJsonData:
      password: ${POSTGRES_PASSWORD:-trading}
    jsonData:
      sslmode: disable
      maxOpenConns: 10
      maxIdleConns: 5
      connMaxLifetime: 14400
      postgresVersion: 1400  # PostgreSQL 14
      timescaledb: true
    isDefault: true
    editable: false

  # Prometheus - Métricas en tiempo real (opcional)
  - name: Prometheus
    type: prometheus
    url: http://${PROMETHEUS_HOST:-prometheus}:9090
    jsonData:
      httpMethod: POST
      manageAlerts: true
      prometheusType: Prometheus
    editable: false

  # InfluxDB - Series temporales (si se usa)
  - name: InfluxDB-Trading
    type: influxdb
    url: http://${INFLUXDB_HOST:-influxdb}:8086
    database: trading_metrics
    user: ${INFLUXDB_USER:-trading}
    secureJsonData:
      password: ${INFLUXDB_PASSWORD:-trading}
    jsonData:
      httpMode: GET
    editable: false
```

---

## C1.7.2: Provisioning de Dashboards

**Archivo:** `grafana/provisioning/dashboards/dashboards.yaml`

```yaml
# Grafana Dashboard Provisioning
apiVersion: 1

providers:
  - name: 'Trading Dashboards'
    orgId: 1
    folder: 'Trading'
    folderUid: 'trading'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
```

---

## C1.7.3: Dashboard Principal JSON

**Archivo:** `grafana/dashboards/trading_metrics.json`

```json
{
  "annotations": {
    "list": []
  },
  "description": "Nexus Trading - Métricas principales",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "id": 1,
      "title": "Equity Curve",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 16, "x": 0, "y": 0},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "WITH cumulative AS (\n  SELECT \n    exit_timestamp as time,\n    strategy_id,\n    SUM(pnl_eur) OVER (PARTITION BY strategy_id ORDER BY exit_timestamp) as cumulative_pnl\n  FROM metrics.trades\n  WHERE status = 'CLOSED'\n    AND exit_timestamp >= $__timeFrom()\n    AND exit_timestamp <= $__timeTo()\n)\nSELECT \n  time,\n  strategy_id as metric,\n  25000 + cumulative_pnl as value\nFROM cumulative\nORDER BY time",
          "format": "time_series"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "palette-classic"},
          "custom": {"drawStyle": "line", "lineWidth": 2, "fillOpacity": 10},
          "unit": "currencyEUR"
        }
      },
      "options": {
        "legend": {"displayMode": "table", "placement": "right"}
      }
    },
    {
      "id": 2,
      "title": "KPIs",
      "type": "stat",
      "gridPos": {"h": 4, "w": 8, "x": 16, "y": 0},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT ROUND(SUM(pnl_eur)::numeric, 2) as \"Total PnL\" FROM metrics.trades WHERE status = 'CLOSED'",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "currencyEUR",
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0},
              {"color": "green", "value": 500}
            ]
          }
        }
      }
    },
    {
      "id": 3,
      "title": "Win Rate",
      "type": "gauge",
      "gridPos": {"h": 4, "w": 4, "x": 16, "y": 4},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT ROUND((SUM(CASE WHEN pnl_eur > 0 THEN 1 ELSE 0 END)::float / NULLIF(COUNT(*), 0) * 100)::numeric, 1) as win_rate FROM metrics.trades WHERE status = 'CLOSED'",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "min": 0,
          "max": 100,
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 40},
              {"color": "green", "value": 55}
            ]
          }
        }
      }
    },
    {
      "id": 4,
      "title": "Sharpe Ratio",
      "type": "stat",
      "gridPos": {"h": 4, "w": 4, "x": 20, "y": 4},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT sharpe_ratio FROM metrics.strategy_performance WHERE period_type = 'all_time' ORDER BY calculated_at DESC LIMIT 1",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "decimals": 2,
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 0.5},
              {"color": "green", "value": 1.0}
            ]
          }
        }
      }
    },
    {
      "id": 5,
      "title": "PnL por Estrategia",
      "type": "barchart",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT strategy_id, ROUND(SUM(pnl_eur)::numeric, 2) as pnl FROM metrics.trades WHERE status = 'CLOSED' AND exit_timestamp >= $__timeFrom() GROUP BY strategy_id ORDER BY pnl DESC",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "defaults": {"unit": "currencyEUR"}
      }
    },
    {
      "id": 6,
      "title": "PnL por Régimen",
      "type": "piechart",
      "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT COALESCE(regime_at_entry, 'UNKNOWN') as regime, ROUND(SUM(pnl_eur)::numeric, 2) as pnl FROM metrics.trades WHERE status = 'CLOSED' GROUP BY regime_at_entry",
          "format": "table"
        }
      ]
    },
    {
      "id": 7,
      "title": "Drawdown",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "WITH equity AS (\n  SELECT exit_timestamp as time, 25000 + SUM(pnl_eur) OVER (ORDER BY exit_timestamp) as equity\n  FROM metrics.trades WHERE status = 'CLOSED' AND exit_timestamp >= $__timeFrom()\n),\npeaks AS (\n  SELECT time, equity, MAX(equity) OVER (ORDER BY time) as peak FROM equity\n)\nSELECT time, ((peak - equity) / peak * 100) as drawdown FROM peaks ORDER BY time",
          "format": "time_series"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "color": {"mode": "fixed", "fixedColor": "red"},
          "custom": {"drawStyle": "line", "fillOpacity": 30}
        }
      }
    },
    {
      "id": 8,
      "title": "Últimos Trades",
      "type": "table",
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 16},
      "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
      "targets": [
        {
          "rawSql": "SELECT symbol, strategy_id, direction, ROUND(entry_price::numeric, 2) as entry, ROUND(exit_price::numeric, 2) as exit, ROUND(pnl_eur::numeric, 2) as pnl, ROUND(pnl_pct::numeric, 2) as pnl_pct, regime_at_entry as regime, ROUND(holding_duration_hours::numeric, 1) as hours, exit_timestamp FROM metrics.trades WHERE status = 'CLOSED' ORDER BY exit_timestamp DESC LIMIT 15",
          "format": "table"
        }
      ],
      "fieldConfig": {
        "overrides": [
          {"matcher": {"id": "byName", "options": "pnl"}, "properties": [{"id": "unit", "value": "currencyEUR"}]},
          {"matcher": {"id": "byName", "options": "pnl_pct"}, "properties": [{"id": "unit", "value": "percent"}]}
        ]
      }
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["trading", "nexus"],
  "templating": {
    "list": [
      {
        "name": "strategy",
        "type": "query",
        "datasource": {"type": "postgres", "uid": "PostgreSQL-Trading"},
        "query": "SELECT DISTINCT strategy_id FROM metrics.trades",
        "includeAll": true,
        "multi": true
      }
    ]
  },
  "time": {"from": "now-7d", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Nexus Trading - Overview",
  "uid": "nexus-trading-overview",
  "version": 1,
  "weekStart": "monday"
}
```

---

## C1.7.4: Docker Compose Updates

**Archivo:** `docker-compose.yml` (sección Grafana)

```yaml
# Añadir/modificar en docker-compose.yml existente

services:
  # ... otros servicios ...

  grafana:
    image: grafana/grafana:10.2.0
    container_name: trading_grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_SERVER_ROOT_URL=http://localhost:3000
      - POSTGRES_HOST=postgres
      - POSTGRES_USER=${POSTGRES_USER:-trading}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-trading}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    depends_on:
      - postgres
    networks:
      - trading_network

volumes:
  grafana_data:

networks:
  trading_network:
    driver: bridge
```

---

# Tarea C1.8: Verificación e Integración

**Estado:** ⬜ Pendiente  
**Duración estimada:** 2-3 horas  
**Dependencias:** Todas las anteriores (C1.1-C1.7)

**Objetivo:** Scripts de verificación, integración y checklist final.

---

## C1.8.1: Script de Verificación Principal

**Archivo:** `scripts/verify_fase_c1.py`

```python
#!/usr/bin/env python3
"""
Script de verificación para Fase C1: Sistema de Métricas.

Ejecutar: python scripts/verify_fase_c1.py

Verifica:
- Módulos Python importables
- Conexiones a BD y Redis
- Tablas de métricas existen
- Calculators funcionan correctamente
- Collector puede procesar eventos
- Aggregator puede calcular métricas
- Grafana accesible
"""

import asyncio
import sys
import os
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

# Añadir src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")


def print_check(name: str, passed: bool, details: str = ""):
    status = f"{Colors.GREEN}✓ PASS{Colors.END}" if passed else f"{Colors.RED}✗ FAIL{Colors.END}"
    print(f"  {status} - {name}")
    if details and not passed:
        print(f"         {Colors.YELLOW}{details}{Colors.END}")


async def check_imports() -> tuple[bool, list]:
    """Verifica que todos los módulos se pueden importar."""
    results = []
    
    modules = [
        ("metrics.schemas", "Schemas Pydantic"),
        ("metrics.calculators", "Calculators"),
        ("metrics.collector", "MetricsCollector"),
        ("metrics.aggregator", "MetricsAggregator"),
        ("metrics.experiments", "ExperimentManager"),
        ("metrics.exporters.prometheus", "Prometheus Exporter"),
        ("metrics.exporters.postgres", "PostgreSQL Queries"),
    ]
    
    all_passed = True
    for module, name in modules:
        try:
            __import__(module)
            results.append((name, True, ""))
        except ImportError as e:
            results.append((name, False, str(e)))
            all_passed = False
    
    return all_passed, results


async def check_database() -> tuple[bool, list]:
    """Verifica conexión a PostgreSQL y tablas de métricas."""
    results = []
    
    try:
        import asyncpg
        
        pool = await asyncpg.create_pool(
            "postgresql://trading:trading@localhost:5432/trading",
            min_size=1,
            max_size=2
        )
        results.append(("Conexión PostgreSQL", True, ""))
        
        # Verificar tablas
        tables = [
            "metrics.trades",
            "metrics.strategy_performance",
            "metrics.model_performance",
            "metrics.experiments",
            "metrics.experiment_results"
        ]
        
        async with pool.acquire() as conn:
            for table in tables:
                try:
                    await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    results.append((f"Tabla {table}", True, ""))
                except Exception as e:
                    results.append((f"Tabla {table}", False, str(e)))
        
        await pool.close()
        
    except Exception as e:
        results.append(("Conexión PostgreSQL", False, str(e)))
        return False, results
    
    all_passed = all(r[1] for r in results)
    return all_passed, results


async def check_redis() -> tuple[bool, list]:
    """Verifica conexión a Redis."""
    results = []
    
    try:
        import aioredis
        
        redis = await aioredis.from_url("redis://localhost:6379")
        await redis.ping()
        results.append(("Conexión Redis", True, ""))
        
        # Test pub/sub
        pubsub = redis.pubsub()
        await pubsub.subscribe("test_channel")
        await pubsub.unsubscribe("test_channel")
        results.append(("Redis Pub/Sub", True, ""))
        
        await redis.close()
        
    except Exception as e:
        results.append(("Conexión Redis", False, str(e)))
        return False, results
    
    return True, results


async def check_calculators() -> tuple[bool, list]:
    """Verifica que los calculators funcionan correctamente."""
    results = []
    
    try:
        import numpy as np
        from metrics.calculators import (
            RiskMetricsCalculator,
            TradeMetricsCalculator,
            TimeMetricsCalculator
        )
        
        # Test Risk Calculator
        risk_calc = RiskMetricsCalculator()
        returns = np.array([0.01, -0.005, 0.02, -0.01, 0.015] * 20)
        equity = np.array([10000, 10100, 10050, 10250, 10150] * 20)
        
        risk_metrics = risk_calc.calculate(returns, equity)
        
        if risk_metrics.sharpe_ratio is not None:
            results.append(("RiskMetricsCalculator", True, ""))
        else:
            results.append(("RiskMetricsCalculator", False, "Sharpe ratio es None"))
        
        # Test Trade Calculator
        trade_calc = TradeMetricsCalculator()
        # Crear trades mock
        from metrics.schemas import TradeRecord, TradeDirection, TradeStatus
        
        trades = []
        for i, pnl in enumerate([100, -50, 75, -25, 150]):
            trade = TradeRecord(
                trade_id=uuid4(),
                strategy_id="test",
                symbol="TEST",
                direction=TradeDirection.LONG,
                status=TradeStatus.CLOSED,
                entry_price=Decimal("100"),
                exit_price=Decimal("101"),
                size_shares=Decimal("10"),
                size_value_eur=Decimal("1000"),
                pnl_eur=Decimal(str(pnl)),
                pnl_pct=float(pnl) / 10,
                entry_timestamp=datetime.utcnow(),
                exit_timestamp=datetime.utcnow(),
                holding_duration_hours=24.0
            )
            trades.append(trade)
        
        trade_metrics = trade_calc.calculate(trades)
        
        if trade_metrics.total_trades == 5 and trade_metrics.win_rate is not None:
            results.append(("TradeMetricsCalculator", True, ""))
        else:
            results.append(("TradeMetricsCalculator", False, "Cálculos incorrectos"))
        
        # Test Time Calculator
        time_calc = TimeMetricsCalculator()
        time_metrics = time_calc.calculate(trades)
        
        if time_metrics.avg_holding_hours is not None:
            results.append(("TimeMetricsCalculator", True, ""))
        else:
            results.append(("TimeMetricsCalculator", False, "Holding time es None"))
        
    except Exception as e:
        results.append(("Calculators", False, str(e)))
        return False, results
    
    all_passed = all(r[1] for r in results)
    return all_passed, results


async def check_grafana() -> tuple[bool, list]:
    """Verifica que Grafana está accesible."""
    results = []
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:3000/api/health") as resp:
                if resp.status == 200:
                    results.append(("Grafana API", True, ""))
                else:
                    results.append(("Grafana API", False, f"Status: {resp.status}"))
    
    except Exception as e:
        results.append(("Grafana API", False, str(e)))
        return False, results
    
    return True, results


async def main():
    print_header("VERIFICACIÓN FASE C1: SISTEMA DE MÉTRICAS")
    
    all_passed = True
    
    # 1. Imports
    print("\n📦 Verificando imports...")
    passed, results = await check_imports()
    for name, ok, details in results:
        print_check(name, ok, details)
    all_passed = all_passed and passed
    
    # 2. Database
    print("\n🗄️ Verificando PostgreSQL...")
    passed, results = await check_database()
    for name, ok, details in results:
        print_check(name, ok, details)
    all_passed = all_passed and passed
    
    # 3. Redis
    print("\n📮 Verificando Redis...")
    passed, results = await check_redis()
    for name, ok, details in results:
        print_check(name, ok, details)
    all_passed = all_passed and passed
    
    # 4. Calculators
    print("\n🔢 Verificando Calculators...")
    passed, results = await check_calculators()
    for name, ok, details in results:
        print_check(name, ok, details)
    all_passed = all_passed and passed
    
    # 5. Grafana
    print("\n📊 Verificando Grafana...")
    passed, results = await check_grafana()
    for name, ok, details in results:
        print_check(name, ok, details)
    # Grafana es opcional, no afecta el resultado general
    
    # Resultado final
    print_header("RESULTADO FINAL")
    
    if all_passed:
        print(f"\n{Colors.GREEN}✓ FASE C1 VERIFICADA CORRECTAMENTE{Colors.END}\n")
        return 0
    else:
        print(f"\n{Colors.RED}✗ HAY ERRORES QUE CORREGIR{Colors.END}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

---

## C1.8.2: Script de Inicialización

**Archivo:** `scripts/init_metrics_system.py`

```python
#!/usr/bin/env python3
"""
Script de inicialización del sistema de métricas.

Ejecutar después de verificación exitosa.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


async def main():
    print("Inicializando sistema de métricas...")
    
    import asyncpg
    from metrics.schemas import MetricsConfig
    from metrics.collector import MetricsCollector
    from metrics.aggregator import MetricsAggregator
    from metrics.experiments import ExperimentManager
    from metrics.exporters.prometheus import PrometheusExporter
    
    # Configuración
    config = MetricsConfig()
    
    # Pool de PostgreSQL
    pg_pool = await asyncpg.create_pool(
        "postgresql://trading:trading@localhost:5432/trading",
        min_size=2,
        max_size=10
    )
    
    # Inicializar componentes
    collector = MetricsCollector(config)
    aggregator = MetricsAggregator(config, pg_pool)
    experiments = ExperimentManager(config, pg_pool, aggregator)
    prometheus = PrometheusExporter(port=9090)
    
    print("✓ Componentes inicializados")
    
    # Iniciar Prometheus exporter
    prometheus.start()
    print("✓ Prometheus exporter iniciado en :9090")
    
    # Ejecutar agregación inicial
    print("Ejecutando agregación inicial...")
    results = await aggregator.run_full_aggregation()
    print(f"✓ Agregación completada: {results}")
    
    await pg_pool.close()
    print("\n✓ Sistema de métricas listo")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## C1.8.3: Checklist Final de Fase C1

```
═══════════════════════════════════════════════════════════════════════════════════
                        FASE C1: CHECKLIST FINAL
═══════════════════════════════════════════════════════════════════════════════════

TAREA C1.1: SCHEMAS PYDANTIC
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/__init__.py creado
[ ] src/metrics/schemas.py creado
[ ] ENUMs: TradeDirection, TradeStatus, RegimeType, ExperimentStatus, PeriodType
[ ] Schemas: TradeOpenEvent, TradeCloseEvent, TradeRecord
[ ] Schemas: RiskMetrics, TradeMetrics, TimeMetrics, AggregatedMetrics
[ ] Schemas: ExperimentVariant, ExperimentConfig, ExperimentResult
[ ] Schema: MetricsConfig
[ ] Helper: trade_event_to_record()
[ ] Validaciones Pydantic funcionando

TAREA C1.2: CALCULATORS
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/calculators/__init__.py creado
[ ] risk_metrics.py: Sharpe, Sortino, MaxDD, Calmar, VaR
[ ] trade_metrics.py: Win Rate, Profit Factor, R-Multiple, Expectancy
[ ] time_metrics.py: Holding time, Streaks
[ ] Tests: test_calculators.py con casos conocidos
[ ] Edge cases manejados (división por cero, NaN)

TAREA C1.3: METRICS COLLECTOR
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/collector.py creado
[ ] MetricsCollector con lifecycle (start, stop)
[ ] Event handlers: TRADE_OPEN, TRADE_CLOSE, TRADE_CANCEL
[ ] Context enrichment (régimen, indicadores)
[ ] Database operations (INSERT, UPDATE, SELECT)
[ ] src/metrics/publisher.py helper
[ ] Tests: test_collector.py

TAREA C1.4: METRICS AGGREGATOR
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/aggregator.py creado
[ ] run_full_aggregation()
[ ] aggregate_by_strategy() con períodos
[ ] aggregate_by_model()
[ ] aggregate_by_regime()
[ ] _build_equity_curve()
[ ] UPSERT para strategy_performance
[ ] UPSERT para model_performance

TAREA C1.5: EXPERIMENT MANAGER
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/experiments.py creado
[ ] create_experiment() con variantes
[ ] assign_variant() weighted random
[ ] analyze_experiment() con métricas
[ ] _determine_winner()
[ ] _calculate_statistical_significance()
[ ] Auto-conclude check

TAREA C1.6: EXPORTERS
────────────────────────────────────────────────────────────────────────────────────
[ ] src/metrics/exporters/__init__.py creado
[ ] prometheus.py con métricas definidas
[ ] postgres.py con queries optimizadas
[ ] PrometheusExporter funcionando en :9090

TAREA C1.7: DASHBOARD GRAFANA
────────────────────────────────────────────────────────────────────────────────────
[ ] grafana/provisioning/datasources/datasources.yaml
[ ] grafana/provisioning/dashboards/dashboards.yaml
[ ] grafana/dashboards/trading_metrics.json
[ ] docker-compose.yml actualizado con Grafana
[ ] Dashboard accesible en http://localhost:3000
[ ] Paneles: Equity Curve, KPIs, PnL por Estrategia, Drawdown, Trades

TAREA C1.8: VERIFICACIÓN
────────────────────────────────────────────────────────────────────────────────────
[ ] scripts/verify_fase_c1.py creado y ejecutable
[ ] scripts/init_metrics_system.py creado
[ ] Todos los checks pasan
[ ] Grafana muestra datos (si hay trades)

═══════════════════════════════════════════════════════════════════════════════════

GATE DE AVANCE A FASE C2:
────────────────────────────────────────────────────────────────────────────────────
[ ] python scripts/verify_fase_c1.py retorna 0 (éxito)
[ ] docker-compose up -d levanta todos los servicios incluyendo Grafana
[ ] Collector puede procesar eventos de test
[ ] Aggregator puede calcular métricas
[ ] Dashboard Grafana accesible y funcional
[ ] No hay errores críticos en logs

═══════════════════════════════════════════════════════════════════════════════════
```

---

## Troubleshooting

### Error: "Módulo metrics no encontrado"

```bash
# Verificar estructura de directorios
ls -la src/metrics/

# Asegurar que __init__.py existe
touch src/metrics/__init__.py
touch src/metrics/calculators/__init__.py
touch src/metrics/exporters/__init__.py
```

### Error: "asyncpg no instalado"

```bash
pip install asyncpg aioredis
```

### Error: "Tabla metrics.trades no existe"

```bash
# Ejecutar script de fase A1 primero
docker exec -i trading_postgres psql -U trading -d trading < init-scripts/07_metrics_schema.sql
```

### Error: "Grafana no conecta a PostgreSQL"

```bash
# Verificar que PostgreSQL acepta conexiones
docker exec trading_postgres pg_isready -U trading

# Verificar red Docker
docker network inspect trading_network

# Ver logs de Grafana
docker-compose logs grafana
```

### Error: "Prometheus port already in use"

```bash
# Cambiar puerto en config o matar proceso
lsof -i :9090
kill -9 <PID>
```

### Error: "NaN en cálculos de Sharpe"

```python
# Verificar que hay suficientes datos
# Mínimo 10 trades para métricas válidas
# Verificar que no hay división por cero en std
```

---

## Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Esquemas metrics.* | fase_a1_extensiones_base.md | Tarea A1.1 |
| Signal dataclass | fase_b1_estrategias_swing.md | C1.3.1 |
| AgentDecision | fase_b2_ai_agent.md | Interfaces |
| Redis pub/sub | fase_3_agentes_core.md | Sistema mensajería |
| PostgreSQL base | fase_0_infraestructura.md | Tarea 0.4 |
| Docker Compose | fase_0_infraestructura.md | Tarea 0.1 |

---

## Siguiente Fase

Una vez completada la Fase C1:

1. **Verificar:** `python scripts/verify_fase_c1.py` retorna éxito
2. **Verificar:** Dashboard Grafana muestra datos (ejecutar trades de prueba)
3. **Siguiente documento:** `fase_c2_intraday.md`
4. **Contenido Fase C2:**
   - Estrategia Mean Reversion Intraday
   - Estrategia Volatility Breakout
   - Toggle datos real-time
   - Integración con sistema de métricas

---

*Fin de Parte 5 - Documento fase_c1_metricas.md COMPLETO*

---

# Apéndice: Comandos de Referencia Rápida

```bash
# Levantar infraestructura
docker-compose up -d

# Verificar fase
python scripts/verify_fase_c1.py

# Inicializar sistema de métricas
python scripts/init_metrics_system.py

# Ver logs de Grafana
docker-compose logs -f grafana

# Acceder a Grafana
# http://localhost:3000 (admin/admin)

# Conectar a PostgreSQL y ver métricas
docker exec -it trading_postgres psql -U trading -d trading
\dt metrics.*
SELECT * FROM metrics.trades LIMIT 5;
SELECT * FROM metrics.strategy_performance;

# Ver métricas Prometheus
curl http://localhost:9090/metrics

# Ejecutar tests
pytest src/metrics/tests/ -v

# Ejecutar agregación manual
python -c "
import asyncio
from src.metrics.aggregator import MetricsAggregator
# ... inicializar y ejecutar
"
```

---

*Documento de Implementación - Fase C1: Sistema de Métricas*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
