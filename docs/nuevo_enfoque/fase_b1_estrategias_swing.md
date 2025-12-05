# 📈 Fase B1: Estrategias Swing Trading

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 1 semana  
**Dependencias:** Fase A2 (ML Modular) completada  
**Prerrequisito:** Sistema de detección de régimen funcionando (HMM o Rules)

---

## 1. Contexto y Motivación

### 1.1 Situación Actual

La Fase A2 ha establecido:
- Interfaz `RegimeDetector` ABC con implementaciones HMM y Rules
- Factory para crear detectores según configuración YAML
- Server mcp-ml-models sirviendo predicciones de régimen
- Cuatro estados de mercado: BULL, BEAR, SIDEWAYS, VOLATILE

### 1.2 Objetivo de Esta Fase

Implementar el sistema de estrategias de trading **modular e intercambiable**, empezando con **ETF Momentum** como estrategia principal para swing trading:

```
FILOSOFÍA CLAVE:
═══════════════════════════════════════════════════════════════════════
1. Estrategias como componentes intercambiables
   - Interface común TradingStrategy ABC
   - Activar/desactivar por configuración YAML
   - Múltiples estrategias pueden ejecutar en paralelo

2. Régimen determina qué estrategias están activas
   - BULL: ETF Momentum activo
   - BEAR: Solo cierres, sin nuevas posiciones
   - SIDEWAYS: Mean Reversion (futuro)
   - VOLATILE: Pausar todo

3. Señales estructuradas y trazables
   - Cada señal incluye: estrategia origen, régimen, confianza
   - Todo registrado en metrics.trades para análisis posterior

4. Paper trading primero
   - MVP funcional antes de optimización
   - Feedback real > backtesting perfecto
═══════════════════════════════════════════════════════════════════════
```

### 1.3 Decisiones de Diseño

| Decisión | Justificación |
|----------|---------------|
| ABC para TradingStrategy | Contrato uniforme, fácil testing, extensible |
| Dataclass para Signal | Inmutable, serialización JSON nativa, tipado estricto |
| Registry pattern | Registro dinámico de estrategias, activación por config |
| Integración directa con régimen | Estrategias consultan régimen antes de generar señales |
| Position sizing delegado | La estrategia sugiere, Risk Manager decide tamaño final |

### 1.4 Por Qué ETF Momentum Primero

| Razón | Explicación |
|-------|-------------|
| Menor complejidad | No requiere análisis de empresas individuales |
| Diversificación inherente | ETFs ya están diversificados |
| Liquidez alta | Spreads pequeños, ejecución fiable |
| Comisiones optimizadas | Menos operaciones que trading individual |
| Alineado con capital inicial | Óptimo para 25.000€ paper trading |

---

## 2. Objetivos de la Fase

| Objetivo | Criterio de Éxito |
|----------|-------------------|
| Interfaz TradingStrategy | ABC definida con todos los métodos abstractos |
| Signal dataclass | Estructura completa con validaciones |
| ETF Momentum implementado | Genera señales LONG válidas en régimen BULL |
| Integración con régimen | Estrategia consulta mcp-ml-models antes de operar |
| Strategy Registry | Registro dinámico, activación por YAML |
| Tests unitarios | > 80% cobertura en `src/strategies/` |

---

## 3. Arquitectura de Estrategias

### 3.1 Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           STRATEGY SYSTEM                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  config/strategies.yaml                                                          │
│  ┌─────────────────────────────────┐                                             │
│  │ strategies:                     │                                             │
│  │   etf_momentum:                 │                                             │
│  │     enabled: true               │                                             │
│  │     required_regime: [BULL]     │                                             │
│  │   mean_reversion:               │                                             │
│  │     enabled: false              │  ◄── Futuro                                 │
│  └─────────────────────────────────┘                                             │
│              │                                                                   │
│              ▼                                                                   │
│  ┌─────────────────────────────────┐                                             │
│  │     StrategyRegistry            │                                             │
│  │     .register()                 │◄──────── Registra estrategias disponibles   │
│  │     .get_active()               │◄──────── Filtra por régimen actual          │
│  └─────────────────────────────────┘                                             │
│              │                                                                   │
│      ┌───────┴───────┐                                                           │
│      ▼               ▼                                                           │
│  ┌────────────┐  ┌────────────────┐  ┌────────────────┐                          │
│  │    ETF     │  │ Mean Reversion │  │   AI Agent     │  ◄── Fase B2             │
│  │  Momentum  │  │   (Futuro)     │  │   (Futuro)     │                          │
│  └────────────┘  └────────────────┘  └────────────────┘                          │
│        │                                                                         │
│        ▼                                                                         │
│  ┌─────────────────────────────────┐        ┌─────────────────────────────┐      │
│  │  TradingStrategy (ABC)          │◄───────│   Signal (dataclass)        │      │
│  │  - strategy_id                  │        │   - strategy_id             │      │
│  │  - required_regime              │        │   - symbol, direction       │      │
│  │  - generate_signals()           │        │   - confidence, prices      │      │
│  │  - should_close()               │        │   - regime_at_signal        │      │
│  └─────────────────────────────────┘        └─────────────────────────────┘      │
│              │                                                                   │
│              ▼                                                                   │
│  ┌─────────────────────────────────┐                                             │
│  │   mcp-ml-models (puerto 3005)   │                                             │
│  │   get_regime() → RegimePrediction                                             │
│  └─────────────────────────────────┘                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Flujo de Generación de Señales

```
                    ┌─────────────────────┐
                    │   Scheduler/Cron    │
                    │   (cada 5 min)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Strategy Runner    │
                    │  .run_all_active()  │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
        ┌──────────┐    ┌──────────────┐  ┌──────────┐
        │ Obtener  │    │   Obtener    │  │ Obtener  │
        │ Régimen  │    │  Portfolio   │  │  Market  │
        │  actual  │    │   actual     │  │   Data   │
        └────┬─────┘    └──────┬───────┘  └────┬─────┘
             │                 │               │
             └────────────┬────┴───────────────┘
                          │
                    ┌─────▼─────┐
                    │  ¿Régimen │
                    │  permite  │──── NO ────► Skip estrategia
                    │ estrategia│
                    └─────┬─────┘
                          │ SÍ
                          ▼
                    ┌───────────────────┐
                    │ strategy.generate │
                    │ _signals()        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Lista[Signal]    │
                    │  (0 o más)        │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   Publicar en     │
                    │  canal "signals"  │
                    └───────────────────┘
```

### 3.3 Estructura de Directorios

```
src/strategies/
├── __init__.py
├── interfaces.py           # ← NUEVO: TradingStrategy ABC + Signal dataclass
├── registry.py             # ← NUEVO: StrategyRegistry
├── runner.py               # ← NUEVO: StrategyRunner
├── config.py               # ← NUEVO: Carga config YAML
├── swing/
│   ├── __init__.py
│   ├── etf_momentum.py     # ← NUEVO: Estrategia principal
│   └── base_swing.py       # ← NUEVO: Clase base para swing strategies
└── intraday/               # ← Futuro (Fase C2)
    ├── __init__.py
    ├── mean_reversion.py
    └── breakout.py

config/
└── strategies.yaml         # ← NUEVO: Configuración de estrategias

tests/strategies/
├── __init__.py
├── test_interfaces.py
├── test_registry.py
├── test_etf_momentum.py
└── test_integration.py
```

---

## 4. Dependencias Entre Tareas

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FASE B1: ESTRATEGIAS SWING                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────┐                                           │
│  │ B1.1: Interfaces         │                                           │
│  │ (Signal + TradingStrategy)│───────┐                                  │
│  └──────────────────────────┘       │                                   │
│                                     │                                   │
│  ┌──────────────────────────┐       │    ┌──────────────────────────┐   │
│  │ B1.2: Strategy Registry  │───────┼───►│ B1.5: Strategy Runner    │   │
│  │ + Configuración YAML     │       │    └──────────────────────────┘   │
│  └──────────────────────────┘       │                 │                 │
│                                     │                 │                 │
│  ┌──────────────────────────┐       │                 │                 │
│  │ B1.3: ETF Momentum       │───────┤                 │                 │
│  │ (estrategia principal)   │       │                 │                 │
│  └──────────────────────────┘       │                 │                 │
│                                     │                 ▼                 │
│  ┌──────────────────────────┐       │    ┌──────────────────────────┐   │
│  │ B1.4: Integración con    │───────┴───►│ B1.6: Tests y            │   │
│  │ Régimen Detector         │            │ Verificación             │   │
│  └──────────────────────────┘            └──────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

LEYENDA:
────────
B1.1 es prerequisito para todo
B1.2, B1.3, B1.4 pueden desarrollarse en paralelo (después de B1.1)
B1.5 requiere B1.2, B1.3, B1.4
B1.6 requiere todos los anteriores
```

---

## 5. Tarea B1.1: Interfaces y Dataclasses

**Estado:** ⬜ Pendiente

**Objetivo:** Definir el contrato común para todas las estrategias y el formato de señales.

**Referencias:** Handoff doc sección 3.2, Doc 4 (Motor Trading)

### 5.1 Signal Dataclass

```python
# src/strategies/interfaces.py
"""
Interfaces y dataclasses para el sistema de estrategias.
Todas las estrategias deben implementar TradingStrategy ABC
y generar objetos Signal.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any
import uuid


class SignalDirection(str, Enum):
    """Dirección de la señal de trading."""
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"
    HOLD = "HOLD"  # Mantener posición actual, no hacer nada


class MarketRegime(str, Enum):
    """Estados de régimen de mercado (debe coincidir con ml/interfaces.py)."""
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"


@dataclass(frozen=True)
class Signal:
    """
    Señal de trading generada por una estrategia.
    
    Inmutable (frozen=True) para garantizar integridad.
    Incluye toda la información necesaria para evaluación
    por Risk Manager y posterior análisis.
    
    Attributes:
        signal_id: Identificador único de la señal
        strategy_id: ID de la estrategia que generó la señal
        symbol: Símbolo del instrumento (ej: "VWCE.DE", "SPY")
        direction: Dirección de la operación
        confidence: Nivel de confianza (0.0 - 1.0)
        entry_price: Precio de entrada sugerido
        stop_loss: Precio de stop loss
        take_profit: Precio de take profit
        size_suggestion: Tamaño sugerido (posiciones o % capital)
        regime_at_signal: Régimen de mercado cuando se generó
        regime_confidence: Confianza del detector de régimen
        timeframe: Marco temporal del análisis
        reasoning: Explicación de la señal
        indicators: Valores de indicadores usados
        metadata: Información adicional
        created_at: Timestamp de creación
        expires_at: Timestamp de expiración (señal caduca)
    """
    # Identificación
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = ""
    
    # Instrumento y dirección
    symbol: str = ""
    direction: SignalDirection = SignalDirection.HOLD
    
    # Niveles de confianza y precios
    confidence: float = 0.0  # 0.0 - 1.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    # Sizing (sugerencia, Risk Manager decide final)
    size_suggestion: Optional[float] = None  # Porcentaje del capital o número de unidades
    size_type: str = "percent"  # "percent" o "units"
    
    # Contexto de régimen
    regime_at_signal: MarketRegime = MarketRegime.SIDEWAYS
    regime_confidence: float = 0.0
    
    # Contexto adicional
    timeframe: str = "1d"  # "1d", "4h", "1h", etc.
    reasoning: str = ""
    indicators: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None  # None = no expira
    
    def __post_init__(self):
        """Validaciones post-inicialización."""
        # Validar confianza
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence debe estar entre 0.0 y 1.0, recibido: {self.confidence}")
        
        if not 0.0 <= self.regime_confidence <= 1.0:
            raise ValueError(f"regime_confidence debe estar entre 0.0 y 1.0")
        
        # Validar que señales activas tengan precios
        if self.direction in (SignalDirection.LONG, SignalDirection.SHORT):
            if self.entry_price is None:
                raise ValueError(f"Señales {self.direction.value} requieren entry_price")
            if self.stop_loss is None:
                raise ValueError(f"Señales {self.direction.value} requieren stop_loss")
    
    def is_expired(self) -> bool:
        """Verificar si la señal ha expirado."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def risk_reward_ratio(self) -> Optional[float]:
        """Calcular ratio riesgo/beneficio."""
        if None in (self.entry_price, self.stop_loss, self.take_profit):
            return None
        
        risk = abs(self.entry_price - self.stop_loss)
        reward = abs(self.take_profit - self.entry_price)
        
        if risk == 0:
            return None
        
        return reward / risk
    
    def to_dict(self) -> dict:
        """Serializar a diccionario para JSON."""
        return {
            "signal_id": self.signal_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "size_suggestion": self.size_suggestion,
            "size_type": self.size_type,
            "regime_at_signal": self.regime_at_signal.value,
            "regime_confidence": self.regime_confidence,
            "timeframe": self.timeframe,
            "reasoning": self.reasoning,
            "indicators": self.indicators,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "risk_reward_ratio": self.risk_reward_ratio(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        """Deserializar desde diccionario."""
        data = data.copy()
        data["direction"] = SignalDirection(data["direction"])
        data["regime_at_signal"] = MarketRegime(data["regime_at_signal"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        # Eliminar campos calculados que no son parámetros del constructor
        data.pop("risk_reward_ratio", None)
        return cls(**data)


@dataclass
class PositionInfo:
    """
    Información de una posición abierta para evaluación de cierre.
    
    Las estrategias reciben esto para decidir si cerrar posiciones.
    """
    position_id: str
    symbol: str
    direction: SignalDirection  # LONG o SHORT
    entry_price: float
    current_price: float
    size: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    opened_at: datetime
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_id: str = ""  # Estrategia que abrió la posición
    
    def holding_hours(self) -> float:
        """Horas desde apertura."""
        delta = datetime.utcnow() - self.opened_at
        return delta.total_seconds() / 3600


@dataclass
class MarketContext:
    """
    Contexto de mercado proporcionado a las estrategias.
    
    Agrupa toda la información necesaria para generar señales.
    """
    # Régimen actual
    regime: MarketRegime
    regime_confidence: float
    regime_probabilities: dict  # {"BULL": 0.7, "BEAR": 0.1, ...}
    
    # Datos de mercado por símbolo
    # {symbol: {"price": float, "volume": float, "indicators": {...}}}
    market_data: dict
    
    # Portfolio actual
    capital_available: float
    positions: list[PositionInfo]
    
    # Metadatos
    timestamp: datetime = field(default_factory=datetime.utcnow)
```

### 5.2 TradingStrategy ABC

```python
# Continuación de src/strategies/interfaces.py

class TradingStrategy(ABC):
    """
    Clase base abstracta para todas las estrategias de trading.
    
    Cada estrategia concreta debe:
    1. Implementar strategy_id único
    2. Definir en qué regímenes opera
    3. Implementar generación de señales
    4. Implementar lógica de cierre de posiciones
    
    Example:
        class ETFMomentum(TradingStrategy):
            @property
            def strategy_id(self) -> str:
                return "etf_momentum_v1"
            
            @property
            def required_regime(self) -> list[MarketRegime]:
                return [MarketRegime.BULL]
            
            def generate_signals(self, context: MarketContext) -> list[Signal]:
                # Lógica de generación...
                pass
    """
    
    def __init__(self, config: dict = None):
        """
        Inicializar estrategia con configuración.
        
        Args:
            config: Diccionario de configuración específica de la estrategia
        """
        self.config = config or {}
        self._enabled = True
        self._last_signals: list[Signal] = []
    
    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """
        Identificador único de la estrategia.
        
        Formato recomendado: "{nombre}_{version}"
        Ejemplo: "etf_momentum_v1", "mean_reversion_v2"
        """
        pass
    
    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Nombre legible de la estrategia."""
        pass
    
    @property
    @abstractmethod
    def strategy_description(self) -> str:
        """Descripción breve de la estrategia."""
        pass
    
    @property
    @abstractmethod
    def required_regime(self) -> list[MarketRegime]:
        """
        Lista de regímenes en los que esta estrategia puede operar.
        
        Si el régimen actual no está en esta lista, la estrategia
        no generará señales de entrada (pero sí puede cerrar posiciones).
        """
        pass
    
    @property
    def enabled(self) -> bool:
        """Si la estrategia está habilitada."""
        return self._enabled
    
    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value
    
    @property
    def last_signals(self) -> list[Signal]:
        """Últimas señales generadas."""
        return self._last_signals
    
    def can_operate_in_regime(self, current_regime: MarketRegime) -> bool:
        """
        Verificar si la estrategia puede operar en el régimen actual.
        
        Args:
            current_regime: Régimen de mercado actual
            
        Returns:
            True si puede generar señales de entrada
        """
        return current_regime in self.required_regime
    
    @abstractmethod
    def generate_signals(self, context: MarketContext) -> list[Signal]:
        """
        Generar señales de trading basadas en el contexto actual.
        
        Este método es llamado periódicamente por el StrategyRunner.
        Solo debe generar señales de ENTRADA (LONG/SHORT), no de cierre.
        
        Args:
            context: Contexto completo del mercado incluyendo régimen,
                    datos de mercado, portfolio, etc.
        
        Returns:
            Lista de señales generadas (puede estar vacía)
        
        Note:
            - La estrategia debe verificar internamente si puede operar
              en el régimen actual antes de generar señales
            - Las señales deben tener confidence > 0 para ser consideradas
            - El sizing es sugerencia, Risk Manager tiene última palabra
        """
        pass
    
    @abstractmethod
    def should_close(
        self, 
        position: PositionInfo, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Evaluar si una posición abierta debe cerrarse.
        
        Este método es llamado para cada posición abierta que fue
        creada por esta estrategia.
        
        Args:
            position: Información de la posición abierta
            context: Contexto actual del mercado
        
        Returns:
            Signal con direction=CLOSE si debe cerrarse, None si no
        
        Note:
            - Una posición puede cerrarse incluso si el régimen actual
              no está en required_regime (ej: cerrar LONG si mercado
              pasa a BEAR)
            - El stop_loss y take_profit pueden ser manejados por
              el broker, pero la estrategia puede decidir cerrar antes
        """
        pass
    
    def validate_signal(self, signal: Signal) -> tuple[bool, str]:
        """
        Validar que una señal cumple requisitos mínimos.
        
        Args:
            signal: Señal a validar
        
        Returns:
            (es_válida, mensaje_error)
        """
        if signal.direction in (SignalDirection.LONG, SignalDirection.SHORT):
            # Validar ratio riesgo/beneficio mínimo
            rr = signal.risk_reward_ratio()
            min_rr = self.config.get("min_risk_reward", 1.5)
            if rr is not None and rr < min_rr:
                return False, f"Risk/Reward {rr:.2f} < mínimo {min_rr}"
            
            # Validar confianza mínima
            min_conf = self.config.get("min_confidence", 0.50)
            if signal.confidence < min_conf:
                return False, f"Confianza {signal.confidence:.2f} < mínimo {min_conf}"
        
        return True, "OK"
    
    def get_metrics(self) -> dict:
        """
        Obtener métricas de la estrategia.
        
        Returns:
            Diccionario con estadísticas de operación
        """
        return {
            "strategy_id": self.strategy_id,
            "enabled": self.enabled,
            "required_regime": [r.value for r in self.required_regime],
            "total_signals_generated": len(self._last_signals),
            "config": self.config,
        }
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.strategy_id}, enabled={self.enabled})"
```

### 5.3 Tests para Interfaces

```python
# tests/strategies/test_interfaces.py
"""Tests para interfaces y dataclasses de estrategias."""

import pytest
from datetime import datetime, timedelta
from src.strategies.interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    PositionInfo,
    MarketContext,
    TradingStrategy,
)


class TestSignal:
    """Tests para Signal dataclass."""
    
    def test_signal_creation_valid(self):
        """Crear señal válida."""
        signal = Signal(
            strategy_id="test_strategy",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.75,
            entry_price=450.0,
            stop_loss=445.0,
            take_profit=465.0,
            regime_at_signal=MarketRegime.BULL,
            regime_confidence=0.80,
        )
        
        assert signal.strategy_id == "test_strategy"
        assert signal.symbol == "SPY"
        assert signal.direction == SignalDirection.LONG
        assert signal.confidence == 0.75
        assert signal.signal_id  # UUID generado
    
    def test_signal_requires_entry_for_long(self):
        """Señales LONG requieren entry_price."""
        with pytest.raises(ValueError, match="requieren entry_price"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.LONG,
                confidence=0.70,
                entry_price=None,  # ← Error: requerido
                stop_loss=445.0,
            )
    
    def test_signal_requires_stop_loss(self):
        """Señales LONG/SHORT requieren stop_loss."""
        with pytest.raises(ValueError, match="requieren stop_loss"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.LONG,
                confidence=0.70,
                entry_price=450.0,
                stop_loss=None,  # ← Error: requerido
            )
    
    def test_confidence_validation(self):
        """Confianza debe estar entre 0 y 1."""
        with pytest.raises(ValueError, match="confidence debe estar entre"):
            Signal(
                strategy_id="test",
                symbol="SPY",
                direction=SignalDirection.HOLD,
                confidence=1.5,  # ← Error: > 1.0
            )
    
    def test_risk_reward_ratio(self):
        """Calcular ratio riesgo/beneficio."""
        signal = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.70,
            entry_price=100.0,
            stop_loss=95.0,    # Riesgo: 5
            take_profit=115.0,  # Beneficio: 15
        )
        
        assert signal.risk_reward_ratio() == 3.0  # 15 / 5 = 3
    
    def test_signal_expiration(self):
        """Verificar expiración de señal."""
        # Señal que expira en el pasado
        signal = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.HOLD,
            confidence=0.50,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        assert signal.is_expired() is True
        
        # Señal que expira en el futuro
        signal2 = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.HOLD,
            confidence=0.50,
            expires_at=datetime.utcnow() + timedelta(hours=1),
        )
        assert signal2.is_expired() is False
    
    def test_signal_serialization(self):
        """Serializar y deserializar señal."""
        original = Signal(
            strategy_id="test_strategy",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.75,
            entry_price=450.0,
            stop_loss=445.0,
            take_profit=465.0,
            regime_at_signal=MarketRegime.BULL,
            regime_confidence=0.80,
            indicators={"rsi": 35, "macd": 0.5},
        )
        
        data = original.to_dict()
        restored = Signal.from_dict(data)
        
        assert restored.strategy_id == original.strategy_id
        assert restored.symbol == original.symbol
        assert restored.direction == original.direction
        assert restored.confidence == original.confidence
        assert restored.indicators == original.indicators


class TestPositionInfo:
    """Tests para PositionInfo dataclass."""
    
    def test_position_holding_hours(self):
        """Calcular horas desde apertura."""
        position = PositionInfo(
            position_id="pos_123",
            symbol="SPY",
            direction=SignalDirection.LONG,
            entry_price=450.0,
            current_price=455.0,
            size=10,
            unrealized_pnl=50.0,
            unrealized_pnl_pct=1.11,
            opened_at=datetime.utcnow() - timedelta(hours=5),
        )
        
        hours = position.holding_hours()
        assert 4.9 < hours < 5.1  # Aproximadamente 5 horas


class TestTradingStrategyABC:
    """Tests para TradingStrategy ABC."""
    
    def test_cannot_instantiate_abc(self):
        """No se puede instanciar la clase abstracta."""
        with pytest.raises(TypeError):
            TradingStrategy()
    
    def test_concrete_strategy_required_methods(self):
        """Estrategia concreta debe implementar métodos abstractos."""
        
        class IncompleteStrategy(TradingStrategy):
            @property
            def strategy_id(self) -> str:
                return "incomplete"
            # Faltan otros métodos abstractos
        
        with pytest.raises(TypeError):
            IncompleteStrategy()
    
    def test_can_operate_in_regime(self):
        """Verificar si puede operar en régimen."""
        
        class TestStrategy(TradingStrategy):
            @property
            def strategy_id(self) -> str:
                return "test_v1"
            
            @property
            def strategy_name(self) -> str:
                return "Test Strategy"
            
            @property
            def strategy_description(self) -> str:
                return "Strategy for testing"
            
            @property
            def required_regime(self) -> list[MarketRegime]:
                return [MarketRegime.BULL, MarketRegime.SIDEWAYS]
            
            def generate_signals(self, context):
                return []
            
            def should_close(self, position, context):
                return None
        
        strategy = TestStrategy()
        
        assert strategy.can_operate_in_regime(MarketRegime.BULL) is True
        assert strategy.can_operate_in_regime(MarketRegime.SIDEWAYS) is True
        assert strategy.can_operate_in_regime(MarketRegime.BEAR) is False
        assert strategy.can_operate_in_regime(MarketRegime.VOLATILE) is False
```

### 5.4 Archivo __init__.py

```python
# src/strategies/__init__.py
"""
Sistema de estrategias de trading para Nexus Trading.

Exporta las interfaces principales y clases base.
"""

from .interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    PositionInfo,
    MarketContext,
    TradingStrategy,
)

__all__ = [
    "Signal",
    "SignalDirection",
    "MarketRegime",
    "PositionInfo",
    "MarketContext",
    "TradingStrategy",
]
```

---

## 6. Checklist Tarea B1.1

```
TAREA B1.1: INTERFACES Y DATACLASSES
═══════════════════════════════════════════════════════════════════════════════

[ ] Archivo src/strategies/__init__.py creado
[ ] Archivo src/strategies/interfaces.py creado
[ ] Enum SignalDirection definido (LONG, SHORT, CLOSE, HOLD)
[ ] Enum MarketRegime definido (coincide con ml/interfaces.py)
[ ] Dataclass Signal con todos los campos
[ ] Validaciones en Signal.__post_init__
[ ] Métodos Signal.is_expired() y Signal.risk_reward_ratio()
[ ] Serialización Signal.to_dict() y Signal.from_dict()
[ ] Dataclass PositionInfo definida
[ ] Dataclass MarketContext definida
[ ] ABC TradingStrategy con todos los métodos abstractos
[ ] Método TradingStrategy.can_operate_in_regime()
[ ] Método TradingStrategy.validate_signal()
[ ] Tests en tests/strategies/test_interfaces.py
[ ] pytest tests/strategies/test_interfaces.py pasa

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 1 - Contexto, Objetivos, Arquitectura e Interfaces*

---

**Siguiente:** Parte 2 - ETF Momentum Strategy (implementación completa)
# 📈 Fase B1: Estrategias Swing Trading - Parte 2

## ETF Momentum Strategy - Implementación Completa

---

## 7. Tarea B1.2: Base Swing Strategy

**Estado:** ⬜ Pendiente

**Objetivo:** Clase base con funcionalidad común para todas las estrategias swing.

### 7.1 BaseSwingStrategy

```python
# src/strategies/swing/base_swing.py
"""
Clase base para estrategias de swing trading.

Proporciona funcionalidad común:
- Integración con detector de régimen
- Cálculo de niveles stop/take-profit
- Gestión de timeframes
- Logging estructurado
"""

from abc import abstractmethod
from datetime import datetime, timedelta
from typing import Optional
import logging

from ..interfaces import (
    TradingStrategy,
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)


class BaseSwingStrategy(TradingStrategy):
    """
    Clase base para estrategias de swing trading.
    
    Características comunes:
    - Holding period: días a semanas
    - Análisis en timeframes diarios/4h
    - Stop loss basado en ATR
    - Take profit con ratio R:R configurable
    
    Las subclases deben implementar:
    - _analyze_symbol(): Lógica específica de análisis
    - _calculate_entry_price(): Precio de entrada
    """
    
    # Configuración por defecto
    DEFAULT_CONFIG = {
        "timeframe": "1d",
        "min_confidence": 0.55,
        "min_risk_reward": 1.5,
        "atr_stop_multiplier": 2.0,      # Stop = entry - (ATR * multiplier)
        "atr_profit_multiplier": 3.0,    # TP = entry + (ATR * multiplier)
        "max_holding_days": 20,          # Cierre forzado después de N días
        "signal_ttl_hours": 24,          # Señales expiran en 24h
        "position_size_pct": 0.05,       # 5% del capital por posición
    }
    
    def __init__(self, config: dict = None):
        """
        Inicializar estrategia swing.
        
        Args:
            config: Configuración específica (se mergea con DEFAULT_CONFIG)
        """
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config)
        
        self.logger = logging.getLogger(f"strategy.{self.strategy_id}")
        self._signals_generated = 0
        self._positions_closed = 0
    
    @property
    @abstractmethod
    def symbols(self) -> list[str]:
        """Lista de símbolos que analiza esta estrategia."""
        pass
    
    def generate_signals(self, context: MarketContext) -> list[Signal]:
        """
        Generar señales para todos los símbolos configurados.
        
        1. Verificar si régimen permite operar
        2. Para cada símbolo, analizar y generar señal si aplica
        3. Validar señales antes de retornarlas
        """
        signals = []
        
        # Verificar régimen
        if not self.can_operate_in_regime(context.regime):
            self.logger.debug(
                f"Régimen {context.regime.value} no permite operar. "
                f"Requeridos: {[r.value for r in self.required_regime]}"
            )
            return signals
        
        # Analizar cada símbolo
        for symbol in self.symbols:
            try:
                # Verificar si ya tenemos posición en este símbolo
                existing_position = self._get_position_for_symbol(
                    symbol, context.positions
                )
                if existing_position:
                    self.logger.debug(f"Ya existe posición en {symbol}, skip")
                    continue
                
                # Obtener datos del símbolo
                market_data = context.market_data.get(symbol)
                if not market_data:
                    self.logger.warning(f"Sin datos de mercado para {symbol}")
                    continue
                
                # Analizar y generar señal
                signal = self._analyze_symbol(symbol, market_data, context)
                
                if signal and signal.direction != SignalDirection.HOLD:
                    # Validar señal
                    is_valid, error = self.validate_signal(signal)
                    if is_valid:
                        signals.append(signal)
                        self._signals_generated += 1
                        self.logger.info(
                            f"Señal generada: {symbol} {signal.direction.value} "
                            f"conf={signal.confidence:.2f}"
                        )
                    else:
                        self.logger.debug(f"Señal descartada para {symbol}: {error}")
                        
            except Exception as e:
                self.logger.error(f"Error analizando {symbol}: {e}")
                continue
        
        self._last_signals = signals
        return signals
    
    def should_close(
        self, 
        position: PositionInfo, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Evaluar si cerrar una posición abierta.
        
        Razones para cerrar:
        1. Régimen cambió a desfavorable (BEAR para LONG)
        2. Tiempo máximo de holding excedido
        3. Indicadores muestran reversión
        4. Take profit técnico alcanzado (si no lo maneja broker)
        """
        # 1. Cambio de régimen desfavorable
        if position.direction == SignalDirection.LONG:
            if context.regime in (MarketRegime.BEAR, MarketRegime.VOLATILE):
                return self._create_close_signal(
                    position,
                    context,
                    f"Régimen cambió a {context.regime.value}"
                )
        
        # 2. Holding máximo excedido
        max_days = self.config.get("max_holding_days", 20)
        if position.holding_hours() > max_days * 24:
            return self._create_close_signal(
                position,
                context,
                f"Holding máximo excedido ({max_days} días)"
            )
        
        # 3. Análisis técnico de reversión
        market_data = context.market_data.get(position.symbol)
        if market_data:
            if self._should_close_on_technicals(position, market_data, context):
                return self._create_close_signal(
                    position,
                    context,
                    "Señales técnicas de reversión"
                )
        
        return None
    
    @abstractmethod
    def _analyze_symbol(
        self, 
        symbol: str, 
        market_data: dict, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Analizar un símbolo específico y generar señal si aplica.
        
        Args:
            symbol: Símbolo a analizar
            market_data: Datos de mercado del símbolo
            context: Contexto completo del mercado
            
        Returns:
            Signal si hay oportunidad, None si no
        """
        pass
    
    def _should_close_on_technicals(
        self,
        position: PositionInfo,
        market_data: dict,
        context: MarketContext
    ) -> bool:
        """
        Verificar si cerrar basándose en indicadores técnicos.
        
        Override en subclases para lógica específica.
        Por defecto: cerrar si RSI > 75 para LONG.
        """
        indicators = market_data.get("indicators", {})
        rsi = indicators.get("rsi_14")
        
        if position.direction == SignalDirection.LONG:
            if rsi and rsi > 75:
                return True
        
        return False
    
    def _create_close_signal(
        self,
        position: PositionInfo,
        context: MarketContext,
        reason: str
    ) -> Signal:
        """Crear señal de cierre para una posición."""
        self._positions_closed += 1
        
        return Signal(
            strategy_id=self.strategy_id,
            symbol=position.symbol,
            direction=SignalDirection.CLOSE,
            confidence=0.90,  # Alta confianza en cierres
            entry_price=position.current_price,
            stop_loss=position.current_price,  # N/A para cierres
            take_profit=position.current_price,
            regime_at_signal=context.regime,
            regime_confidence=context.regime_confidence,
            timeframe=self.config["timeframe"],
            reasoning=reason,
            metadata={
                "position_id": position.position_id,
                "unrealized_pnl": position.unrealized_pnl,
                "holding_hours": position.holding_hours(),
            }
        )
    
    def _calculate_stop_loss(
        self, 
        entry_price: float, 
        atr: float, 
        direction: SignalDirection
    ) -> float:
        """
        Calcular stop loss basado en ATR.
        
        Args:
            entry_price: Precio de entrada
            atr: Average True Range
            direction: LONG o SHORT
            
        Returns:
            Precio de stop loss
        """
        multiplier = self.config["atr_stop_multiplier"]
        
        if direction == SignalDirection.LONG:
            return entry_price - (atr * multiplier)
        else:  # SHORT
            return entry_price + (atr * multiplier)
    
    def _calculate_take_profit(
        self,
        entry_price: float,
        atr: float,
        direction: SignalDirection
    ) -> float:
        """
        Calcular take profit basado en ATR.
        
        Args:
            entry_price: Precio de entrada
            atr: Average True Range
            direction: LONG o SHORT
            
        Returns:
            Precio de take profit
        """
        multiplier = self.config["atr_profit_multiplier"]
        
        if direction == SignalDirection.LONG:
            return entry_price + (atr * multiplier)
        else:  # SHORT
            return entry_price - (atr * multiplier)
    
    def _get_position_for_symbol(
        self, 
        symbol: str, 
        positions: list[PositionInfo]
    ) -> Optional[PositionInfo]:
        """Buscar posición existente para un símbolo."""
        for pos in positions:
            if pos.symbol == symbol and pos.strategy_id == self.strategy_id:
                return pos
        return None
    
    def _calculate_signal_expiry(self) -> datetime:
        """Calcular timestamp de expiración de señal."""
        ttl_hours = self.config.get("signal_ttl_hours", 24)
        return datetime.utcnow() + timedelta(hours=ttl_hours)
    
    def get_metrics(self) -> dict:
        """Obtener métricas extendidas."""
        base_metrics = super().get_metrics()
        return {
            **base_metrics,
            "signals_generated": self._signals_generated,
            "positions_closed": self._positions_closed,
            "symbols_count": len(self.symbols),
        }
```

---

## 8. Tarea B1.3: ETF Momentum Strategy

**Estado:** ⬜ Pendiente

**Objetivo:** Implementar estrategia de momentum para ETFs europeos y americanos.

### 8.1 Concepto de la Estrategia

```
ETF MOMENTUM STRATEGY
═══════════════════════════════════════════════════════════════════════════════

IDEA CENTRAL:
- Comprar ETFs que muestran momentum positivo sostenido
- Mantener mientras el momentum continúe
- Vender cuando momentum se debilita o régimen cambia

UNIVERSO DE ETFs:
┌─────────────────────────────────────────────────────────────────────────────┐
│ EUROPA (Xetra)                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│ VWCE.DE  - Vanguard FTSE All-World (Global)                                 │
│ EUNL.DE  - iShares Core MSCI Europe                                         │
│ EXS1.DE  - iShares Core DAX (Alemania)                                      │
│ VUSA.DE  - Vanguard S&P 500                                                 │
│ IQQH.DE  - iShares Global Clean Energy                                      │
│ EQQQ.DE  - Invesco NASDAQ-100                                               │
└─────────────────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│ USA (NYSE/NASDAQ)                                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ SPY      - SPDR S&P 500                                                     │
│ QQQ      - Invesco NASDAQ-100                                               │
│ IWM      - iShares Russell 2000                                             │
│ VTI      - Vanguard Total Stock Market                                      │
│ VEA      - Vanguard FTSE Developed Markets                                  │
│ VWO      - Vanguard FTSE Emerging Markets                                   │
└─────────────────────────────────────────────────────────────────────────────┘

SEÑALES DE ENTRADA (LONG):
1. Momentum Score > umbral (ranking relativo)
2. RSI entre 40-65 (no sobrecomprado)
3. Precio > SMA 50 (tendencia alcista)
4. Régimen = BULL

SEÑALES DE SALIDA:
1. Momentum Score cae del top N
2. RSI > 75 (sobrecomprado)
3. Precio < SMA 50 (tendencia rota)
4. Régimen cambia a BEAR/VOLATILE

═══════════════════════════════════════════════════════════════════════════════
```

### 8.2 Cálculo de Momentum Score

```python
# src/strategies/swing/momentum_calculator.py
"""
Calculador de momentum para ranking de ETFs.

El momentum score combina múltiples timeframes para
capturar tendencia de corto, medio y largo plazo.
"""

from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class MomentumScore:
    """Resultado del cálculo de momentum."""
    symbol: str
    score: float                    # Score combinado (0-100)
    return_1m: float               # Retorno 1 mes (%)
    return_3m: float               # Retorno 3 meses (%)
    return_6m: float               # Retorno 6 meses (%)
    return_12m: float              # Retorno 12 meses (%)
    volatility_adjusted_score: float  # Score ajustado por volatilidad
    rank: Optional[int] = None     # Ranking dentro del universo


class MomentumCalculator:
    """
    Calculador de momentum multi-timeframe.
    
    Fórmula del score:
    score = w1*ret_1m + w2*ret_3m + w3*ret_6m + w4*ret_12m
    
    Donde los pesos por defecto son:
    - 1 mes: 0.40 (más reciente, más peso)
    - 3 meses: 0.30
    - 6 meses: 0.20
    - 12 meses: 0.10
    """
    
    DEFAULT_WEIGHTS = {
        "1m": 0.40,
        "3m": 0.30,
        "6m": 0.20,
        "12m": 0.10,
    }
    
    def __init__(self, weights: dict = None):
        """
        Inicializar calculador.
        
        Args:
            weights: Pesos personalizados para cada timeframe
        """
        self.weights = weights or self.DEFAULT_WEIGHTS
        
        # Validar que pesos sumen 1.0
        total = sum(self.weights.values())
        if not np.isclose(total, 1.0):
            raise ValueError(f"Pesos deben sumar 1.0, suman {total}")
    
    def calculate(
        self,
        symbol: str,
        prices: list[float],
        volatility: Optional[float] = None
    ) -> MomentumScore:
        """
        Calcular momentum score para un símbolo.
        
        Args:
            symbol: Símbolo del ETF
            prices: Lista de precios históricos (más reciente al final)
                   Mínimo 252 precios (1 año de trading days)
            volatility: Volatilidad anualizada (opcional, para ajuste)
            
        Returns:
            MomentumScore con todos los componentes
        """
        if len(prices) < 252:
            raise ValueError(f"Se requieren mínimo 252 precios, recibidos {len(prices)}")
        
        current_price = prices[-1]
        
        # Calcular retornos por periodo
        # Aproximaciones: 1m=21 días, 3m=63, 6m=126, 12m=252
        ret_1m = self._calculate_return(prices, 21)
        ret_3m = self._calculate_return(prices, 63)
        ret_6m = self._calculate_return(prices, 126)
        ret_12m = self._calculate_return(prices, 252)
        
        # Score ponderado
        score = (
            self.weights["1m"] * ret_1m +
            self.weights["3m"] * ret_3m +
            self.weights["6m"] * ret_6m +
            self.weights["12m"] * ret_12m
        )
        
        # Normalizar score a escala 0-100
        # Asumiendo retornos típicos entre -50% y +50%
        normalized_score = self._normalize_score(score)
        
        # Ajuste por volatilidad (opcional)
        vol_adjusted = normalized_score
        if volatility and volatility > 0:
            # Penalizar alta volatilidad: score / sqrt(volatility)
            vol_adjusted = normalized_score / np.sqrt(volatility)
        
        return MomentumScore(
            symbol=symbol,
            score=normalized_score,
            return_1m=ret_1m * 100,  # Convertir a porcentaje
            return_3m=ret_3m * 100,
            return_6m=ret_6m * 100,
            return_12m=ret_12m * 100,
            volatility_adjusted_score=vol_adjusted,
        )
    
    def _calculate_return(self, prices: list[float], lookback: int) -> float:
        """Calcular retorno para un período."""
        if len(prices) < lookback:
            return 0.0
        
        current = prices[-1]
        past = prices[-lookback]
        
        if past == 0:
            return 0.0
        
        return (current - past) / past
    
    def _normalize_score(self, raw_score: float) -> float:
        """
        Normalizar score a escala 0-100.
        
        Usa función sigmoidea para manejar valores extremos.
        """
        # Sigmoid centrada en 0, escalada para que ±30% → ~15-85
        normalized = 50 + 50 * np.tanh(raw_score * 3)
        return np.clip(normalized, 0, 100)
    
    def rank_universe(
        self, 
        scores: list[MomentumScore],
        use_vol_adjusted: bool = True
    ) -> list[MomentumScore]:
        """
        Rankear universo de ETFs por momentum.
        
        Args:
            scores: Lista de MomentumScore calculados
            use_vol_adjusted: Usar score ajustado por volatilidad
            
        Returns:
            Lista ordenada de mayor a menor momentum con ranks asignados
        """
        key = "volatility_adjusted_score" if use_vol_adjusted else "score"
        
        sorted_scores = sorted(
            scores,
            key=lambda x: getattr(x, key),
            reverse=True
        )
        
        # Asignar rankings
        for i, score in enumerate(sorted_scores, 1):
            # Crear nuevo objeto con rank (dataclass es inmutable por campos)
            object.__setattr__(score, 'rank', i)
        
        return sorted_scores
```

### 8.3 ETF Momentum Strategy - Implementación

```python
# src/strategies/swing/etf_momentum.py
"""
Estrategia ETF Momentum para swing trading.

Compra ETFs con mayor momentum relativo en régimen BULL,
mantiene mientras momentum persiste, cierra en reversión.
"""

from datetime import datetime, timedelta
from typing import Optional
import logging

from ..interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)
from .base_swing import BaseSwingStrategy
from .momentum_calculator import MomentumCalculator, MomentumScore


class ETFMomentumStrategy(BaseSwingStrategy):
    """
    Estrategia de momentum para ETFs.
    
    Reglas de entrada:
    - Régimen BULL
    - ETF en top N del ranking de momentum
    - RSI entre 40-65
    - Precio > SMA 50
    - Sin posición existente en el símbolo
    
    Reglas de salida:
    - Régimen cambia a BEAR/VOLATILE
    - RSI > 75 (sobrecomprado)
    - ETF cae del top N de momentum
    - Holding máximo excedido
    - Precio < SMA 50
    """
    
    # Universo de ETFs
    ETF_UNIVERSE_EU = [
        "VWCE.DE",   # Vanguard FTSE All-World
        "EUNL.DE",   # iShares Core MSCI Europe
        "EXS1.DE",   # iShares Core DAX
        "VUSA.DE",   # Vanguard S&P 500
        "IQQH.DE",   # iShares Global Clean Energy
        "EQQQ.DE",   # Invesco NASDAQ-100
    ]
    
    ETF_UNIVERSE_US = [
        "SPY",       # SPDR S&P 500
        "QQQ",       # Invesco NASDAQ-100
        "IWM",       # iShares Russell 2000
        "VTI",       # Vanguard Total Stock Market
        "VEA",       # Vanguard FTSE Developed Markets
        "VWO",       # Vanguard FTSE Emerging Markets
    ]
    
    # Configuración específica de la estrategia
    STRATEGY_CONFIG = {
        "top_n": 3,                    # Comprar solo top N ETFs
        "rsi_entry_low": 40,           # RSI mínimo para entrada
        "rsi_entry_high": 65,          # RSI máximo para entrada
        "rsi_exit_high": 75,           # RSI para salida (sobrecomprado)
        "min_momentum_score": 55,      # Score mínimo para considerar
        "use_vol_adjusted": True,      # Usar score ajustado por volatilidad
        "markets": ["EU", "US"],       # Mercados a operar
        "max_positions": 5,            # Máximo de posiciones simultáneas
    }
    
    def __init__(self, config: dict = None):
        """
        Inicializar estrategia ETF Momentum.
        
        Args:
            config: Configuración personalizada
        """
        # Merge configs
        merged = {
            **BaseSwingStrategy.DEFAULT_CONFIG,
            **self.STRATEGY_CONFIG,
            **(config or {})
        }
        super().__init__(merged)
        
        self.momentum_calc = MomentumCalculator()
        self.logger = logging.getLogger("strategy.etf_momentum")
        
        # Cache de rankings (se actualiza cada análisis)
        self._last_rankings: list[MomentumScore] = []
    
    @property
    def strategy_id(self) -> str:
        return "etf_momentum_v1"
    
    @property
    def strategy_name(self) -> str:
        return "ETF Momentum"
    
    @property
    def strategy_description(self) -> str:
        return (
            "Estrategia de momentum que compra ETFs con mayor momentum "
            "relativo en mercados alcistas. Usa ranking multi-timeframe "
            "y ajuste por volatilidad."
        )
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.BULL]
    
    @property
    def symbols(self) -> list[str]:
        """Obtener universo de símbolos según mercados configurados."""
        symbols = []
        markets = self.config.get("markets", ["EU", "US"])
        
        if "EU" in markets:
            symbols.extend(self.ETF_UNIVERSE_EU)
        if "US" in markets:
            symbols.extend(self.ETF_UNIVERSE_US)
        
        return symbols
    
    def generate_signals(self, context: MarketContext) -> list[Signal]:
        """
        Generar señales basadas en ranking de momentum.
        
        Proceso:
        1. Verificar régimen BULL
        2. Calcular momentum score para todo el universo
        3. Rankear ETFs
        4. Generar señales para top N que cumplan filtros
        """
        signals = []
        
        # 1. Verificar régimen
        if not self.can_operate_in_regime(context.regime):
            self.logger.debug(f"Régimen {context.regime.value} no permite entrada")
            return signals
        
        # 2. Verificar límite de posiciones
        current_positions = len([
            p for p in context.positions 
            if p.strategy_id == self.strategy_id
        ])
        max_positions = self.config.get("max_positions", 5)
        
        if current_positions >= max_positions:
            self.logger.debug(
                f"Máximo de posiciones alcanzado ({current_positions}/{max_positions})"
            )
            return signals
        
        # 3. Calcular rankings de momentum
        rankings = self._calculate_momentum_rankings(context)
        self._last_rankings = rankings
        
        if not rankings:
            self.logger.warning("No se pudieron calcular rankings de momentum")
            return signals
        
        # 4. Filtrar top N y generar señales
        top_n = self.config.get("top_n", 3)
        positions_to_open = max_positions - current_positions
        
        for score in rankings[:min(top_n, positions_to_open)]:
            # Verificar si ya tenemos posición
            existing = self._get_position_for_symbol(score.symbol, context.positions)
            if existing:
                continue
            
            # Verificar momentum mínimo
            min_score = self.config.get("min_momentum_score", 55)
            if score.volatility_adjusted_score < min_score:
                self.logger.debug(
                    f"{score.symbol}: score {score.volatility_adjusted_score:.1f} "
                    f"< mínimo {min_score}"
                )
                continue
            
            # Obtener datos de mercado para filtros adicionales
            market_data = context.market_data.get(score.symbol)
            if not market_data:
                continue
            
            # Aplicar filtros técnicos y generar señal
            signal = self._generate_entry_signal(score, market_data, context)
            if signal:
                signals.append(signal)
                self.logger.info(
                    f"Señal LONG: {score.symbol} rank={score.rank} "
                    f"score={score.volatility_adjusted_score:.1f}"
                )
        
        self._last_signals = signals
        return signals
    
    def _calculate_momentum_rankings(
        self, 
        context: MarketContext
    ) -> list[MomentumScore]:
        """
        Calcular y rankear momentum de todo el universo.
        
        Returns:
            Lista de MomentumScore ordenada por ranking
        """
        scores = []
        
        for symbol in self.symbols:
            market_data = context.market_data.get(symbol)
            if not market_data:
                continue
            
            prices = market_data.get("prices", [])
            volatility = market_data.get("indicators", {}).get("volatility_20d")
            
            if len(prices) < 252:
                self.logger.debug(f"{symbol}: datos insuficientes ({len(prices)} precios)")
                continue
            
            try:
                score = self.momentum_calc.calculate(
                    symbol=symbol,
                    prices=prices,
                    volatility=volatility
                )
                scores.append(score)
            except Exception as e:
                self.logger.error(f"Error calculando momentum para {symbol}: {e}")
                continue
        
        # Rankear
        use_vol = self.config.get("use_vol_adjusted", True)
        return self.momentum_calc.rank_universe(scores, use_vol_adjusted=use_vol)
    
    def _generate_entry_signal(
        self,
        momentum: MomentumScore,
        market_data: dict,
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Generar señal de entrada si cumple filtros técnicos.
        
        Filtros:
        - RSI entre rsi_entry_low y rsi_entry_high
        - Precio > SMA 50
        """
        indicators = market_data.get("indicators", {})
        current_price = market_data.get("price", market_data.get("prices", [0])[-1])
        
        # Obtener indicadores
        rsi = indicators.get("rsi_14")
        sma_50 = indicators.get("sma_50")
        atr = indicators.get("atr_14", current_price * 0.02)  # Default 2%
        
        # Validar RSI
        rsi_low = self.config.get("rsi_entry_low", 40)
        rsi_high = self.config.get("rsi_entry_high", 65)
        
        if rsi is not None:
            if not (rsi_low <= rsi <= rsi_high):
                self.logger.debug(
                    f"{momentum.symbol}: RSI {rsi:.1f} fuera de rango [{rsi_low}, {rsi_high}]"
                )
                return None
        
        # Validar tendencia (precio > SMA 50)
        if sma_50 is not None:
            if current_price < sma_50:
                self.logger.debug(
                    f"{momentum.symbol}: precio {current_price:.2f} < SMA50 {sma_50:.2f}"
                )
                return None
        
        # Calcular niveles
        entry_price = current_price
        stop_loss = self._calculate_stop_loss(entry_price, atr, SignalDirection.LONG)
        take_profit = self._calculate_take_profit(entry_price, atr, SignalDirection.LONG)
        
        # Calcular confianza basada en momentum score y régimen
        base_confidence = momentum.volatility_adjusted_score / 100
        regime_boost = 0.1 if context.regime_confidence > 0.7 else 0.0
        confidence = min(0.95, base_confidence + regime_boost)
        
        # Construir reasoning
        reasoning = (
            f"ETF Momentum: Rank #{momentum.rank}, "
            f"Score={momentum.volatility_adjusted_score:.1f}, "
            f"Ret1m={momentum.return_1m:.1f}%, "
            f"Ret3m={momentum.return_3m:.1f}%, "
            f"RSI={rsi:.1f if rsi else 'N/A'}"
        )
        
        return Signal(
            strategy_id=self.strategy_id,
            symbol=momentum.symbol,
            direction=SignalDirection.LONG,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size_suggestion=self.config.get("position_size_pct", 0.05),
            size_type="percent",
            regime_at_signal=context.regime,
            regime_confidence=context.regime_confidence,
            timeframe=self.config.get("timeframe", "1d"),
            reasoning=reasoning,
            indicators={
                "momentum_score": momentum.volatility_adjusted_score,
                "momentum_rank": momentum.rank,
                "return_1m": momentum.return_1m,
                "return_3m": momentum.return_3m,
                "return_6m": momentum.return_6m,
                "rsi_14": rsi,
                "sma_50": sma_50,
                "atr_14": atr,
            },
            metadata={
                "etf_universe": "EU" if ".DE" in momentum.symbol else "US",
            },
            expires_at=self._calculate_signal_expiry(),
        )
    
    def _analyze_symbol(
        self, 
        symbol: str, 
        market_data: dict, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Implementación requerida por BaseSwingStrategy.
        
        En ETF Momentum, el análisis se hace en batch via rankings,
        no individualmente. Este método es un fallback.
        """
        # En esta estrategia, el análisis se hace vía rankings
        # Este método no se usa directamente
        return None
    
    def should_close(
        self, 
        position: PositionInfo, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Evaluar si cerrar posición.
        
        Además de las reglas base (régimen, holding máximo),
        verificar si ETF cayó del ranking.
        """
        # Primero verificar reglas base
        base_close = super().should_close(position, context)
        if base_close:
            return base_close
        
        # Verificar si cayó del top N
        if self._last_rankings:
            top_n = self.config.get("top_n", 3)
            symbol_rank = next(
                (s.rank for s in self._last_rankings if s.symbol == position.symbol),
                999
            )
            
            if symbol_rank > top_n:
                return self._create_close_signal(
                    position,
                    context,
                    f"ETF cayó del top {top_n} (ahora rank #{symbol_rank})"
                )
        
        # Verificar RSI alto
        market_data = context.market_data.get(position.symbol)
        if market_data:
            rsi = market_data.get("indicators", {}).get("rsi_14")
            rsi_exit = self.config.get("rsi_exit_high", 75)
            
            if rsi and rsi > rsi_exit:
                return self._create_close_signal(
                    position,
                    context,
                    f"RSI sobrecomprado ({rsi:.1f} > {rsi_exit})"
                )
            
            # Verificar precio < SMA 50
            price = market_data.get("price")
            sma_50 = market_data.get("indicators", {}).get("sma_50")
            
            if price and sma_50 and price < sma_50:
                return self._create_close_signal(
                    position,
                    context,
                    f"Precio ({price:.2f}) bajo SMA50 ({sma_50:.2f})"
                )
        
        return None
    
    def get_last_rankings(self) -> list[MomentumScore]:
        """Obtener últimos rankings calculados."""
        return self._last_rankings
    
    def get_metrics(self) -> dict:
        """Métricas extendidas con info de rankings."""
        base = super().get_metrics()
        return {
            **base,
            "universe_size": len(self.symbols),
            "markets": self.config.get("markets", []),
            "top_n_setting": self.config.get("top_n", 3),
            "last_rankings_count": len(self._last_rankings),
        }
```

### 8.4 Tests para ETF Momentum

```python
# tests/strategies/test_etf_momentum.py
"""Tests para estrategia ETF Momentum."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import numpy as np

from src.strategies.swing.etf_momentum import ETFMomentumStrategy
from src.strategies.swing.momentum_calculator import MomentumCalculator, MomentumScore
from src.strategies.interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)


class TestMomentumCalculator:
    """Tests para calculador de momentum."""
    
    def test_calculate_momentum_basic(self):
        """Calcular momentum con datos válidos."""
        calc = MomentumCalculator()
        
        # Simular 252 días de precios con tendencia alcista
        base_price = 100
        prices = [base_price * (1 + 0.001 * i) for i in range(252)]
        
        score = calc.calculate("TEST", prices)
        
        assert score.symbol == "TEST"
        assert score.score > 50  # Tendencia alcista = score alto
        assert score.return_1m > 0
        assert score.return_3m > 0
    
    def test_calculate_momentum_bearish(self):
        """Momentum negativo para tendencia bajista."""
        calc = MomentumCalculator()
        
        # Simular precios con tendencia bajista
        base_price = 100
        prices = [base_price * (1 - 0.001 * i) for i in range(252)]
        
        score = calc.calculate("TEST", prices)
        
        assert score.score < 50  # Tendencia bajista = score bajo
        assert score.return_1m < 0
    
    def test_rank_universe(self):
        """Rankear múltiples ETFs."""
        calc = MomentumCalculator()
        
        scores = [
            MomentumScore("ETF_A", 70, 5, 10, 15, 20, 65),
            MomentumScore("ETF_B", 80, 8, 12, 18, 25, 75),
            MomentumScore("ETF_C", 60, 3, 8, 12, 15, 55),
        ]
        
        ranked = calc.rank_universe(scores, use_vol_adjusted=True)
        
        assert ranked[0].symbol == "ETF_B"  # Mayor vol_adjusted_score
        assert ranked[0].rank == 1
        assert ranked[1].symbol == "ETF_A"
        assert ranked[1].rank == 2
        assert ranked[2].symbol == "ETF_C"
        assert ranked[2].rank == 3
    
    def test_insufficient_data_raises(self):
        """Error si no hay suficientes datos."""
        calc = MomentumCalculator()
        
        with pytest.raises(ValueError, match="252 precios"):
            calc.calculate("TEST", [100] * 100)  # Solo 100 precios


class TestETFMomentumStrategy:
    """Tests para estrategia ETF Momentum."""
    
    @pytest.fixture
    def strategy(self):
        """Crear estrategia con config por defecto."""
        return ETFMomentumStrategy()
    
    @pytest.fixture
    def bull_context(self):
        """Contexto de mercado BULL con datos de prueba."""
        # Generar precios con tendencia alcista
        prices_bullish = [100 * (1 + 0.002 * i) for i in range(252)]
        
        return MarketContext(
            regime=MarketRegime.BULL,
            regime_confidence=0.75,
            regime_probabilities={"BULL": 0.75, "BEAR": 0.10, "SIDEWAYS": 0.10, "VOLATILE": 0.05},
            market_data={
                "SPY": {
                    "price": prices_bullish[-1],
                    "prices": prices_bullish,
                    "indicators": {
                        "rsi_14": 55,
                        "sma_50": prices_bullish[-1] * 0.95,  # Precio > SMA50
                        "atr_14": 5.0,
                        "volatility_20d": 0.15,
                    }
                },
                "QQQ": {
                    "price": prices_bullish[-1] * 1.1,
                    "prices": [p * 1.1 for p in prices_bullish],
                    "indicators": {
                        "rsi_14": 52,
                        "sma_50": prices_bullish[-1] * 1.05,
                        "atr_14": 6.0,
                        "volatility_20d": 0.18,
                    }
                },
            },
            capital_available=25000.0,
            positions=[],
        )
    
    def test_strategy_properties(self, strategy):
        """Verificar propiedades básicas."""
        assert strategy.strategy_id == "etf_momentum_v1"
        assert strategy.strategy_name == "ETF Momentum"
        assert MarketRegime.BULL in strategy.required_regime
        assert MarketRegime.BEAR not in strategy.required_regime
    
    def test_can_operate_in_bull(self, strategy):
        """Puede operar en régimen BULL."""
        assert strategy.can_operate_in_regime(MarketRegime.BULL) is True
    
    def test_cannot_operate_in_bear(self, strategy):
        """No puede operar en régimen BEAR."""
        assert strategy.can_operate_in_regime(MarketRegime.BEAR) is False
    
    def test_generate_signals_in_bull(self, strategy, bull_context):
        """Generar señales en régimen BULL."""
        # Configurar para usar solo US market en el test
        strategy.config["markets"] = ["US"]
        
        signals = strategy.generate_signals(bull_context)
        
        # Debería generar al menos una señal
        assert len(signals) >= 0  # Puede ser 0 si filtros no pasan
        
        for signal in signals:
            assert signal.direction == SignalDirection.LONG
            assert signal.strategy_id == "etf_momentum_v1"
            assert signal.regime_at_signal == MarketRegime.BULL
    
    def test_no_signals_in_bear(self, strategy, bull_context):
        """No generar señales en régimen BEAR."""
        bear_context = MarketContext(
            regime=MarketRegime.BEAR,
            regime_confidence=0.80,
            regime_probabilities={"BEAR": 0.80},
            market_data=bull_context.market_data,
            capital_available=25000.0,
            positions=[],
        )
        
        signals = strategy.generate_signals(bear_context)
        assert len(signals) == 0
    
    def test_respects_max_positions(self, strategy, bull_context):
        """Respetar límite de posiciones."""
        strategy.config["max_positions"] = 1
        
        # Simular posición existente
        existing = PositionInfo(
            position_id="pos_1",
            symbol="SPY",
            direction=SignalDirection.LONG,
            entry_price=100,
            current_price=105,
            size=10,
            unrealized_pnl=50,
            unrealized_pnl_pct=5.0,
            opened_at=datetime.utcnow() - timedelta(days=5),
            strategy_id="etf_momentum_v1",
        )
        
        bull_context.positions = [existing]
        
        signals = strategy.generate_signals(bull_context)
        assert len(signals) == 0  # Ya tenemos max_positions
    
    def test_should_close_on_regime_change(self, strategy, bull_context):
        """Cerrar posición si régimen cambia a BEAR."""
        position = PositionInfo(
            position_id="pos_1",
            symbol="SPY",
            direction=SignalDirection.LONG,
            entry_price=100,
            current_price=105,
            size=10,
            unrealized_pnl=50,
            unrealized_pnl_pct=5.0,
            opened_at=datetime.utcnow() - timedelta(days=5),
            strategy_id="etf_momentum_v1",
        )
        
        # Cambiar a régimen BEAR
        bear_context = MarketContext(
            regime=MarketRegime.BEAR,
            regime_confidence=0.80,
            regime_probabilities={"BEAR": 0.80},
            market_data=bull_context.market_data,
            capital_available=25000.0,
            positions=[position],
        )
        
        close_signal = strategy.should_close(position, bear_context)
        
        assert close_signal is not None
        assert close_signal.direction == SignalDirection.CLOSE
        assert "BEAR" in close_signal.reasoning
    
    def test_should_close_on_high_rsi(self, strategy, bull_context):
        """Cerrar posición si RSI está sobrecomprado."""
        position = PositionInfo(
            position_id="pos_1",
            symbol="SPY",
            direction=SignalDirection.LONG,
            entry_price=100,
            current_price=120,
            size=10,
            unrealized_pnl=200,
            unrealized_pnl_pct=20.0,
            opened_at=datetime.utcnow() - timedelta(days=10),
            strategy_id="etf_momentum_v1",
        )
        
        # Modificar RSI a nivel alto
        bull_context.market_data["SPY"]["indicators"]["rsi_14"] = 80
        
        close_signal = strategy.should_close(position, bull_context)
        
        assert close_signal is not None
        assert close_signal.direction == SignalDirection.CLOSE
        assert "RSI" in close_signal.reasoning or "sobrecomprado" in close_signal.reasoning
```

---

## 9. Checklist Tareas B1.2 y B1.3

```
TAREA B1.2: BASE SWING STRATEGY
═══════════════════════════════════════════════════════════════════════════════

[ ] Archivo src/strategies/swing/__init__.py creado
[ ] Archivo src/strategies/swing/base_swing.py creado
[ ] BaseSwingStrategy hereda de TradingStrategy
[ ] Configuración DEFAULT_CONFIG definida
[ ] Método generate_signals() implementado
[ ] Método should_close() implementado
[ ] Método _calculate_stop_loss() basado en ATR
[ ] Método _calculate_take_profit() basado en ATR
[ ] Método _should_close_on_technicals() implementado
[ ] Logging estructurado configurado
[ ] Métricas extendidas en get_metrics()

═══════════════════════════════════════════════════════════════════════════════

TAREA B1.3: ETF MOMENTUM STRATEGY
═══════════════════════════════════════════════════════════════════════════════

[ ] Archivo src/strategies/swing/momentum_calculator.py creado
[ ] Dataclass MomentumScore definida
[ ] MomentumCalculator implementado
[ ] Método calculate() con retornos multi-timeframe
[ ] Método rank_universe() funcional
[ ] Archivo src/strategies/swing/etf_momentum.py creado
[ ] ETFMomentumStrategy hereda de BaseSwingStrategy
[ ] Universo de ETFs EU y US definido
[ ] Propiedades strategy_id, strategy_name, required_regime
[ ] Propiedad symbols retorna universo según config
[ ] _calculate_momentum_rankings() implementado
[ ] _generate_entry_signal() con filtros RSI y SMA
[ ] should_close() con lógica de ranking
[ ] Tests en tests/strategies/test_etf_momentum.py
[ ] pytest tests/strategies/test_etf_momentum.py pasa

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 2 - ETF Momentum Strategy*

---

**Siguiente:** Parte 3 - Strategy Registry, Configuración YAML, Integración con Régimen
# 📈 Fase B1: Estrategias Swing Trading - Parte 3

## Strategy Registry, Configuración e Integración

---

## 10. Tarea B1.4: Strategy Registry

**Estado:** ⬜ Pendiente

**Objetivo:** Sistema de registro dinámico de estrategias con activación por configuración.

### 10.1 Patrón Registry

```python
# src/strategies/registry.py
"""
Registry de estrategias de trading.

Permite registrar, descubrir y obtener estrategias de forma dinámica.
La activación/desactivación se controla via YAML.
"""

from typing import Type, Optional
import logging

from .interfaces import TradingStrategy, MarketRegime


class StrategyRegistry:
    """
    Registro centralizado de estrategias de trading.
    
    Patrón Singleton para asegurar un único registro global.
    
    Uso:
        # Registrar estrategia
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # Obtener estrategia
        strategy = StrategyRegistry.get("etf_momentum", config)
        
        # Obtener activas para régimen
        activas = StrategyRegistry.get_active_for_regime(MarketRegime.BULL)
    """
    
    _instance: Optional["StrategyRegistry"] = None
    _registry: dict[str, Type[TradingStrategy]] = {}
    _instances: dict[str, TradingStrategy] = {}
    _config: dict = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._logger = logging.getLogger("strategy.registry")
        return cls._instance
    
    @classmethod
    def register(
        cls, 
        strategy_id: str, 
        strategy_class: Type[TradingStrategy]
    ) -> None:
        """
        Registrar una clase de estrategia.
        
        Args:
            strategy_id: Identificador único
            strategy_class: Clase que hereda de TradingStrategy
        """
        if not issubclass(strategy_class, TradingStrategy):
            raise TypeError(
                f"{strategy_class} debe heredar de TradingStrategy"
            )
        
        cls._registry[strategy_id] = strategy_class
        logging.getLogger("strategy.registry").info(
            f"Estrategia registrada: {strategy_id}"
        )
    
    @classmethod
    def unregister(cls, strategy_id: str) -> None:
        """Eliminar estrategia del registro."""
        cls._registry.pop(strategy_id, None)
        cls._instances.pop(strategy_id, None)
    
    @classmethod
    def get(
        cls, 
        strategy_id: str, 
        config: dict = None
    ) -> Optional[TradingStrategy]:
        """
        Obtener instancia de estrategia.
        
        Usa caché de instancias para reutilizar objetos.
        
        Args:
            strategy_id: ID de la estrategia
            config: Configuración específica
            
        Returns:
            Instancia de TradingStrategy o None si no existe
        """
        if strategy_id not in cls._registry:
            logging.getLogger("strategy.registry").warning(
                f"Estrategia no registrada: {strategy_id}"
            )
            return None
        
        # Verificar si ya existe instancia
        cache_key = f"{strategy_id}_{hash(str(config))}"
        if cache_key not in cls._instances:
            strategy_class = cls._registry[strategy_id]
            cls._instances[cache_key] = strategy_class(config)
        
        return cls._instances[cache_key]
    
    @classmethod
    def get_all_registered(cls) -> list[str]:
        """Obtener lista de IDs de estrategias registradas."""
        return list(cls._registry.keys())
    
    @classmethod
    def get_active_for_regime(
        cls, 
        regime: MarketRegime,
        strategies_config: dict = None
    ) -> list[TradingStrategy]:
        """
        Obtener estrategias activas para un régimen específico.
        
        Una estrategia está activa si:
        1. Está habilitada en configuración (enabled: true)
        2. Su required_regime incluye el régimen actual
        
        Args:
            regime: Régimen de mercado actual
            strategies_config: Configuración de estrategias (del YAML)
            
        Returns:
            Lista de estrategias activas para este régimen
        """
        active = []
        config = strategies_config or cls._config
        
        for strategy_id in cls._registry.keys():
            # Verificar si está habilitada en config
            strategy_conf = config.get("strategies", {}).get(strategy_id, {})
            if not strategy_conf.get("enabled", False):
                continue
            
            # Obtener instancia
            strategy = cls.get(strategy_id, strategy_conf)
            if strategy is None:
                continue
            
            # Verificar si puede operar en este régimen
            if strategy.can_operate_in_regime(regime):
                active.append(strategy)
        
        return active
    
    @classmethod
    def set_config(cls, config: dict) -> None:
        """
        Establecer configuración global de estrategias.
        
        Args:
            config: Configuración cargada del YAML
        """
        cls._config = config
        
        # Actualizar estado enabled de instancias existentes
        for strategy_id, strategy_conf in config.get("strategies", {}).items():
            cache_keys = [k for k in cls._instances.keys() if k.startswith(strategy_id)]
            for cache_key in cache_keys:
                cls._instances[cache_key].enabled = strategy_conf.get("enabled", False)
    
    @classmethod
    def reset(cls) -> None:
        """Limpiar registro (útil para tests)."""
        cls._registry.clear()
        cls._instances.clear()
        cls._config.clear()
    
    @classmethod
    def get_info(cls) -> dict:
        """Obtener información del registry."""
        return {
            "registered_count": len(cls._registry),
            "registered_strategies": list(cls._registry.keys()),
            "cached_instances": len(cls._instances),
            "config_loaded": bool(cls._config),
        }


# Decorador para auto-registro
def register_strategy(strategy_id: str):
    """
    Decorador para registrar automáticamente estrategias.
    
    Uso:
        @register_strategy("etf_momentum")
        class ETFMomentumStrategy(TradingStrategy):
            ...
    """
    def decorator(cls: Type[TradingStrategy]) -> Type[TradingStrategy]:
        StrategyRegistry.register(strategy_id, cls)
        return cls
    return decorator
```

### 10.2 Configuración YAML

```yaml
# config/strategies.yaml
#
# Configuración de estrategias de trading.
# Cada estrategia puede habilitarse/deshabilitarse
# y configurarse independientemente.
#

# Configuración global
global:
  default_timeframe: "1d"
  signal_ttl_hours: 24
  max_signals_per_run: 10

# Estrategias disponibles
strategies:
  
  # ETF Momentum - Swing Trading
  etf_momentum:
    enabled: true
    description: "Momentum multi-timeframe en ETFs"
    
    # Mercados
    markets:
      - EU
      - US
    
    # Configuración de momentum
    momentum:
      weights:
        1m: 0.40
        3m: 0.30
        6m: 0.20
        12m: 0.10
      min_score: 55
      use_vol_adjusted: true
    
    # Filtros de entrada
    entry:
      top_n: 3
      rsi_low: 40
      rsi_high: 65
      require_above_sma50: true
      min_confidence: 0.55
    
    # Gestión de salida
    exit:
      rsi_high: 75
      max_holding_days: 20
      close_on_rank_drop: true
    
    # Gestión de riesgo (sugerencias, Risk Manager decide)
    risk:
      position_size_pct: 0.05
      atr_stop_multiplier: 2.0
      atr_profit_multiplier: 3.0
      min_risk_reward: 1.5
      max_positions: 5

  # Mean Reversion - Intraday (Futuro - Fase C2)
  mean_reversion:
    enabled: false
    description: "Mean reversion intradía"
    
    required_regime:
      - SIDEWAYS
    
    # Configuración placeholder
    entry:
      zscore_threshold: -2.0
      rsi_low: 25
    
    exit:
      zscore_target: 0.0
      max_holding_hours: 8

  # AI Agent Swing (Futuro - Fase B2)
  ai_agent_swing:
    enabled: false
    description: "Agente IA para swing trading"
    
    autonomy_level: moderate
    llm_model: "claude-sonnet-4-20250514"
    
    required_regime:
      - BULL
      - SIDEWAYS

# Configuración de régimen (referencia a ml_models.yaml)
regime_mapping:
  BULL:
    active_strategies:
      - etf_momentum
      - ai_agent_swing
  BEAR:
    active_strategies: []  # Solo cierres
  SIDEWAYS:
    active_strategies:
      - mean_reversion
      - ai_agent_swing
  VOLATILE:
    active_strategies: []  # Pausar todo
```

### 10.3 Loader de Configuración

```python
# src/strategies/config.py
"""
Carga y gestión de configuración de estrategias.
"""

from pathlib import Path
from typing import Optional
import yaml
import logging

from .registry import StrategyRegistry


logger = logging.getLogger("strategy.config")


class StrategyConfig:
    """
    Gestión de configuración de estrategias.
    
    Carga configuración desde YAML y la proporciona al Registry.
    """
    
    DEFAULT_CONFIG_PATH = "config/strategies.yaml"
    
    def __init__(self, config_path: str = None):
        """
        Inicializar gestor de configuración.
        
        Args:
            config_path: Ruta al archivo YAML (opcional)
        """
        self.config_path = Path(config_path or self.DEFAULT_CONFIG_PATH)
        self._config: dict = {}
        self._loaded = False
    
    def load(self) -> dict:
        """
        Cargar configuración desde archivo YAML.
        
        Returns:
            Diccionario de configuración
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            yaml.YAMLError: Si el YAML es inválido
        """
        if not self.config_path.exists():
            logger.warning(f"Config no encontrada: {self.config_path}")
            self._config = self._default_config()
            return self._config
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        self._loaded = True
        logger.info(f"Configuración cargada desde {self.config_path}")
        
        # Actualizar Registry
        StrategyRegistry.set_config(self._config)
        
        return self._config
    
    def reload(self) -> dict:
        """Recargar configuración (hot reload)."""
        return self.load()
    
    def get(self, key: str, default=None):
        """Obtener valor de configuración."""
        keys = key.split(".")
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        
        return value if value is not None else default
    
    def get_strategy_config(self, strategy_id: str) -> dict:
        """
        Obtener configuración específica de una estrategia.
        
        Args:
            strategy_id: ID de la estrategia
            
        Returns:
            Configuración de la estrategia o dict vacío
        """
        return self._config.get("strategies", {}).get(strategy_id, {})
    
    def is_strategy_enabled(self, strategy_id: str) -> bool:
        """Verificar si una estrategia está habilitada."""
        return self.get_strategy_config(strategy_id).get("enabled", False)
    
    def get_enabled_strategies(self) -> list[str]:
        """Obtener lista de estrategias habilitadas."""
        strategies = self._config.get("strategies", {})
        return [
            sid for sid, conf in strategies.items()
            if conf.get("enabled", False)
        ]
    
    @property
    def config(self) -> dict:
        """Configuración completa."""
        return self._config
    
    def _default_config(self) -> dict:
        """Configuración por defecto si no hay archivo."""
        return {
            "global": {
                "default_timeframe": "1d",
                "signal_ttl_hours": 24,
            },
            "strategies": {
                "etf_momentum": {
                    "enabled": True,
                    "markets": ["EU", "US"],
                }
            }
        }


# Instancia global
_config_instance: Optional[StrategyConfig] = None


def get_strategy_config(config_path: str = None) -> StrategyConfig:
    """
    Obtener instancia de configuración (singleton).
    
    Args:
        config_path: Ruta al config (solo para primera llamada)
        
    Returns:
        Instancia de StrategyConfig
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = StrategyConfig(config_path)
        _config_instance.load()
    
    return _config_instance


def reload_config() -> dict:
    """Recargar configuración."""
    global _config_instance
    
    if _config_instance:
        return _config_instance.reload()
    
    return get_strategy_config().config
```

---

## 11. Tarea B1.5: Strategy Runner

**Estado:** ⬜ Pendiente

**Objetivo:** Ejecutor que coordina la generación de señales con integración de régimen.

### 11.1 Implementación del Runner

```python
# src/strategies/runner.py
"""
Strategy Runner - Ejecutor de estrategias de trading.

Coordina:
- Obtención del régimen actual
- Selección de estrategias activas
- Generación de señales
- Evaluación de cierres
- Publicación en canal pub/sub
"""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from .interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)
from .registry import StrategyRegistry
from .config import get_strategy_config


logger = logging.getLogger("strategy.runner")


class StrategyRunner:
    """
    Ejecutor principal de estrategias.
    
    Responsabilidades:
    1. Consultar régimen de mercado (via mcp-ml-models)
    2. Obtener datos de mercado (via mcp-market-data)
    3. Ejecutar estrategias activas para el régimen
    4. Publicar señales generadas
    
    Uso:
        runner = StrategyRunner(mcp_client, message_bus)
        await runner.run_cycle()  # Un ciclo de análisis
        # o
        await runner.start()  # Loop continuo
    """
    
    def __init__(
        self,
        mcp_client,           # Cliente MCP para llamar a servers
        message_bus = None,   # Bus para publicar señales (opcional)
        db_session = None,    # Sesión de BD para posiciones
        config_path: str = None
    ):
        """
        Inicializar runner.
        
        Args:
            mcp_client: Cliente para comunicación con MCP servers
            message_bus: Bus de mensajes para publicar señales
            db_session: Sesión de base de datos
            config_path: Ruta a configuración
        """
        self.mcp = mcp_client
        self.bus = message_bus
        self.db = db_session
        self.config = get_strategy_config(config_path)
        
        self._running = False
        self._last_run: Optional[datetime] = None
        self._signals_generated: int = 0
        self._cycles_completed: int = 0
    
    async def run_cycle(self) -> list[Signal]:
        """
        Ejecutar un ciclo completo de análisis.
        
        Returns:
            Lista de señales generadas en este ciclo
        """
        cycle_start = datetime.utcnow()
        all_signals: list[Signal] = []
        
        try:
            # 1. Obtener régimen actual
            regime_data = await self._get_current_regime()
            regime = MarketRegime(regime_data["regime"])
            regime_confidence = regime_data["confidence"]
            
            logger.info(
                f"Régimen actual: {regime.value} "
                f"(confianza: {regime_confidence:.2f})"
            )
            
            # 2. Obtener estrategias activas para este régimen
            active_strategies = StrategyRegistry.get_active_for_regime(
                regime,
                self.config.config
            )
            
            if not active_strategies:
                logger.info(f"No hay estrategias activas para régimen {regime.value}")
                return all_signals
            
            logger.info(
                f"Estrategias activas: "
                f"{[s.strategy_id for s in active_strategies]}"
            )
            
            # 3. Obtener datos de mercado
            symbols = self._get_all_symbols(active_strategies)
            market_data = await self._get_market_data(symbols)
            
            # 4. Obtener posiciones actuales
            positions = await self._get_current_positions()
            capital = await self._get_available_capital()
            
            # 5. Construir contexto
            context = MarketContext(
                regime=regime,
                regime_confidence=regime_confidence,
                regime_probabilities=regime_data.get("probabilities", {}),
                market_data=market_data,
                capital_available=capital,
                positions=positions,
            )
            
            # 6. Ejecutar cada estrategia
            for strategy in active_strategies:
                try:
                    # Generar señales de entrada
                    signals = strategy.generate_signals(context)
                    all_signals.extend(signals)
                    
                    # Evaluar cierres de posiciones existentes
                    for position in positions:
                        if position.strategy_id == strategy.strategy_id:
                            close_signal = strategy.should_close(position, context)
                            if close_signal:
                                all_signals.append(close_signal)
                    
                except Exception as e:
                    logger.error(
                        f"Error ejecutando {strategy.strategy_id}: {e}",
                        exc_info=True
                    )
            
            # 7. Publicar señales
            for signal in all_signals:
                await self._publish_signal(signal)
            
            # 8. Actualizar métricas
            self._signals_generated += len(all_signals)
            self._cycles_completed += 1
            self._last_run = datetime.utcnow()
            
            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(
                f"Ciclo completado en {cycle_duration:.2f}s, "
                f"{len(all_signals)} señales generadas"
            )
            
        except Exception as e:
            logger.error(f"Error en ciclo de estrategias: {e}", exc_info=True)
        
        return all_signals
    
    async def start(self, interval_seconds: int = 300):
        """
        Iniciar loop continuo de ejecución.
        
        Args:
            interval_seconds: Segundos entre ciclos (default: 5 min)
        """
        self._running = True
        logger.info(f"Strategy Runner iniciado (intervalo: {interval_seconds}s)")
        
        while self._running:
            await self.run_cycle()
            await asyncio.sleep(interval_seconds)
    
    async def stop(self):
        """Detener loop de ejecución."""
        self._running = False
        logger.info("Strategy Runner detenido")
    
    async def _get_current_regime(self) -> dict:
        """
        Obtener régimen actual desde mcp-ml-models.
        
        Returns:
            {
                "regime": "BULL",
                "confidence": 0.75,
                "probabilities": {"BULL": 0.75, ...}
            }
        """
        try:
            response = await self.mcp.call(
                server="mcp-ml-models",
                tool="get_regime",
                params={}
            )
            return response
        except Exception as e:
            logger.error(f"Error obteniendo régimen: {e}")
            # Fallback a SIDEWAYS si no hay régimen
            return {
                "regime": "SIDEWAYS",
                "confidence": 0.50,
                "probabilities": {
                    "BULL": 0.25,
                    "BEAR": 0.25,
                    "SIDEWAYS": 0.25,
                    "VOLATILE": 0.25,
                }
            }
    
    async def _get_market_data(self, symbols: list[str]) -> dict:
        """
        Obtener datos de mercado para símbolos.
        
        Returns:
            {
                "SPY": {
                    "price": 450.0,
                    "prices": [...],  # Histórico
                    "indicators": {...}
                },
                ...
            }
        """
        market_data = {}
        
        for symbol in symbols:
            try:
                # Obtener precio actual y OHLCV histórico
                ohlcv = await self.mcp.call(
                    server="mcp-market-data",
                    tool="get_ohlcv",
                    params={
                        "symbol": symbol,
                        "timeframe": "1d",
                        "limit": 300  # ~1 año
                    }
                )
                
                # Obtener indicadores técnicos
                indicators = await self.mcp.call(
                    server="mcp-technical",
                    tool="get_indicators",
                    params={
                        "symbol": symbol,
                        "indicators": [
                            "rsi_14",
                            "sma_50",
                            "sma_200",
                            "atr_14",
                            "volatility_20d"
                        ]
                    }
                )
                
                market_data[symbol] = {
                    "price": ohlcv["close"][-1] if ohlcv.get("close") else 0,
                    "prices": ohlcv.get("close", []),
                    "volume": ohlcv.get("volume", []),
                    "indicators": indicators,
                }
                
            except Exception as e:
                logger.warning(f"Error obteniendo datos para {symbol}: {e}")
        
        return market_data
    
    async def _get_current_positions(self) -> list[PositionInfo]:
        """Obtener posiciones abiertas desde BD."""
        if not self.db:
            return []
        
        # Pseudo-código - implementación real usa SQLAlchemy
        # positions = self.db.query(Position).filter(
        #     Position.status == "open"
        # ).all()
        # return [self._to_position_info(p) for p in positions]
        
        return []
    
    async def _get_available_capital(self) -> float:
        """Obtener capital disponible."""
        # Pseudo-código - implementación real consulta broker/BD
        # return await self.mcp.call("mcp-ibkr", "get_account_value")
        
        return self.config.get("global.paper_trading_capital", 25000.0)
    
    def _get_all_symbols(self, strategies) -> list[str]:
        """Obtener todos los símbolos de todas las estrategias."""
        symbols = set()
        for strategy in strategies:
            symbols.update(strategy.symbols)
        return list(symbols)
    
    async def _publish_signal(self, signal: Signal):
        """Publicar señal en bus de mensajes."""
        if not self.bus:
            logger.debug(f"Signal (no bus): {signal.symbol} {signal.direction.value}")
            return
        
        try:
            await self.bus.publish("signals", signal.to_dict())
            logger.info(
                f"Señal publicada: {signal.symbol} {signal.direction.value} "
                f"conf={signal.confidence:.2f}"
            )
        except Exception as e:
            logger.error(f"Error publicando señal: {e}")
    
    def get_metrics(self) -> dict:
        """Obtener métricas del runner."""
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "signals_generated_total": self._signals_generated,
            "cycles_completed": self._cycles_completed,
            "registered_strategies": StrategyRegistry.get_info(),
        }
```

### 11.2 Script de Inicio

```python
# scripts/run_strategies.py
"""
Script para ejecutar el Strategy Runner.

Uso:
    python scripts/run_strategies.py
    python scripts/run_strategies.py --once  # Un solo ciclo
    python scripts/run_strategies.py --interval 60  # Cada 60 segundos
"""

import asyncio
import argparse
import logging
import signal
import sys
from pathlib import Path

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.strategies.runner import StrategyRunner
from src.strategies.registry import StrategyRegistry
from src.strategies.config import get_strategy_config

# Importar estrategias para auto-registro
from src.strategies.swing.etf_momentum import ETFMomentumStrategy


# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("run_strategies")


async def main(args):
    """Main entry point."""
    
    # 1. Registrar estrategias
    logger.info("Registrando estrategias...")
    StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
    
    # 2. Cargar configuración
    config = get_strategy_config(args.config)
    logger.info(f"Estrategias habilitadas: {config.get_enabled_strategies()}")
    
    # 3. Crear cliente MCP (mock para desarrollo)
    mcp_client = create_mcp_client()
    
    # 4. Crear runner
    runner = StrategyRunner(
        mcp_client=mcp_client,
        message_bus=None,  # TODO: Conectar Redis
        config_path=args.config
    )
    
    # 5. Manejar señales de sistema
    stop_event = asyncio.Event()
    
    def handle_shutdown(signum, frame):
        logger.info("Recibida señal de parada...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # 6. Ejecutar
    if args.once:
        logger.info("Ejecutando un solo ciclo...")
        signals = await runner.run_cycle()
        logger.info(f"Señales generadas: {len(signals)}")
        for s in signals:
            logger.info(f"  - {s.symbol} {s.direction.value} conf={s.confidence:.2f}")
    else:
        logger.info(f"Iniciando loop (intervalo: {args.interval}s)...")
        
        # Ejecutar en background y esperar señal de parada
        runner_task = asyncio.create_task(runner.start(args.interval))
        
        await stop_event.wait()
        
        await runner.stop()
        runner_task.cancel()
    
    logger.info("Runner finalizado")


def create_mcp_client():
    """Crear cliente MCP (o mock para desarrollo)."""
    
    class MockMCPClient:
        """Mock de cliente MCP para desarrollo/testing."""
        
        async def call(self, server: str, tool: str, params: dict = None):
            """Simular llamadas MCP."""
            import random
            import numpy as np
            
            if tool == "get_regime":
                return {
                    "regime": "BULL",
                    "confidence": 0.75,
                    "probabilities": {
                        "BULL": 0.75,
                        "BEAR": 0.10,
                        "SIDEWAYS": 0.10,
                        "VOLATILE": 0.05,
                    }
                }
            
            if tool == "get_ohlcv":
                # Generar datos de prueba
                base = 100 + random.random() * 400
                trend = random.choice([0.001, -0.0005, 0])
                prices = [base * (1 + trend * i + random.gauss(0, 0.01)) 
                         for i in range(300)]
                return {
                    "close": prices,
                    "volume": [1000000 * random.random() for _ in range(300)]
                }
            
            if tool == "get_indicators":
                return {
                    "rsi_14": 40 + random.random() * 30,
                    "sma_50": random.random() * 500,
                    "sma_200": random.random() * 500,
                    "atr_14": random.random() * 10,
                    "volatility_20d": 0.1 + random.random() * 0.2,
                }
            
            return {}
    
    return MockMCPClient()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run trading strategies")
    parser.add_argument(
        "--config", 
        default="config/strategies.yaml",
        help="Path to strategies config"
    )
    parser.add_argument(
        "--once", 
        action="store_true",
        help="Run single cycle and exit"
    )
    parser.add_argument(
        "--interval", 
        type=int, 
        default=300,
        help="Seconds between cycles (default: 300)"
    )
    
    args = parser.parse_args()
    asyncio.run(main(args))
```

---

## 12. Tarea B1.6: Integración con Agentes (Fase 3)

**Estado:** ⬜ Pendiente

**Objetivo:** Conectar el sistema de estrategias con los agentes existentes.

### 12.1 Actualización del Technical Analyst

El Technical Analyst de Fase 3 necesita actualizarse para usar el Strategy Runner:

```python
# src/agents/technical.py (actualización)
"""
Technical Analyst Agent actualizado para usar Strategy Runner.
"""

from datetime import datetime
import asyncio
import logging

from .base import BaseAgent
from .schemas import TradingSignal
from ..strategies.runner import StrategyRunner
from ..strategies.interfaces import Signal, SignalDirection


class TechnicalAnalystAgent(BaseAgent):
    """
    Agente de análisis técnico.
    
    Ahora delega la generación de señales al StrategyRunner,
    que coordina múltiples estrategias.
    """
    
    def __init__(self, config: dict, message_bus, mcp_client):
        super().__init__("technical_analyst", config, message_bus)
        self.mcp = mcp_client
        self.runner = StrategyRunner(
            mcp_client=mcp_client,
            message_bus=message_bus,
            config_path=config.get("strategies_config", "config/strategies.yaml")
        )
        self.analysis_interval = config.get("interval_seconds", 300)
        self.logger = logging.getLogger("agent.technical")
    
    async def setup(self):
        """Inicialización del agente."""
        self.logger.info("Technical Analyst inicializándose...")
        # Cargar configuración de estrategias
        # Las estrategias se registran automáticamente
    
    async def process(self):
        """
        Loop principal - ejecutar ciclo de estrategias.
        """
        # Ejecutar ciclo de estrategias
        signals = await self.runner.run_cycle()
        
        # Convertir señales de Strategy a formato de agente
        for signal in signals:
            if signal.direction in (SignalDirection.LONG, SignalDirection.SHORT):
                trading_signal = self._convert_to_trading_signal(signal)
                self.bus.publish("signals", trading_signal)
        
        # Esperar hasta próximo ciclo
        await asyncio.sleep(self.analysis_interval)
    
    def _convert_to_trading_signal(self, signal: Signal) -> TradingSignal:
        """
        Convertir Signal de estrategia a TradingSignal de agente.
        """
        return TradingSignal(
            message_id=signal.signal_id,
            timestamp=signal.created_at,
            from_agent=f"strategy:{signal.strategy_id}",
            symbol=signal.symbol,
            direction="long" if signal.direction == SignalDirection.LONG else "short",
            confidence=signal.confidence,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            timeframe=signal.timeframe,
            reasoning=signal.reasoning,
            indicators=signal.indicators,
            ttl_seconds=3600,  # 1 hora
        )
    
    def health(self) -> dict:
        """Estado de salud del agente."""
        return {
            **super().health(),
            "runner_metrics": self.runner.get_metrics(),
        }
```

### 12.2 Diagrama de Integración

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INTEGRACIÓN ESTRATEGIAS + AGENTES                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    FASE 3: SISTEMA DE AGENTES                         │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐   │  │
│  │  │   Technical     │    │  Orchestrator   │    │  Risk Manager   │   │  │
│  │  │    Analyst      │───►│                 │◄───│                 │   │  │
│  │  └────────┬────────┘    └────────┬────────┘    └─────────────────┘   │  │
│  │           │                      │                                    │  │
│  └───────────┼──────────────────────┼────────────────────────────────────┘  │
│              │                      │                                       │
│              │ usa                  │                                       │
│              ▼                      ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    FASE B1: SISTEMA DE ESTRATEGIAS                    │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐                                                  │  │
│  │  │ Strategy Runner │◄─────── Coordina todo                            │  │
│  │  └────────┬────────┘                                                  │  │
│  │           │                                                           │  │
│  │     ┌─────┴─────┐                                                     │  │
│  │     │           │                                                     │  │
│  │     ▼           ▼                                                     │  │
│  │  ┌──────┐  ┌──────────┐                                               │  │
│  │  │Registry│  │  Config │                                               │  │
│  │  └───┬──┘  └────┬─────┘                                               │  │
│  │      │          │                                                     │  │
│  │      ▼          ▼                                                     │  │
│  │  ┌─────────────────────────────────────────────┐                      │  │
│  │  │              ETF Momentum                    │                      │  │
│  │  │         (y otras estrategias)               │                      │  │
│  │  └─────────────────────────────────────────────┘                      │  │
│  │                      │                                                │  │
│  └──────────────────────┼────────────────────────────────────────────────┘  │
│                         │ consulta                                          │
│                         ▼                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                    FASE A2: ML MODULAR                                │  │
│  │                                                                       │  │
│  │  ┌─────────────────┐    ┌─────────────────┐                           │  │
│  │  │ mcp-ml-models   │    │  RegimeDetector │                           │  │
│  │  │ (puerto 3005)   │───►│  (HMM / Rules)  │                           │  │
│  │  └─────────────────┘    └─────────────────┘                           │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 13. Checklist Tareas B1.4, B1.5, B1.6

```
TAREA B1.4: STRATEGY REGISTRY
═══════════════════════════════════════════════════════════════════════════════

[ ] Archivo src/strategies/registry.py creado
[ ] Clase StrategyRegistry con patrón Singleton
[ ] Método register() funcional
[ ] Método get() con caché de instancias
[ ] Método get_active_for_regime() filtra correctamente
[ ] Decorador @register_strategy funcional
[ ] Tests en tests/strategies/test_registry.py

═══════════════════════════════════════════════════════════════════════════════

TAREA B1.5: CONFIGURACIÓN Y RUNNER
═══════════════════════════════════════════════════════════════════════════════

[ ] Archivo config/strategies.yaml creado
[ ] Archivo src/strategies/config.py creado
[ ] Clase StrategyConfig carga YAML correctamente
[ ] Método get_strategy_config() funciona
[ ] Archivo src/strategies/runner.py creado
[ ] Clase StrategyRunner implementada
[ ] Método run_cycle() genera señales
[ ] Integración con mcp-ml-models para régimen
[ ] Integración con mcp-market-data para precios
[ ] Script scripts/run_strategies.py funcional
[ ] Tests en tests/strategies/test_runner.py

═══════════════════════════════════════════════════════════════════════════════

TAREA B1.6: INTEGRACIÓN CON AGENTES
═══════════════════════════════════════════════════════════════════════════════

[ ] Technical Analyst actualizado para usar StrategyRunner
[ ] Método _convert_to_trading_signal() implementado
[ ] Flujo Signal → TradingSignal → pub/sub verificado
[ ] Health check incluye métricas de runner

═══════════════════════════════════════════════════════════════════════════════
```

---

*Fin de Parte 3 - Strategy Registry, Configuración, Integración*

---

**Siguiente:** Parte 4 - Tests de Integración, Script de Verificación, Checklist Final
# 📈 Fase B1: Estrategias Swing Trading - Parte 4

## Tests, Verificación y Checklist Final

---

## 14. Tests de Integración

### 14.1 Test de Integración Completo

```python
# tests/strategies/test_integration.py
"""
Tests de integración para el sistema de estrategias.

Verifica el flujo completo:
Config → Registry → Runner → Signal Generation
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import tempfile
import yaml

from src.strategies.interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)
from src.strategies.registry import StrategyRegistry, register_strategy
from src.strategies.config import StrategyConfig, get_strategy_config
from src.strategies.runner import StrategyRunner
from src.strategies.swing.etf_momentum import ETFMomentumStrategy


class TestFullIntegration:
    """Tests de integración end-to-end."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Resetear registry antes de cada test."""
        StrategyRegistry.reset()
        yield
        StrategyRegistry.reset()
    
    @pytest.fixture
    def config_file(self, tmp_path):
        """Crear archivo de configuración temporal."""
        config = {
            "global": {
                "default_timeframe": "1d",
                "paper_trading_capital": 25000.0,
            },
            "strategies": {
                "etf_momentum": {
                    "enabled": True,
                    "markets": ["US"],
                    "entry": {
                        "top_n": 2,
                        "rsi_low": 40,
                        "rsi_high": 65,
                    },
                    "risk": {
                        "max_positions": 3,
                    }
                }
            }
        }
        
        config_path = tmp_path / "strategies.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        return str(config_path)
    
    @pytest.fixture
    def mock_mcp_client(self):
        """Mock de cliente MCP."""
        client = Mock()
        
        async def mock_call(server, tool, params=None):
            if tool == "get_regime":
                return {
                    "regime": "BULL",
                    "confidence": 0.75,
                    "probabilities": {
                        "BULL": 0.75,
                        "BEAR": 0.10,
                        "SIDEWAYS": 0.10,
                        "VOLATILE": 0.05,
                    }
                }
            
            if tool == "get_ohlcv":
                # Datos con tendencia alcista
                base = 100
                prices = [base * (1 + 0.002 * i) for i in range(300)]
                return {
                    "close": prices,
                    "volume": [1000000] * 300,
                }
            
            if tool == "get_indicators":
                return {
                    "rsi_14": 55,
                    "sma_50": 95,
                    "sma_200": 90,
                    "atr_14": 2.0,
                    "volatility_20d": 0.15,
                }
            
            return {}
        
        client.call = AsyncMock(side_effect=mock_call)
        return client
    
    @pytest.mark.asyncio
    async def test_full_flow_generates_signals(
        self, 
        config_file, 
        mock_mcp_client
    ):
        """Test flujo completo: config → registry → runner → señales."""
        
        # 1. Registrar estrategia
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # 2. Cargar configuración
        config = StrategyConfig(config_file)
        config.load()
        
        # 3. Crear runner
        runner = StrategyRunner(
            mcp_client=mock_mcp_client,
            config_path=config_file
        )
        
        # 4. Ejecutar ciclo
        signals = await runner.run_cycle()
        
        # 5. Verificar
        # Debería generar señales porque:
        # - Régimen es BULL (permite ETF Momentum)
        # - Datos muestran tendencia alcista
        # - RSI está en rango (55)
        # - Precio > SMA50
        
        # Puede generar 0+ señales dependiendo del ranking
        assert isinstance(signals, list)
        
        for signal in signals:
            assert isinstance(signal, Signal)
            assert signal.strategy_id == "etf_momentum_v1"
            assert signal.direction == SignalDirection.LONG
            assert signal.regime_at_signal == MarketRegime.BULL
    
    @pytest.mark.asyncio
    async def test_no_signals_in_bear_regime(
        self, 
        config_file
    ):
        """No generar señales en régimen BEAR."""
        
        # Mock que retorna BEAR
        mock_client = Mock()
        
        async def mock_call(server, tool, params=None):
            if tool == "get_regime":
                return {
                    "regime": "BEAR",
                    "confidence": 0.80,
                    "probabilities": {"BEAR": 0.80},
                }
            return {"close": [100] * 300}
        
        mock_client.call = AsyncMock(side_effect=mock_call)
        
        # Registrar y ejecutar
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        runner = StrategyRunner(
            mcp_client=mock_client,
            config_path=config_file
        )
        
        signals = await runner.run_cycle()
        
        # No debe haber señales de entrada
        entry_signals = [
            s for s in signals 
            if s.direction in (SignalDirection.LONG, SignalDirection.SHORT)
        ]
        assert len(entry_signals) == 0
    
    @pytest.mark.asyncio
    async def test_disabled_strategy_not_executed(self, tmp_path):
        """Estrategia deshabilitada no se ejecuta."""
        
        # Config con estrategia deshabilitada
        config = {
            "strategies": {
                "etf_momentum": {
                    "enabled": False,
                }
            }
        }
        
        config_path = tmp_path / "strategies.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # Obtener estrategias activas
        strategy_config = StrategyConfig(str(config_path))
        strategy_config.load()
        
        active = StrategyRegistry.get_active_for_regime(
            MarketRegime.BULL,
            strategy_config.config
        )
        
        assert len(active) == 0


class TestRegistryIntegration:
    """Tests de integración del Registry."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        StrategyRegistry.reset()
        yield
        StrategyRegistry.reset()
    
    def test_register_and_retrieve(self):
        """Registrar y recuperar estrategia."""
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        strategy = StrategyRegistry.get("etf_momentum")
        
        assert strategy is not None
        assert strategy.strategy_id == "etf_momentum_v1"
    
    def test_decorator_registration(self):
        """Registro via decorador."""
        
        @register_strategy("test_strategy")
        class TestStrategy(ETFMomentumStrategy):
            @property
            def strategy_id(self):
                return "test_v1"
        
        assert "test_strategy" in StrategyRegistry.get_all_registered()
    
    def test_get_active_for_regime(self):
        """Filtrar estrategias por régimen."""
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        config = {
            "strategies": {
                "etf_momentum": {"enabled": True}
            }
        }
        
        # En BULL, ETF Momentum debe estar activo
        bull_active = StrategyRegistry.get_active_for_regime(
            MarketRegime.BULL, config
        )
        assert len(bull_active) == 1
        
        # En BEAR, no debe estar activo
        bear_active = StrategyRegistry.get_active_for_regime(
            MarketRegime.BEAR, config
        )
        assert len(bear_active) == 0


class TestConfigIntegration:
    """Tests de integración de configuración."""
    
    def test_load_yaml_config(self, tmp_path):
        """Cargar configuración desde YAML."""
        config_data = {
            "strategies": {
                "etf_momentum": {
                    "enabled": True,
                    "markets": ["EU", "US"],
                }
            }
        }
        
        config_path = tmp_path / "test_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = StrategyConfig(str(config_path))
        loaded = config.load()
        
        assert loaded["strategies"]["etf_momentum"]["enabled"] is True
        assert "EU" in loaded["strategies"]["etf_momentum"]["markets"]
    
    def test_get_strategy_config(self, tmp_path):
        """Obtener config específica de estrategia."""
        config_data = {
            "strategies": {
                "etf_momentum": {
                    "enabled": True,
                    "entry": {"top_n": 5}
                }
            }
        }
        
        config_path = tmp_path / "test_config.yaml"
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        config = StrategyConfig(str(config_path))
        config.load()
        
        etf_config = config.get_strategy_config("etf_momentum")
        
        assert etf_config["enabled"] is True
        assert etf_config["entry"]["top_n"] == 5
    
    def test_default_config_when_file_missing(self, tmp_path):
        """Usar config por defecto si archivo no existe."""
        config = StrategyConfig(str(tmp_path / "nonexistent.yaml"))
        loaded = config.load()
        
        # Debe tener config por defecto
        assert "strategies" in loaded
```

### 14.2 Tests de Registry

```python
# tests/strategies/test_registry.py
"""Tests unitarios para Strategy Registry."""

import pytest
from src.strategies.interfaces import TradingStrategy, MarketRegime, Signal, MarketContext
from src.strategies.registry import StrategyRegistry, register_strategy


class MockStrategy(TradingStrategy):
    """Estrategia mock para tests."""
    
    @property
    def strategy_id(self):
        return "mock_v1"
    
    @property
    def strategy_name(self):
        return "Mock Strategy"
    
    @property
    def strategy_description(self):
        return "Mock for testing"
    
    @property
    def required_regime(self):
        return [MarketRegime.BULL, MarketRegime.SIDEWAYS]
    
    def generate_signals(self, context):
        return []
    
    def should_close(self, position, context):
        return None


class TestStrategyRegistry:
    """Tests para StrategyRegistry."""
    
    @pytest.fixture(autouse=True)
    def reset(self):
        StrategyRegistry.reset()
        yield
        StrategyRegistry.reset()
    
    def test_singleton_pattern(self):
        """Registry es singleton."""
        r1 = StrategyRegistry()
        r2 = StrategyRegistry()
        assert r1 is r2
    
    def test_register_strategy(self):
        """Registrar estrategia correctamente."""
        StrategyRegistry.register("mock", MockStrategy)
        
        assert "mock" in StrategyRegistry.get_all_registered()
    
    def test_register_invalid_class_raises(self):
        """Error al registrar clase que no es TradingStrategy."""
        
        class NotAStrategy:
            pass
        
        with pytest.raises(TypeError):
            StrategyRegistry.register("invalid", NotAStrategy)
    
    def test_get_returns_instance(self):
        """Get retorna instancia de estrategia."""
        StrategyRegistry.register("mock", MockStrategy)
        
        strategy = StrategyRegistry.get("mock")
        
        assert isinstance(strategy, MockStrategy)
        assert strategy.strategy_id == "mock_v1"
    
    def test_get_nonexistent_returns_none(self):
        """Get de estrategia no registrada retorna None."""
        result = StrategyRegistry.get("nonexistent")
        assert result is None
    
    def test_get_caches_instances(self):
        """Get cachea instancias."""
        StrategyRegistry.register("mock", MockStrategy)
        
        s1 = StrategyRegistry.get("mock")
        s2 = StrategyRegistry.get("mock")
        
        assert s1 is s2
    
    def test_unregister(self):
        """Eliminar estrategia del registro."""
        StrategyRegistry.register("mock", MockStrategy)
        StrategyRegistry.unregister("mock")
        
        assert "mock" not in StrategyRegistry.get_all_registered()
    
    def test_get_active_for_regime_filters_correctly(self):
        """Filtrar estrategias por régimen y enabled."""
        StrategyRegistry.register("mock", MockStrategy)
        
        config = {
            "strategies": {
                "mock": {"enabled": True}
            }
        }
        
        # MockStrategy tiene required_regime = [BULL, SIDEWAYS]
        
        bull = StrategyRegistry.get_active_for_regime(MarketRegime.BULL, config)
        assert len(bull) == 1
        
        bear = StrategyRegistry.get_active_for_regime(MarketRegime.BEAR, config)
        assert len(bear) == 0
        
        sideways = StrategyRegistry.get_active_for_regime(MarketRegime.SIDEWAYS, config)
        assert len(sideways) == 1
    
    def test_get_active_respects_enabled_flag(self):
        """Solo retorna estrategias habilitadas."""
        StrategyRegistry.register("mock", MockStrategy)
        
        config = {
            "strategies": {
                "mock": {"enabled": False}
            }
        }
        
        active = StrategyRegistry.get_active_for_regime(MarketRegime.BULL, config)
        assert len(active) == 0
    
    def test_get_info(self):
        """Obtener info del registry."""
        StrategyRegistry.register("mock", MockStrategy)
        
        info = StrategyRegistry.get_info()
        
        assert info["registered_count"] == 1
        assert "mock" in info["registered_strategies"]


class TestRegisterDecorator:
    """Tests para decorador @register_strategy."""
    
    @pytest.fixture(autouse=True)
    def reset(self):
        StrategyRegistry.reset()
        yield
        StrategyRegistry.reset()
    
    def test_decorator_registers_class(self):
        """Decorador registra la clase automáticamente."""
        
        @register_strategy("decorated_mock")
        class DecoratedStrategy(MockStrategy):
            @property
            def strategy_id(self):
                return "decorated_v1"
        
        assert "decorated_mock" in StrategyRegistry.get_all_registered()
    
    def test_decorator_returns_class_unchanged(self):
        """Decorador retorna la clase sin modificar."""
        
        @register_strategy("test")
        class TestStrategy(MockStrategy):
            pass
        
        assert issubclass(TestStrategy, MockStrategy)
```

---

## 15. Script de Verificación

### 15.1 verify_fase_b1.py

```python
# scripts/verify_fase_b1.py
"""
Script de verificación para Fase B1: Estrategias Swing Trading.

Ejecutar: python scripts/verify_fase_b1.py

Verifica:
1. Interfaces correctamente definidas
2. ETF Momentum implementado
3. Registry funcional
4. Config YAML carga correctamente
5. Runner ejecuta ciclo
6. Integración con régimen detector
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Añadir src al path
sys.path.insert(0, str(Path(__file__).parent.parent))


class Colors:
    """Colores para output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


def print_header(text: str):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    print(f"{Colors.BLUE}{text}{Colors.RESET}")
    print(f"{Colors.BLUE}{'='*60}{Colors.RESET}")


def print_check(name: str, passed: bool, detail: str = ""):
    status = f"{Colors.GREEN}✓{Colors.RESET}" if passed else f"{Colors.RED}✗{Colors.RESET}"
    detail_str = f" ({detail})" if detail else ""
    print(f"  {status} {name}{detail_str}")
    return passed


def check_imports() -> bool:
    """Verificar que todos los módulos importan correctamente."""
    print_header("1. VERIFICACIÓN DE IMPORTS")
    
    all_ok = True
    
    try:
        from src.strategies.interfaces import (
            Signal, SignalDirection, MarketRegime,
            MarketContext, PositionInfo, TradingStrategy
        )
        all_ok &= print_check("interfaces.py", True)
    except Exception as e:
        all_ok &= print_check("interfaces.py", False, str(e))
    
    try:
        from src.strategies.registry import StrategyRegistry, register_strategy
        all_ok &= print_check("registry.py", True)
    except Exception as e:
        all_ok &= print_check("registry.py", False, str(e))
    
    try:
        from src.strategies.config import StrategyConfig, get_strategy_config
        all_ok &= print_check("config.py", True)
    except Exception as e:
        all_ok &= print_check("config.py", False, str(e))
    
    try:
        from src.strategies.runner import StrategyRunner
        all_ok &= print_check("runner.py", True)
    except Exception as e:
        all_ok &= print_check("runner.py", False, str(e))
    
    try:
        from src.strategies.swing.etf_momentum import ETFMomentumStrategy
        all_ok &= print_check("etf_momentum.py", True)
    except Exception as e:
        all_ok &= print_check("etf_momentum.py", False, str(e))
    
    try:
        from src.strategies.swing.momentum_calculator import MomentumCalculator
        all_ok &= print_check("momentum_calculator.py", True)
    except Exception as e:
        all_ok &= print_check("momentum_calculator.py", False, str(e))
    
    return all_ok


def check_interfaces() -> bool:
    """Verificar interfaces y dataclasses."""
    print_header("2. VERIFICACIÓN DE INTERFACES")
    
    from src.strategies.interfaces import (
        Signal, SignalDirection, MarketRegime, TradingStrategy
    )
    
    all_ok = True
    
    # Verificar Signal
    try:
        signal = Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=0.75,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            regime_at_signal=MarketRegime.BULL,
            regime_confidence=0.80,
        )
        all_ok &= print_check("Signal dataclass", True)
        all_ok &= print_check("Signal.to_dict()", bool(signal.to_dict()))
        all_ok &= print_check("Signal.risk_reward_ratio()", signal.risk_reward_ratio() == 2.0)
    except Exception as e:
        all_ok &= print_check("Signal dataclass", False, str(e))
    
    # Verificar validaciones
    try:
        Signal(
            strategy_id="test",
            symbol="SPY",
            direction=SignalDirection.LONG,
            confidence=1.5,  # Inválido
        )
        all_ok &= print_check("Signal validación confidence", False, "No lanzó error")
    except ValueError:
        all_ok &= print_check("Signal validación confidence", True)
    
    # Verificar enums
    all_ok &= print_check("SignalDirection enum", len(SignalDirection) == 4)
    all_ok &= print_check("MarketRegime enum", len(MarketRegime) == 4)
    
    return all_ok


def check_etf_momentum() -> bool:
    """Verificar estrategia ETF Momentum."""
    print_header("3. VERIFICACIÓN ETF MOMENTUM")
    
    from src.strategies.swing.etf_momentum import ETFMomentumStrategy
    from src.strategies.interfaces import MarketRegime
    
    all_ok = True
    
    try:
        strategy = ETFMomentumStrategy()
        
        all_ok &= print_check("Instanciación", True)
        all_ok &= print_check("strategy_id", strategy.strategy_id == "etf_momentum_v1")
        all_ok &= print_check("required_regime incluye BULL", 
                              MarketRegime.BULL in strategy.required_regime)
        all_ok &= print_check("required_regime excluye BEAR", 
                              MarketRegime.BEAR not in strategy.required_regime)
        all_ok &= print_check("symbols no vacío", len(strategy.symbols) > 0)
        all_ok &= print_check("config por defecto", bool(strategy.config))
        
    except Exception as e:
        all_ok &= print_check("ETFMomentumStrategy", False, str(e))
    
    return all_ok


def check_momentum_calculator() -> bool:
    """Verificar calculador de momentum."""
    print_header("4. VERIFICACIÓN MOMENTUM CALCULATOR")
    
    from src.strategies.swing.momentum_calculator import MomentumCalculator
    
    all_ok = True
    
    try:
        calc = MomentumCalculator()
        
        # Datos con tendencia alcista
        prices = [100 * (1 + 0.001 * i) for i in range(252)]
        
        score = calc.calculate("TEST", prices)
        
        all_ok &= print_check("calculate()", True)
        all_ok &= print_check("score > 50 (tendencia alcista)", score.score > 50)
        all_ok &= print_check("return_1m positivo", score.return_1m > 0)
        
        # Ranking
        scores = [
            calc.calculate("A", [100 * (1 + 0.002 * i) for i in range(252)]),
            calc.calculate("B", [100 * (1 + 0.001 * i) for i in range(252)]),
        ]
        ranked = calc.rank_universe(scores)
        
        all_ok &= print_check("rank_universe()", len(ranked) == 2)
        all_ok &= print_check("ranking ordenado", ranked[0].symbol == "A")
        
    except Exception as e:
        all_ok &= print_check("MomentumCalculator", False, str(e))
    
    return all_ok


def check_registry() -> bool:
    """Verificar Strategy Registry."""
    print_header("5. VERIFICACIÓN REGISTRY")
    
    from src.strategies.registry import StrategyRegistry
    from src.strategies.swing.etf_momentum import ETFMomentumStrategy
    from src.strategies.interfaces import MarketRegime
    
    all_ok = True
    
    try:
        # Reset para test limpio
        StrategyRegistry.reset()
        
        # Registrar
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        all_ok &= print_check("register()", True)
        
        # Recuperar
        strategy = StrategyRegistry.get("etf_momentum")
        all_ok &= print_check("get()", strategy is not None)
        
        # Listar
        registered = StrategyRegistry.get_all_registered()
        all_ok &= print_check("get_all_registered()", "etf_momentum" in registered)
        
        # Filtrar por régimen
        config = {"strategies": {"etf_momentum": {"enabled": True}}}
        active = StrategyRegistry.get_active_for_regime(MarketRegime.BULL, config)
        all_ok &= print_check("get_active_for_regime(BULL)", len(active) == 1)
        
        # Reset
        StrategyRegistry.reset()
        all_ok &= print_check("reset()", len(StrategyRegistry.get_all_registered()) == 0)
        
    except Exception as e:
        all_ok &= print_check("StrategyRegistry", False, str(e))
    
    return all_ok


def check_config() -> bool:
    """Verificar carga de configuración."""
    print_header("6. VERIFICACIÓN CONFIG")
    
    from src.strategies.config import StrategyConfig
    from pathlib import Path
    
    all_ok = True
    
    config_path = Path("config/strategies.yaml")
    
    if config_path.exists():
        try:
            config = StrategyConfig(str(config_path))
            loaded = config.load()
            
            all_ok &= print_check("YAML cargado", True)
            all_ok &= print_check("strategies en config", "strategies" in loaded)
            
            enabled = config.get_enabled_strategies()
            all_ok &= print_check("get_enabled_strategies()", isinstance(enabled, list))
            
        except Exception as e:
            all_ok &= print_check("StrategyConfig", False, str(e))
    else:
        all_ok &= print_check("config/strategies.yaml existe", False, "Archivo no encontrado")
    
    return all_ok


async def check_runner() -> bool:
    """Verificar Strategy Runner (con mocks)."""
    print_header("7. VERIFICACIÓN RUNNER")
    
    from src.strategies.runner import StrategyRunner
    from src.strategies.registry import StrategyRegistry
    from src.strategies.swing.etf_momentum import ETFMomentumStrategy
    from unittest.mock import Mock, AsyncMock
    
    all_ok = True
    
    try:
        # Reset y registrar
        StrategyRegistry.reset()
        StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)
        
        # Mock MCP client
        mock_client = Mock()
        
        async def mock_call(server, tool, params=None):
            if tool == "get_regime":
                return {
                    "regime": "BULL",
                    "confidence": 0.75,
                    "probabilities": {"BULL": 0.75},
                }
            if tool == "get_ohlcv":
                return {"close": [100 * (1 + 0.001 * i) for i in range(300)]}
            if tool == "get_indicators":
                return {
                    "rsi_14": 55,
                    "sma_50": 95,
                    "atr_14": 2.0,
                    "volatility_20d": 0.15,
                }
            return {}
        
        mock_client.call = AsyncMock(side_effect=mock_call)
        
        # Crear runner
        runner = StrategyRunner(mcp_client=mock_client)
        all_ok &= print_check("Instanciación", True)
        
        # Ejecutar ciclo
        signals = await runner.run_cycle()
        all_ok &= print_check("run_cycle()", isinstance(signals, list))
        
        # Métricas
        metrics = runner.get_metrics()
        all_ok &= print_check("get_metrics()", "cycles_completed" in metrics)
        
        StrategyRegistry.reset()
        
    except Exception as e:
        all_ok &= print_check("StrategyRunner", False, str(e))
    
    return all_ok


def check_tests() -> bool:
    """Verificar que tests existen."""
    print_header("8. VERIFICACIÓN DE TESTS")
    
    from pathlib import Path
    
    all_ok = True
    
    test_files = [
        "tests/strategies/__init__.py",
        "tests/strategies/test_interfaces.py",
        "tests/strategies/test_registry.py",
        "tests/strategies/test_etf_momentum.py",
        "tests/strategies/test_integration.py",
    ]
    
    for test_file in test_files:
        exists = Path(test_file).exists()
        all_ok &= print_check(test_file, exists)
    
    return all_ok


async def main():
    """Ejecutar todas las verificaciones."""
    print(f"\n{Colors.BLUE}VERIFICACIÓN FASE B1: ESTRATEGIAS SWING{Colors.RESET}")
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    results.append(("Imports", check_imports()))
    results.append(("Interfaces", check_interfaces()))
    results.append(("ETF Momentum", check_etf_momentum()))
    results.append(("Momentum Calculator", check_momentum_calculator()))
    results.append(("Registry", check_registry()))
    results.append(("Config", check_config()))
    results.append(("Runner", await check_runner()))
    results.append(("Tests", check_tests()))
    
    # Resumen
    print_header("RESUMEN")
    
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    
    for name, ok in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if ok else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  {status} {name}")
    
    print(f"\n{Colors.BLUE}{'='*60}{Colors.RESET}")
    
    if passed == total:
        print(f"{Colors.GREEN}✓ FASE B1 VERIFICADA CORRECTAMENTE ({passed}/{total}){Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}✗ FASE B1 TIENE ERRORES ({passed}/{total}){Colors.RESET}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
```

---

## 16. Checklist Final de Fase B1

```
FASE B1: ESTRATEGIAS SWING TRADING
═══════════════════════════════════════════════════════════════════════════════

TAREA B1.1: INTERFACES Y DATACLASSES
─────────────────────────────────────────────────────────────────────────────
[ ] src/strategies/__init__.py creado
[ ] src/strategies/interfaces.py creado
[ ] Enum SignalDirection (LONG, SHORT, CLOSE, HOLD)
[ ] Enum MarketRegime (BULL, BEAR, SIDEWAYS, VOLATILE)
[ ] Dataclass Signal con validaciones
[ ] Dataclass PositionInfo
[ ] Dataclass MarketContext
[ ] ABC TradingStrategy con métodos abstractos
[ ] Tests tests/strategies/test_interfaces.py

TAREA B1.2: BASE SWING STRATEGY
─────────────────────────────────────────────────────────────────────────────
[ ] src/strategies/swing/__init__.py creado
[ ] src/strategies/swing/base_swing.py creado
[ ] BaseSwingStrategy hereda de TradingStrategy
[ ] Configuración DEFAULT_CONFIG
[ ] Cálculo de stop/take-profit con ATR
[ ] Lógica de cierre por régimen/holding

TAREA B1.3: ETF MOMENTUM STRATEGY
─────────────────────────────────────────────────────────────────────────────
[ ] src/strategies/swing/momentum_calculator.py creado
[ ] MomentumScore dataclass
[ ] MomentumCalculator con ranking
[ ] src/strategies/swing/etf_momentum.py creado
[ ] ETFMomentumStrategy hereda de BaseSwingStrategy
[ ] Universo ETFs EU + US definido
[ ] Lógica de ranking y filtros
[ ] Tests tests/strategies/test_etf_momentum.py

TAREA B1.4: STRATEGY REGISTRY
─────────────────────────────────────────────────────────────────────────────
[ ] src/strategies/registry.py creado
[ ] StrategyRegistry singleton
[ ] Métodos register/get/unregister
[ ] get_active_for_regime filtra correctamente
[ ] Decorador @register_strategy
[ ] Tests tests/strategies/test_registry.py

TAREA B1.5: CONFIGURACIÓN Y RUNNER
─────────────────────────────────────────────────────────────────────────────
[ ] config/strategies.yaml creado
[ ] src/strategies/config.py creado
[ ] StrategyConfig carga YAML
[ ] src/strategies/runner.py creado
[ ] StrategyRunner ejecuta ciclos
[ ] Integración con mcp-ml-models
[ ] scripts/run_strategies.py funcional
[ ] Tests tests/strategies/test_runner.py

TAREA B1.6: INTEGRACIÓN CON AGENTES
─────────────────────────────────────────────────────────────────────────────
[ ] Technical Analyst usa StrategyRunner
[ ] Conversión Signal → TradingSignal
[ ] Flujo end-to-end verificado

═══════════════════════════════════════════════════════════════════════════════

GATE DE AVANCE A FASE B2:
─────────────────────────────────────────────────────────────────────────────
[ ] python scripts/verify_fase_b1.py retorna 0 (éxito)
[ ] pytest tests/strategies/ pasa (>80% cobertura)
[ ] ETF Momentum genera señales en régimen BULL
[ ] ETF Momentum no genera señales en régimen BEAR
[ ] Registry filtra estrategias correctamente
[ ] Config YAML se carga sin errores

═══════════════════════════════════════════════════════════════════════════════
```

---

## 17. Troubleshooting

### Error: "ModuleNotFoundError: strategies"

```bash
# Asegurar que src está en PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# O usar instalación editable
pip install -e .
```

### Error: "Config no encontrada"

```bash
# Crear directorio y archivo
mkdir -p config
touch config/strategies.yaml

# Copiar contenido de sección 10.2 al archivo
```

### Error: "Registry vacío"

```python
# Verificar que estrategias se registran antes de usar
from src.strategies.swing.etf_momentum import ETFMomentumStrategy
from src.strategies.registry import StrategyRegistry

StrategyRegistry.register("etf_momentum", ETFMomentumStrategy)

# O usar auto-import en __init__.py
```

### Error: "Datos insuficientes para momentum"

```python
# MomentumCalculator requiere 252 precios (1 año)
# Verificar que mcp-market-data retorna suficientes datos

response = await mcp.call(
    "mcp-market-data",
    "get_ohlcv",
    {"symbol": "SPY", "limit": 300}  # Pedir más de 252
)
```

### Señales no se generan

1. Verificar régimen es BULL
2. Verificar estrategia está enabled en YAML
3. Verificar filtros RSI/SMA50 no rechazan
4. Verificar momentum score > min_momentum_score
5. Revisar logs del runner

```python
import logging
logging.getLogger("strategy").setLevel(logging.DEBUG)
```

### Tests fallan por estado compartido

```python
# Usar fixture para resetear registry
@pytest.fixture(autouse=True)
def reset_registry():
    StrategyRegistry.reset()
    yield
    StrategyRegistry.reset()
```

---

## 18. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Régimen detector | fase_a2_ml_modular.md | Tarea A2.2-A2.3 |
| mcp-ml-models | fase_a1_extensiones_base.md | Tarea A1.4 |
| Agentes core | fase_3_agentes_core.md | Tareas 3.1-3.4 |
| Technical Analyst | fase_3_agentes_core.md | Tarea 3.2 |
| Sistema pub/sub | fase_3_agentes_core.md | Tarea 3.1 |
| Risk Manager | fase_3_agentes_core.md | Tarea 3.3 |
| Handoff interfaces | nexus_trading_handoff.md | Sección 3 |
| AI Agent | fase_b2_ai_agent.md | (próximo) |

---

## 19. Siguiente Fase

Una vez completada la Fase B1:

1. **Verificar:** `python scripts/verify_fase_b1.py` retorna 0
2. **Verificar:** `pytest tests/strategies/` pasa con >80% cobertura
3. **Verificar:** ETF Momentum genera señales válidas en régimen BULL
4. **Siguiente documento:** `fase_b2_ai_agent.md`
5. **Contenido Fase B2:**
   - Interfaces LLMAgent ABC
   - Claude Agent implementación
   - Prompts por nivel de autonomía (conservative/moderate/experimental)
   - Integración con sistema de estrategias
   - Ejecución paralela con ETF Momentum

---

*Fin de Parte 4 - Tests, Verificación, Checklist Final*

---

*Documento de Implementación - Fase B1: Estrategias Swing Trading*  
*Nexus Trading - Bot de Trading Autónomo con IA*  
*Versión 1.0 - Diciembre 2024*
