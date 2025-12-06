"""
Estrategia de Mean Reversion Intradía.
"""
from typing import List, Any, Optional
import pandas as pd
import numpy as np

from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
from src.strategies.intraday.base import IntraDayStrategy

class MeanReversionIntraday(IntraDayStrategy):
    """
    Estrategia de reversión a la media para mercados laterales (SIDEWAYS).
    Usa Bandas de Bollinger y Z-Score.
    """
    
    @property
    def strategy_id(self) -> str:
        return "mean_reversion_intraday"
    
    @property
    def required_regime(self) -> List[MarketRegime]:
        return [MarketRegime.SIDEWAYS]
    
    def _calculate_entry_signals(
        self,
        market_data: pd.DataFrame,
        regime: MarketRegime,
        portfolio: dict
    ) -> List[Signal]:
        """
        Genera señales cuando el precio toca bandas extremas.
        """
        signals = []
        
        # Parámetros (podrían venir de config)
        period = 20
        std_dev = 2.0
        rsi_period = 14
        
        # Calcular indicadores
        closes = market_data['close']
        sma = closes.rolling(window=period).mean()
        std = closes.rolling(window=period).std()
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        # RSI
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # Últimos valores
        current_price = closes.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_upper = upper_band.iloc[-1]
        
        # Lógica de entrada LONG
        # Precio < Banda Inferior AND RSI < 30 (sobreventa)
        if current_price < current_lower and current_rsi < 30:
            signals.append(Signal(
                strategy_id=self.strategy_id,
                symbol=market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN",
                direction=SignalDirection.LONG,
                confidence=0.7,
                entry_price=current_price,
                stop_loss=current_price * 0.99, # Stop ajustado 1%
                take_profit=sma.iloc[-1],       # Target a la media
                reasoning=f"Price below lower BB ({current_lower:.2f}) and RSI oversold ({current_rsi:.1f})",
                regime_at_signal=regime,
                metadata={"rsi": current_rsi, "zscore": (current_price - sma.iloc[-1]) / std.iloc[-1]}
            ))
            
        # Lógica de entrada SHORT
        # Precio > Banda Superior AND RSI > 70 (sobrecompra)
        elif current_price > current_upper and current_rsi > 70:
            signals.append(Signal(
                strategy_id=self.strategy_id,
                symbol=market_data['symbol'].iloc[-1] if 'symbol' in market_data else "UNKNOWN",
                direction=SignalDirection.SHORT,
                confidence=0.7,
                entry_price=current_price,
                stop_loss=current_price * 1.01, # Stop ajustado 1%
                take_profit=sma.iloc[-1],       # Target a la media
                reasoning=f"Price above upper BB ({current_upper:.2f}) and RSI overbought ({current_rsi:.1f})",
                regime_at_signal=regime,
                metadata={"rsi": current_rsi, "zscore": (current_price - sma.iloc[-1]) / std.iloc[-1]}
            ))
            
        return signals
