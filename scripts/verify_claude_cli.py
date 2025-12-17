
import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from src.agents.llm.factory import LLMAgentFactory
from src.agents.llm.interfaces import AgentContext, AutonomyLevel, RegimeInfo, MarketContext, PortfolioSummary, RiskLimits
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_claude_cli():
    """Confirms that Claude CLI agent can be instantiated and run."""
    print("--- Starting Verification of Claude CLI Agent ---")
    
    # 1. Instantiate
    try:
        agent = LLMAgentFactory.create_from_config()
        print(f"✅ Agent instantiated: {agent.provider} (ID: {agent.agent_id})")
    except Exception as e:
        print(f"❌ Failed to instantiate agent: {e}")
        return

    if agent.provider != "claude_cli":
        print(f"❌ Verification Failed: Expected 'claude_cli' provider, got '{agent.provider}'. Check config.")
        return

    # 2. Create Dummy Context
    context = AgentContext(
        context_id="test_ctx",
        timestamp=datetime.now(timezone.utc),
        regime=RegimeInfo(regime="BULL", confidence=0.8, probabilities={}, model_id="test"),
        market=MarketContext(spy_change_pct=0.5, qqq_change_pct=0.8, vix_level=15.0, vix_change_pct=-1.0, market_breadth=0.6, sector_rotation={}),
        portfolio=PortfolioSummary(total_value=10000, cash_available=10000, invested_value=0, positions=[], daily_pnl=0, daily_pnl_pct=0, total_pnl=0, total_pnl_pct=0),
        watchlist=(),
        risk_limits=RiskLimits(max_position_pct=0.1, max_portfolio_risk_pct=0.02, max_daily_trades=5, max_daily_loss_pct=0.02, current_daily_trades=0, current_daily_pnl_pct=0),
        autonomy_level=AutonomyLevel.MODERATE,
        notes="Please verify you can search the web. What is the current price of Ethereum (ETH) in USD? Use your tools."
    )

    # 3. Execute Decision
    print("\n--- Sending Request to Claude CLI (This may take a moment) ---")
    try:
        decision = await agent.decide(context)
        print("\n✅ Decision Received!")
        print(f"ID: {decision.decision_id}")
        print(f"Market View: {decision.market_view}")
        print(f"Reasoning: {decision.reasoning}")
        print(f"Signals: {len(decision.signals)}")
        
        if "Ethereum" in decision.reasoning or "ETH" in decision.reasoning:
             print("✅ Reasoning mentions Ethereum/ETH, suggesting context was processed.")
        else:
             print("⚠️ Reasoning does NOT mention Ethereum. Check logs if search happened.")

    except Exception as e:
        print(f"❌ Error during decision execution: {e}")

if __name__ == "__main__":
    asyncio.run(verify_claude_cli())
