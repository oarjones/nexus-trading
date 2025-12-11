"""
Adapter that implements the DataProvider protocol using MCPClient.

Allows the UniverseManager to obtain market data through existing MCP servers
(mcp-market-data, mcp-technical).
"""

import logging
from typing import Protocol, List, Dict, Any, Optional

# Local imports
from src.agents.mcp_client import MCPClient, MCPServers

logger = logging.getLogger(__name__)


class MCPDataProviderAdapter:
    """
    Adapter that connects UniverseManager with MCP servers.
    
    Implements the DataProvider protocol required by UniverseManager:
    - get_quote(symbol) -> dict
    - get_indicators(symbol, indicators) -> dict
    - get_historical(symbol, days) -> list[dict]
    """
    
    def __init__(self, mcp_client: MCPClient, servers_config: MCPServers):
        """
        Args:
            mcp_client: Instance of MCPClient
            servers_config: MCPServers with server URLs
        """
        self.mcp = mcp_client
        self.servers = servers_config
        
    async def get_quote(self, symbol: str) -> dict:
        """
        Get current quote with volume.
        
        Returns:
            {
                "symbol": "SPY",
                "price": 450.0,
                "bid": 449.95,
                "ask": 450.05,
                "volume": 50000000,
                "avg_volume_20d": 45000000,
                "change_pct": 0.5
            }
        """
        try:
            result = await self.mcp.call(
                self.servers.market_data,
                "get_quote",
                {"symbol": symbol}
            )
            
            # Normalize response to expected format by UniverseManager
            # Handle different possible naming conventions from MCP
            price = result.get("price", result.get("last", 0))
            avg_vol = result.get("avg_volume", result.get("avgVolume", 0))
            change_pct = result.get("change_pct", result.get("changePercent", 0))
            
            return {
                "symbol": symbol,
                "price": float(price) if price is not None else 0.0,
                "bid": float(result.get("bid", 0)),
                "ask": float(result.get("ask", 0)),
                "volume": int(result.get("volume", 0)),
                "avg_volume_20d": int(avg_vol) if avg_vol is not None else 0,
                "change_pct": float(change_pct) if change_pct is not None else 0.0,
            }
            
        except Exception as e:
            logger.warning(f"Error getting quote for {symbol}: {e}")
            # Return values that will cause the symbol to be filtered out
            return {
                "symbol": symbol,
                "price": 0.0,
                "bid": 0.0,
                "ask": 0.0,
                "volume": 0,
                "avg_volume_20d": 0,
                "change_pct": 0.0,
            }
    
    async def get_indicators(self, symbol: str, indicators: List[str]) -> dict:
        """
        Get technical indicators.
        
        Args:
            symbol: Ticker symbol
            indicators: List of indicators ["rsi_14", "sma_200", "atr_14"]
            
        Returns:
            {
                "rsi_14": 55.0,
                "sma_200": 420.0,
                "atr_14": 5.5,
                ...
            }
        """
        try:
            # We assume 200 is enough for most indicators like SMA200
            result = await self.mcp.call(
                self.servers.technical,
                "calculate_indicators",
                {
                    "symbol": symbol,
                    "indicators": indicators,
                    "period": 200 
                }
            )
            
            # Extract values from structured response
            extracted = {}
            for ind in indicators:
                # The technical server might return nested structures
                # Try to extract the value in various ways
                if ind in result:
                    val = result[ind]
                    if isinstance(val, dict):
                        extracted[ind] = val.get("value", val.get("current", 0))
                    else:
                        extracted[ind] = val
                else:
                    # Search by alternative name (RSI vs rsi_14)
                    base_name = ind.split("_")[0].upper()
                    if base_name in result:
                        val = result[base_name]
                        # Handle potential dict return or direct value
                        extracted[ind] = val.get("value", 0) if isinstance(val, dict) else val
                    else:
                        extracted[ind] = 0
                        
            return extracted
            
        except Exception as e:
            logger.warning(f"Error getting indicators for {symbol}: {e}")
            return {ind: 0 for ind in indicators}
    
    async def get_historical(self, symbol: str, days: int) -> List[Dict[str, Any]]:
        """
        Get historical OHLCV data.
        
        Args:
            symbol: Ticker symbol
            days: Number of days of history
            
        Returns:
            [
                {"date": "2024-01-01", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000000},
                ...
            ]
        """
        try:
            result = await self.mcp.call(
                self.servers.market_data,
                "get_ohlcv",
                {
                    "symbol": symbol,
                    "timeframe": "1d",
                    "limit": days
                }
            )
            
            # Convert array format to list of dicts if necessary
            if isinstance(result, dict) and "close" in result:
                # Format: {"open": [...], "high": [...], ...}
                length = len(result.get("close", []))
                historical = []
                dates = result.get("dates", [None] * length)
                opens = result.get("open", [0] * length)
                highs = result.get("high", [0] * length)
                lows = result.get("low", [0] * length)
                closes = result.get("close", [0] * length)
                volumes = result.get("volume", [0] * length)
                
                for i in range(length):
                    historical.append({
                        "date": dates[i],
                        "open": opens[i],
                        "high": highs[i],
                        "low": lows[i],
                        "close": closes[i],
                        "volume": volumes[i],
                    })
                return historical
            
            # If it's already a list of dicts
            if isinstance(result, list):
                return result
                
            return []
            
        except Exception as e:
            logger.warning(f"Error getting historical for {symbol}: {e}")
            return []
