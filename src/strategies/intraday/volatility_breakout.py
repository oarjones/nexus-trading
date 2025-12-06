"""
Estrategia de Volatility Breakout Intradía.
"""
from typing import List, Any
import pandas as pd
import numpy as np

from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
from src.strategies.intraday.base import IntraDayStrategy

class VolatilityBreakout(IntraDayStrategy):
    """
    Estrategia de ruptura de volatilidad para mercados volátiles o alcistas fuertes.
    Busca rupturas de rango con confirmación de volumen.
    """
    
    @property
    def strategy_id(self) -> str:
        return "volatility_breakout"
    
    @property
    def required_regime(self) -> List[MarketRegime]:
        return [MarketRegime.VOLATILE, MarketRegime.BULL]
    
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: MarketRegime,
        portfolio: dict
    ) -> List[Signal]:
        """
        Genera señales en rupturas de rango.
        """
        signals = []
        
        # Parámetros
        lookback = 20
        atr_period = 14
        breakout_threshold = 1.0 # ATRs para confirmar ruptura
        
        # Calcular ATR
        high = market_data['high']
        low = market_data['low']
        close = market_data['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=atr_period).mean()
        
        # Calcular rango (Donchian Channel)
        upper_channel = high.rolling(window=lookback).max().shift(1) # Shift para no mirar el futuro
        lower_channel = low.rolling(window=lookback).min().shift(1)
        
        current_price = close.iloc[-1]
        current_atr = atr.iloc[-1]
        current_upper = upper_channel.iloc[-1]
        current_lower = lower_channel.iloc[-1]
        
        # Volumen relativo
        if 'volume' in market_data.columns:
            avg_vol = market_data['volume'].rolling(20).mean().iloc[-1]
            curr_vol = market_data['volume'].iloc[-1]
            vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        else:
            vol_ratio = 1.0 # Sin datos de volumen
            
        # Lógica LONG
        # Precio rompe máximo previo + Volumen alto
        if current_price > current_upper and vol_ratio > 1.2:
            signals.append(Signal(
                strategy_id=self.strategy_id,
                symbol=market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN",
                direction=SignalDirection.LONG,
                confidence=0.8, # Alta confianza en breakouts confirmados
                entry_price=current_price,
                stop_loss=current_price - (2 * current_atr), # Stop amplio (2 ATR)
                take_profit=current_price + (4 * current_atr), # Target agresivo (4 ATR)
                reasoning=f"Breakout above {current_upper:.2f} with vol ratio {vol_ratio:.1f}",
                regime_at_signal=regime,
                metadata={"vol_ratio": vol_ratio, "atr": current_atr}
            ))
            
        # Lógica SHORT (solo en régimen VOLATILE, no BULL)
        elif regime == MarketRegime.VOLATILE and current_price < current_lower and vol_ratio > 1.2:
            signals.append(Signal(
                strategy_id=self.strategy_id,
                symbol=market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN",
                direction=SignalDirection.SHORT,
                confidence=0.8,
                entry_price=current_price,
                stop_loss=current_price + (2 * current_atr),
                take_profit=current_price - (4 * current_atr),
                reasoning=f"Breakout below {current_lower:.2f} with vol ratio {vol_ratio:.1f}",
                regime_at_signal=regime,
                metadata={"vol_ratio": vol_ratio, "atr": current_atr}
            ))
            
        return signals
