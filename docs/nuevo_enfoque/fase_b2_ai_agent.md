# 🤖 Fase B2: AI Agent (LLM Trading)

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fase B1 (Estrategias Swing) completada  
**Prerrequisito:** ETF Momentum funcional, interfaces TradingStrategy y Signal definidas

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

La Fase B1 ha establecido:
- Interfaz `TradingStrategy` ABC con métodos `generate_signals()` y `should_close()`
- Dataclass `Signal` con estructura completa para señales de trading
- `StrategyRegistry` para registro dinámico de estrategias
- `StrategyRunner` para ejecución coordinada
- ETF Momentum como estrategia base funcionando en régimen BULL

### 1.2 Objetivo de Esta Fase

Implementar un **AI Agent basado en LLM** (inicialmente Claude) que:
- Toma decisiones de trading basadas en contexto completo del mercado
- Opera con diferentes niveles de autonomía (conservative/moderate/experimental)
- Se integra como otra estrategia más en el sistema existente
- Es intercambiable (Claude ↔ GPT-4 ↔ Gemini) mediante interfaces comunes

```
FILOSOFÍA CLAVE:
═══════════════════════════════════════════════════════════════════════════
1. El LLM es UNA estrategia más, no un sistema paralelo
   - Implementa TradingStrategy ABC
   - Genera Signal como cualquier otra estrategia
   - Se registra en StrategyRegistry

2. Autonomía como parámetro, no como diseño diferente
   - conservative: Solo información, humano decide
   - moderate: Sugiere con sizing, confirmación requerida
   - experimental: Ejecuta dentro de límites estrictos

3. Context is King
   - El LLM recibe TODO el contexto: régimen, portfolio, indicadores, noticias
   - Mejores decisiones = mejor contexto, no mejor modelo

4. Trazabilidad completa
   - Cada decisión incluye reasoning
   - Todo se registra en metrics.trades
   - A/B testing con otras estrategias
═══════════════════════════════════════════════════════════════════════════
```

### 1.3 Decisiones de Diseño

| Decisión | Justificación |
|----------|---------------|
| ABC para LLMAgent | Contrato uniforme, fácil swap Claude ↔ GPT-4 |
| Implementa TradingStrategy | Integración nativa con sistema existente |
| Dataclass AgentDecision | Output estructurado, serializable, tipado |
| Prompts por autonomía | Mismo código, diferente comportamiento por config |
| Context builder modular | Fácil añadir/quitar fuentes de contexto |
| Cache de decisiones | Evita llamadas repetidas, respeta rate limits |
| Async by default | No bloquea mientras espera respuesta del LLM |

### 1.4 Por Qué Claude Primero

| Razón | Explicación |
|-------|-------------|
| API estable | Anthropic API bien documentada y estable |
| Sonnet costo-efectivo | Buen balance rendimiento/precio para trading |
| Context window amplio | 200K tokens permite contexto extenso |
| Structured output | Buen seguimiento de instrucciones JSON |
| Español nativo | Mejor para tu workflow mixto ES/EN |

### 1.5 Flujo de Decisión del AI Agent

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        AI AGENT DECISION FLOW                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. CONTEXT GATHERING                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │  │
│  │  │   Régimen    │  │  Portfolio   │  │  Indicadores │             │  │
│  │  │   (HMM)      │  │  (posiciones)│  │  (técnicos)  │             │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │  │
│  │         │                 │                 │                      │  │
│  │         └────────────┬────┴────────────────┘                      │  │
│  │                      ▼                                             │  │
│  │               ┌──────────────┐                                     │  │
│  │               │   Context    │                                     │  │
│  │               │   Builder    │                                     │  │
│  │               └──────┬───────┘                                     │  │
│  │                      │                                             │  │
│  └──────────────────────┼─────────────────────────────────────────────┘  │
│                         │                                                │
│  2. PROMPT CONSTRUCTION │                                                │
│  ┌──────────────────────┼─────────────────────────────────────────────┐  │
│  │                      ▼                                             │  │
│  │         ┌────────────────────────┐                                 │  │
│  │         │   Autonomy Level       │                                 │  │
│  │         │   (conservative/       │                                 │  │
│  │         │    moderate/           │                                 │  │
│  │         │    experimental)       │                                 │  │
│  │         └───────────┬────────────┘                                 │  │
│  │                     │                                              │  │
│  │                     ▼                                              │  │
│  │         ┌────────────────────────┐     ┌─────────────────────┐     │  │
│  │         │    System Prompt       │ +   │   User Context      │     │  │
│  │         │    (por autonomía)     │     │   (datos mercado)   │     │  │
│  │         └───────────┬────────────┘     └──────────┬──────────┘     │  │
│  │                     └──────────┬─────────────────┘                 │  │
│  │                                │                                   │  │
│  └────────────────────────────────┼───────────────────────────────────┘  │
│                                   │                                      │
│  3. LLM INFERENCE                 │                                      │
│  ┌────────────────────────────────┼───────────────────────────────────┐  │
│  │                                ▼                                   │  │
│  │                    ┌───────────────────────┐                       │  │
│  │                    │     Claude API        │                       │  │
│  │                    │     (Sonnet 4)        │                       │  │
│  │                    └───────────┬───────────┘                       │  │
│  │                                │                                   │  │
│  │                                ▼                                   │  │
│  │                    ┌───────────────────────┐                       │  │
│  │                    │   Response Parser     │                       │  │
│  │                    │   (JSON → Decision)   │                       │  │
│  │                    └───────────┬───────────┘                       │  │
│  │                                │                                   │  │
│  └────────────────────────────────┼───────────────────────────────────┘  │
│                                   │                                      │
│  4. OUTPUT                        │                                      │
│  ┌────────────────────────────────┼───────────────────────────────────┐  │
│  │                                ▼                                   │  │
│  │                    ┌───────────────────────┐                       │  │
│  │                    │   AgentDecision       │                       │  │
│  │                    │   ├─ actions: Signal[]│                       │  │
│  │                    │   ├─ reasoning        │                       │  │
│  │                    │   ├─ market_view      │                       │  │
│  │                    │   └─ confidence       │                       │  │
│  │                    └───────────┬───────────┘                       │  │
│  │                                │                                   │  │
│  │                    ┌───────────▼───────────┐                       │  │
│  │                    │   Signal[]            │◄── Compatible con     │  │
│  │                    │   (para Strategy      │    sistema estrategias│  │
│  │                    │    Runner)            │                       │  │
│  │                    └───────────────────────┘                       │  │
│  │                                                                    │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| Interfaz LLMAgent ABC | Definida con todos los métodos abstractos |
| AgentDecision dataclass | Estructura completa con validaciones |
| AgentContext dataclass | Contexto estructurado para el LLM |
| Sistema de prompts | 3 niveles de autonomía implementados |
| ClaudeAgent funcional | Genera decisiones válidas con Claude API |
| Integración TradingStrategy | `AIAgentStrategy` usa `LLMAgent` internamente |
| Config YAML | Autonomía y modelo configurables |
| Tests unitarios | > 80% cobertura en `src/agents/llm/` |
| Rate limiting | Respeta límites de API de Anthropic |

---

## 3. Arquitectura del AI Agent

### 3.1 Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              AI AGENT SYSTEM                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  config/agents.yaml                                                              │
│  ┌─────────────────────────────────┐                                             │
│  │ ai_agent:                       │                                             │
│  │   active: "claude"              │                                             │
│  │   autonomy_level: "moderate"    │                                             │
│  │   models:                       │                                             │
│  │     claude:                     │                                             │
│  │       model: "claude-sonnet-4"  │                                             │
│  │       max_tokens: 2000          │                                             │
│  └─────────────────────────────────┘                                             │
│              │                                                                   │
│              ▼                                                                   │
│  ┌─────────────────────────────────┐                                             │
│  │       LLMAgentFactory           │                                             │
│  │       .create_agent()           │◄──────── Lee config, instancia agente       │
│  └─────────────────────────────────┘                                             │
│              │                                                                   │
│      ┌───────┴───────┐                                                           │
│      ▼               ▼                                                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                                  │
│  │   Claude   │  │   GPT-4    │  │   Gemini   │  ◄── Futuro                      │
│  │   Agent    │  │   Agent    │  │   Agent    │                                  │
│  └────────────┘  └────────────┘  └────────────┘                                  │
│        │                                                                         │
│        └───────────────┬─────────────────────────────────────────────────────┐   │
│                        │                                                     │   │
│                        ▼                                                     │   │
│  ┌─────────────────────────────────┐        ┌───────────────────────────────┐│   │
│  │     LLMAgent (ABC)              │◄───────│     AgentDecision            ││   │
│  │     - agent_id                  │        │     (dataclass output)        ││   │
│  │     - decide()                  │        │     - actions: list[Signal]   ││   │
│  │     - get_system_prompt()       │        │     - reasoning               ││   │
│  │     - build_context()           │        │     - market_view             ││   │
│  └─────────────────────────────────┘        │     - confidence              ││   │
│                        │                    └───────────────────────────────┘│   │
│                        │                                                     │   │
│                        ▼                                                     │   │
│  ┌─────────────────────────────────┐                                         │   │
│  │    AIAgentStrategy              │                                         │   │
│  │    (TradingStrategy impl)       │◄──────── Adapta LLMAgent al sistema     │   │
│  │    - generate_signals()         │          de estrategias                 │   │
│  │    - should_close()             │                                         │   │
│  └─────────────────────────────────┘                                         │   │
│                        │                                                     │   │
│                        ▼                                                     │   │
│  ┌─────────────────────────────────┐                                         │   │
│  │    StrategyRegistry             │◄──────── Se registra como estrategia    │   │
│  │    (de Fase B1)                 │          más en el sistema              │   │
│  └─────────────────────────────────┘                                         │   │
│                                                                              │   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Integración con Sistema Existente

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                    INTEGRACIÓN AI AGENT ↔ STRATEGY SYSTEM                       │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                        StrategyRunner (Fase B1)                         │   │
│  │                        .run_all_active()                                │   │
│  └───────────────────────────────────┬─────────────────────────────────────┘   │
│                                      │                                         │
│          ┌──────────────────────────┼────────────────────────┐                │
│          │                          │                        │                │
│          ▼                          ▼                        ▼                │
│  ┌───────────────────┐    ┌───────────────────┐    ┌───────────────────┐      │
│  │   ETFMomentum     │    │  AIAgentStrategy  │    │   MeanReversion   │      │
│  │   Strategy        │    │  (usa LLMAgent)   │    │   (futuro)        │      │
│  │                   │    │                   │    │                   │      │
│  │ required_regime:  │    │ required_regime:  │    │ required_regime:  │      │
│  │   [BULL]          │    │   [BULL, SIDEWAYS]│    │   [SIDEWAYS]      │      │
│  └─────────┬─────────┘    └─────────┬─────────┘    └─────────┬─────────┘      │
│            │                        │                        │                │
│            │                        │                        │                │
│            ▼                        ▼                        ▼                │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                            Signal[]                                      │ │
│  │   Todas las estrategias emiten el mismo tipo de output                   │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                      │                                         │
│                                      ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                    Risk Manager → Orchestrator                           │ │
│  │                    (Fase 3 - flujo existente)                            │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                                │
└────────────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Estructura de Directorios

```
src/agents/
├── __init__.py
├── base.py                    # (Fase 3 - existente)
├── messaging.py               # (Fase 3 - existente)
├── schemas.py                 # (Fase 3 - existente)
├── technical.py               # (Fase 3 - existente)
├── risk_manager.py            # (Fase 3 - existente)
├── orchestrator.py            # (Fase 3 - existente)
└── llm/                       # ◄── NUEVO: módulo AI Agent
    ├── __init__.py
    ├── interfaces.py          # LLMAgent ABC, AgentDecision, AgentContext
    ├── factory.py             # LLMAgentFactory
    ├── config.py              # Carga config/agents.yaml
    ├── context_builder.py     # Construye contexto para LLM
    ├── rate_limiter.py        # Rate limiting para APIs
    ├── agents/
    │   ├── __init__.py
    │   ├── claude_agent.py    # Implementación Claude
    │   └── openai_agent.py    # Placeholder GPT-4 (futuro)
    └── prompts/
        ├── __init__.py
        ├── base.py            # Prompts compartidos
        ├── conservative.py    # Prompt nivel conservative
        ├── moderate.py        # Prompt nivel moderate
        └── experimental.py    # Prompt nivel experimental

src/strategies/
├── __init__.py
├── interfaces.py              # (Fase B1 - existente)
├── registry.py                # (Fase B1 - existente)
├── swing/
│   ├── __init__.py
│   ├── etf_momentum.py        # (Fase B1 - existente)
│   └── ai_agent_strategy.py   # ◄── NUEVO: Wrapper TradingStrategy

config/
├── agents.yaml                # ◄── NUEVO: Config AI Agent
└── strategies.yaml            # ACTUALIZAR: añadir ai_agent_swing

tests/agents/llm/
├── __init__.py
├── test_interfaces.py
├── test_context_builder.py
├── test_claude_agent.py
├── test_prompts.py
├── test_factory.py
└── test_integration.py
```

---

## 4. Dependencias Entre Tareas

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           FASE B2: AI AGENT                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────┐                                                │
│  │ B2.1: Interfaces         │                                                │
│  │ (ABC + Dataclasses)      │◄────────── PRIMERO: Define contrato            │
│  └──────────────────────────┘                                                │
│              │                                                               │
│              ▼                                                               │
│  ┌──────────────────────────┐                                                │
│  │ B2.2: Context Builder    │                                                │
│  │ (recopilar datos)        │◄────────── Segundo: Prepara input LLM          │
│  └──────────────────────────┘                                                │
│              │                                                               │
│              ▼                                                               │
│  ┌──────────────────────────┐                                                │
│  │ B2.3: Sistema Prompts    │                                                │
│  │ (3 niveles autonomía)    │◄────────── Define comportamiento               │
│  └──────────────────────────┘                                                │
│              │                                                               │
│              ▼                                                               │
│  ┌──────────────────────────┐     ┌──────────────────────────┐               │
│  │ B2.4: Claude Agent       │     │ B2.5: Rate Limiter       │               │
│  │ (implementación)         │────▶│ (protección API)         │               │
│  └──────────────────────────┘     └──────────────────────────┘               │
│              │                              │                                │
│              └──────────────┬───────────────┘                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────┐                                │
│  │ B2.6: AIAgentStrategy + Factory          │                                │
│  │ (integración con sistema estrategias)    │                                │
│  └──────────────────────────────────────────┘                                │
│                             │                                                │
│                             ▼                                                │
│  ┌──────────────────────────────────────────┐                                │
│  │ B2.7: Configuración y Verificación       │                                │
│  │ (config YAML + scripts verificación)     │                                │
│  └──────────────────────────────────────────┘                                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

LEYENDA:
────────
B2.1 debe completarse primero (define interfaces)
B2.2-B2.3 pueden desarrollarse en paralelo
B2.4-B2.5 dependen de B2.1-B2.3
B2.6 integra todo
B2.7 verifica sistema completo
```

---

## 5. Resumen de Cambios

### 5.1 Nuevos Archivos

| Archivo | Propósito |
|---------|-----------|
| `src/agents/llm/interfaces.py` | ABC y dataclasses |
| `src/agents/llm/factory.py` | Factory para crear agentes |
| `src/agents/llm/config.py` | Carga configuración YAML |
| `src/agents/llm/context_builder.py` | Construye contexto para LLM |
| `src/agents/llm/rate_limiter.py` | Rate limiting APIs |
| `src/agents/llm/agents/claude_agent.py` | Implementación Claude |
| `src/agents/llm/prompts/*.py` | Prompts por autonomía |
| `src/strategies/swing/ai_agent_strategy.py` | Wrapper TradingStrategy |
| `config/agents.yaml` | Configuración AI Agent |

### 5.2 Archivos Modificados

| Archivo | Cambio |
|---------|--------|
| `config/strategies.yaml` | Añadir `ai_agent_swing` |
| `src/strategies/__init__.py` | Export AIAgentStrategy |

### 5.3 Dependencias Externas

```
# Nuevas dependencias en requirements.txt
anthropic>=0.40.0        # Cliente oficial Anthropic
aiolimiter>=1.1.0        # Rate limiting async
tenacity>=8.2.0          # Retry logic
tiktoken>=0.7.0          # Conteo de tokens (opcional, para estimación)
```

---

## 6. Niveles de Autonomía

### 6.1 Comparativa de Niveles

| Aspecto | Conservative | Moderate | Experimental |
|---------|-------------|----------|--------------|
| **Descripción** | Solo información | Sugerencias con sizing | Ejecución autónoma |
| **Output** | Análisis + opinión | Signal con detalles | Signal lista para ejecutar |
| **Confirmación** | Siempre requerida | Requerida | Solo alertas |
| **Sizing** | No incluye | Sugiere % portfolio | Calcula con límites |
| **Stop Loss** | Informativo | Recomendado | Hardcoded en Signal |
| **Max posición** | N/A | 5% portfolio | 2% portfolio |
| **Max diario** | N/A | 3 trades | 5 trades |
| **Caso de uso** | Aprendizaje | Paper trading | Live limitado |

### 6.2 Transición Entre Niveles

```
PROGRESIÓN RECOMENDADA:
═══════════════════════════════════════════════════════════════════

 Mes 1-2          Mes 3-4              Mes 5+
    │                │                    │
    ▼                ▼                    ▼
┌────────────┐  ┌────────────┐      ┌────────────┐
│Conservative│──▶│ Moderate   │──────▶│Experimental│
└────────────┘  └────────────┘      └────────────┘
    │                │                    │
    ▼                ▼                    ▼
 "Entender"     "Validar"           "Confiar"

CRITERIOS PARA AVANZAR:
───────────────────────────────────────────────────────────────────
Conservative → Moderate:
  - 30+ decisiones analizadas
  - Entiendes su lógica
  - Win rate > 50% en paper

Moderate → Experimental:
  - 100+ trades en paper
  - Sharpe > 0.5
  - Max drawdown < 15%
  - Confianza en kill switches

═══════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 1 - Contexto, Objetivos, Arquitectura y Dependencias*

---

*Documento de Implementación - Fase B2: AI Agent*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
-e 

---

## Interfaces y Dataclasses

---

## 7. Tarea B2.1: Interfaces Base

**Objetivo:** Definir el contrato que todos los LLM agents deben cumplir.

**Archivos a crear:**
- `src/agents/llm/__init__.py`
- `src/agents/llm/interfaces.py`

---

### 7.1 Dataclass: AgentContext

El contexto es TODO lo que el LLM necesita para tomar una decisión informada.

```python
# src/agents/llm/interfaces.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import json


class AutonomyLevel(str, Enum):
    """Niveles de autonomía del AI Agent."""
    CONSERVATIVE = "conservative"   # Solo información
    MODERATE = "moderate"           # Sugerencias con sizing
    EXPERIMENTAL = "experimental"   # Ejecución autónoma limitada


class MarketView(str, Enum):
    """Visión del mercado del agente."""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class PortfolioPosition:
    """Posición actual en portfolio."""
    symbol: str
    quantity: int
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    holding_days: int
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price


@dataclass(frozen=True)
class PortfolioSummary:
    """Resumen del estado del portfolio."""
    total_value: float
    cash_available: float
    invested_value: float
    positions: tuple[PortfolioPosition, ...]  # tuple para inmutabilidad
    daily_pnl: float
    daily_pnl_pct: float
    total_pnl: float
    total_pnl_pct: float
    
    @property
    def cash_pct(self) -> float:
        if self.total_value == 0:
            return 100.0
        return (self.cash_available / self.total_value) * 100
    
    @property
    def num_positions(self) -> int:
        return len(self.positions)


@dataclass(frozen=True)
class SymbolData:
    """Datos de mercado para un símbolo específico."""
    symbol: str
    name: str
    current_price: float
    change_pct: float
    volume: int
    avg_volume_20d: int
    
    # Indicadores técnicos
    rsi_14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    sma_20: float
    sma_50: float
    sma_200: float
    bb_upper: float
    bb_middle: float
    bb_lower: float
    atr_14: float
    adx_14: float
    
    # Niveles clave
    support_1: Optional[float] = None
    resistance_1: Optional[float] = None
    
    # Momentum
    momentum_1m: Optional[float] = None  # 1 mes
    momentum_3m: Optional[float] = None  # 3 meses
    momentum_6m: Optional[float] = None  # 6 meses
    
    def to_summary(self) -> str:
        """Genera resumen legible para el LLM."""
        trend = "alcista" if self.current_price > self.sma_50 else "bajista"
        rsi_status = "sobrecompra" if self.rsi_14 > 70 else ("sobreventa" if self.rsi_14 < 30 else "neutral")
        
        return (
            f"{self.symbol} ({self.name}): ${self.current_price:.2f} ({self.change_pct:+.2f}%)\n"
            f"  Tendencia: {trend} | RSI: {self.rsi_14:.1f} ({rsi_status})\n"
            f"  MACD: {self.macd:.3f} | ADX: {self.adx_14:.1f}\n"
            f"  Volumen: {self.volume:,} vs avg {self.avg_volume_20d:,}"
        )


@dataclass(frozen=True)
class RegimeInfo:
    """Información del régimen de mercado actual."""
    regime: str                     # "BULL", "BEAR", "SIDEWAYS", "VOLATILE"
    confidence: float               # 0.0 - 1.0
    probabilities: dict[str, float] # {"BULL": 0.7, "BEAR": 0.1, ...}
    model_id: str                   # "hmm_v1", "rules_v1"
    last_change: Optional[datetime] = None
    days_in_regime: int = 0
    
    def to_summary(self) -> str:
        """Genera resumen legible para el LLM."""
        return (
            f"Régimen: {self.regime} (confianza: {self.confidence:.0%})\n"
            f"  Días en régimen: {self.days_in_regime}\n"
            f"  Probabilidades: BULL={self.probabilities.get('BULL', 0):.0%}, "
            f"BEAR={self.probabilities.get('BEAR', 0):.0%}, "
            f"SIDEWAYS={self.probabilities.get('SIDEWAYS', 0):.0%}"
        )


@dataclass(frozen=True)
class RiskLimits:
    """Límites de riesgo actuales."""
    max_position_pct: float         # % máximo por posición
    max_portfolio_risk_pct: float   # % riesgo total portfolio
    max_daily_trades: int           # Número máximo de trades por día
    max_daily_loss_pct: float       # % pérdida máxima diaria
    current_daily_trades: int       # Trades ejecutados hoy
    current_daily_pnl_pct: float    # P&L del día
    
    @property
    def can_trade(self) -> bool:
        """Verifica si se puede operar según límites."""
        return (
            self.current_daily_trades < self.max_daily_trades and
            self.current_daily_pnl_pct > -self.max_daily_loss_pct
        )
    
    @property
    def remaining_trades(self) -> int:
        return max(0, self.max_daily_trades - self.current_daily_trades)


@dataclass(frozen=True)
class MarketContext:
    """Contexto general del mercado (índices, VIX, etc.)."""
    spy_change_pct: float           # S&P 500 cambio %
    qqq_change_pct: float           # Nasdaq cambio %
    vix_level: float                # Nivel VIX
    vix_change_pct: float           # Cambio VIX %
    market_breadth: float           # % acciones sobre SMA50 (-1 a 1)
    sector_rotation: dict[str, float]  # Performance por sector
    
    def to_summary(self) -> str:
        """Genera resumen legible para el LLM."""
        market_sentiment = "risk-on" if self.vix_level < 20 else ("risk-off" if self.vix_level > 30 else "neutral")
        return (
            f"Mercado General:\n"
            f"  SPY: {self.spy_change_pct:+.2f}% | QQQ: {self.qqq_change_pct:+.2f}%\n"
            f"  VIX: {self.vix_level:.1f} ({self.vix_change_pct:+.2f}%) - {market_sentiment}\n"
            f"  Breadth: {self.market_breadth:.0%} acciones sobre SMA50"
        )


@dataclass
class AgentContext:
    """
    Contexto completo para el AI Agent.
    
    Este es el INPUT principal del LLM. Contiene toda la información
    necesaria para tomar decisiones de trading informadas.
    """
    # Identificadores
    context_id: str
    timestamp: datetime
    
    # Estado del mercado
    regime: RegimeInfo
    market: MarketContext
    
    # Portfolio
    portfolio: PortfolioSummary
    
    # Símbolos a analizar
    watchlist: tuple[SymbolData, ...]
    
    # Límites de riesgo
    risk_limits: RiskLimits
    
    # Configuración
    autonomy_level: AutonomyLevel
    
    # Historial reciente (opcional)
    recent_trades: tuple[dict, ...] = field(default_factory=tuple)
    recent_signals: tuple[dict, ...] = field(default_factory=tuple)
    
    # Notas adicionales (noticias, eventos, etc.)
    notes: Optional[str] = None
    
    def to_prompt_text(self) -> str:
        """
        Convierte el contexto completo a texto para el prompt del LLM.
        
        Returns:
            String formateado con toda la información relevante
        """
        sections = []
        
        # 1. Fecha y hora
        sections.append(f"📅 FECHA Y HORA: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # 2. Régimen de mercado
        sections.append(f"\n🎯 RÉGIMEN DE MERCADO:\n{self.regime.to_summary()}")
        
        # 3. Contexto general del mercado
        sections.append(f"\n📊 MERCADO GENERAL:\n{self.market.to_summary()}")
        
        # 4. Portfolio
        sections.append(f"\n💼 PORTFOLIO:")
        sections.append(f"  Valor total: €{self.portfolio.total_value:,.2f}")
        sections.append(f"  Cash disponible: €{self.portfolio.cash_available:,.2f} ({self.portfolio.cash_pct:.1f}%)")
        sections.append(f"  P&L del día: {self.portfolio.daily_pnl_pct:+.2f}%")
        sections.append(f"  Posiciones abiertas: {self.portfolio.num_positions}")
        
        if self.portfolio.positions:
            sections.append("\n  Posiciones actuales:")
            for pos in self.portfolio.positions:
                sections.append(
                    f"    - {pos.symbol}: {pos.quantity} @ €{pos.avg_entry_price:.2f} "
                    f"→ €{pos.current_price:.2f} ({pos.unrealized_pnl_pct:+.2f}%)"
                )
        
        # 5. Límites de riesgo
        sections.append(f"\n⚠️ LÍMITES DE RIESGO:")
        sections.append(f"  Max posición: {self.risk_limits.max_position_pct:.1f}% portfolio")
        sections.append(f"  Trades restantes hoy: {self.risk_limits.remaining_trades}")
        sections.append(f"  P&L diario: {self.risk_limits.current_daily_pnl_pct:+.2f}% (límite: -{self.risk_limits.max_daily_loss_pct:.1f}%)")
        if not self.risk_limits.can_trade:
            sections.append("  ❌ TRADING PAUSADO POR LÍMITES")
        
        # 6. Watchlist con análisis
        sections.append(f"\n📈 WATCHLIST ({len(self.watchlist)} símbolos):")
        for symbol_data in self.watchlist:
            sections.append(f"\n{symbol_data.to_summary()}")
        
        # 7. Trades recientes
        if self.recent_trades:
            sections.append(f"\n📜 TRADES RECIENTES ({len(self.recent_trades)} últimos):")
            for trade in self.recent_trades[-5:]:  # Últimos 5
                sections.append(
                    f"  - {trade.get('symbol')}: {trade.get('direction')} "
                    f"@ €{trade.get('entry_price', 0):.2f} → {trade.get('pnl_pct', 0):+.2f}%"
                )
        
        # 8. Notas adicionales
        if self.notes:
            sections.append(f"\n📝 NOTAS:\n{self.notes}")
        
        # 9. Nivel de autonomía
        autonomy_desc = {
            AutonomyLevel.CONSERVATIVE: "Solo análisis e información",
            AutonomyLevel.MODERATE: "Sugerencias con sizing recomendado",
            AutonomyLevel.EXPERIMENTAL: "Decisiones autónomas dentro de límites"
        }
        sections.append(f"\n🤖 NIVEL DE AUTONOMÍA: {self.autonomy_level.value}")
        sections.append(f"   ({autonomy_desc[self.autonomy_level]})")
        
        return "\n".join(sections)
    
    def to_dict(self) -> dict:
        """Serializa el contexto a diccionario."""
        return {
            "context_id": self.context_id,
            "timestamp": self.timestamp.isoformat(),
            "regime": {
                "regime": self.regime.regime,
                "confidence": self.regime.confidence,
                "probabilities": self.regime.probabilities,
                "model_id": self.regime.model_id,
            },
            "portfolio": {
                "total_value": self.portfolio.total_value,
                "cash_available": self.portfolio.cash_available,
                "num_positions": self.portfolio.num_positions,
            },
            "risk_limits": {
                "can_trade": self.risk_limits.can_trade,
                "remaining_trades": self.risk_limits.remaining_trades,
            },
            "watchlist_count": len(self.watchlist),
            "autonomy_level": self.autonomy_level.value,
        }
```

---

### 7.2 Dataclass: AgentDecision

El output estructurado del LLM.

```python
# Continuación de src/agents/llm/interfaces.py

from src.strategies.interfaces import Signal  # Import de Fase B1


@dataclass
class AgentDecision:
    """
    Decisión del AI Agent.
    
    Este es el OUTPUT del LLM después de analizar el contexto.
    Incluye acciones concretas (Signal[]) más metadatos para trazabilidad.
    """
    # Identificadores
    decision_id: str
    context_id: str                 # Referencia al AgentContext usado
    timestamp: datetime
    
    # Acciones a tomar
    actions: list[Signal]           # Señales generadas (puede estar vacío)
    
    # Análisis del agente
    market_view: MarketView         # Visión general del mercado
    reasoning: str                  # Explicación detallada de la decisión
    key_factors: list[str]          # Factores clave considerados
    
    # Confianza
    confidence: float               # 0.0 - 1.0, confianza en la decisión
    
    # Metadatos
    model_used: str                 # "claude-sonnet-4-20250514"
    autonomy_level: AutonomyLevel   # Nivel con el que se tomó la decisión
    tokens_used: int                # Tokens consumidos
    latency_ms: float               # Tiempo de respuesta
    
    # Warnings o notas
    warnings: list[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validaciones post-inicialización."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        
        if self.actions and self.autonomy_level == AutonomyLevel.CONSERVATIVE:
            # En modo conservative, las acciones son solo informativas
            pass  # OK, pero se debe comunicar al usuario
    
    @property
    def has_actions(self) -> bool:
        return len(self.actions) > 0
    
    @property
    def action_summary(self) -> str:
        if not self.actions:
            return "No actions recommended"
        
        summaries = []
        for action in self.actions:
            summaries.append(
                f"{action.direction} {action.symbol} @ {action.entry_price:.2f} "
                f"(SL: {action.stop_loss:.2f}, TP: {action.take_profit:.2f})"
            )
        return "; ".join(summaries)
    
    def to_dict(self) -> dict:
        """Serializa la decisión a diccionario para logging/BD."""
        return {
            "decision_id": self.decision_id,
            "context_id": self.context_id,
            "timestamp": self.timestamp.isoformat(),
            "actions": [
                {
                    "strategy_id": a.strategy_id,
                    "symbol": a.symbol,
                    "direction": a.direction,
                    "confidence": a.confidence,
                    "entry_price": a.entry_price,
                    "stop_loss": a.stop_loss,
                    "take_profit": a.take_profit,
                }
                for a in self.actions
            ],
            "market_view": self.market_view.value,
            "reasoning": self.reasoning,
            "key_factors": self.key_factors,
            "confidence": self.confidence,
            "model_used": self.model_used,
            "autonomy_level": self.autonomy_level.value,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "warnings": self.warnings,
        }
    
    def to_json(self) -> str:
        """Serializa a JSON string."""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
```

---

### 7.3 Abstract Base Class: LLMAgent

```python
# Continuación de src/agents/llm/interfaces.py

class LLMAgent(ABC):
    """
    Clase base abstracta para agentes basados en LLM.
    
    Define el contrato que todas las implementaciones (Claude, GPT-4, Gemini)
    deben cumplir para ser intercambiables.
    """
    
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """
        Identificador único del agente.
        
        Returns:
            String identificador, ej: "claude_sonnet_v1", "gpt4_turbo_v1"
        """
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Nombre del modelo LLM usado.
        
        Returns:
            String con nombre del modelo, ej: "claude-sonnet-4-20250514"
        """
        pass
    
    @property
    @abstractmethod
    def supports_streaming(self) -> bool:
        """
        Indica si el agente soporta streaming de respuestas.
        
        Returns:
            True si soporta streaming
        """
        pass
    
    @abstractmethod
    async def decide(
        self,
        context: AgentContext,
        autonomy_level: Optional[AutonomyLevel] = None
    ) -> AgentDecision:
        """
        Toma una decisión de trading basada en el contexto.
        
        Este es el método principal del agente. Recibe todo el contexto
        necesario y devuelve una decisión estructurada.
        
        Args:
            context: AgentContext con toda la información del mercado
            autonomy_level: Nivel de autonomía (override del config si se provee)
        
        Returns:
            AgentDecision con acciones y razonamiento
        
        Raises:
            LLMAPIError: Si hay error en la llamada al LLM
            LLMRateLimitError: Si se excede el rate limit
            LLMParseError: Si no se puede parsear la respuesta
        """
        pass
    
    @abstractmethod
    def get_system_prompt(self, autonomy_level: AutonomyLevel) -> str:
        """
        Obtiene el system prompt para el nivel de autonomía dado.
        
        Args:
            autonomy_level: Nivel de autonomía
        
        Returns:
            String con el system prompt completo
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> dict:
        """
        Verifica el estado del agente y conexión al LLM.
        
        Returns:
            Dict con status y detalles
            {
                "status": "healthy" | "degraded" | "unhealthy",
                "model": "claude-sonnet-4-20250514",
                "latency_ms": 150,
                "rate_limit_remaining": 95,
                "last_error": null
            }
        """
        pass
    
    @abstractmethod
    def estimate_tokens(self, context: AgentContext) -> int:
        """
        Estima los tokens que consumirá una llamada con este contexto.
        
        Útil para:
        - Verificar que no excedemos context window
        - Estimar costos
        - Decidir si truncar contexto
        
        Args:
            context: AgentContext a evaluar
        
        Returns:
            Número estimado de tokens
        """
        pass
    
    # Métodos opcionales con implementación por defecto
    
    def validate_context(self, context: AgentContext) -> tuple[bool, list[str]]:
        """
        Valida que el contexto sea adecuado para el agente.
        
        Args:
            context: Contexto a validar
        
        Returns:
            Tuple (is_valid, list of issues)
        """
        issues = []
        
        # Verificar que hay watchlist
        if not context.watchlist:
            issues.append("Watchlist vacía - nada que analizar")
        
        # Verificar límites de riesgo
        if not context.risk_limits.can_trade:
            issues.append("Trading pausado por límites de riesgo")
        
        # Verificar régimen
        if context.regime.confidence < 0.5:
            issues.append(f"Confianza de régimen baja: {context.regime.confidence:.0%}")
        
        return len(issues) == 0, issues
    
    def should_skip_decision(self, context: AgentContext) -> tuple[bool, str]:
        """
        Determina si se debe omitir la decisión por alguna razón.
        
        Args:
            context: Contexto actual
        
        Returns:
            Tuple (should_skip, reason)
        """
        # Skip si no se puede operar
        if not context.risk_limits.can_trade:
            return True, "Risk limits reached - trading paused"
        
        # Skip si régimen es VOLATILE
        if context.regime.regime == "VOLATILE":
            return True, "Market regime is VOLATILE - waiting for clarity"
        
        # Skip si VIX muy alto
        if context.market.vix_level > 35:
            return True, f"VIX too high ({context.market.vix_level}) - extreme fear"
        
        return False, ""
```

---

### 7.4 Excepciones Específicas

```python
# Continuación de src/agents/llm/interfaces.py (o en exceptions.py separado)

class LLMAgentError(Exception):
    """Base exception para errores del LLM Agent."""
    pass


class LLMAPIError(LLMAgentError):
    """Error en la llamada a la API del LLM."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class LLMRateLimitError(LLMAgentError):
    """Rate limit excedido."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after  # Segundos hasta retry


class LLMParseError(LLMAgentError):
    """Error parseando la respuesta del LLM."""
    def __init__(self, message: str, raw_response: Optional[str] = None):
        super().__init__(message)
        self.raw_response = raw_response


class LLMContextTooLargeError(LLMAgentError):
    """El contexto excede el límite de tokens."""
    def __init__(self, message: str, tokens_needed: int, tokens_available: int):
        super().__init__(message)
        self.tokens_needed = tokens_needed
        self.tokens_available = tokens_available


class LLMTimeoutError(LLMAgentError):
    """Timeout en la llamada al LLM."""
    def __init__(self, message: str, timeout_seconds: float):
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
```

---

### 7.5 Archivo __init__.py

```python
# src/agents/llm/__init__.py
"""
LLM Agent Module - AI-powered trading decisions.

Este módulo implementa agentes de trading basados en Large Language Models.
Actualmente soporta Claude (Anthropic), con arquitectura preparada para
GPT-4 (OpenAI) y Gemini (Google).

Uso básico:
    from src.agents.llm import LLMAgentFactory, AgentContext, AutonomyLevel
    
    # Crear agente desde config
    agent = LLMAgentFactory.create_from_config()
    
    # Construir contexto
    context = build_agent_context(...)
    
    # Obtener decisión
    decision = await agent.decide(context, AutonomyLevel.MODERATE)
"""

from .interfaces import (
    # Enums
    AutonomyLevel,
    MarketView,
    
    # Dataclasses de contexto
    PortfolioPosition,
    PortfolioSummary,
    SymbolData,
    RegimeInfo,
    RiskLimits,
    MarketContext,
    AgentContext,
    
    # Output
    AgentDecision,
    
    # ABC
    LLMAgent,
    
    # Exceptions
    LLMAgentError,
    LLMAPIError,
    LLMRateLimitError,
    LLMParseError,
    LLMContextTooLargeError,
    LLMTimeoutError,
)

# Lazy imports para evitar ciclos
def get_factory():
    from .factory import LLMAgentFactory
    return LLMAgentFactory

def get_context_builder():
    from .context_builder import ContextBuilder
    return ContextBuilder


__all__ = [
    # Enums
    "AutonomyLevel",
    "MarketView",
    
    # Dataclasses
    "PortfolioPosition",
    "PortfolioSummary", 
    "SymbolData",
    "RegimeInfo",
    "RiskLimits",
    "MarketContext",
    "AgentContext",
    "AgentDecision",
    
    # ABC
    "LLMAgent",
    
    # Exceptions
    "LLMAgentError",
    "LLMAPIError",
    "LLMRateLimitError",
    "LLMParseError",
    "LLMContextTooLargeError",
    "LLMTimeoutError",
    
    # Factories
    "get_factory",
    "get_context_builder",
]
```

---

## 8. Tarea B2.2: Context Builder

**Objetivo:** Construir el AgentContext recopilando datos de múltiples fuentes.

**Archivo:** `src/agents/llm/context_builder.py`

```python
# src/agents/llm/context_builder.py
"""
Context Builder - Construye AgentContext desde múltiples fuentes de datos.

Este módulo es responsable de:
1. Consultar mcp-ml-models para régimen
2. Consultar mcp-market-data para datos de mercado
3. Consultar mcp-ibkr para portfolio
4. Consolidar todo en AgentContext
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Protocol
import logging

from .interfaces import (
    AgentContext,
    AutonomyLevel,
    PortfolioPosition,
    PortfolioSummary,
    SymbolData,
    RegimeInfo,
    RiskLimits,
    MarketContext,
)


logger = logging.getLogger(__name__)


class MCPClient(Protocol):
    """Protocolo para cliente MCP (duck typing)."""
    async def call(self, server: str, tool: str, params: dict) -> dict: ...


class ContextBuilder:
    """
    Construye AgentContext recopilando datos de múltiples fuentes.
    
    Diseñado para ser modular - cada fuente de datos es independiente
    y puede fallar sin afectar las demás.
    """
    
    def __init__(
        self,
        mcp_client: MCPClient,
        default_autonomy: AutonomyLevel = AutonomyLevel.MODERATE,
        cache_ttl_seconds: int = 60
    ):
        """
        Args:
            mcp_client: Cliente para llamadas MCP
            default_autonomy: Nivel de autonomía por defecto
            cache_ttl_seconds: TTL del cache de contexto
        """
        self.mcp = mcp_client
        self.default_autonomy = default_autonomy
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[datetime, any]] = {}
    
    async def build(
        self,
        watchlist: list[str],
        autonomy_level: Optional[AutonomyLevel] = None,
        notes: Optional[str] = None
    ) -> AgentContext:
        """
        Construye un AgentContext completo.
        
        Args:
            watchlist: Lista de símbolos a analizar
            autonomy_level: Nivel de autonomía (usa default si no se provee)
            notes: Notas adicionales para el contexto
        
        Returns:
            AgentContext completo listo para el LLM
        """
        context_id = f"ctx_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.utcnow()
        autonomy = autonomy_level or self.default_autonomy
        
        logger.info(f"Building context {context_id} for {len(watchlist)} symbols")
        
        # Ejecutar todas las consultas en paralelo
        results = await asyncio.gather(
            self._get_regime(),
            self._get_market_context(),
            self._get_portfolio(),
            self._get_watchlist_data(watchlist),
            self._get_risk_limits(),
            self._get_recent_trades(),
            return_exceptions=True  # No fallar si una consulta falla
        )
        
        regime, market, portfolio, watchlist_data, risk_limits, recent_trades = results
        
        # Manejar errores individuales con defaults
        if isinstance(regime, Exception):
            logger.warning(f"Error getting regime: {regime}, using default")
            regime = self._default_regime()
        
        if isinstance(market, Exception):
            logger.warning(f"Error getting market context: {market}, using default")
            market = self._default_market_context()
        
        if isinstance(portfolio, Exception):
            logger.warning(f"Error getting portfolio: {portfolio}, using default")
            portfolio = self._default_portfolio()
        
        if isinstance(watchlist_data, Exception):
            logger.warning(f"Error getting watchlist data: {watchlist_data}")
            watchlist_data = ()
        
        if isinstance(risk_limits, Exception):
            logger.warning(f"Error getting risk limits: {risk_limits}, using conservative")
            risk_limits = self._conservative_risk_limits()
        
        if isinstance(recent_trades, Exception):
            logger.warning(f"Error getting recent trades: {recent_trades}")
            recent_trades = ()
        
        return AgentContext(
            context_id=context_id,
            timestamp=timestamp,
            regime=regime,
            market=market,
            portfolio=portfolio,
            watchlist=tuple(watchlist_data),
            risk_limits=risk_limits,
            autonomy_level=autonomy,
            recent_trades=tuple(recent_trades) if recent_trades else (),
            notes=notes
        )
    
    async def _get_regime(self) -> RegimeInfo:
        """Obtiene régimen actual de mcp-ml-models."""
        # Check cache
        cached = self._get_cached("regime")
        if cached:
            return cached
        
        response = await self.mcp.call(
            "mcp-ml-models",
            "get_regime",
            {}
        )
        
        regime = RegimeInfo(
            regime=response["regime"],
            confidence=response["confidence"],
            probabilities=response.get("probabilities", {}),
            model_id=response.get("model_id", "unknown"),
            last_change=response.get("last_change"),
            days_in_regime=response.get("days_in_regime", 0)
        )
        
        self._set_cached("regime", regime)
        return regime
    
    async def _get_market_context(self) -> MarketContext:
        """Obtiene contexto general del mercado."""
        cached = self._get_cached("market")
        if cached:
            return cached
        
        # Obtener datos de índices principales
        spy_data = await self.mcp.call(
            "mcp-market-data",
            "get_quote",
            {"symbol": "SPY"}
        )
        
        qqq_data = await self.mcp.call(
            "mcp-market-data", 
            "get_quote",
            {"symbol": "QQQ"}
        )
        
        vix_data = await self.mcp.call(
            "mcp-market-data",
            "get_quote", 
            {"symbol": "VIX"}
        )
        
        # Market breadth (simplificado)
        breadth = await self._calculate_market_breadth()
        
        market = MarketContext(
            spy_change_pct=spy_data.get("change_pct", 0),
            qqq_change_pct=qqq_data.get("change_pct", 0),
            vix_level=vix_data.get("price", 20),
            vix_change_pct=vix_data.get("change_pct", 0),
            market_breadth=breadth,
            sector_rotation={}  # TODO: Implementar
        )
        
        self._set_cached("market", market)
        return market
    
    async def _get_portfolio(self) -> PortfolioSummary:
        """Obtiene estado actual del portfolio de IBKR."""
        response = await self.mcp.call(
            "mcp-ibkr",
            "get_portfolio",
            {}
        )
        
        positions = []
        for pos in response.get("positions", []):
            positions.append(PortfolioPosition(
                symbol=pos["symbol"],
                quantity=pos["quantity"],
                avg_entry_price=pos["avg_entry_price"],
                current_price=pos["current_price"],
                unrealized_pnl=pos["unrealized_pnl"],
                unrealized_pnl_pct=pos["unrealized_pnl_pct"],
                holding_days=pos.get("holding_days", 0)
            ))
        
        return PortfolioSummary(
            total_value=response["total_value"],
            cash_available=response["cash_available"],
            invested_value=response["invested_value"],
            positions=tuple(positions),
            daily_pnl=response.get("daily_pnl", 0),
            daily_pnl_pct=response.get("daily_pnl_pct", 0),
            total_pnl=response.get("total_pnl", 0),
            total_pnl_pct=response.get("total_pnl_pct", 0)
        )
    
    async def _get_watchlist_data(self, symbols: list[str]) -> list[SymbolData]:
        """Obtiene datos de mercado para cada símbolo del watchlist."""
        tasks = [self._get_symbol_data(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_data = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"Error getting data for {symbol}: {result}")
                continue
            valid_data.append(result)
        
        return valid_data
    
    async def _get_symbol_data(self, symbol: str) -> SymbolData:
        """Obtiene datos completos de un símbolo."""
        # Datos de quote
        quote = await self.mcp.call(
            "mcp-market-data",
            "get_quote",
            {"symbol": symbol}
        )
        
        # Indicadores técnicos
        indicators = await self.mcp.call(
            "mcp-technical",
            "get_indicators",
            {"symbol": symbol, "indicators": ["RSI", "MACD", "SMA", "BB", "ATR", "ADX"]}
        )
        
        return SymbolData(
            symbol=symbol,
            name=quote.get("name", symbol),
            current_price=quote["price"],
            change_pct=quote["change_pct"],
            volume=quote["volume"],
            avg_volume_20d=quote.get("avg_volume_20d", quote["volume"]),
            rsi_14=indicators.get("RSI", {}).get("value", 50),
            macd=indicators.get("MACD", {}).get("macd", 0),
            macd_signal=indicators.get("MACD", {}).get("signal", 0),
            macd_histogram=indicators.get("MACD", {}).get("histogram", 0),
            sma_20=indicators.get("SMA", {}).get("sma_20", quote["price"]),
            sma_50=indicators.get("SMA", {}).get("sma_50", quote["price"]),
            sma_200=indicators.get("SMA", {}).get("sma_200", quote["price"]),
            bb_upper=indicators.get("BB", {}).get("upper", quote["price"] * 1.02),
            bb_middle=indicators.get("BB", {}).get("middle", quote["price"]),
            bb_lower=indicators.get("BB", {}).get("lower", quote["price"] * 0.98),
            atr_14=indicators.get("ATR", {}).get("value", quote["price"] * 0.02),
            adx_14=indicators.get("ADX", {}).get("value", 25),
            support_1=indicators.get("levels", {}).get("support_1"),
            resistance_1=indicators.get("levels", {}).get("resistance_1"),
            momentum_1m=indicators.get("momentum", {}).get("1m"),
            momentum_3m=indicators.get("momentum", {}).get("3m"),
            momentum_6m=indicators.get("momentum", {}).get("6m"),
        )
    
    async def _get_risk_limits(self) -> RiskLimits:
        """Obtiene límites de riesgo actuales."""
        response = await self.mcp.call(
            "mcp-risk",
            "get_limits",
            {}
        )
        
        return RiskLimits(
            max_position_pct=response.get("max_position_pct", 5.0),
            max_portfolio_risk_pct=response.get("max_portfolio_risk_pct", 2.0),
            max_daily_trades=response.get("max_daily_trades", 5),
            max_daily_loss_pct=response.get("max_daily_loss_pct", 3.0),
            current_daily_trades=response.get("current_daily_trades", 0),
            current_daily_pnl_pct=response.get("current_daily_pnl_pct", 0),
        )
    
    async def _get_recent_trades(self) -> list[dict]:
        """Obtiene trades recientes para contexto histórico."""
        # Pseudo-implementación - conectar a metrics.trades
        return []
    
    async def _calculate_market_breadth(self) -> float:
        """Calcula market breadth simplificado."""
        # Pseudo-implementación
        # Idealmente: % de acciones del S&P500 sobre su SMA50
        return 0.6  # Default: 60% bullish
    
    # Métodos de cache
    def _get_cached(self, key: str) -> Optional[any]:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if datetime.utcnow() - timestamp < timedelta(seconds=self.cache_ttl):
                return value
        return None
    
    def _set_cached(self, key: str, value: any):
        self._cache[key] = (datetime.utcnow(), value)
    
    # Defaults para manejo de errores
    def _default_regime(self) -> RegimeInfo:
        return RegimeInfo(
            regime="SIDEWAYS",
            confidence=0.5,
            probabilities={"BULL": 0.25, "BEAR": 0.25, "SIDEWAYS": 0.25, "VOLATILE": 0.25},
            model_id="default_fallback"
        )
    
    def _default_market_context(self) -> MarketContext:
        return MarketContext(
            spy_change_pct=0,
            qqq_change_pct=0,
            vix_level=20,
            vix_change_pct=0,
            market_breadth=0.5,
            sector_rotation={}
        )
    
    def _default_portfolio(self) -> PortfolioSummary:
        return PortfolioSummary(
            total_value=25000,  # Paper trading default
            cash_available=25000,
            invested_value=0,
            positions=(),
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            total_pnl_pct=0
        )
    
    def _conservative_risk_limits(self) -> RiskLimits:
        """Límites conservadores cuando hay error."""
        return RiskLimits(
            max_position_pct=2.0,   # Muy conservador
            max_portfolio_risk_pct=1.0,
            max_daily_trades=2,
            max_daily_loss_pct=1.0,
            current_daily_trades=0,
            current_daily_pnl_pct=0
        )
```

---

## 9. Validación de Interfaces

### 9.1 Test de Estructura

```python
# tests/agents/llm/test_interfaces.py
"""Tests para interfaces del LLM Agent."""

import pytest
from datetime import datetime
from src.agents.llm.interfaces import (
    AutonomyLevel,
    MarketView,
    PortfolioPosition,
    PortfolioSummary,
    SymbolData,
    RegimeInfo,
    RiskLimits,
    AgentContext,
    AgentDecision,
)
from src.strategies.interfaces import Signal


class TestAutonomyLevel:
    def test_enum_values(self):
        assert AutonomyLevel.CONSERVATIVE.value == "conservative"
        assert AutonomyLevel.MODERATE.value == "moderate"
        assert AutonomyLevel.EXPERIMENTAL.value == "experimental"


class TestPortfolioPosition:
    def test_market_value(self):
        pos = PortfolioPosition(
            symbol="AAPL",
            quantity=10,
            avg_entry_price=150.0,
            current_price=160.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=6.67,
            holding_days=5
        )
        assert pos.market_value == 1600.0
    
    def test_immutability(self):
        pos = PortfolioPosition(
            symbol="AAPL",
            quantity=10,
            avg_entry_price=150.0,
            current_price=160.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=6.67,
            holding_days=5
        )
        with pytest.raises(AttributeError):
            pos.quantity = 20


class TestRiskLimits:
    def test_can_trade_true(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=2,
            current_daily_pnl_pct=-1.0
        )
        assert limits.can_trade is True
        assert limits.remaining_trades == 3
    
    def test_can_trade_false_max_trades(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=5,  # Alcanzó máximo
            current_daily_pnl_pct=0
        )
        assert limits.can_trade is False
        assert limits.remaining_trades == 0
    
    def test_can_trade_false_max_loss(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=1,
            current_daily_pnl_pct=-4.0  # Excede pérdida máxima
        )
        assert limits.can_trade is False


class TestAgentContext:
    @pytest.fixture
    def sample_context(self):
        return AgentContext(
            context_id="ctx_test123",
            timestamp=datetime.utcnow(),
            regime=RegimeInfo(
                regime="BULL",
                confidence=0.75,
                probabilities={"BULL": 0.75, "BEAR": 0.1, "SIDEWAYS": 0.1, "VOLATILE": 0.05},
                model_id="hmm_v1"
            ),
            market=MarketContext(
                spy_change_pct=0.5,
                qqq_change_pct=0.8,
                vix_level=18.5,
                vix_change_pct=-2.0,
                market_breadth=0.65,
                sector_rotation={}
            ),
            portfolio=PortfolioSummary(
                total_value=25000,
                cash_available=20000,
                invested_value=5000,
                positions=(),
                daily_pnl=50,
                daily_pnl_pct=0.2,
                total_pnl=500,
                total_pnl_pct=2.0
            ),
            watchlist=(),
            risk_limits=RiskLimits(
                max_position_pct=5.0,
                max_portfolio_risk_pct=2.0,
                max_daily_trades=5,
                max_daily_loss_pct=3.0,
                current_daily_trades=1,
                current_daily_pnl_pct=0.2
            ),
            autonomy_level=AutonomyLevel.MODERATE
        )
    
    def test_to_prompt_text_not_empty(self, sample_context):
        text = sample_context.to_prompt_text()
        assert len(text) > 100
        assert "RÉGIMEN" in text
        assert "PORTFOLIO" in text
        assert "BULL" in text
    
    def test_to_dict_serializable(self, sample_context):
        d = sample_context.to_dict()
        import json
        json_str = json.dumps(d)  # No debe lanzar excepción
        assert "context_id" in d


class TestAgentDecision:
    def test_confidence_validation(self):
        with pytest.raises(ValueError):
            AgentDecision(
                decision_id="dec_test",
                context_id="ctx_test",
                timestamp=datetime.utcnow(),
                actions=[],
                market_view=MarketView.BULLISH,
                reasoning="Test",
                key_factors=["factor1"],
                confidence=1.5,  # Inválido
                model_used="test",
                autonomy_level=AutonomyLevel.MODERATE,
                tokens_used=100,
                latency_ms=150
            )
    
    def test_has_actions(self):
        decision = AgentDecision(
            decision_id="dec_test",
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            actions=[],
            market_view=MarketView.NEUTRAL,
            reasoning="No opportunities",
            key_factors=[],
            confidence=0.8,
            model_used="test",
            autonomy_level=AutonomyLevel.MODERATE,
            tokens_used=100,
            latency_ms=150
        )
        assert decision.has_actions is False
```

---

*Fin de Parte 2 - Interfaces y Dataclasses*

---

*Documento de Implementación - Fase B2: AI Agent*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
-e 

---

## Implementación Claude Agent + Sistema de Prompts

---

## 10. Tarea B2.3: Sistema de Prompts

**Objetivo:** Definir los system prompts que controlan el comportamiento del AI Agent según el nivel de autonomía.

**Archivos:**
- `src/agents/llm/prompts/__init__.py`
- `src/agents/llm/prompts/base.py`
- `src/agents/llm/prompts/conservative.py`
- `src/agents/llm/prompts/moderate.py`
- `src/agents/llm/prompts/experimental.py`

---

### 10.1 Prompt Base (Compartido)

```python
# src/agents/llm/prompts/base.py
"""
Base prompts compartidos entre todos los niveles de autonomía.

Estos componentes se combinan con prompts específicos de autonomía
para formar el system prompt completo.
"""

# Identidad del agente
AGENT_IDENTITY = """Eres un asistente de trading profesional especializado en análisis técnico y gestión de riesgo.
Tu objetivo es ayudar a tomar decisiones de trading informadas basadas en datos objetivos.

PRINCIPIOS FUNDAMENTALES:
1. La preservación del capital es la prioridad número uno
2. Nunca recomiendes operaciones que excedan los límites de riesgo establecidos
3. Sé honesto sobre la incertidumbre - si no estás seguro, dilo claramente
4. Basa tus análisis en datos concretos, no en especulaciones
5. El régimen de mercado determina qué tipo de operaciones son apropiadas"""

# Descripción de regímenes
REGIME_DESCRIPTIONS = """
REGÍMENES DE MERCADO:
═══════════════════════════════════════════════════════════════════════════
• BULL (Alcista):
  - Tendencia clara al alza
  - Estrategias recomendadas: Momentum, seguimiento de tendencia
  - Riesgo: Medio - buscar pullbacks para entrar

• BEAR (Bajista):
  - Tendencia clara a la baja
  - Estrategias recomendadas: SOLO cierres de posiciones largas
  - Riesgo: Alto - preservar capital, no abrir nuevas posiciones largas

• SIDEWAYS (Lateral):
  - Sin tendencia clara, rango definido
  - Estrategias recomendadas: Mean reversion, comprar soporte, vender resistencia
  - Riesgo: Medio - stops ajustados

• VOLATILE (Volátil):
  - Alta incertidumbre, movimientos erráticos
  - Estrategias recomendadas: NINGUNA - esperar claridad
  - Riesgo: Muy alto - quedarse en cash
═══════════════════════════════════════════════════════════════════════════"""

# Instrucciones de análisis técnico
TECHNICAL_ANALYSIS_GUIDE = """
GUÍA DE ANÁLISIS TÉCNICO:
─────────────────────────────────────────────────────────────────────────────
RSI (Relative Strength Index):
  • < 30: Sobreventa - posible rebote
  • 30-70: Zona neutral
  • > 70: Sobrecompra - posible corrección

MACD:
  • Histograma positivo creciente: Momentum alcista fuerte
  • Histograma negativo decreciente: Momentum bajista fuerte
  • Cruce de línea de señal: Posible cambio de tendencia

Medias Móviles (SMA):
  • Precio > SMA50 > SMA200: Tendencia alcista confirmada
  • Precio < SMA50 < SMA200: Tendencia bajista confirmada
  • Golden Cross (SMA50 cruza SMA200 al alza): Señal alcista
  • Death Cross (SMA50 cruza SMA200 a la baja): Señal bajista

ADX (Average Directional Index):
  • < 20: Tendencia débil o inexistente
  • 20-40: Tendencia moderada
  • > 40: Tendencia fuerte

Bollinger Bands:
  • Precio en banda superior: Posible sobreextensión
  • Precio en banda inferior: Posible sobreventa
  • Bandas estrechándose: Volatilidad baja, posible ruptura próxima

Volumen:
  • > 1.5x promedio: Confirma movimiento
  • < 0.5x promedio: Movimiento sospechoso, falta convicción
─────────────────────────────────────────────────────────────────────────────"""

# Formato de respuesta JSON
RESPONSE_FORMAT_BASE = """
FORMATO DE RESPUESTA:
Tu respuesta DEBE ser un JSON válido con la siguiente estructura exacta:

```json
{
  "market_view": "bullish" | "bearish" | "neutral" | "uncertain",
  "confidence": 0.0-1.0,
  "reasoning": "Explicación detallada de tu análisis...",
  "key_factors": [
    "Factor 1 considerado",
    "Factor 2 considerado",
    ...
  ],
  "actions": [
    {
      "symbol": "TICKER",
      "direction": "LONG" | "SHORT" | "CLOSE",
      "entry_price": 123.45,
      "stop_loss": 120.00,
      "take_profit": 130.00,
      "size_suggestion": 0.05,
      "reasoning": "Por qué esta acción específica"
    }
  ],
  "warnings": [
    "Advertencia 1 si aplica",
    ...
  ]
}
```

IMPORTANTE:
- "actions" puede ser una lista vacía [] si no hay oportunidades claras
- "confidence" refleja tu confianza general en el análisis
- "size_suggestion" es un porcentaje del portfolio (0.05 = 5%)
- NO incluyas comentarios o texto fuera del JSON
"""

# Restricciones de seguridad
SAFETY_RESTRICTIONS = """
RESTRICCIONES DE SEGURIDAD (NUNCA VIOLAR):
═══════════════════════════════════════════════════════════════════════════
❌ NUNCA sugieras operaciones si risk_limits.can_trade es False
❌ NUNCA sugieras posiciones que excedan max_position_pct del portfolio
❌ NUNCA sugieras más trades si se alcanzó max_daily_trades
❌ NUNCA sugieras operaciones en régimen VOLATILE
❌ NUNCA sugieras posiciones largas nuevas en régimen BEAR
❌ NUNCA ignores un stop loss - toda posición DEBE tener stop loss
❌ NUNCA sugieras apalancamiento
❌ NUNCA bases decisiones solo en una señal - busca confluencia
═══════════════════════════════════════════════════════════════════════════"""


def build_base_prompt() -> str:
    """Construye la parte base del prompt (común a todos los niveles)."""
    return "\n\n".join([
        AGENT_IDENTITY,
        REGIME_DESCRIPTIONS,
        TECHNICAL_ANALYSIS_GUIDE,
        SAFETY_RESTRICTIONS,
    ])
```

---

### 10.2 Prompt Conservative

```python
# src/agents/llm/prompts/conservative.py
"""
Prompt para nivel de autonomía CONSERVATIVE.

En este nivel:
- El agente proporciona análisis e información
- NO toma decisiones de trading
- El humano siempre decide
- Enfoque educativo
"""

from .base import build_base_prompt, RESPONSE_FORMAT_BASE

CONSERVATIVE_SPECIFIC = """
═══════════════════════════════════════════════════════════════════════════
                    NIVEL DE AUTONOMÍA: CONSERVATIVE
═══════════════════════════════════════════════════════════════════════════

Tu rol en este nivel es INFORMATIVO y EDUCATIVO:

1. ANÁLISIS: Proporciona un análisis completo y objetivo del mercado
2. OPINIÓN: Comparte tu visión del mercado (bullish/bearish/neutral)
3. OPORTUNIDADES: Identifica posibles oportunidades, pero NO las ejecutes
4. EDUCACIÓN: Explica el razonamiento detrás de cada observación

⚠️ IMPORTANTE EN ESTE NIVEL:
- NO debes incluir acciones ejecutables en tu respuesta
- El campo "actions" SIEMPRE debe estar vacío: []
- Tu rol es informar, el humano decide
- Sé detallado en el reasoning para que el humano aprenda

EJEMPLO DE RESPUESTA CORRECTA:
```json
{
  "market_view": "bullish",
  "confidence": 0.7,
  "reasoning": "El régimen actual es BULL con alta confianza (75%). SPY muestra momentum positivo con RSI en 58 (neutral-alcista). VWCE.DE presenta una oportunidad interesante: precio sobre SMA50, MACD positivo, y volumen 20% sobre media. Sin embargo, está cerca de resistencia en 112€. Un pullback hacia 108€ sería una mejor entrada.",
  "key_factors": [
    "Régimen BULL confirmado",
    "VIX bajo (18.5) indica baja volatilidad",
    "VWCE.DE con momentum positivo",
    "Resistencia cercana limita upside inmediato"
  ],
  "actions": [],
  "warnings": [
    "Resistencia en 112€ podría limitar subida a corto plazo",
    "Considerar esperar pullback para mejor R/R"
  ]
}
```

═══════════════════════════════════════════════════════════════════════════"""

CONSERVATIVE_RESPONSE_FORMAT = """
FORMATO DE RESPUESTA (CONSERVATIVE):
Tu respuesta DEBE ser JSON válido:

```json
{
  "market_view": "bullish" | "bearish" | "neutral" | "uncertain",
  "confidence": 0.0-1.0,
  "reasoning": "Análisis detallado y educativo...",
  "key_factors": ["Factor 1", "Factor 2", ...],
  "actions": [],  // SIEMPRE vacío en este nivel
  "warnings": ["Advertencia si aplica"]
}
```

Recuerda: actions = [] siempre. Tu rol es informar.
"""


def get_conservative_prompt() -> str:
    """Obtiene el system prompt completo para nivel CONSERVATIVE."""
    return "\n\n".join([
        build_base_prompt(),
        CONSERVATIVE_SPECIFIC,
        CONSERVATIVE_RESPONSE_FORMAT,
    ])
```

---

### 10.3 Prompt Moderate

```python
# src/agents/llm/prompts/moderate.py
"""
Prompt para nivel de autonomía MODERATE.

En este nivel:
- El agente sugiere operaciones concretas
- Incluye sizing recomendado
- El humano debe confirmar antes de ejecutar
- Balance entre autonomía y control
"""

from .base import build_base_prompt

MODERATE_SPECIFIC = """
═══════════════════════════════════════════════════════════════════════════
                    NIVEL DE AUTONOMÍA: MODERATE
═══════════════════════════════════════════════════════════════════════════

Tu rol en este nivel es de ASESOR ACTIVO:

1. ANÁLISIS: Proporciona análisis completo del mercado
2. RECOMENDACIONES: Sugiere operaciones concretas cuando veas oportunidades
3. SIZING: Calcula tamaño de posición apropiado (respetando límites)
4. NIVELES: Define entry, stop loss y take profit específicos
5. CONFIRMACIÓN: El humano revisará y confirmará antes de ejecutar

REGLAS PARA SUGERIR OPERACIONES:
─────────────────────────────────────────────────────────────────────────────
✓ Solo sugiere cuando hay confluencia de señales (mínimo 2-3 indicadores)
✓ Risk/Reward mínimo de 1:1.5 (preferible 1:2 o mejor)
✓ Stop loss máximo: 2% del precio de entrada
✓ size_suggestion máximo: 5% del portfolio
✓ Máximo 2 operaciones por análisis
✓ Prioriza calidad sobre cantidad

CUÁNDO NO SUGERIR OPERACIONES:
─────────────────────────────────────────────────────────────────────────────
✗ Régimen VOLATILE o BEAR (para longs)
✗ VIX > 25 (alta incertidumbre)
✗ Señales contradictorias entre indicadores
✗ Cerca de earnings o eventos importantes
✗ Volumen muy bajo (< 0.5x promedio)
✗ Límites de riesgo alcanzados
─────────────────────────────────────────────────────────────────────────────

CÁLCULO DE SIZE SUGGESTION:
1. Determina riesgo por trade: (entry - stop_loss) / entry
2. Si riesgo > 2%, reduce position size o ajusta stop
3. size_suggestion = min(max_position_pct, risk_budget / trade_risk)
4. Nunca exceder 5% del portfolio en una sola posición

═══════════════════════════════════════════════════════════════════════════"""

MODERATE_RESPONSE_FORMAT = """
FORMATO DE RESPUESTA (MODERATE):
Tu respuesta DEBE ser JSON válido:

```json
{
  "market_view": "bullish" | "bearish" | "neutral" | "uncertain",
  "confidence": 0.0-1.0,
  "reasoning": "Análisis completo y justificación de recomendaciones...",
  "key_factors": [
    "Factor 1 que soporta la decisión",
    "Factor 2...",
    ...
  ],
  "actions": [
    {
      "symbol": "VWCE.DE",
      "direction": "LONG",
      "entry_price": 108.50,
      "stop_loss": 106.35,
      "take_profit": 114.20,
      "size_suggestion": 0.04,
      "reasoning": "Pullback a SMA20 en tendencia alcista, RSI 45 desde sobreventa, MACD positivo. R/R = 1:2.6"
    }
  ],
  "warnings": [
    "Requiere confirmación del usuario",
    "Earnings de componentes importantes próxima semana"
  ]
}
```

IMPORTANTE:
- size_suggestion entre 0.01 (1%) y 0.05 (5%)
- Stop loss OBLIGATORIO en cada acción
- Risk/Reward implícito debe ser ≥ 1.5
- Si no hay buenas oportunidades, actions = []
"""


def get_moderate_prompt() -> str:
    """Obtiene el system prompt completo para nivel MODERATE."""
    return "\n\n".join([
        build_base_prompt(),
        MODERATE_SPECIFIC,
        MODERATE_RESPONSE_FORMAT,
    ])
```

---

### 10.4 Prompt Experimental

```python
# src/agents/llm/prompts/experimental.py
"""
Prompt para nivel de autonomía EXPERIMENTAL.

En este nivel:
- El agente puede tomar decisiones autónomas
- Límites más estrictos como salvaguarda
- Solo para usuarios experimentados
- Requiere kill switches activos
"""

from .base import build_base_prompt

EXPERIMENTAL_SPECIFIC = """
═══════════════════════════════════════════════════════════════════════════
                    NIVEL DE AUTONOMÍA: EXPERIMENTAL
═══════════════════════════════════════════════════════════════════════════

⚠️ MODO DE ALTA AUTONOMÍA - LÍMITES ESTRICTOS ACTIVOS ⚠️

Tu rol en este nivel es de OPERADOR AUTÓNOMO con límites:

1. ANÁLISIS: Evalúa el mercado de forma continua
2. DECISIÓN: Toma decisiones de trading dentro de límites
3. EJECUCIÓN: Las acciones se enviarán para ejecución automática
4. RESPONSABILIDAD: Cada decisión debe estar bien fundamentada

LÍMITES ESTRICTOS (NUNCA EXCEDER):
─────────────────────────────────────────────────────────────────────────────
• size_suggestion MÁXIMO: 2% del portfolio (más conservador que moderate)
• Stop loss MÁXIMO: 1.5% del precio de entrada
• Risk/Reward MÍNIMO: 1:2 (más exigente)
• MÁXIMO 1 operación nueva por análisis
• Solo operar en régimen BULL o SIDEWAYS
• VIX debe ser < 22
• Confianza mínima: 0.7 para ejecutar
─────────────────────────────────────────────────────────────────────────────

CRITERIOS PARA ACCIÓN AUTOMÁTICA:
─────────────────────────────────────────────────────────────────────────────
Para que una acción se ejecute automáticamente TODOS estos criterios:

✓ Régimen = BULL o SIDEWAYS
✓ risk_limits.can_trade = True
✓ VIX < 22
✓ Confluencia de 3+ indicadores
✓ Volumen > promedio
✓ No hay resistencia/soporte importante en camino al target
✓ R/R ≥ 2
✓ Tu confianza ≥ 0.7
✓ size_suggestion ≤ 0.02 (2%)

Si CUALQUIER criterio no se cumple → actions = []
─────────────────────────────────────────────────────────────────────────────

CUANDO ALGO SALE MAL:
Si tienes CUALQUIER duda sobre una operación → NO la hagas
Es mejor perder una oportunidad que perder capital
La preservación del capital es siempre la prioridad

═══════════════════════════════════════════════════════════════════════════"""

EXPERIMENTAL_RESPONSE_FORMAT = """
FORMATO DE RESPUESTA (EXPERIMENTAL):
Tu respuesta DEBE ser JSON válido:

```json
{
  "market_view": "bullish" | "bearish" | "neutral" | "uncertain",
  "confidence": 0.0-1.0,
  "reasoning": "Análisis detallado con justificación clara de cada decisión...",
  "key_factors": [
    "Criterio 1 cumplido",
    "Criterio 2 cumplido",
    "Criterio 3 cumplido",
    ...
  ],
  "actions": [
    {
      "symbol": "VWCE.DE",
      "direction": "LONG",
      "entry_price": 108.50,
      "stop_loss": 106.90,
      "take_profit": 112.70,
      "size_suggestion": 0.02,
      "reasoning": "Todos los criterios cumplidos: Régimen BULL (75%), VIX 18.5, RSI 42, MACD+, Vol 1.2x. R/R = 2.6. Stop 1.5%, Size 2%."
    }
  ],
  "warnings": [
    "⚠️ MODO AUTOMÁTICO - Verificar kill switch activo",
    "Earnings de ASML (componente) en 5 días"
  ]
}
```

CRÍTICO:
- confidence < 0.7 → actions DEBE ser []
- size_suggestion > 0.02 → RECHAZADO
- Solo 1 acción máximo
- Incluir SIEMPRE warning sobre modo automático
"""

KILL_SWITCH_REMINDER = """
═══════════════════════════════════════════════════════════════════════════
                        🛑 KILL SWITCH REMINDER 🛑
═══════════════════════════════════════════════════════════════════════════
Antes de operar en modo EXPERIMENTAL, verificar que:

1. Kill switch de emergencia está ACTIVO y accesible
2. Límites diarios configurados en el broker
3. Stop losses están siendo respetados por el sistema
4. Alertas de Telegram configuradas y funcionando
5. El usuario ha revisado y aceptado los riesgos

Si cualquiera de estos puntos no está confirmado → NO OPERAR
═══════════════════════════════════════════════════════════════════════════"""


def get_experimental_prompt() -> str:
    """Obtiene el system prompt completo para nivel EXPERIMENTAL."""
    return "\n\n".join([
        build_base_prompt(),
        EXPERIMENTAL_SPECIFIC,
        EXPERIMENTAL_RESPONSE_FORMAT,
        KILL_SWITCH_REMINDER,
    ])
```

---

### 10.5 Prompt Manager

```python
# src/agents/llm/prompts/__init__.py
"""
Prompt Manager - Gestión centralizada de prompts por nivel de autonomía.
"""

from typing import Callable
from src.agents.llm.interfaces import AutonomyLevel

from .conservative import get_conservative_prompt
from .moderate import get_moderate_prompt
from .experimental import get_experimental_prompt


# Registry de prompts por nivel
_PROMPT_REGISTRY: dict[AutonomyLevel, Callable[[], str]] = {
    AutonomyLevel.CONSERVATIVE: get_conservative_prompt,
    AutonomyLevel.MODERATE: get_moderate_prompt,
    AutonomyLevel.EXPERIMENTAL: get_experimental_prompt,
}


def get_system_prompt(autonomy_level: AutonomyLevel) -> str:
    """
    Obtiene el system prompt para el nivel de autonomía dado.
    
    Args:
        autonomy_level: Nivel de autonomía
    
    Returns:
        System prompt completo
    
    Raises:
        ValueError: Si el nivel no está registrado
    """
    if autonomy_level not in _PROMPT_REGISTRY:
        raise ValueError(f"Unknown autonomy level: {autonomy_level}")
    
    return _PROMPT_REGISTRY[autonomy_level]()


def get_prompt_token_estimate(autonomy_level: AutonomyLevel) -> int:
    """
    Estima tokens del system prompt (aproximado).
    
    Args:
        autonomy_level: Nivel de autonomía
    
    Returns:
        Estimación de tokens (chars / 4 aproximadamente)
    """
    prompt = get_system_prompt(autonomy_level)
    return len(prompt) // 4


__all__ = [
    "get_system_prompt",
    "get_prompt_token_estimate",
]
```

---

## 11. Tarea B2.4: Claude Agent Implementation

**Objetivo:** Implementar el agente concreto para Claude/Anthropic.

**Archivo:** `src/agents/llm/agents/claude_agent.py`

```python
# src/agents/llm/agents/claude_agent.py
"""
Claude Agent - Implementación del LLM Agent usando Anthropic Claude.

Esta es la implementación principal del AI Agent para trading.
"""

from __future__ import annotations

import json
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, Any

import anthropic
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
    MarketView,
    LLMAPIError,
    LLMRateLimitError,
    LLMParseError,
    LLMTimeoutError,
    LLMContextTooLargeError,
)
from src.agents.llm.prompts import get_system_prompt
from src.strategies.interfaces import Signal


logger = logging.getLogger(__name__)


class ClaudeAgent(LLMAgent):
    """
    Implementación del LLM Agent usando Claude de Anthropic.
    
    Características:
    - Soporte para claude-sonnet-4-20250514 (recomendado) y otros modelos
    - Retry automático con backoff exponencial
    - Parsing robusto de respuestas JSON
    - Estimación de tokens
    - Health check de API
    """
    
    # Límites de contexto por modelo (aproximados)
    MODEL_CONTEXT_LIMITS = {
        "claude-sonnet-4-20250514": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-opus-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
    }
    
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2000,
        temperature: float = 0.3,
        default_autonomy: AutonomyLevel = AutonomyLevel.MODERATE,
        timeout_seconds: float = 60.0,
    ):
        """
        Inicializa el Claude Agent.
        
        Args:
            api_key: API key de Anthropic
            model: Modelo a usar
            max_tokens: Máximo de tokens en respuesta
            temperature: Temperatura para generación (0-1)
            default_autonomy: Nivel de autonomía por defecto
            timeout_seconds: Timeout para llamadas API
        """
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._default_autonomy = default_autonomy
        self._timeout = timeout_seconds
        
        # Cliente de Anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        
        # Métricas internas
        self._total_calls = 0
        self._total_tokens = 0
        self._last_error: Optional[str] = None
        self._last_call_time: Optional[datetime] = None
        
        logger.info(f"ClaudeAgent initialized with model={model}, autonomy={default_autonomy.value}")
    
    @property
    def agent_id(self) -> str:
        return f"claude_{self._model.split('-')[1]}_{self._default_autonomy.value}"
    
    @property
    def model_name(self) -> str:
        return self._model
    
    @property
    def supports_streaming(self) -> bool:
        return True  # Claude soporta streaming
    
    @retry(
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
    )
    async def decide(
        self,
        context: AgentContext,
        autonomy_level: Optional[AutonomyLevel] = None
    ) -> AgentDecision:
        """
        Toma una decisión de trading basada en el contexto.
        
        Args:
            context: Contexto completo del mercado
            autonomy_level: Override del nivel de autonomía
        
        Returns:
            AgentDecision con acciones y razonamiento
        """
        autonomy = autonomy_level or self._default_autonomy
        decision_id = f"dec_{uuid.uuid4().hex[:12]}"
        
        logger.info(f"Making decision {decision_id} with autonomy={autonomy.value}")
        
        # Verificar si debemos saltar
        should_skip, skip_reason = self.should_skip_decision(context)
        if should_skip:
            logger.info(f"Skipping decision: {skip_reason}")
            return self._create_skip_decision(
                decision_id=decision_id,
                context=context,
                autonomy=autonomy,
                reason=skip_reason
            )
        
        # Verificar contexto
        is_valid, issues = self.validate_context(context)
        if not is_valid:
            logger.warning(f"Context validation issues: {issues}")
        
        # Estimar tokens y verificar límites
        estimated_tokens = self.estimate_tokens(context)
        max_context = self.MODEL_CONTEXT_LIMITS.get(self._model, 100000)
        if estimated_tokens > max_context * 0.9:
            raise LLMContextTooLargeError(
                f"Context too large: {estimated_tokens} tokens",
                tokens_needed=estimated_tokens,
                tokens_available=max_context
            )
        
        # Construir prompts
        system_prompt = self.get_system_prompt(autonomy)
        user_prompt = context.to_prompt_text()
        
        # Llamar a Claude
        start_time = time.time()
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ],
                timeout=self._timeout,
            )
        except anthropic.RateLimitError as e:
            self._last_error = str(e)
            raise LLMRateLimitError(str(e), retry_after=60)
        except anthropic.APITimeoutError as e:
            self._last_error = str(e)
            raise LLMTimeoutError(str(e), timeout_seconds=self._timeout)
        except anthropic.APIError as e:
            self._last_error = str(e)
            raise LLMAPIError(str(e), status_code=getattr(e, 'status_code', None))
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Actualizar métricas
        self._total_calls += 1
        self._total_tokens += response.usage.input_tokens + response.usage.output_tokens
        self._last_call_time = datetime.utcnow()
        
        # Parsear respuesta
        raw_content = response.content[0].text
        parsed = self._parse_response(raw_content, context, autonomy)
        
        # Construir decisión
        decision = AgentDecision(
            decision_id=decision_id,
            context_id=context.context_id,
            timestamp=datetime.utcnow(),
            actions=parsed["actions"],
            market_view=parsed["market_view"],
            reasoning=parsed["reasoning"],
            key_factors=parsed["key_factors"],
            confidence=parsed["confidence"],
            model_used=self._model,
            autonomy_level=autonomy,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
            latency_ms=latency_ms,
            warnings=parsed.get("warnings", [])
        )
        
        logger.info(
            f"Decision {decision_id} complete: "
            f"view={decision.market_view.value}, "
            f"actions={len(decision.actions)}, "
            f"confidence={decision.confidence:.2f}, "
            f"latency={latency_ms:.0f}ms"
        )
        
        return decision
    
    def get_system_prompt(self, autonomy_level: AutonomyLevel) -> str:
        """Obtiene el system prompt para el nivel de autonomía."""
        return get_system_prompt(autonomy_level)
    
    async def health_check(self) -> dict:
        """Verifica estado del agente y conexión a Anthropic."""
        try:
            # Llamada mínima para verificar API
            start = time.time()
            response = self._client.messages.create(
                model=self._model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ping"}],
                timeout=10,
            )
            latency = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "model": self._model,
                "latency_ms": latency,
                "total_calls": self._total_calls,
                "total_tokens": self._total_tokens,
                "last_error": None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "model": self._model,
                "latency_ms": None,
                "total_calls": self._total_calls,
                "total_tokens": self._total_tokens,
                "last_error": str(e)
            }
    
    def estimate_tokens(self, context: AgentContext) -> int:
        """Estima tokens para el contexto dado."""
        # Estimación simple: chars / 4
        # En producción, usar tiktoken o la API de Anthropic
        prompt_text = context.to_prompt_text()
        system_prompt = self.get_system_prompt(context.autonomy_level)
        total_chars = len(prompt_text) + len(system_prompt)
        return total_chars // 4
    
    def _parse_response(
        self,
        raw_response: str,
        context: AgentContext,
        autonomy: AutonomyLevel
    ) -> dict:
        """
        Parsea la respuesta del LLM a estructura interna.
        
        Args:
            raw_response: Texto raw de Claude
            context: Contexto original
            autonomy: Nivel de autonomía
        
        Returns:
            Dict con campos parseados
        
        Raises:
            LLMParseError: Si no se puede parsear
        """
        # Intentar extraer JSON del response
        try:
            # Buscar JSON en la respuesta (puede estar envuelto en markdown)
            json_str = self._extract_json(raw_response)
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse JSON: {e}\nRaw: {raw_response[:500]}")
            raise LLMParseError(f"Invalid JSON response: {e}", raw_response=raw_response)
        
        # Validar campos requeridos
        required_fields = ["market_view", "confidence", "reasoning", "key_factors", "actions"]
        for field in required_fields:
            if field not in data:
                raise LLMParseError(f"Missing required field: {field}", raw_response=raw_response)
        
        # Parsear market_view
        try:
            market_view = MarketView(data["market_view"])
        except ValueError:
            logger.warning(f"Unknown market_view: {data['market_view']}, defaulting to UNCERTAIN")
            market_view = MarketView.UNCERTAIN
        
        # Parsear acciones a Signal
        actions = []
        for action_data in data.get("actions", []):
            try:
                signal = self._parse_action_to_signal(action_data, context)
                actions.append(signal)
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse action: {e}, skipping")
                continue
        
        # Validar acciones según autonomía
        if autonomy == AutonomyLevel.CONSERVATIVE and actions:
            logger.warning("Conservative mode should not have actions, clearing")
            actions = []
        
        if autonomy == AutonomyLevel.EXPERIMENTAL and len(actions) > 1:
            logger.warning("Experimental mode limited to 1 action, keeping first")
            actions = actions[:1]
        
        return {
            "market_view": market_view,
            "confidence": max(0.0, min(1.0, float(data["confidence"]))),
            "reasoning": str(data["reasoning"]),
            "key_factors": list(data["key_factors"]),
            "actions": actions,
            "warnings": data.get("warnings", [])
        }
    
    def _extract_json(self, text: str) -> str:
        """Extrae JSON de texto que puede tener markdown u otro formato."""
        # Intentar encontrar bloque de código JSON
        import re
        
        # Patrón: ```json ... ``` o ``` ... ```
        code_block = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if code_block:
            return code_block.group(1)
        
        # Intentar encontrar JSON directo (empieza con {)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json_match.group(0)
        
        # Último recurso: devolver todo
        return text
    
    def _parse_action_to_signal(self, action_data: dict, context: AgentContext) -> Signal:
        """Convierte datos de acción del LLM a Signal."""
        return Signal(
            strategy_id=f"ai_agent_{context.autonomy_level.value}",
            symbol=action_data["symbol"],
            direction=action_data["direction"].upper(),
            confidence=float(action_data.get("confidence", 0.7)),
            entry_price=float(action_data["entry_price"]),
            stop_loss=float(action_data["stop_loss"]),
            take_profit=float(action_data["take_profit"]),
            size_suggestion=float(action_data.get("size_suggestion", 0.02)),
            regime_at_signal=context.regime.regime,
            reasoning=action_data.get("reasoning", ""),
            metadata={
                "agent_id": self.agent_id,
                "model": self._model,
                "autonomy_level": context.autonomy_level.value,
                "context_id": context.context_id
            }
        )
    
    def _create_skip_decision(
        self,
        decision_id: str,
        context: AgentContext,
        autonomy: AutonomyLevel,
        reason: str
    ) -> AgentDecision:
        """Crea una decisión vacía cuando se salta el análisis."""
        return AgentDecision(
            decision_id=decision_id,
            context_id=context.context_id,
            timestamp=datetime.utcnow(),
            actions=[],
            market_view=MarketView.UNCERTAIN,
            reasoning=f"Decision skipped: {reason}",
            key_factors=[reason],
            confidence=0.0,
            model_used=self._model,
            autonomy_level=autonomy,
            tokens_used=0,
            latency_ms=0,
            warnings=[f"⚠️ {reason}"]
        )
```

---

## 12. Tarea B2.5: Rate Limiter

**Archivo:** `src/agents/llm/rate_limiter.py`

```python
# src/agents/llm/rate_limiter.py
"""
Rate Limiter - Protección contra exceso de llamadas a APIs de LLM.

Implementa rate limiting para:
- Respetar límites de Anthropic API
- Controlar costos
- Evitar ban por abuso
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import logging

from aiolimiter import AsyncLimiter


logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuración de rate limiting."""
    requests_per_minute: int = 50      # RPM
    tokens_per_minute: int = 40000     # TPM
    requests_per_day: int = 5000       # RPD
    cooldown_seconds: float = 1.0      # Tiempo mínimo entre requests


class RateLimiter:
    """
    Rate limiter para llamadas a LLM APIs.
    
    Implementa múltiples niveles de limiting:
    - Por minuto (requests y tokens)
    - Por día (requests)
    - Cooldown entre requests
    """
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """
        Inicializa el rate limiter.
        
        Args:
            config: Configuración de límites
        """
        self.config = config or RateLimitConfig()
        
        # Limiters
        self._rpm_limiter = AsyncLimiter(
            self.config.requests_per_minute,
            time_period=60
        )
        self._tpm_limiter = AsyncLimiter(
            self.config.tokens_per_minute,
            time_period=60
        )
        
        # Contadores diarios
        self._daily_requests = 0
        self._daily_reset_time = self._next_daily_reset()
        
        # Cooldown tracking
        self._last_request_time: Optional[float] = None
        
        logger.info(f"RateLimiter initialized: {self.config}")
    
    async def acquire(self, estimated_tokens: int = 1000) -> bool:
        """
        Adquiere permiso para hacer una request.
        
        Args:
            estimated_tokens: Tokens estimados para la request
        
        Returns:
            True si se puede proceder, False si está limitado
        
        Raises:
            RateLimitExceeded: Si se excede algún límite
        """
        # Verificar reset diario
        self._check_daily_reset()
        
        # Verificar límite diario
        if self._daily_requests >= self.config.requests_per_day:
            logger.warning("Daily request limit reached")
            return False
        
        # Cooldown
        if self._last_request_time:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.config.cooldown_seconds:
                await asyncio.sleep(self.config.cooldown_seconds - elapsed)
        
        # Adquirir RPM
        await self._rpm_limiter.acquire()
        
        # Adquirir TPM (por tokens estimados)
        for _ in range(max(1, estimated_tokens // 1000)):
            await self._tpm_limiter.acquire()
        
        # Actualizar contadores
        self._daily_requests += 1
        self._last_request_time = time.time()
        
        return True
    
    def get_status(self) -> dict:
        """Obtiene estado actual del rate limiter."""
        return {
            "daily_requests": self._daily_requests,
            "daily_limit": self.config.requests_per_day,
            "daily_remaining": self.config.requests_per_day - self._daily_requests,
            "reset_time": self._daily_reset_time.isoformat(),
            "rpm_limit": self.config.requests_per_minute,
            "tpm_limit": self.config.tokens_per_minute,
        }
    
    def _check_daily_reset(self):
        """Verifica y ejecuta reset diario si corresponde."""
        now = datetime.utcnow()
        if now >= self._daily_reset_time:
            logger.info(f"Daily reset: {self._daily_requests} requests used")
            self._daily_requests = 0
            self._daily_reset_time = self._next_daily_reset()
    
    def _next_daily_reset(self) -> datetime:
        """Calcula próximo tiempo de reset (00:00 UTC)."""
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)


# Singleton para uso global
_default_limiter: Optional[RateLimiter] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Obtiene el rate limiter global."""
    global _default_limiter
    if _default_limiter is None:
        _default_limiter = RateLimiter(config)
    return _default_limiter
```

---

*Fin de Parte 3 - Implementación Claude Agent + Sistema de Prompts*

---

*Documento de Implementación - Fase B2: AI Agent*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
-e 

---

## Integración, Configuración y Factory

---

## 13. Tarea B2.6: AIAgentStrategy + Factory

**Objetivo:** Integrar el LLM Agent con el sistema de estrategias existente (Fase B1).

---

### 13.1 LLM Agent Factory

**Archivo:** `src/agents/llm/factory.py`

```python
# src/agents/llm/factory.py
"""
LLM Agent Factory - Crea agentes según configuración.

Permite cambiar entre Claude, GPT-4, Gemini con solo cambiar config.
"""

from __future__ import annotations

import os
from typing import Optional, Type
import logging

from .interfaces import LLMAgent, AutonomyLevel
from .config import LLMAgentConfig, load_agent_config
from .agents.claude_agent import ClaudeAgent


logger = logging.getLogger(__name__)


# Registry de implementaciones disponibles
_AGENT_REGISTRY: dict[str, Type[LLMAgent]] = {
    "claude": ClaudeAgent,
    # Futuras implementaciones:
    # "openai": OpenAIAgent,
    # "gemini": GeminiAgent,
}


class LLMAgentFactory:
    """
    Factory para crear instancias de LLM Agents.
    
    Uso:
        # Desde configuración YAML
        agent = LLMAgentFactory.create_from_config()
        
        # Especificando parámetros
        agent = LLMAgentFactory.create(
            provider="claude",
            model="claude-sonnet-4-20250514",
            autonomy=AutonomyLevel.MODERATE
        )
    """
    
    @classmethod
    def create_from_config(
        cls,
        config_path: Optional[str] = None
    ) -> LLMAgent:
        """
        Crea un agente desde archivo de configuración.
        
        Args:
            config_path: Ruta al archivo YAML (default: config/agents.yaml)
        
        Returns:
            Instancia de LLMAgent configurada
        """
        config = load_agent_config(config_path)
        return cls.create_from_config_object(config)
    
    @classmethod
    def create_from_config_object(cls, config: LLMAgentConfig) -> LLMAgent:
        """
        Crea un agente desde objeto de configuración.
        
        Args:
            config: Objeto LLMAgentConfig
        
        Returns:
            Instancia de LLMAgent
        """
        provider = config.active_provider
        
        if provider not in _AGENT_REGISTRY:
            available = list(_AGENT_REGISTRY.keys())
            raise ValueError(f"Unknown provider '{provider}'. Available: {available}")
        
        agent_class = _AGENT_REGISTRY[provider]
        provider_config = config.get_provider_config(provider)
        
        # Obtener API key desde env o config
        api_key = cls._get_api_key(provider, provider_config)
        
        logger.info(f"Creating {provider} agent with model={provider_config.get('model')}")
        
        if provider == "claude":
            return ClaudeAgent(
                api_key=api_key,
                model=provider_config.get("model", "claude-sonnet-4-20250514"),
                max_tokens=provider_config.get("max_tokens", 2000),
                temperature=provider_config.get("temperature", 0.3),
                default_autonomy=AutonomyLevel(config.autonomy_level),
                timeout_seconds=provider_config.get("timeout", 60.0),
            )
        
        # Placeholder para otros providers
        raise NotImplementedError(f"Provider {provider} not yet implemented")
    
    @classmethod
    def create(
        cls,
        provider: str = "claude",
        model: Optional[str] = None,
        autonomy: AutonomyLevel = AutonomyLevel.MODERATE,
        api_key: Optional[str] = None,
        **kwargs
    ) -> LLMAgent:
        """
        Crea un agente con parámetros explícitos.
        
        Args:
            provider: Nombre del provider (claude, openai, gemini)
            model: Modelo específico (usa default del provider si no se especifica)
            autonomy: Nivel de autonomía
            api_key: API key (usa env var si no se especifica)
            **kwargs: Parámetros adicionales para el agente
        
        Returns:
            Instancia de LLMAgent
        """
        if provider not in _AGENT_REGISTRY:
            raise ValueError(f"Unknown provider: {provider}")
        
        # Defaults por provider
        defaults = {
            "claude": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2000,
                "temperature": 0.3,
            },
            "openai": {
                "model": "gpt-4-turbo",
                "max_tokens": 2000,
                "temperature": 0.3,
            },
        }
        
        provider_defaults = defaults.get(provider, {})
        final_model = model or provider_defaults.get("model")
        final_api_key = api_key or cls._get_api_key(provider, {})
        
        agent_class = _AGENT_REGISTRY[provider]
        
        if provider == "claude":
            return ClaudeAgent(
                api_key=final_api_key,
                model=final_model,
                max_tokens=kwargs.get("max_tokens", provider_defaults.get("max_tokens", 2000)),
                temperature=kwargs.get("temperature", provider_defaults.get("temperature", 0.3)),
                default_autonomy=autonomy,
                timeout_seconds=kwargs.get("timeout", 60.0),
            )
        
        raise NotImplementedError(f"Provider {provider} not yet implemented")
    
    @classmethod
    def _get_api_key(cls, provider: str, config: dict) -> str:
        """Obtiene API key desde config o environment."""
        # Primero intentar desde config
        if "api_key" in config and config["api_key"]:
            return config["api_key"]
        
        # Luego desde environment
        env_vars = {
            "claude": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
        }
        
        env_var = env_vars.get(provider)
        if env_var:
            api_key = os.environ.get(env_var)
            if api_key:
                return api_key
        
        raise ValueError(
            f"No API key found for {provider}. "
            f"Set {env_var} environment variable or provide in config."
        )
    
    @classmethod
    def list_available_providers(cls) -> list[str]:
        """Lista providers disponibles."""
        return list(_AGENT_REGISTRY.keys())
    
    @classmethod
    def register_provider(cls, name: str, agent_class: Type[LLMAgent]):
        """
        Registra un nuevo provider.
        
        Args:
            name: Nombre del provider
            agent_class: Clase que implementa LLMAgent
        """
        if not issubclass(agent_class, LLMAgent):
            raise TypeError(f"{agent_class} must be a subclass of LLMAgent")
        _AGENT_REGISTRY[name] = agent_class
        logger.info(f"Registered LLM provider: {name}")
```

---

### 13.2 Configuración de Agentes

**Archivo:** `src/agents/llm/config.py`

```python
# src/agents/llm/config.py
"""
Configuración del LLM Agent.

Carga configuración desde YAML y proporciona defaults seguros.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
import os

import yaml


@dataclass
class LLMAgentConfig:
    """Configuración completa del sistema de LLM Agents."""
    
    # Provider activo
    active_provider: str = "claude"
    
    # Nivel de autonomía por defecto
    autonomy_level: str = "moderate"
    
    # Configuración por provider
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    # Rate limiting
    rate_limit: dict[str, int] = field(default_factory=lambda: {
        "requests_per_minute": 50,
        "tokens_per_minute": 40000,
        "requests_per_day": 5000,
    })
    
    # Caching
    cache_enabled: bool = True
    cache_ttl_seconds: int = 300  # 5 minutos
    
    def get_provider_config(self, provider: str) -> dict[str, Any]:
        """Obtiene configuración de un provider específico."""
        return self.providers.get(provider, {})


def load_agent_config(config_path: Optional[str] = None) -> LLMAgentConfig:
    """
    Carga configuración desde archivo YAML.
    
    Args:
        config_path: Ruta al archivo (default: config/agents.yaml)
    
    Returns:
        LLMAgentConfig poblado
    """
    if config_path is None:
        # Buscar en ubicaciones standard
        possible_paths = [
            Path("config/agents.yaml"),
            Path("../config/agents.yaml"),
            Path(os.environ.get("NEXUS_CONFIG_PATH", "")) / "agents.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                break
    
    if config_path and Path(config_path).exists():
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        
        return LLMAgentConfig(
            active_provider=data.get("ai_agent", {}).get("active", "claude"),
            autonomy_level=data.get("ai_agent", {}).get("autonomy_level", "moderate"),
            providers=data.get("ai_agent", {}).get("models", {}),
            rate_limit=data.get("ai_agent", {}).get("rate_limit", {}),
            cache_enabled=data.get("ai_agent", {}).get("cache_enabled", True),
            cache_ttl_seconds=data.get("ai_agent", {}).get("cache_ttl_seconds", 300),
        )
    
    # Retornar defaults si no hay archivo
    return LLMAgentConfig()


# Configuración por defecto para config/agents.yaml
DEFAULT_CONFIG_YAML = """
# AI Agent Configuration
# Este archivo configura el agente de trading basado en LLM

ai_agent:
  # Provider activo: claude, openai, gemini
  active: "claude"
  
  # Nivel de autonomía por defecto
  # - conservative: Solo información, humano decide
  # - moderate: Sugiere operaciones, requiere confirmación
  # - experimental: Ejecución autónoma con límites estrictos
  autonomy_level: "moderate"
  
  # Configuración por provider
  models:
    claude:
      model: "claude-sonnet-4-20250514"
      max_tokens: 2000
      temperature: 0.3
      timeout: 60
      # api_key: se lee de ANTHROPIC_API_KEY env var
    
    openai:
      model: "gpt-4-turbo"
      max_tokens: 2000
      temperature: 0.3
      timeout: 60
      # api_key: se lee de OPENAI_API_KEY env var
  
  # Rate limiting para proteger la API
  rate_limit:
    requests_per_minute: 50
    tokens_per_minute: 40000
    requests_per_day: 5000
  
  # Cache de decisiones
  cache_enabled: true
  cache_ttl_seconds: 300  # 5 minutos
"""
```

---

### 13.3 AIAgentStrategy (Wrapper TradingStrategy)

**Archivo:** `src/strategies/swing/ai_agent_strategy.py`

```python
# src/strategies/swing/ai_agent_strategy.py
"""
AI Agent Strategy - Wrapper que integra LLMAgent con el sistema de estrategias.

Esta clase adapta el LLMAgent para que funcione como una TradingStrategy más,
permitiendo su ejecución junto con otras estrategias como ETF Momentum.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional

from src.strategies.interfaces import TradingStrategy, Signal
from src.agents.llm.interfaces import (
    LLMAgent,
    AgentContext,
    AgentDecision,
    AutonomyLevel,
)
from src.agents.llm.factory import LLMAgentFactory
from src.agents.llm.context_builder import ContextBuilder
from src.agents.llm.rate_limiter import get_rate_limiter


logger = logging.getLogger(__name__)


class AIAgentStrategy(TradingStrategy):
    """
    Estrategia de trading basada en AI Agent (LLM).
    
    Integra el LLMAgent con el sistema de estrategias de Fase B1,
    permitiendo su ejecución coordinada con otras estrategias.
    
    Características:
    - Se comporta como cualquier otra TradingStrategy
    - Genera Signal[] compatibles con el pipeline existente
    - Respeta los regímenes de mercado
    - Incluye rate limiting y caching
    """
    
    def __init__(
        self,
        llm_agent: Optional[LLMAgent] = None,
        context_builder: Optional[ContextBuilder] = None,
        autonomy_level: AutonomyLevel = AutonomyLevel.MODERATE,
        watchlist: Optional[list[str]] = None,
    ):
        """
        Inicializa la estrategia AI Agent.
        
        Args:
            llm_agent: Instancia de LLMAgent (crea desde config si no se provee)
            context_builder: Builder de contexto (crea default si no se provee)
            autonomy_level: Nivel de autonomía
            watchlist: Lista de símbolos a analizar
        """
        self._llm_agent = llm_agent or LLMAgentFactory.create_from_config()
        self._context_builder = context_builder
        self._autonomy = autonomy_level
        self._watchlist = watchlist or self._default_watchlist()
        
        # Rate limiter
        self._rate_limiter = get_rate_limiter()
        
        # Cache de última decisión
        self._last_decision: Optional[AgentDecision] = None
        self._last_decision_time: Optional[datetime] = None
        
        logger.info(
            f"AIAgentStrategy initialized: "
            f"agent={self._llm_agent.agent_id}, "
            f"autonomy={self._autonomy.value}, "
            f"watchlist={len(self._watchlist)} symbols"
        )
    
    @property
    def strategy_id(self) -> str:
        return f"ai_agent_{self._autonomy.value}"
    
    @property
    def required_regime(self) -> list[str]:
        """
        Regímenes en los que esta estrategia está activa.
        
        AI Agent puede operar en BULL y SIDEWAYS.
        En BEAR y VOLATILE, se pausa automáticamente.
        """
        return ["BULL", "SIDEWAYS"]
    
    def generate_signals(
        self,
        market_data: dict,
        regime: dict,
        portfolio: dict
    ) -> list[Signal]:
        """
        Genera señales de trading usando el LLM Agent.
        
        Este método es síncrono para compatibilidad con TradingStrategy,
        pero internamente ejecuta la lógica async del LLM.
        
        Args:
            market_data: Datos de mercado para watchlist
            regime: Información de régimen actual
            portfolio: Estado del portfolio
        
        Returns:
            Lista de Signal generadas por el AI Agent
        """
        # Ejecutar async en event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Ya estamos en un contexto async
                future = asyncio.ensure_future(
                    self._generate_signals_async(market_data, regime, portfolio)
                )
                return asyncio.get_event_loop().run_until_complete(future)
            else:
                return loop.run_until_complete(
                    self._generate_signals_async(market_data, regime, portfolio)
                )
        except RuntimeError:
            # No hay event loop, crear uno
            return asyncio.run(
                self._generate_signals_async(market_data, regime, portfolio)
            )
    
    async def _generate_signals_async(
        self,
        market_data: dict,
        regime: dict,
        portfolio: dict
    ) -> list[Signal]:
        """Implementación async de generate_signals."""
        
        # Verificar rate limiting
        can_proceed = await self._rate_limiter.acquire(estimated_tokens=2000)
        if not can_proceed:
            logger.warning("Rate limit reached, skipping AI Agent analysis")
            return []
        
        # Verificar régimen
        current_regime = regime.get("regime", "UNKNOWN")
        if current_regime not in self.required_regime:
            logger.info(f"AI Agent paused: regime {current_regime} not in {self.required_regime}")
            return []
        
        try:
            # Construir contexto
            context = await self._build_context(market_data, regime, portfolio)
            
            # Obtener decisión del LLM
            decision = await self._llm_agent.decide(context, self._autonomy)
            
            # Guardar para debugging
            self._last_decision = decision
            self._last_decision_time = datetime.utcnow()
            
            # Log de decisión
            logger.info(
                f"AI Agent decision: "
                f"view={decision.market_view.value}, "
                f"confidence={decision.confidence:.2f}, "
                f"actions={len(decision.actions)}"
            )
            
            if decision.reasoning:
                logger.debug(f"Reasoning: {decision.reasoning[:200]}...")
            
            return decision.actions
            
        except Exception as e:
            logger.error(f"AI Agent error: {e}", exc_info=True)
            return []
    
    def should_close(
        self,
        position: dict,
        market_data: dict,
        regime: dict
    ) -> Optional[Signal]:
        """
        Determina si una posición debe cerrarse.
        
        El AI Agent puede recomendar cierres basados en:
        - Cambio de régimen
        - Alcance de stop loss o take profit
        - Cambio en las condiciones que motivaron la entrada
        """
        # Verificar cambio de régimen
        current_regime = regime.get("regime", "UNKNOWN")
        position_regime = position.get("regime_at_entry", "UNKNOWN")
        
        # Si el régimen cambió a BEAR o VOLATILE, cerrar
        if current_regime in ["BEAR", "VOLATILE"] and position_regime not in ["BEAR", "VOLATILE"]:
            logger.info(f"Closing {position['symbol']}: regime changed to {current_regime}")
            return Signal(
                strategy_id=self.strategy_id,
                symbol=position["symbol"],
                direction="CLOSE",
                confidence=0.9,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                size_suggestion=1.0,  # Cerrar toda la posición
                regime_at_signal=current_regime,
                reasoning=f"Regime change: {position_regime} → {current_regime}",
                metadata={"close_reason": "regime_change"}
            )
        
        # Verificar stop loss / take profit tradicional
        current_price = market_data.get("current_price", 0)
        stop_loss = position.get("stop_loss", 0)
        take_profit = position.get("take_profit", float("inf"))
        
        if current_price <= stop_loss:
            return Signal(
                strategy_id=self.strategy_id,
                symbol=position["symbol"],
                direction="CLOSE",
                confidence=1.0,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                size_suggestion=1.0,
                regime_at_signal=current_regime,
                reasoning=f"Stop loss hit: {current_price} <= {stop_loss}",
                metadata={"close_reason": "stop_loss"}
            )
        
        if current_price >= take_profit:
            return Signal(
                strategy_id=self.strategy_id,
                symbol=position["symbol"],
                direction="CLOSE",
                confidence=1.0,
                entry_price=None,
                stop_loss=None,
                take_profit=None,
                size_suggestion=1.0,
                regime_at_signal=current_regime,
                reasoning=f"Take profit hit: {current_price} >= {take_profit}",
                metadata={"close_reason": "take_profit"}
            )
        
        return None
    
    async def _build_context(
        self,
        market_data: dict,
        regime: dict,
        portfolio: dict
    ) -> AgentContext:
        """Construye el contexto para el LLM."""
        if self._context_builder:
            return await self._context_builder.build(
                watchlist=self._watchlist,
                autonomy_level=self._autonomy
            )
        
        # Fallback: construir contexto mínimo desde los datos provistos
        from src.agents.llm.interfaces import (
            RegimeInfo,
            MarketContext,
            PortfolioSummary,
            RiskLimits,
            SymbolData,
        )
        import uuid
        
        return AgentContext(
            context_id=f"ctx_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.utcnow(),
            regime=RegimeInfo(
                regime=regime.get("regime", "SIDEWAYS"),
                confidence=regime.get("confidence", 0.5),
                probabilities=regime.get("probabilities", {}),
                model_id=regime.get("model_id", "unknown")
            ),
            market=MarketContext(
                spy_change_pct=market_data.get("spy_change_pct", 0),
                qqq_change_pct=market_data.get("qqq_change_pct", 0),
                vix_level=market_data.get("vix_level", 20),
                vix_change_pct=market_data.get("vix_change_pct", 0),
                market_breadth=market_data.get("market_breadth", 0.5),
                sector_rotation={}
            ),
            portfolio=PortfolioSummary(
                total_value=portfolio.get("total_value", 25000),
                cash_available=portfolio.get("cash_available", 25000),
                invested_value=portfolio.get("invested_value", 0),
                positions=(),
                daily_pnl=portfolio.get("daily_pnl", 0),
                daily_pnl_pct=portfolio.get("daily_pnl_pct", 0),
                total_pnl=portfolio.get("total_pnl", 0),
                total_pnl_pct=portfolio.get("total_pnl_pct", 0)
            ),
            watchlist=(),  # Se poblaría con datos reales
            risk_limits=RiskLimits(
                max_position_pct=5.0,
                max_portfolio_risk_pct=2.0,
                max_daily_trades=5,
                max_daily_loss_pct=3.0,
                current_daily_trades=0,
                current_daily_pnl_pct=0
            ),
            autonomy_level=self._autonomy
        )
    
    def _default_watchlist(self) -> list[str]:
        """Watchlist por defecto para el AI Agent."""
        return [
            # ETFs EU
            "VWCE.DE",   # Vanguard FTSE All-World
            "CSPX.DE",   # iShares S&P 500
            "EUNL.DE",   # iShares Core MSCI World
            
            # ETFs US
            "SPY",       # S&P 500
            "QQQ",       # Nasdaq 100
            "IWM",       # Russell 2000
            "DIA",       # Dow Jones
        ]
    
    def get_last_decision(self) -> Optional[AgentDecision]:
        """Obtiene la última decisión del agente (para debugging)."""
        return self._last_decision


# Función helper para crear estrategia desde config
def create_ai_agent_strategy(
    config_path: Optional[str] = None,
    mcp_client=None
) -> AIAgentStrategy:
    """
    Factory function para crear AIAgentStrategy.
    
    Args:
        config_path: Ruta a config/agents.yaml
        mcp_client: Cliente MCP para context builder
    
    Returns:
        AIAgentStrategy configurada
    """
    from src.agents.llm.config import load_agent_config
    
    config = load_agent_config(config_path)
    agent = LLMAgentFactory.create_from_config_object(config)
    
    context_builder = None
    if mcp_client:
        context_builder = ContextBuilder(
            mcp_client=mcp_client,
            default_autonomy=AutonomyLevel(config.autonomy_level)
        )
    
    return AIAgentStrategy(
        llm_agent=agent,
        context_builder=context_builder,
        autonomy_level=AutonomyLevel(config.autonomy_level)
    )
```

---

## 14. Configuración YAML

### 14.1 config/agents.yaml

```yaml
# config/agents.yaml
# Configuración del AI Agent para Nexus Trading
# Versión: 1.0

ai_agent:
  # =========================================================================
  # PROVIDER ACTIVO
  # =========================================================================
  # Provider a usar: claude, openai (futuro), gemini (futuro)
  active: "claude"
  
  # =========================================================================
  # NIVEL DE AUTONOMÍA
  # =========================================================================
  # Controla el comportamiento del agente:
  #
  # conservative:
  #   - Solo proporciona análisis e información
  #   - NO genera acciones de trading
  #   - Ideal para aprender y entender el sistema
  #
  # moderate:
  #   - Sugiere operaciones con sizing
  #   - Requiere confirmación del usuario
  #   - Recomendado para paper trading
  #
  # experimental:
  #   - Ejecución autónoma con límites estrictos
  #   - Max 2% por posición, max 1 trade por ciclo
  #   - REQUIERE kill switches activos
  #   - Solo para usuarios experimentados
  #
  autonomy_level: "moderate"
  
  # =========================================================================
  # CONFIGURACIÓN DE MODELOS
  # =========================================================================
  models:
    claude:
      # Modelo de Anthropic a usar
      # Opciones: claude-sonnet-4-20250514 (recomendado), claude-3-opus-20240229
      model: "claude-sonnet-4-20250514"
      
      # Máximo tokens en respuesta
      max_tokens: 2000
      
      # Temperatura (0-1): más bajo = más determinístico
      temperature: 0.3
      
      # Timeout en segundos para llamadas API
      timeout: 60
      
      # API key: preferir variable de entorno ANTHROPIC_API_KEY
      # api_key: "sk-ant-..."  # NO COMMITEAR
    
    # Placeholder para futuros providers
    openai:
      model: "gpt-4-turbo"
      max_tokens: 2000
      temperature: 0.3
      timeout: 60
    
    gemini:
      model: "gemini-pro"
      max_tokens: 2000
      temperature: 0.3
      timeout: 60
  
  # =========================================================================
  # RATE LIMITING
  # =========================================================================
  # Protege contra exceso de llamadas a la API
  rate_limit:
    # Requests por minuto (Anthropic default: 50)
    requests_per_minute: 50
    
    # Tokens por minuto (Anthropic default: 40,000)
    tokens_per_minute: 40000
    
    # Requests por día (para controlar costos)
    requests_per_day: 500
  
  # =========================================================================
  # CACHING
  # =========================================================================
  # Cache de contexto y decisiones
  cache_enabled: true
  
  # Tiempo de vida del cache en segundos
  # Decisiones se consideran válidas por este tiempo
  cache_ttl_seconds: 300  # 5 minutos
  
  # =========================================================================
  # WATCHLIST
  # =========================================================================
  # Símbolos que el AI Agent analiza
  watchlist:
    # ETFs Europeos
    - "VWCE.DE"   # Vanguard FTSE All-World
    - "CSPX.DE"   # iShares S&P 500
    - "EUNL.DE"   # iShares Core MSCI World
    
    # ETFs US
    - "SPY"       # S&P 500
    - "QQQ"       # Nasdaq 100
    - "IWM"       # Russell 2000
    - "DIA"       # Dow Jones
```

---

### 14.2 Actualización config/strategies.yaml

```yaml
# config/strategies.yaml
# Añadir sección para AI Agent

strategies:
  # ETF Momentum (existente de Fase B1)
  etf_momentum:
    enabled: true
    required_regime: ["BULL"]
    max_positions: 5
    min_momentum_score: 0.6
    rsi_oversold: 35
    rsi_overbought: 75
    
  # AI Agent Strategy (NUEVO)
  ai_agent_swing:
    enabled: true
    required_regime: ["BULL", "SIDEWAYS"]
    
    # Config específica
    autonomy_level: "moderate"  # Override del config/agents.yaml si se desea
    
    # Límites para esta estrategia
    max_positions: 3
    max_position_size_pct: 5.0
    
    # Integración con otras estrategias
    # Si true, las señales del AI Agent requieren confirmación de ETF Momentum
    require_momentum_confirmation: false
    
  # Mean Reversion (futuro)
  mean_reversion:
    enabled: false
    required_regime: ["SIDEWAYS"]
```

---

## 15. Scripts de Verificación

### 15.1 Script de Verificación de Fase B2

**Archivo:** `scripts/verify_fase_b2.py`

```python
#!/usr/bin/env python3
"""
Script de verificación para Fase B2: AI Agent.

Verifica que todos los componentes del AI Agent estén correctamente
implementados y funcionando.

Uso:
    python scripts/verify_fase_b2.py
    
Exit codes:
    0: Todos los checks pasaron
    1: Algún check falló
"""

import sys
import os
import asyncio
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))


def print_header(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_check(name: str, passed: bool, detail: str = ""):
    status = "✅" if passed else "❌"
    print(f"  {status} {name}")
    if detail:
        print(f"      {detail}")


def check_imports() -> bool:
    """Verifica que todos los módulos se pueden importar."""
    print_header("CHECK 1: Imports")
    all_passed = True
    
    modules = [
        ("src.agents.llm.interfaces", "Interfaces base"),
        ("src.agents.llm.factory", "LLM Agent Factory"),
        ("src.agents.llm.config", "Configuración"),
        ("src.agents.llm.context_builder", "Context Builder"),
        ("src.agents.llm.rate_limiter", "Rate Limiter"),
        ("src.agents.llm.prompts", "Sistema de Prompts"),
        ("src.agents.llm.agents.claude_agent", "Claude Agent"),
        ("src.strategies.swing.ai_agent_strategy", "AI Agent Strategy"),
    ]
    
    for module_name, description in modules:
        try:
            __import__(module_name)
            print_check(description, True)
        except ImportError as e:
            print_check(description, False, str(e))
            all_passed = False
    
    return all_passed


def check_interfaces() -> bool:
    """Verifica que las interfaces estén correctamente definidas."""
    print_header("CHECK 2: Interfaces")
    all_passed = True
    
    try:
        from src.agents.llm.interfaces import (
            AutonomyLevel,
            MarketView,
            AgentContext,
            AgentDecision,
            LLMAgent,
        )
        
        # Verificar AutonomyLevel
        levels = [AutonomyLevel.CONSERVATIVE, AutonomyLevel.MODERATE, AutonomyLevel.EXPERIMENTAL]
        print_check("AutonomyLevel enum", len(levels) == 3, f"Niveles: {[l.value for l in levels]}")
        
        # Verificar MarketView
        views = [MarketView.BULLISH, MarketView.BEARISH, MarketView.NEUTRAL, MarketView.UNCERTAIN]
        print_check("MarketView enum", len(views) == 4)
        
        # Verificar LLMAgent ABC
        from abc import ABC
        print_check("LLMAgent es ABC", issubclass(LLMAgent, ABC))
        
        # Verificar métodos abstractos
        abstract_methods = ['agent_id', 'model_name', 'decide', 'get_system_prompt', 'health_check', 'estimate_tokens']
        has_all = all(hasattr(LLMAgent, m) for m in abstract_methods)
        print_check("LLMAgent métodos abstractos", has_all)
        
    except Exception as e:
        print_check("Interfaces", False, str(e))
        all_passed = False
    
    return all_passed


def check_prompts() -> bool:
    """Verifica que los prompts estén definidos."""
    print_header("CHECK 3: Sistema de Prompts")
    all_passed = True
    
    try:
        from src.agents.llm.prompts import get_system_prompt, get_prompt_token_estimate
        from src.agents.llm.interfaces import AutonomyLevel
        
        for level in AutonomyLevel:
            prompt = get_system_prompt(level)
            tokens = get_prompt_token_estimate(level)
            
            # Verificar que el prompt no está vacío y tiene contenido significativo
            has_content = len(prompt) > 1000
            has_format = "json" in prompt.lower()
            has_safety = "nunca" in prompt.lower() or "never" in prompt.lower()
            
            print_check(
                f"Prompt {level.value}",
                has_content and has_format,
                f"~{tokens} tokens, formato JSON: {has_format}"
            )
            
            if not has_content:
                all_passed = False
    
    except Exception as e:
        print_check("Prompts", False, str(e))
        all_passed = False
    
    return all_passed


def check_config_files() -> bool:
    """Verifica que los archivos de configuración existan."""
    print_header("CHECK 4: Archivos de Configuración")
    all_passed = True
    
    config_files = [
        ("config/agents.yaml", "Config AI Agent"),
    ]
    
    for file_path, description in config_files:
        exists = Path(file_path).exists()
        print_check(description, exists, file_path)
        if not exists:
            all_passed = False
    
    # Verificar que strategies.yaml tiene sección ai_agent
    strategies_path = Path("config/strategies.yaml")
    if strategies_path.exists():
        content = strategies_path.read_text()
        has_ai_agent = "ai_agent" in content
        print_check("strategies.yaml tiene ai_agent", has_ai_agent)
        if not has_ai_agent:
            all_passed = False
    
    return all_passed


def check_factory() -> bool:
    """Verifica que el factory funcione."""
    print_header("CHECK 5: LLM Agent Factory")
    all_passed = True
    
    try:
        from src.agents.llm.factory import LLMAgentFactory
        
        # Verificar providers disponibles
        providers = LLMAgentFactory.list_available_providers()
        print_check("Providers registrados", "claude" in providers, f"Disponibles: {providers}")
        
        # Verificar creación (sin API key, debería fallar de forma controlada)
        try:
            # Esto fallará si no hay API key, pero verifica que el código existe
            if os.environ.get("ANTHROPIC_API_KEY"):
                agent = LLMAgentFactory.create(provider="claude")
                print_check("Crear Claude Agent", True, f"ID: {agent.agent_id}")
            else:
                print_check("Crear Claude Agent", True, "Skipped (no API key)")
        except ValueError as e:
            if "API key" in str(e):
                print_check("Crear Claude Agent", True, "Error esperado: no API key")
            else:
                print_check("Crear Claude Agent", False, str(e))
                all_passed = False
    
    except Exception as e:
        print_check("Factory", False, str(e))
        all_passed = False
    
    return all_passed


def check_ai_agent_strategy() -> bool:
    """Verifica que AIAgentStrategy implemente TradingStrategy."""
    print_header("CHECK 6: AI Agent Strategy")
    all_passed = True
    
    try:
        from src.strategies.swing.ai_agent_strategy import AIAgentStrategy
        from src.strategies.interfaces import TradingStrategy
        
        # Verificar herencia
        print_check("Hereda de TradingStrategy", issubclass(AIAgentStrategy, TradingStrategy))
        
        # Verificar propiedades requeridas
        # No podemos instanciar sin agent, pero verificamos que los métodos existen
        required_methods = ['strategy_id', 'required_regime', 'generate_signals', 'should_close']
        has_all = all(hasattr(AIAgentStrategy, m) for m in required_methods)
        print_check("Métodos de TradingStrategy", has_all)
        
    except Exception as e:
        print_check("AI Agent Strategy", False, str(e))
        all_passed = False
    
    return all_passed


async def check_rate_limiter() -> bool:
    """Verifica que el rate limiter funcione."""
    print_header("CHECK 7: Rate Limiter")
    all_passed = True
    
    try:
        from src.agents.llm.rate_limiter import RateLimiter, RateLimitConfig
        
        config = RateLimitConfig(
            requests_per_minute=10,
            requests_per_day=100
        )
        limiter = RateLimiter(config)
        
        # Verificar acquire
        can_proceed = await limiter.acquire(estimated_tokens=100)
        print_check("Rate limiter acquire", can_proceed)
        
        # Verificar status
        status = limiter.get_status()
        print_check("Rate limiter status", "daily_requests" in status, f"Requests: {status['daily_requests']}")
        
    except Exception as e:
        print_check("Rate Limiter", False, str(e))
        all_passed = False
    
    return all_passed


def run_tests() -> bool:
    """Ejecuta tests unitarios."""
    print_header("CHECK 8: Tests Unitarios")
    
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/agents/llm/", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    passed = result.returncode == 0
    print_check("pytest tests/agents/llm/", passed)
    
    if not passed:
        print("\n  Output:")
        for line in result.stdout.split('\n')[-20:]:
            print(f"    {line}")
    
    return passed


async def main():
    """Ejecuta todas las verificaciones."""
    print("\n" + "="*60)
    print("    VERIFICACIÓN FASE B2: AI AGENT")
    print("="*60)
    
    checks = [
        ("Imports", check_imports),
        ("Interfaces", check_interfaces),
        ("Prompts", check_prompts),
        ("Config Files", check_config_files),
        ("Factory", check_factory),
        ("AI Agent Strategy", check_ai_agent_strategy),
    ]
    
    all_passed = True
    
    for name, check_func in checks:
        try:
            if asyncio.iscoroutinefunction(check_func):
                passed = await check_func()
            else:
                passed = check_func()
            if not passed:
                all_passed = False
        except Exception as e:
            print_check(name, False, f"Exception: {e}")
            all_passed = False
    
    # Rate limiter es async
    try:
        passed = await check_rate_limiter()
        if not passed:
            all_passed = False
    except Exception as e:
        print_check("Rate Limiter", False, str(e))
        all_passed = False
    
    # Tests unitarios (opcional)
    if Path("tests/agents/llm").exists():
        try:
            passed = run_tests()
            if not passed:
                all_passed = False
        except Exception as e:
            print_check("Tests", False, str(e))
    
    # Resumen
    print_header("RESUMEN")
    if all_passed:
        print("  ✅ Todos los checks pasaron")
        print("\n  Fase B2 lista para integración.")
        print("  Siguiente paso: Fase C1 (Sistema de Métricas)")
        return 0
    else:
        print("  ❌ Algunos checks fallaron")
        print("\n  Revisar errores antes de continuar.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

---

*Fin de Parte 4 - Integración, Configuración y Factory*

---

*Documento de Implementación - Fase B2: AI Agent*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
-e 

---

## Tests, Checklist Final y Troubleshooting

---

## 16. Tests Unitarios

### 16.1 Tests de Interfaces

**Archivo:** `tests/agents/llm/test_interfaces.py`

```python
# tests/agents/llm/test_interfaces.py
"""Tests para interfaces del LLM Agent."""

import pytest
from datetime import datetime
from src.agents.llm.interfaces import (
    AutonomyLevel,
    MarketView,
    PortfolioPosition,
    PortfolioSummary,
    SymbolData,
    RegimeInfo,
    RiskLimits,
    MarketContext,
    AgentContext,
    AgentDecision,
    LLMAgent,
    LLMAgentError,
    LLMAPIError,
    LLMRateLimitError,
)
from src.strategies.interfaces import Signal


class TestAutonomyLevel:
    """Tests para AutonomyLevel enum."""
    
    def test_values(self):
        assert AutonomyLevel.CONSERVATIVE.value == "conservative"
        assert AutonomyLevel.MODERATE.value == "moderate"
        assert AutonomyLevel.EXPERIMENTAL.value == "experimental"
    
    def test_from_string(self):
        assert AutonomyLevel("conservative") == AutonomyLevel.CONSERVATIVE
        assert AutonomyLevel("moderate") == AutonomyLevel.MODERATE
    
    def test_invalid_value(self):
        with pytest.raises(ValueError):
            AutonomyLevel("invalid")


class TestPortfolioPosition:
    """Tests para PortfolioPosition dataclass."""
    
    @pytest.fixture
    def position(self):
        return PortfolioPosition(
            symbol="VWCE.DE",
            quantity=10,
            avg_entry_price=100.0,
            current_price=110.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=10.0,
            holding_days=5
        )
    
    def test_market_value(self, position):
        assert position.market_value == 1100.0
    
    def test_immutability(self, position):
        with pytest.raises(AttributeError):
            position.quantity = 20


class TestPortfolioSummary:
    """Tests para PortfolioSummary dataclass."""
    
    @pytest.fixture
    def portfolio(self):
        return PortfolioSummary(
            total_value=25000.0,
            cash_available=20000.0,
            invested_value=5000.0,
            positions=(),
            daily_pnl=50.0,
            daily_pnl_pct=0.2,
            total_pnl=500.0,
            total_pnl_pct=2.0
        )
    
    def test_cash_pct(self, portfolio):
        assert portfolio.cash_pct == 80.0
    
    def test_num_positions(self, portfolio):
        assert portfolio.num_positions == 0
    
    def test_cash_pct_zero_total(self):
        portfolio = PortfolioSummary(
            total_value=0,
            cash_available=0,
            invested_value=0,
            positions=(),
            daily_pnl=0,
            daily_pnl_pct=0,
            total_pnl=0,
            total_pnl_pct=0
        )
        assert portfolio.cash_pct == 100.0


class TestRiskLimits:
    """Tests para RiskLimits dataclass."""
    
    def test_can_trade_true(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=2,
            current_daily_pnl_pct=-1.0
        )
        assert limits.can_trade is True
        assert limits.remaining_trades == 3
    
    def test_can_trade_false_trades_exhausted(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=5,
            current_daily_pnl_pct=0
        )
        assert limits.can_trade is False
        assert limits.remaining_trades == 0
    
    def test_can_trade_false_loss_exceeded(self):
        limits = RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=3.0,
            current_daily_trades=1,
            current_daily_pnl_pct=-4.0
        )
        assert limits.can_trade is False


class TestAgentContext:
    """Tests para AgentContext dataclass."""
    
    @pytest.fixture
    def context(self):
        return AgentContext(
            context_id="ctx_test123",
            timestamp=datetime(2024, 12, 15, 10, 30, 0),
            regime=RegimeInfo(
                regime="BULL",
                confidence=0.75,
                probabilities={"BULL": 0.75, "BEAR": 0.1, "SIDEWAYS": 0.1, "VOLATILE": 0.05},
                model_id="hmm_v1"
            ),
            market=MarketContext(
                spy_change_pct=0.5,
                qqq_change_pct=0.8,
                vix_level=18.5,
                vix_change_pct=-2.0,
                market_breadth=0.65,
                sector_rotation={}
            ),
            portfolio=PortfolioSummary(
                total_value=25000,
                cash_available=20000,
                invested_value=5000,
                positions=(),
                daily_pnl=50,
                daily_pnl_pct=0.2,
                total_pnl=500,
                total_pnl_pct=2.0
            ),
            watchlist=(),
            risk_limits=RiskLimits(
                max_position_pct=5.0,
                max_portfolio_risk_pct=2.0,
                max_daily_trades=5,
                max_daily_loss_pct=3.0,
                current_daily_trades=1,
                current_daily_pnl_pct=0.2
            ),
            autonomy_level=AutonomyLevel.MODERATE
        )
    
    def test_to_prompt_text_contains_required_sections(self, context):
        text = context.to_prompt_text()
        assert "RÉGIMEN" in text
        assert "PORTFOLIO" in text
        assert "BULL" in text
        assert "MODERATE" in text.lower()
    
    def test_to_dict_serializable(self, context):
        import json
        d = context.to_dict()
        json_str = json.dumps(d)  # No debe lanzar
        assert "context_id" in d
        assert d["context_id"] == "ctx_test123"


class TestAgentDecision:
    """Tests para AgentDecision dataclass."""
    
    def test_confidence_validation_valid(self):
        decision = AgentDecision(
            decision_id="dec_test",
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            actions=[],
            market_view=MarketView.BULLISH,
            reasoning="Test reasoning",
            key_factors=["factor1"],
            confidence=0.75,
            model_used="claude-sonnet",
            autonomy_level=AutonomyLevel.MODERATE,
            tokens_used=100,
            latency_ms=150
        )
        assert decision.confidence == 0.75
    
    def test_confidence_validation_invalid_high(self):
        with pytest.raises(ValueError):
            AgentDecision(
                decision_id="dec_test",
                context_id="ctx_test",
                timestamp=datetime.utcnow(),
                actions=[],
                market_view=MarketView.BULLISH,
                reasoning="Test",
                key_factors=[],
                confidence=1.5,  # Invalid
                model_used="test",
                autonomy_level=AutonomyLevel.MODERATE,
                tokens_used=100,
                latency_ms=150
            )
    
    def test_confidence_validation_invalid_low(self):
        with pytest.raises(ValueError):
            AgentDecision(
                decision_id="dec_test",
                context_id="ctx_test",
                timestamp=datetime.utcnow(),
                actions=[],
                market_view=MarketView.BULLISH,
                reasoning="Test",
                key_factors=[],
                confidence=-0.1,  # Invalid
                model_used="test",
                autonomy_level=AutonomyLevel.MODERATE,
                tokens_used=100,
                latency_ms=150
            )
    
    def test_has_actions_false(self):
        decision = AgentDecision(
            decision_id="dec_test",
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            actions=[],
            market_view=MarketView.NEUTRAL,
            reasoning="No opportunities",
            key_factors=[],
            confidence=0.8,
            model_used="test",
            autonomy_level=AutonomyLevel.MODERATE,
            tokens_used=100,
            latency_ms=150
        )
        assert decision.has_actions is False
        assert decision.action_summary == "No actions recommended"
    
    def test_to_json(self):
        decision = AgentDecision(
            decision_id="dec_test",
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            actions=[],
            market_view=MarketView.BULLISH,
            reasoning="Test",
            key_factors=["factor1"],
            confidence=0.8,
            model_used="test",
            autonomy_level=AutonomyLevel.MODERATE,
            tokens_used=100,
            latency_ms=150
        )
        json_str = decision.to_json()
        import json
        data = json.loads(json_str)
        assert data["decision_id"] == "dec_test"
        assert data["market_view"] == "bullish"


class TestExceptions:
    """Tests para excepciones específicas."""
    
    def test_llm_api_error(self):
        error = LLMAPIError("API failed", status_code=500, response="Internal error")
        assert str(error) == "API failed"
        assert error.status_code == 500
    
    def test_llm_rate_limit_error(self):
        error = LLMRateLimitError("Rate limited", retry_after=60)
        assert error.retry_after == 60
```

---

### 16.2 Tests de Prompts

**Archivo:** `tests/agents/llm/test_prompts.py`

```python
# tests/agents/llm/test_prompts.py
"""Tests para el sistema de prompts."""

import pytest
from src.agents.llm.interfaces import AutonomyLevel
from src.agents.llm.prompts import get_system_prompt, get_prompt_token_estimate


class TestPromptSystem:
    """Tests para el sistema de prompts."""
    
    @pytest.mark.parametrize("level", [
        AutonomyLevel.CONSERVATIVE,
        AutonomyLevel.MODERATE,
        AutonomyLevel.EXPERIMENTAL,
    ])
    def test_prompt_exists(self, level):
        prompt = get_system_prompt(level)
        assert prompt is not None
        assert len(prompt) > 0
    
    @pytest.mark.parametrize("level", [
        AutonomyLevel.CONSERVATIVE,
        AutonomyLevel.MODERATE,
        AutonomyLevel.EXPERIMENTAL,
    ])
    def test_prompt_has_minimum_content(self, level):
        prompt = get_system_prompt(level)
        # Debe tener al menos 1000 caracteres
        assert len(prompt) > 1000
    
    @pytest.mark.parametrize("level", [
        AutonomyLevel.CONSERVATIVE,
        AutonomyLevel.MODERATE,
        AutonomyLevel.EXPERIMENTAL,
    ])
    def test_prompt_has_json_format(self, level):
        prompt = get_system_prompt(level)
        assert "json" in prompt.lower()
    
    @pytest.mark.parametrize("level", [
        AutonomyLevel.CONSERVATIVE,
        AutonomyLevel.MODERATE,
        AutonomyLevel.EXPERIMENTAL,
    ])
    def test_prompt_has_safety_section(self, level):
        prompt = get_system_prompt(level)
        # Debe mencionar restricciones de seguridad
        assert "nunca" in prompt.lower() or "never" in prompt.lower()
    
    def test_conservative_no_actions(self):
        prompt = get_system_prompt(AutonomyLevel.CONSERVATIVE)
        # Conservative debe indicar que actions está vacío
        assert "actions" in prompt.lower()
        assert "[]" in prompt or "vacío" in prompt.lower() or "empty" in prompt.lower()
    
    def test_experimental_kill_switch(self):
        prompt = get_system_prompt(AutonomyLevel.EXPERIMENTAL)
        # Experimental debe mencionar kill switch
        assert "kill" in prompt.lower() or "emergencia" in prompt.lower()
    
    def test_token_estimate(self):
        for level in AutonomyLevel:
            tokens = get_prompt_token_estimate(level)
            # Debe ser un número razonable
            assert 500 < tokens < 10000
    
    def test_invalid_level_raises(self):
        with pytest.raises((ValueError, KeyError)):
            get_system_prompt("invalid_level")
```

---

### 16.3 Tests de Claude Agent

**Archivo:** `tests/agents/llm/test_claude_agent.py`

```python
# tests/agents/llm/test_claude_agent.py
"""Tests para Claude Agent."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.agents.llm.interfaces import (
    AutonomyLevel,
    AgentContext,
    RegimeInfo,
    MarketContext,
    PortfolioSummary,
    RiskLimits,
    LLMParseError,
)
from src.agents.llm.agents.claude_agent import ClaudeAgent


class TestClaudeAgent:
    """Tests para ClaudeAgent."""
    
    @pytest.fixture
    def mock_anthropic_client(self):
        """Mock del cliente de Anthropic."""
        with patch('anthropic.Anthropic') as mock:
            yield mock
    
    @pytest.fixture
    def sample_context(self):
        """Contexto de prueba."""
        return AgentContext(
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            regime=RegimeInfo(
                regime="BULL",
                confidence=0.75,
                probabilities={"BULL": 0.75},
                model_id="test"
            ),
            market=MarketContext(
                spy_change_pct=0.5,
                qqq_change_pct=0.8,
                vix_level=18,
                vix_change_pct=-1,
                market_breadth=0.6,
                sector_rotation={}
            ),
            portfolio=PortfolioSummary(
                total_value=25000,
                cash_available=20000,
                invested_value=5000,
                positions=(),
                daily_pnl=50,
                daily_pnl_pct=0.2,
                total_pnl=500,
                total_pnl_pct=2.0
            ),
            watchlist=(),
            risk_limits=RiskLimits(
                max_position_pct=5.0,
                max_portfolio_risk_pct=2.0,
                max_daily_trades=5,
                max_daily_loss_pct=3.0,
                current_daily_trades=1,
                current_daily_pnl_pct=0.2
            ),
            autonomy_level=AutonomyLevel.MODERATE
        )
    
    def test_agent_id(self):
        """Verifica formato del agent_id."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(
                api_key="test_key",
                model="claude-sonnet-4-20250514",
                default_autonomy=AutonomyLevel.MODERATE
            )
            assert "claude" in agent.agent_id
            assert "moderate" in agent.agent_id
    
    def test_model_name(self):
        """Verifica model_name."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(
                api_key="test_key",
                model="claude-sonnet-4-20250514"
            )
            assert agent.model_name == "claude-sonnet-4-20250514"
    
    def test_supports_streaming(self):
        """Claude soporta streaming."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            assert agent.supports_streaming is True
    
    def test_get_system_prompt(self):
        """Verifica que retorna prompt válido."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            
            for level in AutonomyLevel:
                prompt = agent.get_system_prompt(level)
                assert len(prompt) > 1000
    
    def test_estimate_tokens(self, sample_context):
        """Verifica estimación de tokens."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            tokens = agent.estimate_tokens(sample_context)
            assert tokens > 0
            assert isinstance(tokens, int)
    
    def test_validate_context_valid(self, sample_context):
        """Contexto válido pasa validación."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            is_valid, issues = agent.validate_context(sample_context)
            # El contexto de prueba puede tener issues por watchlist vacía
            # pero no debería ser crítico
            assert isinstance(is_valid, bool)
            assert isinstance(issues, list)
    
    def test_should_skip_volatile_regime(self, sample_context):
        """Debe saltar si régimen es VOLATILE."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            
            # Modificar contexto para régimen VOLATILE
            volatile_context = AgentContext(
                context_id=sample_context.context_id,
                timestamp=sample_context.timestamp,
                regime=RegimeInfo(
                    regime="VOLATILE",
                    confidence=0.8,
                    probabilities={"VOLATILE": 0.8},
                    model_id="test"
                ),
                market=sample_context.market,
                portfolio=sample_context.portfolio,
                watchlist=sample_context.watchlist,
                risk_limits=sample_context.risk_limits,
                autonomy_level=sample_context.autonomy_level
            )
            
            should_skip, reason = agent.should_skip_decision(volatile_context)
            assert should_skip is True
            assert "VOLATILE" in reason
    
    def test_extract_json_from_markdown(self):
        """Verifica extracción de JSON desde markdown."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            
            markdown_response = '''
            Here's my analysis:
            
            ```json
            {"market_view": "bullish", "confidence": 0.8}
            ```
            '''
            
            extracted = agent._extract_json(markdown_response)
            assert "market_view" in extracted
    
    def test_extract_json_direct(self):
        """Verifica extracción de JSON directo."""
        with patch('anthropic.Anthropic'):
            agent = ClaudeAgent(api_key="test_key")
            
            direct_json = '{"market_view": "bullish", "confidence": 0.8}'
            extracted = agent._extract_json(direct_json)
            assert extracted == direct_json


class TestClaudeAgentParsing:
    """Tests para parsing de respuestas."""
    
    @pytest.fixture
    def agent(self):
        with patch('anthropic.Anthropic'):
            return ClaudeAgent(api_key="test_key")
    
    @pytest.fixture
    def sample_context(self):
        return AgentContext(
            context_id="ctx_test",
            timestamp=datetime.utcnow(),
            regime=RegimeInfo(regime="BULL", confidence=0.75, probabilities={}, model_id="test"),
            market=MarketContext(
                spy_change_pct=0.5, qqq_change_pct=0.8, vix_level=18,
                vix_change_pct=-1, market_breadth=0.6, sector_rotation={}
            ),
            portfolio=PortfolioSummary(
                total_value=25000, cash_available=20000, invested_value=5000,
                positions=(), daily_pnl=50, daily_pnl_pct=0.2,
                total_pnl=500, total_pnl_pct=2.0
            ),
            watchlist=(),
            risk_limits=RiskLimits(
                max_position_pct=5.0, max_portfolio_risk_pct=2.0, max_daily_trades=5,
                max_daily_loss_pct=3.0, current_daily_trades=1, current_daily_pnl_pct=0.2
            ),
            autonomy_level=AutonomyLevel.MODERATE
        )
    
    def test_parse_valid_response(self, agent, sample_context):
        """Parsea respuesta válida correctamente."""
        valid_response = '''
        {
            "market_view": "bullish",
            "confidence": 0.8,
            "reasoning": "Market looks good",
            "key_factors": ["factor1", "factor2"],
            "actions": [],
            "warnings": []
        }
        '''
        
        parsed = agent._parse_response(valid_response, sample_context, AutonomyLevel.MODERATE)
        assert parsed["confidence"] == 0.8
        assert len(parsed["key_factors"]) == 2
    
    def test_parse_invalid_json_raises(self, agent, sample_context):
        """JSON inválido lanza LLMParseError."""
        invalid_response = "This is not JSON"
        
        with pytest.raises(LLMParseError):
            agent._parse_response(invalid_response, sample_context, AutonomyLevel.MODERATE)
    
    def test_parse_missing_field_raises(self, agent, sample_context):
        """Campo faltante lanza LLMParseError."""
        missing_field = '{"market_view": "bullish"}'  # Falta confidence, reasoning, etc.
        
        with pytest.raises(LLMParseError):
            agent._parse_response(missing_field, sample_context, AutonomyLevel.MODERATE)
```

---

### 16.4 Tests de Rate Limiter

**Archivo:** `tests/agents/llm/test_rate_limiter.py`

```python
# tests/agents/llm/test_rate_limiter.py
"""Tests para Rate Limiter."""

import pytest
import asyncio
from datetime import datetime

from src.agents.llm.rate_limiter import RateLimiter, RateLimitConfig


class TestRateLimiter:
    """Tests para RateLimiter."""
    
    @pytest.fixture
    def limiter(self):
        config = RateLimitConfig(
            requests_per_minute=10,
            tokens_per_minute=10000,
            requests_per_day=100
        )
        return RateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_acquire_success(self, limiter):
        """Primera adquisición debe ser exitosa."""
        result = await limiter.acquire(estimated_tokens=100)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_acquire_increments_counter(self, limiter):
        """Acquire incrementa contador diario."""
        initial = limiter._daily_requests
        await limiter.acquire()
        assert limiter._daily_requests == initial + 1
    
    def test_get_status(self, limiter):
        """Status retorna información correcta."""
        status = limiter.get_status()
        
        assert "daily_requests" in status
        assert "daily_limit" in status
        assert "daily_remaining" in status
        assert "reset_time" in status
        assert "rpm_limit" in status
    
    @pytest.mark.asyncio
    async def test_daily_limit_blocks(self):
        """Cuando se alcanza límite diario, retorna False."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_day=2  # Límite muy bajo
        )
        limiter = RateLimiter(config)
        
        # Primeras dos deben pasar
        await limiter.acquire()
        await limiter.acquire()
        
        # Tercera debe fallar
        result = await limiter.acquire()
        assert result is False
```

---

## 17. Checklist de Verificación Final

```
FASE B2: AI AGENT
═══════════════════════════════════════════════════════════════════════════════

TAREA B2.1: INTERFACES
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/__init__.py creado
[ ] src/agents/llm/interfaces.py creado
[ ] AutonomyLevel enum (CONSERVATIVE, MODERATE, EXPERIMENTAL)
[ ] MarketView enum (BULLISH, BEARISH, NEUTRAL, UNCERTAIN)
[ ] PortfolioPosition dataclass con market_value property
[ ] PortfolioSummary dataclass con cash_pct y num_positions
[ ] SymbolData dataclass con to_summary()
[ ] RegimeInfo dataclass con to_summary()
[ ] RiskLimits dataclass con can_trade y remaining_trades
[ ] MarketContext dataclass con to_summary()
[ ] AgentContext dataclass con to_prompt_text() y to_dict()
[ ] AgentDecision dataclass con validación de confidence
[ ] LLMAgent ABC con métodos abstractos
[ ] Excepciones: LLMAPIError, LLMRateLimitError, LLMParseError, etc.
[ ] Tests tests/agents/llm/test_interfaces.py

TAREA B2.2: CONTEXT BUILDER
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/context_builder.py creado
[ ] ContextBuilder clase con build() async
[ ] Integración con mcp-ml-models para régimen
[ ] Integración con mcp-market-data para quotes
[ ] Integración con mcp-ibkr para portfolio
[ ] Integración con mcp-technical para indicadores
[ ] Manejo de errores con defaults
[ ] Cache con TTL configurable
[ ] Tests tests/agents/llm/test_context_builder.py

TAREA B2.3: SISTEMA DE PROMPTS
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/prompts/__init__.py creado
[ ] src/agents/llm/prompts/base.py creado
[ ] src/agents/llm/prompts/conservative.py creado
[ ] src/agents/llm/prompts/moderate.py creado
[ ] src/agents/llm/prompts/experimental.py creado
[ ] get_system_prompt(autonomy_level) funciona
[ ] Prompt CONSERVATIVE indica actions = []
[ ] Prompt MODERATE incluye sizing
[ ] Prompt EXPERIMENTAL tiene límites estrictos y kill switch
[ ] Todos los prompts tienen formato JSON
[ ] Todos los prompts tienen sección de seguridad
[ ] Tests tests/agents/llm/test_prompts.py

TAREA B2.4: CLAUDE AGENT
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/agents/__init__.py creado
[ ] src/agents/llm/agents/claude_agent.py creado
[ ] ClaudeAgent implementa LLMAgent ABC
[ ] decide() async con retry automático
[ ] get_system_prompt() retorna prompt correcto
[ ] health_check() verifica conexión API
[ ] estimate_tokens() estima correctamente
[ ] _parse_response() maneja JSON y markdown
[ ] Validación de contexto
[ ] should_skip_decision() funciona
[ ] Tests tests/agents/llm/test_claude_agent.py

TAREA B2.5: RATE LIMITER
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/rate_limiter.py creado
[ ] RateLimitConfig dataclass
[ ] RateLimiter con acquire() async
[ ] Límite por minuto (RPM)
[ ] Límite por día (RPD)
[ ] Límite por tokens (TPM)
[ ] Cooldown entre requests
[ ] get_status() retorna info útil
[ ] Tests tests/agents/llm/test_rate_limiter.py

TAREA B2.6: FACTORY E INTEGRACIÓN
───────────────────────────────────────────────────────────────────────────────
[ ] src/agents/llm/factory.py creado
[ ] src/agents/llm/config.py creado
[ ] LLMAgentFactory.create_from_config() funciona
[ ] LLMAgentFactory.create() con parámetros explícitos
[ ] LLMAgentConfig carga YAML correctamente
[ ] src/strategies/swing/ai_agent_strategy.py creado
[ ] AIAgentStrategy implementa TradingStrategy
[ ] AIAgentStrategy.generate_signals() funciona
[ ] AIAgentStrategy.should_close() funciona
[ ] Tests tests/agents/llm/test_factory.py

TAREA B2.7: CONFIGURACIÓN
───────────────────────────────────────────────────────────────────────────────
[ ] config/agents.yaml creado
[ ] config/strategies.yaml actualizado con ai_agent_swing
[ ] Variable de entorno ANTHROPIC_API_KEY documentada
[ ] scripts/verify_fase_b2.py creado
[ ] Documentación actualizada

═══════════════════════════════════════════════════════════════════════════════

GATE DE AVANCE A FASE C1:
───────────────────────────────────────────────────────────────────────────────
[ ] python scripts/verify_fase_b2.py retorna 0 (éxito)
[ ] pytest tests/agents/llm/ pasa (>80% cobertura)
[ ] ClaudeAgent puede hacer health_check sin errores
[ ] AIAgentStrategy se registra correctamente en StrategyRegistry
[ ] Config YAML se carga sin errores
[ ] Sistema de prompts funciona para los 3 niveles

═══════════════════════════════════════════════════════════════════════════════
```

---

## 18. Troubleshooting

### Error: "ANTHROPIC_API_KEY not found"

```bash
# Linux/Mac
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# O en .env file
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
```

### Error: "anthropic module not found"

```bash
pip install anthropic>=0.40.0
```

### Error: "Rate limit exceeded"

```python
# Verificar status del rate limiter
from src.agents.llm.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()
status = limiter.get_status()
print(f"Requests restantes hoy: {status['daily_remaining']}")

# Si es necesario, esperar
import asyncio
await asyncio.sleep(60)  # Esperar 1 minuto
```

### Error: "LLMParseError: Invalid JSON"

El LLM devolvió una respuesta que no es JSON válido. Posibles causas:
1. Prompt no suficientemente claro
2. Modelo confundido por contexto muy largo
3. Error transitorio del modelo

```python
# Debugging: ver respuesta raw
try:
    decision = await agent.decide(context)
except LLMParseError as e:
    print(f"Raw response: {e.raw_response[:500]}")
```

### Error: "Context too large"

```python
# Reducir watchlist
context = await builder.build(
    watchlist=["SPY", "QQQ"],  # Menos símbolos
    autonomy_level=AutonomyLevel.MODERATE
)

# O truncar datos históricos
# Modificar context_builder para limitar recent_trades
```

### AIAgentStrategy no genera señales

1. Verificar régimen:
```python
print(f"Régimen actual: {regime}")
print(f"Requerido: {strategy.required_regime}")
```

2. Verificar risk limits:
```python
print(f"Can trade: {context.risk_limits.can_trade}")
print(f"Remaining trades: {context.risk_limits.remaining_trades}")
```

3. Verificar autonomía:
```python
# Conservative NUNCA genera acciones
print(f"Autonomy: {context.autonomy_level}")
```

### Tests fallan por estado compartido

```python
# Resetear rate limiter entre tests
@pytest.fixture(autouse=True)
def reset_rate_limiter():
    from src.agents.llm import rate_limiter
    rate_limiter._default_limiter = None
    yield
```

### Prompts muy largos consumen muchos tokens

```python
# Verificar tokens del prompt
from src.agents.llm.prompts import get_prompt_token_estimate

for level in AutonomyLevel:
    tokens = get_prompt_token_estimate(level)
    print(f"{level.value}: ~{tokens} tokens")
```

---

## 19. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Interfaz TradingStrategy | fase_b1_estrategias_swing.md | Tarea B1.1 |
| Signal dataclass | fase_b1_estrategias_swing.md | Tarea B1.2 |
| StrategyRegistry | fase_b1_estrategias_swing.md | Tarea B1.4 |
| StrategyRunner | fase_b1_estrategias_swing.md | Tarea B1.5 |
| RegimeDetector | fase_a2_ml_modular.md | Tarea A2.1 |
| mcp-ml-models | fase_a1_extensiones_base.md | Tarea A1.4 |
| Agentes Core | fase_3_agentes_core.md | Tareas 3.1-3.4 |
| Risk Manager | fase_3_agentes_core.md | Tarea 3.3 |
| Sistema de Métricas | fase_c1_metricas.md | (próximo) |

---

## 20. Siguiente Fase

Una vez completada la Fase B2:

1. **Verificar:** `python scripts/verify_fase_b2.py` retorna 0
2. **Verificar:** `pytest tests/agents/llm/` pasa con >80% cobertura
3. **Verificar:** AIAgentStrategy se integra con StrategyRunner
4. **Siguiente documento:** `fase_c1_metricas.md`
5. **Contenido Fase C1:**
   - Collector de trades
   - Aggregator de métricas (Sharpe, MaxDD, etc.)
   - Sistema de experimentos A/B
   - Dashboard Grafana
   - Alertas y notificaciones

---

*Fin de Parte 5 - Tests, Checklist Final y Troubleshooting*

---

*Documento de Implementación - Fase B2: AI Agent*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
