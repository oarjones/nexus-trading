"""Tests para AIAgentStrategy."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.strategies.swing.ai_agent_strategy import AIAgentStrategy
from src.agents.llm.interfaces import AgentDecision, MarketView, AutonomyLevel
from src.strategies.interfaces import Signal


@pytest.fixture
def mock_dependencies():
    with patch("src.strategies.swing.ai_agent_strategy.LLMAgentFactory") as factory_mock, \
         patch("src.strategies.swing.ai_agent_strategy.ContextBuilder") as builder_mock:
        
        # Mock Agent
        agent_mock = AsyncMock()
        factory_mock.create_from_config.return_value = agent_mock
        
        # Mock Builder
        builder_instance = AsyncMock()
        builder_mock.return_value = builder_instance
        
        yield factory_mock, builder_mock, agent_mock, builder_instance


@pytest.mark.asyncio
async def test_generate_signals_success(mock_dependencies):
    factory_mock, builder_mock, agent_mock, builder_instance = mock_dependencies
    
    # Setup mocks
    mock_context = MagicMock()
    builder_instance.build.return_value = mock_context
    
    mock_signal = Signal(
        strategy_id="ai_agent_moderate",
        symbol="AAPL",
        direction="LONG",
        confidence=0.9,
        entry_price=150.0,
        stop_loss=145.0,
        take_profit=160.0,
        regime_at_signal="BULL",
        reasoning="Test"
    )
    
    mock_decision = AgentDecision(
        decision_id="dec_1",
        context_id="ctx_1",
        timestamp=MagicMock(),
        actions=[mock_signal],
        market_view=MarketView.BULLISH,
        reasoning="Test",
        key_factors=[],
        confidence=0.9,
        model_used="test",
        autonomy_level=AutonomyLevel.MODERATE,
        tokens_used=100,
        latency_ms=100
    )
    agent_mock.decide.return_value = mock_decision
    
    # Init strategy
    strategy = AIAgentStrategy(
        mcp_client=MagicMock(),
        symbols=["AAPL"]
    )
    
    # Run
    signals = await strategy.generate_signals(MagicMock())
    
    # Verify
    assert len(signals) == 1
    assert signals[0].symbol == "AAPL"
    assert signals[0].direction == "LONG"
    
    # Verify calls
    builder_instance.build.assert_called_once()
    agent_mock.decide.assert_called_once_with(mock_context)


@pytest.mark.asyncio
async def test_generate_signals_error(mock_dependencies):
    factory_mock, builder_mock, agent_mock, builder_instance = mock_dependencies
    
    # Setup error
    builder_instance.build.side_effect = Exception("Build error")
    
    strategy = AIAgentStrategy(
        mcp_client=MagicMock(),
        symbols=["AAPL"]
    )
    
    signals = await strategy.generate_signals(MagicMock())
    
    assert len(signals) == 0
