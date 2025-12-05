# 🔄 Nexus Trading - Contexto para Continuación

## Documento de Handoff

**Fecha:** Diciembre 2024  
**Estado:** Listo para generar documentos de implementación  
**Próximo paso:** `fase_a1_extensiones_base.md`

---

## 1. Decisiones Confirmadas

### 1.1 Configuración General

| Aspecto | Decisión |
|---------|----------|
| Capital paper trading | 25.000€ |
| Fuente de datos principal | IBKR (no Yahoo Finance) |
| Datos real-time | Delayed OK para desarrollo (15 min en paper) |
| Mercados | EU + US (más oportunidades) |
| LLM para AI Agent | Claude (con arquitectura para cambiar a GPT-4/Gemini) |
| Autonomía AI Agent | Moderado por defecto, configurable (conservative/moderate/experimental) |

### 1.2 Filosofía del Proyecto

```
PRINCIPIOS CLAVE:
═════════════════

1. MVP funcionando en paper trading ANTES de backtesting perfecto
   - El paper trading ES el laboratorio
   - Feedback real > métricas históricas

2. Arquitectura modular e intercambiable
   - Modelos ML: interface común, implementaciones swappeables
   - LLMs: interface común, fácil cambiar Claude ↔ GPT-4 ↔ Gemini
   - Estrategias: interface común, activar/desactivar por config

3. Métricas para comparar todo
   - Cada trade tagged con: estrategia, modelo, régimen, etc.
   - Sistema de experimentos A/B
   - Dashboard comparativo

4. Swing primero, intradía después
   - Menos partes móviles inicialmente
   - Intradía se añade cuando swing funcione
```

### 1.3 Orden de Implementación

```
Fase A: Core + ML (2 semanas)
├── A1: Extensiones a Fases 0-3 existentes
│   ├── IBKR como fuente principal de datos
│   ├── Nuevas tablas de métricas en PostgreSQL
│   └── mcp-ml-models server
└── A2: ML Modular
    ├── Interfaces (RegimeDetector ABC)
    ├── HMM implementación
    ├── Rules baseline (comparación)
    └── Factory + configuración YAML

Fase B: Estrategias Swing (2 semanas)
├── B1: ETF Momentum
│   ├── Interfaces (TradingStrategy ABC)
│   ├── Implementación
│   └── Integración con HMM
└── B2: AI Agent
    ├── Interfaces (LLMAgent ABC)
    ├── Claude Agent
    ├── Prompts por autonomía
    └── Ejecución paralela con ETF Momentum

Fase C: Métricas + Intradía (2 semanas)
├── C1: Sistema de métricas
│   ├── Collector de trades
│   ├── Agregador de métricas
│   ├── Experimentos A/B
│   └── Dashboard Grafana
└── C2: Intradía (después del MVP swing)
    ├── Mean Reversion Intraday
    ├── Volatility Breakout
    └── Toggle datos real-time
```

---

## 2. Estado de Fases 0-3 (Existentes)

### 2.1 Resumen de Reutilización

| Fase | Reutilizable | Cambios Necesarios |
|------|--------------|-------------------|
| Fase 0: Infraestructura | 100% | Solo añadir tablas métricas |
| Fase 1: Data Pipeline | 80% | Cambiar Yahoo → IBKR |
| Fase 2: MCP Servers | 90% | Añadir mcp-ml-models |
| Fase 3: Agentes Core | 70% | Añadir interfaces + AI Agent |

### 2.2 Qué Existe (Documentado)

```
FASE 0 - INFRAESTRUCTURA ✅
├── Docker Compose (PostgreSQL, TimescaleDB, Redis, InfluxDB, Grafana)
├── Esquemas de BD iniciales
├── Scripts de verificación
└── requirements.txt base

FASE 1 - DATA PIPELINE ✅
├── Estructura de pipeline
├── Feature Store (30+ features)
├── Scheduler de actualización
├── Indicadores técnicos (RSI, MACD, BB, ADX, ATR, etc.)
└── Conector Yahoo (a reemplazar por IBKR)

FASE 2 - MCP SERVERS ✅
├── BaseMCPServer (clase común)
├── mcp-market-data (puerto 3001)
├── mcp-technical (puerto 3002)
├── mcp-risk (puerto 3003)
├── mcp-ibkr (puerto 3004)
└── Tests de integración

FASE 3 - AGENTES CORE ✅
├── Clase base Agent
├── Sistema pub/sub Redis
├── Technical Analyst
├── Risk Manager
├── Orchestrator básico
└── Schemas de mensajes (Pydantic)
```

### 2.3 Qué Añadimos (Nuevo)

```
NUEVO - ML MODULAR
├── src/ml/
│   ├── interfaces.py        # RegimeDetector ABC
│   ├── factory.py           # Crear modelos según config
│   └── models/
│       ├── hmm_regime.py    # HMM con hmmlearn
│       ├── rules_baseline.py # Baseline simple
│       └── ppo_regime.py    # Futuro: RL

NUEVO - ESTRATEGIAS MODULARES
├── src/strategies/
│   ├── interfaces.py        # TradingStrategy ABC, Signal dataclass
│   ├── swing/
│   │   ├── etf_momentum.py
│   │   └── ai_agent_swing.py
│   └── intraday/
│       ├── mean_reversion.py
│       └── breakout.py

NUEVO - AI AGENT (LLM)
├── src/agents/llm/
│   ├── interfaces.py        # LLMAgent ABC, AgentDecision dataclass
│   ├── claude_agent.py
│   └── prompts/
│       ├── conservative.py
│       ├── moderate.py
│       └── experimental.py

NUEVO - MÉTRICAS
├── src/metrics/
│   ├── collector.py         # Captura trades, decisiones
│   ├── aggregator.py        # Calcula Sharpe, MaxDD, etc.
│   ├── experiments.py       # A/B testing
│   └── schemas.py

NUEVO - MCP SERVER
└── mcp-servers/mcp-ml-models/
    ├── src/index.ts
    └── python/serve.py
```

---

## 3. Arquitectura de Interfaces (Clave)

### 3.1 RegimeDetector (ML)

```python
@dataclass
class RegimePrediction:
    regime: str                    # "BULL", "BEAR", "SIDEWAYS", "VOLATILE"
    confidence: float              # 0.0 - 1.0
    probabilities: dict[str, float]  # {"BULL": 0.7, "BEAR": 0.1, ...}
    model_id: str                  # "hmm_v1", "ppo_v1", etc.
    inference_time_ms: float
    metadata: Optional[dict] = None

class RegimeDetector(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> "RegimeDetector": ...
    
    @abstractmethod
    def predict(self, X: np.ndarray) -> RegimePrediction: ...
    
    @abstractmethod
    def save(self, path: str) -> None: ...
    
    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "RegimeDetector": ...
```

### 3.2 TradingStrategy

```python
@dataclass
class Signal:
    strategy_id: str
    symbol: str
    direction: str              # "LONG", "SHORT", "CLOSE"
    confidence: float
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    size_suggestion: Optional[float]
    regime_at_signal: str
    reasoning: Optional[str]
    metadata: Optional[dict]

class TradingStrategy(ABC):
    @property
    @abstractmethod
    def strategy_id(self) -> str: ...
    
    @property
    @abstractmethod
    def required_regime(self) -> list[str]: ...
    
    @abstractmethod
    def generate_signals(self, market_data, regime, portfolio) -> list[Signal]: ...
    
    @abstractmethod
    def should_close(self, position, market_data, regime) -> Optional[Signal]: ...
```

### 3.3 LLMAgent

```python
@dataclass
class AgentDecision:
    actions: list[Signal]
    reasoning: str
    market_view: str            # "bullish", "bearish", "neutral"
    confidence: float
    model_used: str
    autonomy_level: str
    tokens_used: int

class LLMAgent(ABC):
    @property
    @abstractmethod
    def agent_id(self) -> str: ...
    
    @abstractmethod
    async def decide(self, context, autonomy_level="moderate") -> AgentDecision: ...
    
    @abstractmethod
    def get_system_prompt(self, autonomy_level: str) -> str: ...
```

---

## 4. HMM - Resumen Técnico

### 4.1 Qué Es

Hidden Markov Model para detectar "régimen" del mercado (estado oculto) a partir de observaciones (features).

### 4.2 Estados

| Estado | Características | Estrategias Activas |
|--------|-----------------|---------------------|
| BULL | Retornos +, vol baja, ADX moderado | ETF Momentum, AI Agent |
| BEAR | Retornos -, vol alta, ADX alto | Solo cierres |
| SIDEWAYS | Retornos ~0, vol baja, ADX bajo | Mean Reversion |
| VOLATILE | Vol muy alta, retornos variables | Pausar todo |

### 4.3 Features de Entrada

```python
hmm_features = [
    'returns_5d',       # Momentum semanal
    'volatility_20d',   # Riesgo reciente
    'adx_14',           # Fuerza de tendencia
    'volume_ratio',     # Actividad vs normal
]
```

### 4.4 Entrenamiento

- Datos: 4-5 años históricos (2019-2024)
- Librería: hmmlearn (GaussianHMM)
- Validación: Walk-forward simple (no complicar)
- Reentrenamiento: Cada 3-6 meses

---

## 5. Estrategias Planificadas

### 5.1 Swing (Prioridad Alta)

| ID | Nombre | Descripción |
|----|--------|-------------|
| `etf_momentum` | ETF Momentum | RSI + tendencia en ETFs EU/US |
| `ai_agent_swing` | AI Agent Swing | Claude decide basándose en contexto |

### 5.2 Intradía (Después del MVP)

| ID | Nombre | Descripción |
|----|--------|-------------|
| `mean_reversion_intraday` | Mean Reversion | Comprar caídas, vender subidas intradía |
| `volatility_breakout` | Breakout | Subirse a rupturas de rango |

### 5.3 Experimentales (Futuro)

| ID | Nombre | Descripción |
|----|--------|-------------|
| `ppo_regime` | PPO Regime | RL para detección de régimen |
| `rl_trading` | RL Trading | RL para decisiones de trading |

---

## 6. Configuración YAML

### 6.1 Modelos ML

```yaml
# config/models.yaml
regime_detector:
  active: "hmm"  # Cambiar a "ppo" o "rules"
  models:
    hmm:
      n_states: 4
      covariance_type: "full"
      n_iter: 100
      features: ["returns_5d", "volatility_20d", "adx_14", "volume_ratio"]
    rules:
      bull_threshold: 0.02
      bear_threshold: -0.02
      volatility_high: 0.25
```

### 6.2 AI Agent

```yaml
# config/agents.yaml
ai_agent:
  active: "claude"
  autonomy_level: "moderate"  # conservative, moderate, experimental
  models:
    claude:
      model: "claude-sonnet-4-20250514"
      max_tokens: 2000
      temperature: 0.3
```

### 6.3 Datos

```yaml
# config/data_sources.yaml
data_source:
  primary: "ibkr"
  ibkr:
    host: "127.0.0.1"
    port: 7497              # Paper trading
    client_id: 1
    delayed_ok: true        # Aceptamos 15 min delay
  fallback: "yahoo"
```

---

## 7. Métricas a Capturar

### 7.1 Por Trade

```python
trade_record = {
    "trade_id": "uuid",
    "timestamp": "ISO datetime",
    "strategy_id": "etf_momentum",
    "model_id": "hmm_v1",
    "agent_id": "claude_moderate",  # Si aplica
    "symbol": "VWCE.DE",
    "direction": "LONG",
    "entry_price": 100.50,
    "exit_price": 103.20,
    "pnl_eur": 67.16,
    "pnl_pct": 2.68,
    "holding_hours": 72,
    "regime_at_entry": "BULL",
    "regime_confidence": 0.78,
    "reasoning": "..."  # Si es AI Agent
}
```

### 7.2 Agregadas

- Sharpe Ratio, Sortino Ratio, Calmar Ratio
- Max Drawdown, VaR 95%
- Win Rate, Profit Factor
- Por dimensión: estrategia, modelo, régimen, período, mercado

---

## 8. Documentos a Generar

| # | Documento | Contenido |
|---|-----------|-----------|
| 1 | `fase_a1_extensiones_base.md` | Modificaciones Fases 0-3, IBKR, tablas métricas |
| 2 | `fase_a2_ml_modular.md` | Interfaces ML, HMM, Rules baseline, Factory |
| 3 | `fase_b1_estrategias_swing.md` | Interfaces Strategy, ETF Momentum |
| 4 | `fase_b2_ai_agent.md` | Interfaces LLM, Claude Agent, Prompts |
| 5 | `fase_c1_metricas.md` | Collector, Aggregator, A/B, Dashboard |
| 6 | `fase_c2_intraday.md` | Mean Reversion, Breakout (post-MVP) |

---

## 9. Para Continuar

En la nueva conversación:

1. Adjuntar este documento (`nexus_trading_handoff.md`)
2. Decir: "Continuamos con fase_a1_extensiones_base.md"
3. El documento incluirá:
   - Modificaciones a esquemas BD (tablas métricas)
   - Cambio de Yahoo → IBKR como fuente principal
   - Nuevo mcp-ml-models server
   - Scripts de migración/verificación

---

## 10. Repositorio

**GitHub:** https://github.com/oarjones/nexus-trading

**Estructura actual del proyecto:**
- Documentos técnicos: `01_arquitectura_vision_general.md` hasta `07_operaciones.md`
- Documentos de fase: `fase_0_infraestructura.md` hasta `fase_5_ml_pipeline.md`
- Roadmap: `00_roadmap.md`

---

*Documento de Handoff - Nexus Trading*  
*Para continuar desarrollo en nueva conversación*
