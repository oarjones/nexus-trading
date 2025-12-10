"""
Interfaces y dataclasses para el sistema de AI Agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Any, List
import json

from src.strategies.interfaces import Signal, SignalDirection


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
            "autonomy_level": self.autonomy_level.value,
        }


@dataclass
class AgentDecision:
    """
    Decisión tomada por el AI Agent.
    
    Este es el OUTPUT principal del LLM.
    """
    decision_id: str
    timestamp: datetime
    
    # Análisis
    market_view: MarketView
    confidence: float
    reasoning: str
    
    # Acciones concretas
    signals: List[Signal]
    
    # Metadatos
    model_used: str
    tokens_used: int
    execution_time_ms: int
    
    def __post_init__(self):
        """Validar datos."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
    
    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "decision_id": self.decision_id,
            "timestamp": self.timestamp.isoformat(),
            "market_view": self.market_view.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "signals": [s.to_dict() for s in self.signals],
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "execution_time_ms": self.execution_time_ms,
        }


class LLMAgent(ABC):
    """
    Clase base abstracta para agentes basados en LLM.
    """
    
    @abstractmethod
    async def decide(self, context: AgentContext) -> AgentDecision:
        """
        Toma una decisión de trading basada en el contexto.
        
        Args:
            context: Contexto completo del mercado y portfolio
            
        Returns:
            AgentDecision con análisis y señales generadas
        """
        pass
    
    @property
    @abstractmethod
    def agent_id(self) -> str:
        """ID único del agente."""
        pass
    
    @property
    @abstractmethod
    def provider(self) -> str:
        """Proveedor del modelo (claude, openai, etc)."""
        pass
