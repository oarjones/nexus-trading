"""
Technical Analyst Agent.

Generates trading signals based on technical analysis using indicators
from the MCP technical server.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, time zone
from uuid import uuid4

from .base import BaseAgent
from .messaging import MessageBus
from .schemas import TradingSignal, Direction
from .mcp_client import MCPClient, MCPServers

logger = logging.getLogger(__name__)


class TechnicalAnalystAgent(BaseAgent):
    """
    Technical Analyst Agent - Generates trading signals.
    
    Analyzes configured symbols periodically using technical indicators
    and publishes trading signals when opportunities are identified.
    
    Signal Logic (Simplified for MVP):
    - LONG: RSI < 30 AND MACD cross up AND price > SMA50
    - SHORT: RSI > 70 AND MACD cross down AND price < SMA50
    
    Confidence adjustments:
    - +0.05 for high volume (> 1.5x average)
    - +0.05 for strong trend (ADX > 25)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        message_bus: MessageBus,
        mcp_servers: MCPServers
    ):
        """
        Initialize Technical Analyst Agent.
        
        Args:
            config: Configuration dict with:
                - symbols: List of symbols to analyze
                - interval_seconds: Analysis interval
                - confidence_threshold: Min confidence to publish signal
                - indicators: List of indicators to calculate
                - timeframes: List of timeframes
            message_bus: Shared MessageBus instance
            mcp_servers: MCP server URLs
        """
        super().__init__("technical_analyst", config, message_bus)
        
        self.mcp_servers = mcp_servers
        self.mcp_client = MCPClient()
        
        # Configuration
        self.symbols = config.get("symbols", [])
        self.interval_seconds = config.get("interval_seconds", 300)
        self.confidence_threshold = config.get("confidence_threshold", 0.50)
        self.indicators = config.get("indicators", ["RSI", "MACD", "SMA_50", "SMA_200", "ADX", "ATR"])
        self.timeframes = config.get("timeframes", ["1d"])
        self.sr_lookback_days = config.get("sr_lookback_days", 50)
        
        self.logger.info(
            f"Technical Analyst initialized: "
            f"{len(self.symbols)} symbols, {self.interval_seconds}s interval"
        )
    
    async def setup(self):
        """Initialize agent - verify MCP servers are accessible."""
        # Verify MCP servers are up
        servers_ok = await self.mcp_client.health_check(self.mcp_servers.technical)
        if not servers_ok:
            self.logger.warning("Technical MCP server health check failed")
        
        self.logger.info("Technical Analyst setup complete")
    
    async def process(self):
        """
        Main analysis loop.
        
        Analyzes all configured symbols and publishes signals.
        """
        for symbol in self.symbols:
            try:
                signal = await self._analyze_symbol(symbol)
                
                if signal and signal.confidence >= self.confidence_threshold:
                    self.logger.info(
                        f"Publishing signal: {symbol} {signal.direction.value} "
                        f"(confidence: {signal.confidence:.2f})"
                    )
                    self.bus.publish("signals", signal)
                else:
                    self.logger.debug(
                        f"No signal for {symbol} "
                        f"(neutral or below threshold)"
                    )
            
            except Exception as e:
                self.logger.error(f"Error analyzing {symbol}: {e}", exc_info=True)
        
        # Wait until next analysis cycle
        await asyncio.sleep(self.interval_seconds)
    
    async def _analyze_symbol(self, symbol: str) -> Optional[TradingSignal]:
        """
        Analyze a symbol and generate signal if conditions met.
        
        Args:
            symbol: Symbol to analyze
            
        Returns:
            TradingSignal if conditions met, None otherwise
        """
        # Get indicators
        indicators = await self._get_indicators(symbol)
        if not indicators:
            self.logger.warning(f"No indicators available for {symbol}")
            return None
        
        # Get current quote
        quote = await self._get_quote(symbol)
        if not quote:
            self.logger.warning(f"No quote available for {symbol}")
            return None
        
        # Get S/R levels (optional, for future refinement)
        # sr_levels = await self._get_sr_levels(symbol)
        
        # Evaluate conditions
        direction, confidence, reasoning = self._evaluate_conditions(
            indicators, quote
        )
        
        if direction == Direction.NEUTRAL:
            return None
        
        # Calculate entry/stop/target levels
        entry, stop, target = self._calculate_levels(
            direction, quote, indicators
        )
        
        # Create signal
        signal = TradingSignal(
            message_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc),
            from_agent=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            timeframe=self.timeframes[0],
            reasoning=reasoning,
            indicators=indicators
        )
        
        return signal
    
    async def _get_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get technical indicators from MCP server.
        
        Args:
            symbol: Symbol to get indicators for
            
        Returns:
            Dict with indicator values
        """
        try:
            result = await self.mcp_client.call(
                self.mcp_servers.technical,
                "calculate_indicators",
                {
                    "symbol": symbol,
                    "indicators": self.indicators,
                    "timeframe": self.timeframes[0]
                }
            )
            
            # Extract indicators from result
            # MCP server returns: {"indicators": {...}}
            return result.get("indicators", {})
        
        except Exception as e:
            self.logger.error(f"Error getting indicators for {symbol}: {e}")
            return None
    
    async def _get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get current quote from MCP server.
        
        Args:
            symbol: Symbol to get quote for
            
        Returns:
            Dict with quote data
        """
        try:
            result = await self.mcp_client.call(
                self.mcp_servers.market_data,
                "get_quote",
                {"symbol": symbol}
            )
            
            return result
        
        except Exception as e:
            self.logger.error(f"Error getting quote for {symbol}: {e}")
            return None
    
    def _evaluate_conditions(
        self,
        indicators: Dict[str, Any],
        quote: Dict[str, Any]
    ) -> tuple[Direction, float, str]:
        """
        Evaluate trading conditions based on indicators.
        
        Args:
            indicators: Dict of technical indicators
            quote: Current quote data
            
        Returns:
            Tuple of (direction, confidence, reasoning)
        """
        rsi = indicators.get("RSI", 50)
        macd_hist = indicators.get("MACD_hist", 0)
        price = quote.get("last", 0)
        sma50 = indicators.get("SMA_50", price)
        adx = indicators.get("ADX", 20)
        volume = quote.get("volume", 0)
        
        confidence = 0.50
        direction = Direction.NEUTRAL
        reasons = []
        
        # LONG conditions
        if rsi < 30 and macd_hist > 0 and price > sma50:
            direction = Direction.LONG
            # Base confidence + RSI oversold factor
            confidence = 0.60 + (30 - rsi) / 100
            reasons.append(f"RSI oversold ({rsi:.1f})")
            reasons.append("MACD bullish crossover")
            reasons.append("Price above SMA50")
        
        # SHORT conditions
        elif rsi > 70 and macd_hist < 0 and price < sma50:
            direction = Direction.SHORT
            # Base confidence + RSI overbought factor
            confidence = 0.60 + (rsi - 70) / 100
            reasons.append(f"RSI overbought ({rsi:.1f})")
            reasons.append("MACD bearish crossover")
            reasons.append("Price below SMA50")
        
        # Confidence adjustments
        if adx > 25:
            confidence += 0.05
            reasons.append(f"Strong trend (ADX: {adx:.1f})")
        
        # Cap confidence at 0.95
        confidence = min(confidence, 0.95)
        
        reasoning = "; ".join(reasons) if reasons else "No clear signal"
        
        return direction, confidence, reasoning
    
    def _calculate_levels(
        self,
        direction: Direction,
        quote: Dict[str, Any],
        indicators: Dict[str, Any]
    ) -> tuple[float, float, float]:
        """
        Calculate entry, stop, and target levels.
        
        Uses ATR for stop/target calculation (2x ATR for stop, 3x for target).
        
        Args:
            direction: Trade direction
            quote: Quote data
            indicators: Indicator values
            
        Returns:
            Tuple of (entry, stop_loss, take_profit)
        """
        price = quote.get("last", 0)
        atr = indicators.get("ATR", price * 0.02)  # Default 2% if no ATR
        
        entry = price
        
        if direction == Direction.LONG:
            stop = price - (2 * atr)
            target = price + (3 * atr)
        else:  # SHORT
            stop = price + (2 * atr)
            target = price - (3 * atr)
        
        return round(entry, 2), round(stop, 2), round(target, 2)
