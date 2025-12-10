"""
Clase base abstracta para estrategias intradía.
"""
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
import logging

from src.strategies.interfaces import TradingStrategy, Signal, SignalDirection, MarketRegime
from src.strategies.intraday.mixins import IntraDayMixin, IntraDayLimits

logger = logging.getLogger(__name__)


@dataclass
class IntraDayConfig:
    """Configuración específica para estrategias intradía."""
    timeframe: str = "5min"              # "1min", "5min", "15min"
    market: str = "US"                   # "US", "EU", "CRYPTO"
    lookback_bars: int = 100             # Barras de histórico necesarias
    min_volume_ratio: float = 1.0        # Volumen mínimo vs promedio
    max_spread_pct: float = 0.002        # Spread máximo aceptable (0.2%)
    
    # Override de límites por defecto
    limits: IntraDayLimits = field(default_factory=IntraDayLimits)


class IntraDayStrategy(TradingStrategy, IntraDayMixin):
    """
    Clase base para estrategias intradía.
    
    Hereda de TradingStrategy (ABC de Fase B1) y añade:
    - Gestión de sesiones de mercado
    - Límites intradía (trades/día, exposición)
    - Timeframes cortos (1min, 5min)
    - Cierre forzado EOD
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa estrategia intradía.
        
        Args:
            config: Configuración de la estrategia (dict)
        """
        super().__init__(config)
        
        # Parsear config específica
        self.intraday_config = IntraDayConfig(
            timeframe=config.get("timeframe", "5min"),
            market=config.get("market", "US"),
            lookback_bars=config.get("lookback_bars", 100),
            min_volume_ratio=config.get("min_volume_ratio", 1.0),
            max_spread_pct=config.get("max_spread_pct", 0.002),
            limits=IntraDayLimits(**config.get("limits", {}))
        )
        
        self.__init_intraday__(
            market=self.intraday_config.market,
            limits=self.intraday_config.limits
        )
        self._open_positions: dict[str, dict] = {}
    
    @property
    def strategy_name(self) -> str:
        """Nombre legible de la estrategia."""
        return self.strategy_id.replace("_", " ").title()
    
    @property
    def strategy_description(self) -> str:
        """Descripción breve de la estrategia."""
        return self.intraday_config.market + " " + self.intraday_config.timeframe + " Intraday Strategy"

    @property
    def strategy_type(self) -> str:
        """Tipo de estrategia."""
        return "intraday"
    
    @property
    def timeframe(self) -> str:
        """Timeframe de la estrategia."""
        return self.intraday_config.timeframe
    
    def pre_generate_checks(
        self, 
        market_data: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        Verificaciones previas a generar señales.
        
        Returns:
            (can_proceed, reason): Si puede proceder y razón si no
        """
        current_time = current_time or datetime.now()
        
        # 1. Mercado abierto
        if not self.is_market_open(current_time):
            return False, "Market closed"
        
        # 2. No cerca del cierre
        if self.should_force_close(current_time):
            return False, "Too close to market close"
        
        # 3. Límite diario
        if not self.check_daily_limit():
            return False, f"Daily trade limit reached ({self._limits.max_trades_per_day})"
        
        # 4. Datos suficientes
        if len(market_data) < self.intraday_config.lookback_bars:
            return False, f"Insufficient data ({len(market_data)}/{self.intraday_config.lookback_bars})"
        
        # 5. Volumen mínimo
        if 'volume' in market_data.columns:
            avg_volume = market_data['volume'].rolling(20).mean().iloc[-1]
            current_volume = market_data['volume'].iloc[-1]
            if current_volume < avg_volume * self.intraday_config.min_volume_ratio:
                return False, "Volume too low"
        
        return True, "OK"
    
    async def generate_signals(
        self,
        context: Any  # MarketContext
    ) -> List[Signal]:
        """
        Genera señales de trading.
        """
        signals = []
        current_time = datetime.now() # TODO: obtener del contexto
        
        # Extraer datos del contexto
        # Nota: Asumimos que context tiene market_data como DataFrame y otros campos
        # Esto depende de la implementación exacta de MarketContext en interfaces.py
        # Por ahora usamos un acceso genérico
        
        market_data = getattr(context, "market_data", pd.DataFrame())
        regime = getattr(context, "regime", MarketRegime.UNKNOWN)
        portfolio = getattr(context, "portfolio", {})
        
        # Pre-checks
        can_proceed, reason = self.pre_generate_checks(market_data, current_time)
        if not can_proceed:
            # logger.debug(f"Skipping signal generation: {reason}")
            return signals
        
        # Validar régimen
        if regime not in self.required_regime:
            return signals
        
        # Generar señales (implementación específica)
        raw_signals = self._calculate_entry_signals(
            market_data=market_data,
            regime=regime,
            portfolio=portfolio
        )
        
        # Validar y filtrar señales
        portfolio_value = portfolio.get("total_value", 0)
        for signal in raw_signals:
            if self._validate_signal(signal, portfolio_value):
                signals.append(signal)
                self.increment_trade_count()
        
        return signals
    
    @abstractmethod
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: MarketRegime,
        portfolio: dict
    ) -> List[Signal]:
        """
        Calcula señales de entrada específicas de la estrategia.
        Debe ser implementado por cada estrategia concreta.
        """
        pass
    
    async def should_close(
        self,
        position: Any, # PositionInfo
        context: Any   # MarketContext
    ) -> Optional[Signal]:
        """
        Determina si una posición intradía debe cerrarse.
        """
        current_time = datetime.now() # TODO: obtener del contexto
        symbol = position.symbol
        entry_time = position.entry_time
        current_price = position.current_price
        regime = getattr(context, "regime", MarketRegime.UNKNOWN)
        
        # 1. Cierre forzado EOD
        if self.should_force_close(current_time):
            return self._create_close_signal(
                symbol=symbol,
                current_price=current_price,
                reason="EOD_FORCE_CLOSE"
            )
        
        # 2. Max holding time
        if entry_time:
            holding_duration = current_time - entry_time
            max_holding = timedelta(minutes=self._limits.max_holding_minutes)
            if holding_duration > max_holding:
                return self._create_close_signal(
                    symbol=symbol,
                    current_price=current_price,
                    reason="MAX_HOLDING_TIME"
                )
        
        # 3. Cambio de régimen adverso
        if regime not in self.required_regime:
            return self._create_close_signal(
                symbol=symbol,
                current_price=current_price,
                reason=f"REGIME_CHANGE_TO_{regime}"
            )
        
        # 4. Condición específica de estrategia
        # return self._check_strategy_exit(position, context.market_data, regime)
        return None # TODO: Implementar lógica específica
    
    def _create_close_signal(self, symbol: str, current_price: float, reason: str) -> Signal:
        """Helper para crear señal de cierre."""
        return Signal(
            strategy_id=self.strategy_id,
            symbol=symbol,
            direction=SignalDirection.CLOSE,
            confidence=1.0,
            reasoning=reason,
            metadata={"close_reason": reason}
        )
    
    def _validate_signal(
        self, 
        signal: Signal, 
        portfolio_value: float
    ) -> bool:
        """Valida que la señal cumple límites intradía."""
        # Verificar exposición
        if signal.size_suggestion:
            signal_value = signal.size_suggestion * (signal.entry_price or 0)
            available = self.check_exposure_limit(portfolio_value)
            if signal_value > available:
                logger.warning(f"Signal exceeds exposure limit: {signal_value} > {available}")
                return False
        
        return True
