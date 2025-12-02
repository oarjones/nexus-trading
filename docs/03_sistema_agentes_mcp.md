# 🤖 Arquitectura Técnica - Documento 3/7

## Sistema de Agentes MCP

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Visión General

### 1.1 Arquitectura Multi-Agente

El sistema usa agentes especializados coordinados por un Orchestrator central. Cada agente tiene responsabilidad única y se comunica vía MCP (Model Context Protocol).

```
                         ┌─────────────────┐
                         │  ORCHESTRATOR   │
                         └────────┬────────┘
                                  │
          ┌───────────┬───────────┼───────────┬───────────┐
          ▼           ▼           ▼           ▼           ▼
    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
    │TECHNICAL │ │FUNDAMENT.│ │SENTIMENT │ │   RISK   │ │EXECUTION │
    │ ANALYST  │ │ ANALYST  │ │ ANALYST  │ │ MANAGER  │ │  AGENT   │
    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
         │            │            │            │            │
         └────────────┴────────────┴────────────┴────────────┘
                                  │
                         ┌────────┴────────┐
                         │   MCP SERVERS   │
                         └─────────────────┘
```

### 1.2 Principios de Diseño

| Principio | Implementación |
|-----------|----------------|
| Responsabilidad única | Cada agente = 1 dominio específico |
| Comunicación asíncrona | Mensajes vía Redis pub/sub + MCP tools |
| Fail-safe | Risk Manager tiene veto absoluto |
| Observabilidad | Toda decisión queda en audit log |

### 1.3 Jerarquía de Decisiones

1. **Risk Manager** — Veto absoluto, límites hardcoded
2. **Orchestrator** — Decisión final ponderando señales
3. **Agentes analistas** — Generan señales con confianza

---

## 2. Protocolo MCP

### 2.1 Estructura de Comunicación

Los agentes invocan tools de MCP Servers. Comunicación stateless, request-response.

**Request (Agent → MCP Server):**
```json
{
  "method": "tools/call",
  "params": {
    "name": "calculate_indicators",
    "arguments": {
      "symbol": "AAPL",
      "indicators": ["RSI", "MACD"],
      "timeframe": "1h"
    }
  }
}
```

**Response (MCP Server → Agent):**
```json
{
  "content": [{
    "type": "text",
    "text": "{\"rsi_14\": 58.3, \"macd_hist\": 0.45}"
  }]
}
```

### 2.2 Mensajes Inter-Agente

Comunicación entre agentes vía Redis pub/sub con estructura estandarizada:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `message_id` | UUID | Identificador único |
| `timestamp` | ISO8601 | Momento de emisión |
| `from_agent` | string | Agente emisor |
| `to_agent` | string | Destino ("orchestrator" o "broadcast") |
| `type` | enum | `signal`, `approval`, `alert`, `status` |
| `payload` | object | Contenido específico del mensaje |
| `ttl_seconds` | int | Tiempo de vida (default: 300) |

### 2.3 Payload de Señal de Trading

```json
{
  "symbol": "AAPL",
  "direction": "long",
  "confidence": 0.72,
  "entry_price": 185.50,
  "stop_loss": 182.00,
  "take_profit": 195.00,
  "timeframe": "swing_5d",
  "reasoning": "Breakout de consolidación con volumen",
  "indicators": {"rsi": 58, "macd_hist": 0.45, "volume_ratio": 1.8}
}
```

---

## 3. Orchestrator Agent

### 3.1 Responsabilidades

| Función | Descripción |
|---------|-------------|
| Recolección | Recibe señales de todos los analistas |
| Ponderación | Combina señales según confianza y régimen |
| Validación | Consulta Risk Manager antes de ejecutar |
| Decisión | Emite orden final o descarta |
| Escalado | Alerta humano si confianza < 60% |

### 3.2 Lógica de Ponderación

```
score_final = Σ (señal_i.confianza × peso_agente_i × factor_régimen)

Pesos por defecto:
- Technical: 0.40
- Fundamental: 0.30
- Sentiment: 0.30

Ajuste por régimen (ver Doc 1, sección 4.6):
- Trending: Technical × 1.2, Sentiment × 0.8
- Range-bound: Technical × 0.8, Fundamental × 1.2
- High Vol: Todos × 0.7 (más conservador)
```

### 3.3 Criterios de Ejecución

| Condición | Acción |
|-----------|--------|
| score_final ≥ 0.65 + Risk OK | Ejecutar orden |
| score_final 0.50-0.65 | Ejecutar con sizing reducido (50%) |
| score_final < 0.50 | Descartar señal |
| Señales contradictorias | Descartar, loguear conflicto |
| Risk Manager rechaza | Descartar, registrar razón |

### 3.4 Estado Interno

El Orchestrator mantiene en Redis (`session:orchestrator`):
- Última decisión por símbolo
- Contador de señales procesadas hoy
- Estado de cada agente (healthy/degraded/offline)
- Modo actual del sistema (ver Doc 1, sección 5.3)

---

## 4. Agentes de Análisis

### 4.1 Technical Analyst Agent

**Dominio:** Análisis técnico basado en precio, volumen e indicadores.

**Inputs:**
- OHLCV desde TimescaleDB (vía mcp-market-data)
- Indicadores pre-calculados
- Régimen actual

**Outputs:** Señales con dirección, niveles y confianza.

**Tools MCP utilizados:**

| Tool | Descripción |
|------|-------------|
| `get_ohlcv` | Datos históricos de precio |
| `calculate_indicators` | RSI, MACD, Bollinger, etc. |
| `detect_patterns` | Patrones chartistas |
| `find_support_resistance` | Niveles clave |

**Lógica de señal (simplificada):**
```
IF rsi < 30 AND macd_crossover_up AND price > sma_50:
    signal = LONG, confidence = base + (30 - rsi)/100
IF rsi > 70 AND macd_crossover_down AND price < sma_50:
    signal = SHORT, confidence = base + (rsi - 70)/100
ELSE:
    signal = NEUTRAL
```

### 4.2 Fundamental Analyst Agent

**Dominio:** Valoración y calidad financiera de activos.

**Inputs:**
- Datos fundamentales (P/E, EV/EBITDA, deuda, etc.)
- Earnings recientes y estimados
- Comparables del sector

**Outputs:** Score fundamental (-1 a +1) con reasoning.

**Tools MCP utilizados:**

| Tool | Descripción |
|------|-------------|
| `get_fundamentals` | Ratios financieros |
| `get_earnings` | Histórico y estimaciones |
| `get_sector_comparison` | Percentiles vs peers |

**Criterios de scoring:**

| Factor | Peso | Bullish si |
|--------|------|-----------|
| P/E vs sector | 25% | < percentil 40 |
| Crecimiento revenue | 25% | > 10% YoY |
| Deuda/EBITDA | 20% | < 2.5x |
| Earnings surprise | 15% | > +5% últimos 2 quarters |
| Insider buying | 15% | Compras netas > 0 |

**Limitaciones:** Solo aplica a acciones, no a forex/crypto.

### 4.3 Sentiment Analyst Agent

**Dominio:** Percepción del mercado vía noticias y redes sociales.

**Inputs:**
- Noticias de NewsAPI/RSS
- Menciones en redes (si disponible)
- Eventos del calendario económico

**Outputs:** Score de sentimiento (-1 a +1) con fuentes.

**Tools MCP utilizados:**

| Tool | Descripción |
|------|-------------|
| `get_news` | Noticias recientes por símbolo |
| `analyze_sentiment` | Clasificación con FinBERT |
| `get_economic_calendar` | Eventos próximos |

**Pipeline de procesamiento:**

1. Fetch noticias últimas 24h
2. Filtrar por relevancia (menciona símbolo/sector)
3. Clasificar cada noticia: positivo/negativo/neutral + score
4. Agregar: `sentiment = Σ(score_i × relevancia_i × recencia_i)`
5. Normalizar a rango [-1, +1]

**Decay temporal:** Noticias > 12h tienen peso reducido 50%.

---

## 5. Risk Manager Agent

### 5.1 Responsabilidades

| Función | Descripción |
|---------|-------------|
| Pre-trade validation | Verificar límites antes de orden |
| Position sizing | Calcular tamaño óptimo |
| Portfolio monitoring | Exposiciones, correlaciones |
| Veto | Rechazar operaciones que violen límites |

### 5.2 Límites Hardcoded

Referencia: Doc 1, sección 4.5. Estos límites NO son configurables en runtime.

| Límite | Valor | Verificación |
|--------|-------|--------------|
| Max posición individual | 20% capital | Pre-trade |
| Max sector | 40% capital | Pre-trade |
| Max correlación | 0.7 | Pre-trade |
| Max drawdown | 15% | Continuo |
| Min cash | 10% | Pre-trade |

### 5.3 Cálculo de Position Sizing

```
risk_per_trade = capital × 0.01 × confidence_factor
distance_to_stop = |entry_price - stop_loss|
shares = risk_per_trade / distance_to_stop
max_value = capital × 0.20
final_shares = min(shares × entry_price, max_value) / entry_price
```

**Ajustes:**
- Si correlación con portfolio > 0.5: reducir 30%
- Si régimen = High Vol: reducir 50%
- Si drawdown actual > 10%: reducir 50%

### 5.4 Tools MCP Utilizados

| Tool | Descripción |
|------|-------------|
| `calculate_position_size` | Sizing con todos los ajustes |
| `check_risk_limits` | Validación completa pre-trade |
| `get_portfolio_exposure` | Exposiciones actuales |
| `calculate_var` | VaR del portfolio |

### 5.5 Respuesta de Validación

```json
{
  "approved": true,
  "original_size": 100,
  "adjusted_size": 70,
  "adjustments": [
    {"reason": "high_correlation", "factor": 0.7}
  ],
  "warnings": ["Approaching sector limit (35%/40%)"]
}
```

---

## 6. Execution Agent

### 6.1 Responsabilidades

| Función | Descripción |
|---------|-------------|
| Order routing | Seleccionar broker (IBKR/Kraken) |
| Order type selection | Elegir tipo según condiciones |
| Execution | Enviar y monitorear orden |
| Reporting | Slippage, fills, errores |

### 6.2 Selección de Tipo de Orden

| Condición | Tipo de Orden |
|-----------|---------------|
| Urgencia alta (stop hit) | Market |
| Normal | Limit (midpoint + 1 tick) |
| Tamaño > 5% vol diario | TWAP 15 min |
| IBKR disponible | Adaptive (mejor fill) |

### 6.3 Tools MCP Utilizados

| Tool | Descripción |
|------|-------------|
| `get_account_info` | Balance, buying power |
| `get_positions` | Posiciones actuales |
| `place_order` | Enviar orden |
| `cancel_order` | Cancelar orden pendiente |
| `get_order_status` | Estado de orden |

### 6.4 Manejo de Errores

| Error | Acción |
|-------|--------|
| Conexión perdida | Retry 3x, luego alerta |
| Orden rechazada | Log razón, notificar Orchestrator |
| Fill parcial | Esperar 5 min, luego completar con market |
| Timeout | Verificar estado, cancelar si pending |

---

## 7. MCP Servers

### 7.1 Inventario de Servers

| Server | Lenguaje | Puerto | Función |
|--------|----------|--------|---------|
| mcp-market-data | Python | 3001 | Datos de mercado |
| mcp-technical | Python | 3002 | Análisis técnico |
| mcp-ml-models | Python | 3003 | Predicciones ML |
| mcp-news-sentiment | Python | 3004 | Noticias y NLP |
| mcp-ibkr | Python | 3005 | Trading IBKR |
| mcp-kraken | Python | 3006 | Trading Kraken |
| mcp-risk | Python | 3007 | Gestión de riesgo |

### 7.2 mcp-market-data

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `get_quote` | symbol | {bid, ask, last, volume} |
| `get_ohlcv` | symbol, timeframe, start, end | [{time, o, h, l, c, v}] |
| `get_option_chain` | symbol | {calls: [], puts: []} |
| `stream_subscribe` | symbols | confirmation |

### 7.3 mcp-technical

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `calculate_indicators` | symbol, indicators[], timeframe | {indicator: value} |
| `detect_patterns` | symbol, patterns[], lookback | [{pattern, confidence}] |
| `find_sr_levels` | symbol, method | {support: [], resistance: []} |
| `get_regime` | symbol | {regime, probability, since} |

### 7.4 mcp-ml-models

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `predict` | model_name, features | {prediction, confidence, calibration} |
| `get_model_info` | model_name | {version, metrics, last_trained} |
| `ensemble_predict` | model_names[], features | {prediction, individual_preds} |

### 7.5 mcp-news-sentiment

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `get_news` | symbol, hours_back | [{title, source, time, url}] |
| `analyze_sentiment` | text | {sentiment, score, confidence} |
| `get_aggregated_sentiment` | symbol, hours | {score, article_count, sources} |

### 7.6 mcp-ibkr / mcp-kraken

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `get_account` | - | {balance, buying_power, currency} |
| `get_positions` | - | [{symbol, qty, avg_price, pnl}] |
| `place_order` | order_spec | {order_id, status} |
| `cancel_order` | order_id | {success, message} |
| `get_order_status` | order_id | {status, filled_qty, avg_price} |

### 7.7 mcp-risk

| Tool | Parámetros | Retorno |
|------|------------|---------|
| `check_limits` | proposed_trade | {approved, adjustments, warnings} |
| `calculate_size` | signal, capital | {shares, value, risk_amount} |
| `get_exposure` | - | {by_sector, by_currency, total} |
| `calculate_var` | confidence | {var_amount, var_pct} |

---

## 8. Configuración y Deployment

### 8.1 Archivos de Configuración

**`config/agents.yaml`:**
```yaml
orchestrator:
  decision_threshold: 0.65
  reduced_threshold: 0.50
  escalation_threshold: 0.60
  weights:
    technical: 0.40
    fundamental: 0.30
    sentiment: 0.30

technical_analyst:
  indicators: [RSI, MACD, BB, ADX, ATR]
  timeframes: [1h, 4h, 1d]
  pattern_detection: true

risk_manager:
  # Límites en config (los hardcoded están en código)
  default_risk_per_trade: 0.01
  kelly_fraction: 0.25
```

### 8.2 Estructura de Directorios

```
src/agents/
├── base.py              # Clase base Agent
├── orchestrator.py      # Orchestrator
├── technical.py         # Technical Analyst
├── fundamental.py       # Fundamental Analyst
├── sentiment.py         # Sentiment Analyst
├── risk_manager.py      # Risk Manager
└── execution.py         # Execution Agent

mcp-servers/
├── market-data/
│   ├── server.py
│   └── tools/
├── technical/
├── ml-models/
├── news-sentiment/
├── ibkr/
├── kraken/
└── risk/
```

### 8.3 Inicialización

Orden de arranque:
1. Redis, PostgreSQL, TimescaleDB (infraestructura)
2. MCP Servers (servicios)
3. Risk Manager Agent (debe estar antes que Orchestrator)
4. Agentes analistas (paralelo)
5. Execution Agent
6. Orchestrator (último, depende de todos)

### 8.4 Health Checks

Cada agente expone endpoint `/health`:
```json
{
  "status": "healthy",
  "last_activity": "2024-12-15T14:30:00Z",
  "dependencies": {
    "redis": "ok",
    "mcp-market-data": "ok"
  }
}
```

Orchestrator verifica health cada 30s. Si agente unhealthy > 2 min → modo degradado.

---

## 9. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Límites de riesgo hardcoded | Doc 1 | 4.5 |
| Detección de régimen | Doc 1 | 4.6 |
| Circuit breakers | Doc 1 | 5.2 |
| Modos de operación | Doc 1 | 5.3 |
| Esquema de órdenes/trades | Doc 2 | 2.1 |
| Redis pub/sub canales | Doc 2 | 4.2 |
| Feature Store | Doc 2 | 6 |
| Setup Windows/Docker | Doc 2 | 9 |

---

*Documento 3 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
