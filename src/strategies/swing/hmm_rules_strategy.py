import logging
from typing import List, Optional
from datetime import datetime, timezone

from src.strategies.interfaces import (
    TradingStrategy, 
    Signal, 
    SignalDirection, 
    MarketRegime,
    MarketContext,
    PositionInfo
)
from src.strategies.registry import register_strategy

logger = logging.getLogger(__name__)

@register_strategy("hmm_rules")
class HMMRulesStrategy(TradingStrategy):
    """
    Estrategia sistemática basada en reglas condicionadas por régimen HMM.
    
    Lógica:
    - BILL: Trend Following (Buy dips)
    - SIDEWAYS: Mean Reversion (Oscillators)
    - BEAR/VOLATILE: Flat
    """
    
    @property
    def strategy_id(self) -> str:
        return "hmm_rules"
        
    @property
    def strategy_name(self) -> str:
        return "HMM Regime Rules"
        
    @property
    def strategy_description(self) -> str:
        return "Systematic strategy adapting to HMM Market Regimes"
        
    @property
    def strategy_type(self) -> str:
        return "swing"
        
    @property
    def required_regime(self) -> List[MarketRegime]:
        # Leemos de config o hardcoded default
        regimes = self.config.get("required_regime", ["BULL", "SIDEWAYS"])
        return [MarketRegime(r) for r in regimes]

    async def generate_signals(self, context: MarketContext) -> List[Signal]:
        """Generar señales basado en régimen hardcoded en reglas."""
        signals = []
        regime = context.regime
        
        if not self.can_operate_in_regime(regime):
            return []
            
        rules = self.config.get("rules", {})
        
        # Iterar sobre datos disponibles en contexto
        # Asumimos context.market_data = {symbol: {price: ..., indicators: {...}}}
        for symbol, data in context.market_data.items():
            try:
                price = data.get("price")
                indicators = data.get("indicators", {})
                rsi = indicators.get("RSI")
                
                if price is None or rsi is None:
                    logger.warning(f"Missing data for {symbol}: Price={price}, RSI={rsi}")
                    continue
                
                logger.info(f"HMM Debug {symbol}: Regime={regime}, RSI={rsi:.2f}")

                # Lógica BULL
                if regime == MarketRegime.BULL:
                    bull_rules = rules.get("bull", {})
                    threshold = bull_rules.get("rsi_entry_threshold", 60)
                    
                    if rsi < threshold:
                        sl_pct = bull_rules.get("stop_loss_pct", 0.03)
                        tp_pct = bull_rules.get("take_profit_pct", 0.06)
                        
                        signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            confidence=0.8, # Alta confianza en reglas simples
                            entry_price=price,
                            stop_loss=price * (1 - sl_pct),
                            take_profit=price * (1 + tp_pct),
                            size_suggestion=bull_rules.get("position_size_pct", 0.05),
                            regime_at_signal=regime,
                            regime_confidence=context.regime_confidence,
                            reasoning=f"BULL Regime dip: RSI {rsi:.2f} < {threshold}"
                        ))

                # Lógica SIDEWAYS
                elif regime == MarketRegime.SIDEWAYS:
                    side_rules = rules.get("sideways", {})
                    buy_thresh = side_rules.get("rsi_buy_threshold", 30)
                    
                    if rsi < buy_thresh:
                         sl_pct = side_rules.get("stop_loss_pct", 0.02)
                         tp_pct = side_rules.get("take_profit_pct", 0.04)
                         
                         signals.append(Signal(
                            strategy_id=self.strategy_id,
                            symbol=symbol,
                            direction=SignalDirection.LONG,
                            confidence=0.7,
                            entry_price=price,
                            stop_loss=price * (1 - sl_pct),
                            take_profit=price * (1 + tp_pct),
                            size_suggestion=side_rules.get("position_size_pct", 0.03),
                            regime_at_signal=regime,
                            regime_confidence=context.regime_confidence,
                            reasoning=f"SIDEWAYS Mean Rev: RSI {rsi:.2f} < {buy_thresh}"
                        ))
                        
            except Exception as e:
                logger.error(f"Error processing {symbol} in HMMRules: {e}")
                continue
                
        return signals

    async def should_close(self, position: PositionInfo, context: MarketContext) -> Optional[Signal]:
        """Decidir si cerrar posición."""
        current_price = position.current_price
        regime = context.regime
        rules = self.config.get("rules", {})
        
        # 1. Regime Switch: Si pasamos a BEAR, cerrar todo
        if regime == MarketRegime.BEAR:
            return Signal(
                strategy_id=self.strategy_id,
                symbol=position.symbol,
                direction=SignalDirection.CLOSE,
                confidence=1.0,
                entry_price=current_price, # Precio de salida actual
                stop_loss=None, # Irrelevante para close
                take_profit=None,
                regime_at_signal=regime,
                reasoning="Emergency close: Market Regime shifted to BEAR"
            )
            
        # 2. Lógica SIDEWAYS Sell
        if regime == MarketRegime.SIDEWAYS:
            indicators = context.market_data.get(position.symbol, {}).get("indicators", {})
            rsi = indicators.get("RSI")
            side_rules = rules.get("sideways", {})
            sell_thresh = side_rules.get("rsi_sell_threshold", 70)
            
            if rsi and rsi > sell_thresh:
                 return Signal(
                    strategy_id=self.strategy_id,
                    symbol=position.symbol,
                    direction=SignalDirection.CLOSE,
                    confidence=0.9,
                    entry_price=current_price,
                    stop_loss=None,
                    take_profit=None,
                    regime_at_signal=regime,
                    reasoning=f"SIDEWAYS Overbought: RSI {rsi:.2f} > {sell_thresh}"
                )
                
        # TODO: Trailing stop logic could go here if not handled by broker
        
        return None
