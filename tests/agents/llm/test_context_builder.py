"""Tests para ContextBuilder."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.agents.llm.context_builder import ContextBuilder
from src.agents.llm.interfaces import AutonomyLevel, AgentContext


class MockMCPClient:
    def __init__(self):
        self.call = AsyncMock()


@pytest.fixture
def mock_mcp():
    client = MockMCPClient()
    
    # Configurar respuestas default
    client.call.side_effect = lambda server, tool, params: default_responses(server, tool, params)
    return client


def default_responses(server, tool, params):
    if server == "mcp-ml-models" and tool == "get_regime":
        return {
            "regime": "BULL",
            "confidence": 0.8,
            "probabilities": {"BULL": 0.8, "BEAR": 0.1, "SIDEWAYS": 0.1},
            "model_id": "hmm_test"
        }
    
    if server == "mcp-market-data" and tool == "get_quote":
        symbol = params.get("symbol")
        return {
            "symbol": symbol,
            "price": 100.0,
            "change_pct": 1.5,
            "volume": 1000000,
            "avg_volume_20d": 900000
        }
    
    if server == "mcp-technical" and tool == "get_indicators":
        return {
            "RSI": {"value": 60},
            "MACD": {"macd": 0.5, "signal": 0.2, "histogram": 0.3},
            "SMA": {"sma_20": 98.0, "sma_50": 95.0, "sma_200": 90.0},
            "BB": {"upper": 102.0, "middle": 100.0, "lower": 98.0},
            "ATR": {"value": 2.0},
            "ADX": {"value": 30},
            "momentum": {"1m": 5.0, "3m": 10.0, "6m": 15.0}
        }
    
    if server == "mcp-ibkr" and tool == "get_portfolio":
        return {
            "total_value": 50000.0,
            "cash_available": 40000.0,
            "invested_value": 10000.0,
            "positions": [
                {
                    "symbol": "AAPL",
                    "quantity": 10,
                    "avg_entry_price": 150.0,
                    "current_price": 160.0,
                    "unrealized_pnl": 100.0,
                    "unrealized_pnl_pct": 6.67,
                    "holding_days": 5
                }
            ],
            "daily_pnl": 200.0,
            "daily_pnl_pct": 0.4,
            "total_pnl": 1000.0,
            "total_pnl_pct": 2.0
        }
    
    if server == "mcp-risk" and tool == "get_limits":
        return {
            "max_position_pct": 5.0,
            "max_portfolio_risk_pct": 2.0,
            "max_daily_trades": 5,
            "max_daily_loss_pct": 3.0,
            "current_daily_trades": 1,
            "current_daily_pnl_pct": 0.4
        }
        
    return {}


@pytest.mark.asyncio
async def test_build_context_success(mock_mcp):
    builder = ContextBuilder(mock_mcp)
    
    context = await builder.build(
        watchlist=["AAPL", "MSFT"],
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    assert isinstance(context, AgentContext)
    assert context.regime.regime == "BULL"
    assert context.portfolio.total_value == 50000.0
    assert len(context.watchlist) == 2
    assert context.watchlist[0].symbol == "AAPL"
    assert context.risk_limits.can_trade is True


@pytest.mark.asyncio
async def test_build_context_partial_failure(mock_mcp):
    # Simular fallo en mcp-ml-models
    async def side_effect(server, tool, params):
        if server == "mcp-ml-models":
            raise Exception("Connection error")
        return default_responses(server, tool, params)
    
    mock_mcp.call.side_effect = side_effect
    
    builder = ContextBuilder(mock_mcp)
    
    context = await builder.build(
        watchlist=["AAPL"],
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    # Debe usar default regime (SIDEWAYS)
    assert context.regime.regime == "SIDEWAYS"
    assert context.regime.model_id == "default_fallback"
    
    # El resto debe estar bien
    assert context.portfolio.total_value == 50000.0
    assert len(context.watchlist) == 1


@pytest.mark.asyncio
async def test_caching(mock_mcp):
    builder = ContextBuilder(mock_mcp)
    
    # Primera llamada
    await builder.build(["AAPL"])
    assert mock_mcp.call.call_count > 0
    call_count_after_first = mock_mcp.call.call_count
    
    # Segunda llamada inmediata (debe usar cache para regime y market)
    await builder.build(["AAPL"])
    
    # Las llamadas a regime y market deben estar cacheadas
    # Pero watchlist y portfolio siempre se consultan (o al menos watchlist cambia)
    # En la implementación actual, _get_regime y _get_market_context usan cache.
    # _get_portfolio y _get_watchlist_data NO usan cache (correcto, cambian rápido).
    
    # Verificamos que get_regime no se llamó de nuevo
    regime_calls = [c for c in mock_mcp.call.mock_calls if "get_regime" in str(c)]
    assert len(regime_calls) == 1
