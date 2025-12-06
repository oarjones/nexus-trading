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
from typing import Optional, Any, Dict, List
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
    entry_price: float = Field(..., gt=0)
    size_shares: float = Field(..., gt=0)
    size_value_eur: float = Field(..., gt=0)
    
    # Risk levels
    stop_loss: Optional[float] = Field(None, gt=0)
    take_profit: Optional[float] = Field(None, gt=0)
    
    # Contexto (opcional, se enriquece en collector)
    regime_at_entry: Optional[RegimeType] = None
    regime_confidence: Optional[float] = Field(None, ge=0, le=1)
    
    # Metadata
    reasoning: Optional[str] = None
    signals_at_entry: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_encoders = {
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
    exit_price: float = Field(..., gt=0)
    
    # Razón de cierre
    close_reason: str = Field(..., min_length=1)  # "stop_loss", "take_profit", "manual", "signal"
    
    # Costes (opcional, calculado si no se proporciona)
    commission_eur: Optional[float] = Field(default=0.0)
    slippage_eur: Optional[float] = Field(default=0.0)
    
    # Metadata adicional
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True
        json_encoders = {
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
    
    # Instrumento
    symbol: str
    direction: TradeDirection
    
    # Entrada
    entry_time: datetime
    entry_price: float
    size_shares: float
    size_value_eur: float
    
    # Salida (si cerrado)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    close_reason: Optional[str] = None
    
    # Resultados
    pnl_eur: Optional[float] = None
    pnl_pct: Optional[float] = None
    commission_eur: Optional[float] = 0.0
    slippage_eur: Optional[float] = 0.0
    
    # Estado
    status: TradeStatus
    
    # Contexto
    regime_at_entry: Optional[RegimeType] = None
    regime_confidence: Optional[float] = None
    
    # Metadata
    reasoning: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        use_enum_values = True


# ============================================================================
# MÉTRICAS DE RENDIMIENTO
# ============================================================================

class PerformanceMetrics(BaseModel):
    """Métricas agregadas de rendimiento."""
    
    # Básicas
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    
    # PnL
    total_pnl_eur: float = 0.0
    total_pnl_pct: float = 0.0
    avg_pnl_per_trade_eur: float = 0.0
    avg_pnl_per_trade_pct: float = 0.0
    
    # Risk
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    profit_factor: float = 0.0
    
    # Time
    avg_holding_time_hours: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True


class StrategyPerformance(BaseModel):
    """Rendimiento de una estrategia en un período."""
    strategy_id: str
    period_type: PeriodType
    period_start: datetime
    period_end: datetime
    
    metrics: PerformanceMetrics
    
    # Desglose por régimen (opcional)
    by_regime: Optional[Dict[str, PerformanceMetrics]] = None
