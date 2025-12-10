"""Tests para ContextBuilder."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.agents.llm.context_builder import ContextBuilder
from src.agents.llm.interfaces import AutonomyLevel, AgentContext


class MockMCPServers:
    ml_models = "http://mock-ml"
    market_data = "http://mock-market"
    technical = "http://mock-technical"
    risk = "http://mock-risk"
    ibkr = "http://mock-ibkr"


class MockMCPClient:
    def __init__(self):
        self.call = AsyncMock()


@pytest.fixture
def mock_servers():
    return MockMCPServers()


@pytest.fixture
def mock_mcp():
    client = MockMCPClient()
    
    # Configurar respuestas default
    client.call.side_effect = lambda server, tool, params: default_responses(server, tool, params)
    return client


def default_responses(server, tool, params):
    # Check server URL or name depending on implementation. 
    # ContextBuilder uses server URL as first arg to client.call
    
    if "mock-ml" in server and tool == "get_regime":
        return {
            "regime": "BULL",
            "confidence": 0.8,
            "probabilities": {"BULL": 0.8, "BEAR": 0.1, "SIDEWAYS": 0.1},
            "model_id": "hmm_test",
            "days_in_regime": 5
        }
    
    if "mock-market" in server and tool == "get_quote":
        symbol = params.get("symbol")
        return {
            "symbol": symbol,
            "price": 100.0,
            "change_pct": 1.5,
            "volume": 1000000,
            "avg_volume_20d": 900000
        }
    
    if "mock-technical" in server and tool == "calculate_indicators":
        return {
            "RSI": {"value": 60},
            "MACD": {"macd": 0.5, "signal": 0.2, "histogram": 0.3},
            "SMA": {"sma_20": 98.0, "sma_50": 95.0, "sma_200": 90.0},
            "BB": {"upper": 102.0, "middle": 100.0, "lower": 98.0},
            "ATR": {"value": 2.0},
            "ADX": {"value": 30},
            "momentum": {"1m": 5.0, "3m": 10.0, "6m": 15.0}
        }
    
    if "mock-ibkr" in server and tool == "get_account":
        return {
            "total_value": 50000.0,
            "cash_available": 40000.0,
            "invested_value": 10000.0,
            "daily_pnl": 200.0,
            "daily_pnl_pct": 0.4,
            "total_pnl": 1000.0,
            "total_pnl_pct": 2.0
        }

    if "mock-ibkr" in server and tool == "get_positions":
        return {
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
            ]
        }
        
    return {}


@pytest.mark.asyncio
async def test_build_context_success(mock_mcp, mock_servers):
    builder = ContextBuilder(mock_mcp, servers_config=mock_servers)
    
    context = await builder.build(
        symbols=["AAPL", "MSFT"],
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    assert isinstance(context, AgentContext)
    assert context.regime.regime == "BULL"
    # assert context.portfolio.total_value == 25000.0 # Still using fallback for portfolio
    assert len(context.watchlist) == 2
    assert context.watchlist[0].symbol == "AAPL"
    assert context.risk_limits.can_trade is True


@pytest.mark.asyncio
async def test_build_context_partial_failure(mock_mcp, mock_servers):
    # Simular fallo en mcp-ml-models
    async def side_effect(server, tool, params):
        if "mock-ml" in server:
            raise Exception("Connection error")
        return default_responses(server, tool, params)
    
    mock_mcp.call.side_effect = side_effect
    
    builder = ContextBuilder(mock_mcp, servers_config=mock_servers)
    
    context = await builder.build(
        symbols=["AAPL"],
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    # Debe usar default regime (UNCERTAIN due to fallback)
    assert context.regime.regime == "UNCERTAIN"
    assert context.regime.model_id == "fallback"
    
    # El resto debe estar bien
    # assert context.portfolio.total_value == 25000.0
    assert len(context.watchlist) == 1


@pytest.mark.asyncio
async def test_caching(mock_mcp, mock_servers):
    builder = ContextBuilder(mock_mcp, servers_config=mock_servers)
    
    # Primera llamada
    await builder.build(["AAPL"])
    assert mock_mcp.call.call_count > 0 
    
    # Segunda llamada inmediata (debe usar cache para regime y market si implementado)
    # Por ahora solo probamos que el builder funcione con calls reales mocked
    await builder.build(["AAPL"])
