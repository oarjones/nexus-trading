"""Tests para ClaudeAgent."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone

from src.agents.llm.agents.claude_agent import ClaudeAgent
from src.agents.llm.interfaces import (
    AgentContext,
    AutonomyLevel,
    RegimeInfo,
    RiskLimits,
    PortfolioSummary,
    MarketView
)
from src.strategies.interfaces import SignalDirection


@pytest.fixture
def mock_anthropic():
    with patch("src.agents.llm.agents.claude_agent.anthropic.AsyncAnthropic") as mock:
        client = MagicMock()
        client.messages.create = AsyncMock()
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
        timestamp=datetime.now(timezone.utc),
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
    # Mock ContentBlock
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = """{
        "market_view": "bullish",
        "confidence": 0.85,
        "reasoning": "Test reasoning",
        "key_factors": ["Factor 1"],
        "signals": [
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
    }"""
    mock_response.content = [text_block]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    
    mock_anthropic.messages.create.return_value = mock_response
    
    agent = ClaudeAgent(api_key="test_key")
    decision = await agent.decide(sample_context)
    
    print(f"DEBUG: Decision reasoning: {decision.reasoning}")
    assert not decision.reasoning.startswith("ERROR"), f"Agent returned error: {decision.reasoning}"
    assert decision.market_view.value == "bullish"
    assert decision.confidence == 0.85
    assert len(decision.signals) == 1
    assert decision.signals[0].symbol == "AAPL"
    assert decision.signals[0].direction == SignalDirection.LONG


@pytest.mark.asyncio
async def test_decide_skip_volatile(mock_anthropic, sample_context):
    # Modificar contexto para VOLATILE
    volatile_context = AgentContext(
        context_id="ctx_test",
        timestamp=datetime.now(timezone.utc),
        regime=RegimeInfo("VOLATILE", 0.8, {}, "hmm"),
        market=MagicMock(),
        portfolio=PortfolioSummary(10000, 10000, 0, (), 0, 0, 0, 0),
        watchlist=(MagicMock(),),
        risk_limits=RiskLimits(5.0, 2.0, 5, 3.0, 0, 0),
        autonomy_level=AutonomyLevel.MODERATE
    )
    
    agent = ClaudeAgent(api_key="test_key")
    decision = await agent.decide(volatile_context)
    
    assert decision.market_view.value == "uncertain"
    assert len(decision.signals) == 0
    assert "VOLATILE" in decision.reasoning
    # No debe haber llamado a la API
    mock_anthropic.messages.create.assert_not_called()



