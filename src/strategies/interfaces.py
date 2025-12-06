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


class TradingStrategy(ABC):
    """
    Clase base abstracta para todas las estrategias de trading.
    
    Cada estrategia concreta debe:
    1. Implementar strategy_id único
    2. Definir en qué regímenes opera
    3. Implementar generación de señales
    4. Implementar lógica de cierre de posiciones
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
