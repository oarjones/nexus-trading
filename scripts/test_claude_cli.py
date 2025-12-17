"""
Script de prueba para Claude Code CLI Agent.

Verifica:
1. Invocación correcta de 'claude' CLI.
2. Capacidad de streaming y parsing JSON.
3. Uso implícito de herramientas (búsqueda web) si se solicita.
"""

import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Setup path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))
load_dotenv(project_root / ".env")

# Logging
logging.basicConfig(level=logging.DEBUG)

from src.agents.llm.factory import LLMAgentFactory
from src.agents.llm.interfaces import AgentContext, RegimeInfo, MarketContext, PortfolioSummary, RiskLimits, AutonomyLevel
from datetime import datetime, timezone

async def test_cli():
    print("=== TEST CLAUDE CLI AGENT ===")
    
    # 1. Crear Agente
    print("Creating Agent...")
    try:
        agent = LLMAgentFactory.create(provider="claude_cli")
        print(f"Agent created: {agent.provider} ({agent.agent_id})")
    except Exception as e:
        print(f"FAILED to create agent: {e}")
        return

    # 2. Crear Contexto Dummy
    # Pediremos explícitamente información reciente para forzar búsqueda
    context = AgentContext(
        context_id="test_cli_1",
        timestamp=datetime.now(timezone.utc),
        regime=RegimeInfo(regime="BULL", confidence=0.8, probabilities={}, model_id="test"),
        market=MarketContext(
             spy_change_pct=0.0, qqq_change_pct=0.0, vix_level=15.0, vix_change_pct=0.0,
             market_breadth=0.5, sector_rotation={}
        ),
        portfolio=PortfolioSummary(
            total_value=100000, cash_available=100000, invested_value=0, 
            positions=[], daily_pnl=0, daily_pnl_pct=0, total_pnl=0, total_pnl_pct=0
        ),
        watchlist=(),
        risk_limits=RiskLimits(5, 2, 5, 2, 0, 0),
        autonomy_level=AutonomyLevel.CONSERVATIVE,
        notes="URGENT: Using your web search tools, find out the current price of Bitcoin and key news from the last 24 hours. Incorporate this into your reasoning."
    )
    
    # 3. Ejecutar Decisión
    print("\nRunning decide() (this launches 'claude' process)...")
    try:
        decision = await agent.decide(context)
        
        print("\n=== DECISION RECEIVED ===")
        print(f"ID: {decision.decision_id}")
        print(f"Market View: {decision.market_view}")
        print(f"Confidence: {decision.confidence}")
        print(f"Reasoning:\n{decision.reasoning}")
        print(f"Execution Time: {decision.execution_time_ms}ms")
        
    except Exception as e:
        print(f"\n❌ ERROR executing decide: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cli())
