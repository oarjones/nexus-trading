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
                # Verificar si ya existe posición en este símbolo
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
