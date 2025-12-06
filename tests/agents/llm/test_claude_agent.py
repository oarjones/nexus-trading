"""Tests para ClaudeAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.agents.llm.agents.claude_agent import ClaudeAgent
from src.agents.llm.interfaces import (
    AgentContext,
    AutonomyLevel,
    RegimeInfo,
    RiskLimits,
    PortfolioSummary,
    MarketView
)


@pytest.fixture
def mock_anthropic():
    with patch("src.agents.llm.agents.claude_agent.anthropic.Anthropic") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def sample_context():
    market_mock = MagicMock()
    market_mock.vix_level = 20.0
    market_mock.to_summary.return_value = "Market Summary"
    
    watchlist_item = MagicMock()
    watchlist_item.to_summary.return_value = "Symbol Summary"
    
    return AgentContext(
        context_id="ctx_test",
        timestamp=datetime.utcnow(),
        regime=RegimeInfo("BULL", 0.8, {}, "hmm"),
        market=market_mock,
        portfolio=PortfolioSummary(10000, 10000, 0, (), 0, 0, 0, 0),
        watchlist=(watchlist_item,),
        risk_limits=RiskLimits(5.0, 2.0, 5, 3.0, 0, 0),
        autonomy_level=AutonomyLevel.MODERATE
    )


@pytest.mark.asyncio
async def test_decide_success(mock_anthropic, sample_context):
    # Mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="""
    ```json
    {
        "market_view": "bullish",
        "confidence": 0.85,
        "reasoning": "Test reasoning",
        "key_factors": ["Factor 1"],
        "actions": [
            {
                "symbol": "AAPL",
                "direction": "LONG",
                "entry_price": 150.0,
                "stop_loss": 145.0,
                "take_profit": 160.0,
                "size_suggestion": 0.03
            }
        ],
        "warnings": []
    }
    ```
    """)]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    
    mock_anthropic.messages.create.return_value = mock_response
    
    agent = ClaudeAgent(api_key="test_key")
    decision = await agent.decide(sample_context)
    
    assert decision.market_view == MarketView.BULLISH
    assert decision.confidence == 0.85
    assert len(decision.actions) == 1
    assert decision.actions[0].symbol == "AAPL"
    assert decision.actions[0].direction == "LONG"


@pytest.mark.asyncio
async def test_decide_skip_volatile(mock_anthropic, sample_context):
    # Modificar contexto para VOLATILE
    volatile_context = AgentContext(
        context_id="ctx_test",
        timestamp=datetime.utcnow(),
        regime=RegimeInfo("VOLATILE", 0.8, {}, "hmm"),
        market=MagicMock(),
        portfolio=PortfolioSummary(10000, 10000, 0, (), 0, 0, 0, 0),
        watchlist=(MagicMock(),),
        risk_limits=RiskLimits(5.0, 2.0, 5, 3.0, 0, 0),
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    agent = ClaudeAgent(api_key="test_key")
    decision = await agent.decide(volatile_context)
    
    assert decision.market_view == MarketView.UNCERTAIN
    assert len(decision.actions) == 0
    assert "VOLATILE" in decision.reasoning
    # No debe haber llamado a la API
    mock_anthropic.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_health_check(mock_anthropic):
    agent = ClaudeAgent(api_key="test_key")
    
    status = await agent.health_check()
    assert status["status"] == "healthy"
    assert status["model"] == "claude-sonnet-4-20250514"
