# 🏗️ Arquitectura Técnica - Documento 1/7

## Visión General y Arquitectura de Alto Nivel

**Versión:** 2.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Resumen Ejecutivo

### 1.1 Objetivo del Sistema

Sistema de trading algorítmico autónomo basado en arquitectura multi-agente con MCP, Machine Learning adaptativo, y gestión de riesgo automatizada. Ejecución a través de Interactive Brokers (IBKR) y Kraken.

### 1.2 Alcance Técnico

| Aspecto | Especificación |
|---------|----------------|
| **Mercados** | Acciones EU, Forex, Crypto (BTC/ETH), ETFs |
| **Frecuencia** | Swing trading (2-10 días) |
| **Brokers** | IBKR (principal), Kraken (crypto) |
| **Infraestructura** | Self-hosted + Cloud híbrido |
| **Disponibilidad** | 99.5% durante horario de mercado |

### 1.3 Restricciones Clave

**Regulatorias:**
- PDT: Evitar >3 day trades/semana en US (capital < $25k)
- ESMA: Límites de apalancamiento en EU
- MiFID II: Requisitos de reporting

**Técnicas:**
- IBKR API: 50 msg/seg rate limit
- Latencia: No competimos en HFT (>100ms aceptable)

**Capital:**
- Inicial: 1.000€
- Aportaciones: 300-500€/mes
- Horizonte: 3-5 años para capital significativo

### 1.4 Objetivos Cuantitativos y KPIs

**KPIs Primarios (evaluación mensual):**

| KPI | Target Mínimo | Target Óptimo |
|-----|---------------|---------------|
| Sharpe Ratio (rolling 6m) | > 0.8 | > 1.5 |
| Max Drawdown | < 15% | < 10% |
| CAGR | > 8% | > 15% |
| Win Rate | > 45% | > 55% |

**KPIs Secundarios:**
- Profit Factor > 1.3
- Recovery Factor > 2.0
- Ratio operaciones ejecutadas vs. señales generadas

**Triggers de Modo Defensivo (reducción automática de exposición 50%):**
- Drawdown > 10%
- Pérdida semanal > 3%
- Sharpe rolling 30d < 0.5
- Calibración de modelos degradada (ver sección 4.5)

**Triggers de STOP Global (cierre de posiciones, pausa del sistema):**
- Drawdown > 15%
- Pérdida mensual > 8%
- Fallo crítico en data feed > 1 hora
- Desconexión de broker > 30 min durante mercado abierto

---

## 2. Principios de Diseño

### 2.1 Principios Arquitectónicos

| Principio | Implementación |
|-----------|----------------|
| **Modularidad** | Componentes independientes, interfaces bien definidas, desplegables por separado |
| **Resiliencia** | Degradación controlada, auto-healing, alertas inmediatas |
| **Observabilidad** | Logging completo, métricas en tiempo real, historial inmutable |
| **Seguridad** | Mínimo privilegio, secrets centralizados, encriptación en tránsito y reposo |

### 2.2 Patrones Aplicados

- **Event-Driven Architecture:** Comunicación asíncrona, event sourcing para decisiones
- **Multi-Agent System:** Agentes especializados coordinados por orquestador central
- **Circuit Breaker:** Protección ante fallos en cascada (APIs, brokers)
- **CQRS:** Separación de lectura/escritura donde aplique

---

## 3. Arquitectura de Alto Nivel

### 3.1 Diagrama de Capas

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN                         │
│         Dashboard (Grafana) │ Telegram Bot │ API REST           │
├─────────────────────────────────────────────────────────────────┤
│                    CAPA DE ORQUESTACIÓN                         │
│                      ORCHESTRATOR AGENT                         │
├─────────────────────────────────────────────────────────────────┤
│                    CAPA DE AGENTES IA                           │
│  Technical │ Fundamental │ Sentiment │ Risk │ Portfolio │ Exec │
├─────────────────────────────────────────────────────────────────┤
│                    CAPA DE SERVICIOS MCP                        │
│  mcp-market-data │ mcp-ml-models │ mcp-trading │ mcp-risk │... │
├─────────────────────────────────────────────────────────────────┤
│                    CAPA DE DATOS                                │
│     PostgreSQL │ TimescaleDB │ Redis │ InfluxDB                 │
├─────────────────────────────────────────────────────────────────┤
│                    CAPA DE INTEGRACIÓN                          │
│   IBKR │ Kraken │ Yahoo Finance │ NewsAPI │ Alpha Vantage       │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Descripción de Capas

| Capa | Responsabilidad | Tecnologías |
|------|-----------------|-------------|
| Presentación | UI, alertas, API externa | Grafana, Telegram, FastAPI |
| Orquestación | Coordinación central, decisión final | Python, MCP Client |
| Agentes IA | Análisis especializado | Python, LangChain |
| Servicios MCP | Tools y funcionalidades | Node.js/Python, MCP SDK |
| Datos | Persistencia y caché | PostgreSQL, Redis, TimescaleDB |
| Integración | Conexiones externas | APIs REST, WebSocket |

---

## 4. Componentes Principales

### 4.1 Orchestrator (Cerebro Central)

**Responsabilidades:**
- Recibir y ponderar señales de todos los agentes
- Consultar Risk Manager antes de cualquier operación
- Tomar decisión final y emitir órdenes
- Escalar a humano cuando confianza < 60%
- Mantener estado global y logs de decisiones

**Inputs:** Señales de analistas, estado de portfolio, aprobación de riesgo
**Outputs:** Órdenes de trading, alertas, métricas

### 4.2 Agentes de Análisis

| Agente | Función Principal | Outputs |
|--------|-------------------|---------|
| **Technical Analyst** | Indicadores, patrones, S/R | Señales con dirección y confianza |
| **Fundamental Analyst** | Ratios, earnings, valuación | Score fundamental por activo |
| **Sentiment Analyst** | NLP noticias, social media | Score de sentimiento agregado |

### 4.3 Strategy Manager

**Responsabilidades claras (no confundir con Portfolio Manager):**
- Registro de estrategias activas y sus parámetros
- **Asignación dinámica de pesos** entre estrategias basada en:
  - Rolling Sharpe por estrategia (ventana 3 meses)
  - Régimen de mercado actual (ver 4.6)
  - Drawdown reciente de cada estrategia
- Activación/desactivación de estrategias según régimen
- Evaluación continua de rendimiento

**Lógica de pesos (heurística inicial):**
```
peso_estrategia = sharpe_rolling * (1 - dd_reciente/max_dd_tolerado)
Si régimen incompatible → peso = 0
Normalizar pesos para que sumen 1
```

*Nota: Algoritmos más sofisticados (Hedge/Exp3) se considerarán en fases futuras cuando haya suficientes datos.*

### 4.4 Portfolio Manager

**Responsabilidades (distintas de Strategy Manager):**
- Estado actual del portfolio: posiciones, exposiciones, P&L
- Cálculo de correlaciones entre posiciones
- Rebalanceo cuando deriva > umbral
- Exposición por divisa, sector, geografía

**No decide:** qué estrategias usar ni con qué pesos (eso es Strategy Manager).

### 4.5 Risk Manager

**Responsabilidades:**
- Validación pre-trade (límites de posición, sector, correlación)
- Position sizing (Kelly fraccional ajustado por volatilidad)
- Monitorización in-trade (stops, trailing, time stops)
- Cálculo de VaR/ES a nivel portfolio
- **Calibration monitoring:** verificar que modelos ML mantienen calibración

**Límites hardcoded:**

| Límite | Valor | Acción si se viola |
|--------|-------|-------------------|
| Max posición individual | 20% | Rechazar orden |
| Max sector | 40% | Rechazar orden |
| Max correlación entre posiciones | 0.7 | Warning + reducir sizing |
| Max exposición USD | 50% | Rechazar nuevas posiciones USD |
| Max exposición crypto | 15% | Rechazar nuevas posiciones crypto |
| Cash mínimo | 10% | Solo permite cierres |

**Calibration-aware Risk Throttle:**
- Monitoriza calibración de modelos en rolling window (30 días)
- Si frecuencia real de aciertos diverge >15% de probabilidad predicha → modo defensivo
- Reduce sizing 50% hasta que calibración se recupere

### 4.6 Regime Detection Module

**Componente crítico que falta en v1. Estados detectados:**

| Régimen | Características | Estrategias activas |
|---------|-----------------|---------------------|
| **Trending Bull** | ADX>25, precio>SMA200, vol baja | Trend following, momentum |
| **Trending Bear** | ADX>25, precio<SMA200, vol alta | Solo shorts o cash |
| **Range-bound** | ADX<20, vol baja | Mean reversion, pairs |
| **High Volatility** | VIX>25 o ATR>2x normal | Reducir exposición global |
| **Crisis** | VIX>35, correlaciones→1 | Cash, solo hedges |

**Implementación:** HMM (Hidden Markov Model) entrenado con datos históricos. Output: probabilidad de cada régimen. Se usa el régimen más probable.

**Integración:**
- Strategy Manager consulta régimen para activar/desactivar estrategias
- Risk Manager ajusta límites según régimen (más conservador en High Vol/Crisis)
- Features de régimen se pasan a modelos ML

### 4.7 Execution Agent

**Responsabilidades:**
- Conexión con IBKR/Kraken APIs
- Selección de tipo de orden (limit, adaptive, TWAP para órdenes grandes)
- Gestión de fills parciales
- Reporting de slippage

### 4.8 Cost Model Module

**Nuevo componente para estimación y monitorización de costes:**
- Estima slippage esperado según: tipo de orden, volatilidad actual, tamaño relativo al volumen
- Backtests usan este modelo para resultados realistas
- En producción: compara slippage real vs esperado
- Si slippage real > 2x esperado consistentemente → alerta + revisar ejecución

**Modelo simplificado inicial:**
```
slippage_estimado = spread_medio * (1 + volatilidad_normalizada * 0.5)
                   + impacto_volumen si orden > 1% volumen_diario
```

---

## 5. Sistema de Circuit Breakers y Kill Switch

### 5.1 Kill Switch Global

**Activación automática si:**
- Drawdown > 15%
- Pérdida diaria > 3%
- Pérdida semanal > 5%
- Error crítico no recuperable

**Activación manual:** Comando via Telegram o API

**Acción:** Cierra todas las posiciones con órdenes market, pausa toda nueva operativa.

**Reactivación:** Solo manual, requiere revisión y confirmación explícita.

### 5.2 Circuit Breakers por Componente

| Componente | Condición de apertura | Modo degradado |
|------------|----------------------|----------------|
| Data feed (precios) | Sin datos >5 min | Pausar nuevas entradas, mantener stops |
| Data feed (noticias) | Sin datos >1 hora | Solo estrategias técnicas |
| Broker connection | Desconexión >2 min | Alertar, reintentar, escalar |
| ML models | Error de predicción | Usar última predicción válida o pausar estrategia |
| Sentiment Agent | API caída | Operar sin filtro sentiment (mayor conservadurismo) |

### 5.3 Modos de Operación

| Modo | Descripción | Trigger |
|------|-------------|---------|
| **Normal** | Operativa completa | Default |
| **Defensivo** | 50% exposición, solo alta confianza | DD>10%, calibración degradada |
| **Observación** | Genera señales pero no ejecuta | Fallo parcial de sistemas |
| **Pausa** | Solo gestiona posiciones existentes | Kill switch manual |
| **Emergencia** | Cierra todo | Kill switch automático |

---

## 6. Flujos de Datos

### 6.1 Flujo Principal de Trading

1. **Ingesta:** Market data + News → Data Pipeline → Feature Store → Cache
2. **Análisis:** Feature Store → Analysts (Tech/Fund/Sent) → Señales agregadas
3. **Régimen:** Features → Regime Detection → Estado actual del mercado
4. **Decisión:** Señales + Régimen → Orchestrator → Risk Manager → Aprobación
5. **Sizing:** Señal aprobada → Position Sizer (Kelly + ajustes) → Tamaño final
6. **Ejecución:** Orden → Execution Agent → Broker → Fill
7. **Post-trade:** Fill → Portfolio Update → P&L → Metrics → Risk Recalc

### 6.2 Flujo de Comunicación MCP

Los agentes se comunican con MCP Servers mediante tool calls estándar:
- Agent solicita: `tools/call` con nombre de tool y argumentos
- Server responde: resultado estructurado (JSON)
- Ejemplo: Technical Analyst llama `calculate_indicators(symbol="AAPL", indicators=["RSI","MACD"])`

---

## 7. Stack Tecnológico

### 7.1 Tecnologías Principales

| Categoría | Tecnología | Uso |
|-----------|------------|-----|
| **Core** | Python 3.11+ | Sistema principal, ML |
| **MCP** | TypeScript/Node | MCP Servers |
| **API** | FastAPI | APIs REST internas |
| **ML** | PyTorch, scikit-learn | Modelos predictivos |
| **Backtesting** | vectorbt, backtrader | Validación de estrategias |
| **Broker** | ib_insync, ccxt | Conexión IBKR/Kraken |
| **NLP** | transformers (FinBERT) | Análisis de sentimiento |

### 7.2 Bases de Datos

| BD | Uso | Datos |
|----|-----|-------|
| PostgreSQL 15+ | Principal | Config, trades, logs |
| TimescaleDB | Series temporales | OHLCV histórico |
| Redis 7+ | Cache, pub/sub | Quotes real-time, eventos |
| InfluxDB | Métricas | Performance del sistema |

### 7.3 Infraestructura

- Docker + Docker Compose para desarrollo y staging
- Grafana para dashboards
- Prometheus para métricas
- Nginx como reverse proxy (producción)

---

## 8. Estructura del Proyecto

```
trading-bot/
├── src/
│   ├── core/           # Orchestrator, config, events, exceptions
│   ├── agents/         # Todos los agentes (base + especializados)
│   ├── strategies/     # Implementaciones de estrategias
│   ├── ml/
│   │   ├── models/     # TFT, HMM, ensemble
│   │   ├── features/   # Feature engineering
│   │   └── training/   # Pipelines de entrenamiento
│   ├── trading/        # Engine, order manager, execution
│   ├── risk/           # Risk manager, position sizer, cost model
│   ├── data/           # Pipelines, providers, feature store
│   └── regime/         # Regime detection module
├── mcp-servers/        # Servers MCP (Node.js/Python)
├── tests/              # Unit, integration, e2e
├── config/             # Configuración por entorno
├── scripts/            # Utilidades, deployment
└── docs/               # Documentación
```

---

## 9. MLOps (Enfoque Progresivo)

### 9.1 Fase 1 (Inicial - Actual)

- Versionado de datos con DVC
- Logs de experimentos en YAML/JSON estructurado
- Modelos guardados con timestamp y hash de config
- Backtest results versionados

### 9.2 Fase 2 (Cuando hay 2+ modelos en producción)

- MLflow local para experiment tracking
- Model registry básico
- Comparación automática champion vs challenger en paper trading

### 9.3 Fase 3 (Sistema rentable y estable)

- MLOps completo con model registry formal
- A/B testing en producción (% de capital por modelo)
- Retraining automatizado con guardrails
- Rollback automático si nuevo modelo underperforma

---

## 10. Entornos de Ejecución

| Entorno | Propósito | Datos | Trading Real |
|---------|-----------|-------|--------------|
| Development | Desarrollo local | Mocked/Sample | No |
| Testing | CI/CD | Historical | No |
| Staging | Paper trading | Real-time | No (Paper) |
| Production | Trading real | Real-time | Sí |

### 10.1 Requisitos de Hardware

| Entorno | CPU | RAM | Disco | Red |
|---------|-----|-----|-------|-----|
| Development | 4 cores | 16 GB | 100 GB SSD | Estable |
| Staging | 4 vCPU | 8 GB | 200 GB SSD | 100 Mbps |
| Production | 8 vCPU | 16 GB | 500 GB NVMe | 1 Gbps, <50ms a broker |

### 10.2 Costes Estimados (Cloud)

- Development: $0 (local)
- Staging: ~$30-50/mes
- Production: ~$50-100/mes
- Datos adicionales: ~$0-50/mes según fuentes

---

## 11. Próximos Documentos

| # | Documento | Contenido principal |
|---|-----------|---------------------|
| 2 | Arquitectura de Datos | Esquemas BD, pipelines, feature store |
| 3 | Sistema de Agentes MCP | Detalle de cada agente y MCP server |
| 4 | Motor de Trading | Estrategias, backtesting, ejecución |
| 5 | Machine Learning | Modelos, training, validación |
| 6 | Gestión de Riesgo | Risk manager, position sizing, circuit breakers |
| 7 | Operaciones | Deployment, monitoring, runbooks |

---

*Documento 1 de 7 - Arquitectura Técnica del Bot de Trading*
*Versión 2.0 - Revisada con feedback de comentarios*
