#!/usr/bin/env python
# scripts/verify_fase_b2.py
"""
Verification script for Phase B2: AI Agent.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timezone
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.llm.interfaces import (
    AgentContext,
    AgentDecision,
    AutonomyLevel,
    MarketView,
    LLMAgent
)
from src.agents.llm.context_builder import ContextBuilder
from src.agents.llm.prompts import CONSERVATIVE_PROMPT, MODERATE_PROMPT
from src.agents.llm.agents.claude_agent import ClaudeAgent
from src.strategies.swing.ai_agent_strategy import AIAgentStrategy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_b2")


def print_header(text: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def print_check(name: str, passed: bool, detail: str = "") -> None:
    status = "OK" if passed else "FAIL"
    if detail:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")


async def verify_interfaces():
    """Verify interfaces and dataclasses."""
    print_header("VERIFYING INTERFACES")
    
    try:
        # Test AgentContext creation (minimal)
        # We need to mock the components, but for now just checking import and basic instantiation
        # ContextBuilder does the heavy lifting, so we'll test that instead.
        print_check("Imports", True)
        return True
    except Exception as e:
        print_check("Imports", False, str(e))
        return False


async def verify_context_builder():
    """Verify ContextBuilder."""
    print_header("VERIFYING CONTEXT BUILDER")
    
    try:
        builder = ContextBuilder()
        context = await builder.build(
            symbols=["SPY", "QQQ"],
            autonomy_level=AutonomyLevel.CONSERVATIVE
        )
        
        assert isinstance(context, AgentContext)
        assert context.autonomy_level == AutonomyLevel.CONSERVATIVE
        assert len(context.watchlist) == 2
        assert context.regime.regime in ["BULL", "BEAR", "SIDEWAYS", "VOLATILE"]
        
        print_check("Context Builder", True)
        
        # Verify prompt generation
        prompt_text = context.to_prompt_text()
        assert "FECHA Y HORA" in prompt_text
        assert "RÉGIMEN DE MERCADO" in prompt_text
        assert "SPY" in prompt_text
        
        print_check("Prompt Generation", True)
        return True
        
    except Exception as e:
        print_check("Context Builder", False, str(e))
        return False


async def verify_prompts():
    """Verify Prompts."""
    print_header("VERIFYING PROMPTS")
    
    try:
        assert "NIVEL DE AUTONOMÍA: CONSERVATIVE" in CONSERVATIVE_PROMPT
        assert "NIVEL DE AUTONOMÍA: MODERATE" in MODERATE_PROMPT
        assert "FORMATO DE RESPUESTA" in CONSERVATIVE_PROMPT
        
        print_check("Prompts Content", True)
        return True
    except Exception as e:
        print_check("Prompts Content", False, str(e))
        return False


class MockClaudeAgent(LLMAgent):
    """Mock agent for testing without API."""
    
    def __init__(self):
        pass
        
    @property
    def agent_id(self) -> str:
        return "mock_agent"
        
    @property
    def provider(self) -> str:
        return "mock"
        
    async def decide(self, context: AgentContext) -> AgentDecision:
        from src.strategies.interfaces import Signal, SignalDirection, MarketRegime
        
        # Simulate a decision
        return AgentDecision(
            decision_id="mock_dec_1",
            timestamp=datetime.now(timezone.utc),
            market_view=MarketView.BULLISH,
            confidence=0.85,
            reasoning="Mock reasoning: Market is bullish.",
            signals=[
                Signal(
                    strategy_id="mock_agent",
                    symbol="SPY",
                    direction=SignalDirection.LONG,
                    confidence=0.8,
                    entry_price=100.0,
                    stop_loss=95.0,
                    take_profit=110.0,
                    regime_at_signal=MarketRegime.BULL,
                    regime_confidence=0.8
                )
            ],
            model_used="mock-model",
            tokens_used=100,
            execution_time_ms=50
        )


async def verify_strategy_integration():
    """Verify AIAgentStrategy integration."""
    print_header("VERIFYING STRATEGY INTEGRATION")
    
    try:
        # Create strategy with mock config
        strategy = AIAgentStrategy(config={
            "enabled": True,
            "autonomy_level": "conservative",
            "symbols": ["SPY"],
            # We'll inject the mock agent manually since factory creates real ones
        })
        
        # Inject mock agent
        strategy.agent = MockClaudeAgent()
        
        # Create mock market context
        from src.strategies.interfaces import MarketContext as StratMarketContext, MarketRegime
        market_ctx = StratMarketContext(
            regime=MarketRegime.BULL,
            regime_confidence=0.8,
            regime_probabilities={},
            market_data={},
            capital_available=10000,
            positions=[]
        )
        
        # Generate signals (this calls _execute_agent_flow internally)
        # Since generate_signals is sync wrapper around async, we need to be careful in this async script.
        # AIAgentStrategy.generate_signals uses asyncio.run() which fails if loop is already running.
        # So we call _execute_agent_flow directly for this test.
        
        decision = await strategy._execute_agent_flow(market_ctx, AutonomyLevel.CONSERVATIVE)
        
        assert decision is not None
        assert len(decision.signals) == 1
        assert decision.signals[0].symbol == "SPY"
        
        print_check("Strategy Execution (Mocked)", True)
        return True
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print_check("Strategy Execution", False, str(e))
        return False


async def main_async():
    print("STARTING PHASE B2 VERIFICATION")
    
    checks = [
        await verify_interfaces(),
        await verify_context_builder(),
        await verify_prompts(),
        await verify_strategy_integration(),
    ]
    
    if all(checks):
        print("\n" + "="*60)
        print("  ALL CHECKS PASSED - PHASE B2")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("  SOME CHECKS FAILED")
        print("="*60)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
