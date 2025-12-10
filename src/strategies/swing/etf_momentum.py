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
from ..registry import register_strategy
from .base_swing import BaseSwingStrategy
from .momentum_calculator import MomentumCalculator, MomentumScore


@register_strategy("etf_momentum")
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
        
        # Inicializar calculador de momentum
        weights = self.config.get("momentum", {}).get("weights")
        self.momentum_calc = MomentumCalculator(weights)
    
    @property
    def strategy_id(self) -> str:
        return "etf_momentum"
    
    @property
    def strategy_name(self) -> str:
        return "ETF Momentum Strategy"
    
    @property
    def strategy_description(self) -> str:
        return "Estrategia de momentum relativo multi-timeframe para ETFs"
    
    @property
    def required_regime(self) -> list[MarketRegime]:
        return [MarketRegime.BULL]
    
    @property
    def symbols(self) -> list[str]:
        """Obtener universo de símbolos según configuración."""
        universe = []
        markets = self.config.get("markets", ["EU", "US"])
        
        if "EU" in markets:
            universe.extend(self.ETF_UNIVERSE_EU)
        if "US" in markets:
            universe.extend(self.ETF_UNIVERSE_US)
            
        return universe
    
    async def generate_signals(self, context: MarketContext) -> list[Signal]:
        """
        Generar señales basadas en ranking de momentum.
        
        Override del método base para implementar lógica de ranking.
        """
        signals = []
        
        # 1. Verificar régimen
        if not self.can_operate_in_regime(context.regime):
            return []
        
        # 2. Calcular momentum para todo el universo
        scores = self._calculate_momentum_rankings(context)
        if not scores:
            return []
        
        # 3. Filtrar top N
        top_n = self.config["top_n"]
        top_scores = scores[:top_n]
        top_symbols = {s.symbol for s in top_scores}
        
        self.logger.info(f"Top {top_n} Momentum: {top_symbols}")
        
        # 4. Generar señales para candidatos
        for score in top_scores:
            # Verificar si ya tenemos posición
            if self._get_position_for_symbol(score.symbol, context.positions):
                continue
            
            # Verificar score mínimo
            if score.score < self.config["min_momentum_score"]:
                continue
            
            # Analizar entrada técnica
            market_data = context.market_data.get(score.symbol)
            if not market_data:
                continue
                
            signal = self._generate_entry_signal(score, market_data, context)
            
            if signal:
                is_valid, error = self.validate_signal(signal)
                if is_valid:
                    signals.append(signal)
                    self._signals_generated += 1
        
        self._last_signals = signals
        return signals
    
    async def should_close(
        self, 
        position: PositionInfo, 
        context: MarketContext
    ) -> Optional[Signal]:
        """
        Evaluar cierre de posiciones.
        
        Añade lógica específica de ranking: cerrar si cae del top N.
        """
        # 1. Chequeos base (régimen, holding, técnico)
        base_signal = await super().should_close(position, context)
        if base_signal:
            return base_signal
        
        # 2. Chequeo de ranking (solo si habilitado)
        if self.config.get("close_on_rank_drop", True):
            # Recalcular rankings
            scores = self._calculate_momentum_rankings(context)
            top_n = self.config["top_n"]
            
            # Buscar ranking actual del símbolo
            current_rank = next(
                (s.rank for s in scores if s.symbol == position.symbol), 
                None
            )
            
            # Si cayó mucho del ranking (ej: fuera del top N*2)
            if current_rank and current_rank > (top_n * 2):
                return self._create_close_signal(
                    position,
                    context,
                    f"Pérdida de momentum (Rank {current_rank} > {top_n*2})"
                )
        
        return None

    def _analyze_symbol(self, symbol, market_data, context):
        """
        No usado directamente, usamos generate_signals con ranking global.
        Implementación dummy para satisfacer clase base.
        """
        return None
    
    def _calculate_momentum_rankings(
        self, 
        context: MarketContext
    ) -> list[MomentumScore]:
        """Calcular y rankear momentum para todo el universo."""
        scores = []
        
        # Usar active_symbols (dinámicos o hardcodeados)
        for symbol in self.active_symbols:
            market_data = context.market_data.get(symbol)
            if not market_data:
                continue
            
            prices = market_data.get("prices", [])
            if not prices or len(prices) < 252:
                continue
                
            volatility = market_data.get("indicators", {}).get("volatility_20d")
            
            try:
                score = self.momentum_calc.calculate(
                    symbol, 
                    prices, 
                    volatility
                )
                scores.append(score)
            except ValueError:
                continue
        
        # Rankear
        use_vol = self.config.get("use_vol_adjusted", True)
        return self.momentum_calc.rank_universe(scores, use_vol)
    
    def _generate_entry_signal(
        self,
        score: MomentumScore,
        market_data: dict,
        context: MarketContext
    ) -> Optional[Signal]:
        """Generar señal de entrada si cumple filtros técnicos."""
        indicators = market_data.get("indicators", {})
        current_price = market_data.get("price")
        
        if not current_price:
            return None
            
        # 1. Filtro RSI
        rsi = indicators.get("rsi_14")
        if rsi:
            if not (self.config["rsi_entry_low"] <= rsi <= self.config["rsi_entry_high"]):
                return None
        
        # 2. Filtro SMA (Tendencia)
        sma_50 = indicators.get("sma_50")
        if self.config.get("require_above_sma50", True) and sma_50:
            if current_price < sma_50:
                return None
        
        # 3. Calcular niveles
        atr = indicators.get("atr_14", current_price * 0.02)  # Fallback 2%
        stop_loss = self._calculate_stop_loss(current_price, atr, SignalDirection.LONG)
        take_profit = self._calculate_take_profit(current_price, atr, SignalDirection.LONG)
        
        # 4. Crear señal
        return Signal(
            strategy_id=self.strategy_id,
            symbol=score.symbol,
            direction=SignalDirection.LONG,
            confidence=0.80,  # Alta confianza por estar en Top N
            entry_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            size_suggestion=self.config["position_size_pct"],
            regime_at_signal=context.regime,
            regime_confidence=context.regime_confidence,
            timeframe=self.config["timeframe"],
            reasoning=(
                f"Top Momentum (Rank {score.rank}, Score {score.score:.1f}). "
                f"RSI {rsi:.1f}, >SMA50"
            ),
            indicators={
                "rsi_14": rsi,
                "sma_50": sma_50,
                "momentum_score": score.score,
                "momentum_rank": score.rank,
            },
            metadata={
                "volatility_adjusted": score.volatility_adjusted_score
            }
        )
