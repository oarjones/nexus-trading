"""
Ejemplo de uso del sistema de Competición de Trading.

Este script demuestra el flujo completo:
1. Onboarding inicial (una vez)
2. Sesiones diarias con métricas y ranking
3. Actualización de métricas tras trades
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load env vars
load_dotenv()

# Setup path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_competition_example():
    """Ejemplo completo del flujo de competición."""
    
    from src.agents.llm.agents.competition_agent import CompetitionClaudeAgent
    from src.agents.llm.interfaces import (
        AgentContext, RegimeInfo, MarketContext, 
        PortfolioSummary, PortfolioPosition, RiskLimits, 
        AutonomyLevel
    )
    
    print("=" * 70)
    print("🏆 NEXUS TRADING CHAMPIONSHIP - DEMO")
    print("=" * 70)
    
    # =========================================================================
    # 1. CREAR AGENTE
    # =========================================================================
    print("\n📦 Creando agente de competición...")
    
    agent = CompetitionClaudeAgent(
        timeout_seconds=180.0,
        state_file="./data/competition_demo_state.json"
    )
    
    status = agent.get_competition_status()
    print(f"   Estado actual: Día {status['day']}, Onboarded: {status['is_onboarded']}")
    
    # =========================================================================
    # 2. ONBOARDING (SI ES NECESARIO)
    # =========================================================================
    if not status['is_onboarded']:
        print("\n🎓 Iniciando onboarding...")
        print("   (Esto solo ocurre UNA VEZ)")
        
        onboarded = await agent.ensure_onboarded()
        
        if onboarded:
            print("   ✅ Onboarding completado!")
        else:
            print("   ❌ Onboarding fallido")
            return
    else:
        print(f"\n✅ Agente ya está onboarded (Día {status['day']} de competición)")
    
    # =========================================================================
    # 3. SIMULAR SESIÓN DIARIA
    # =========================================================================
    print("\n📅 Iniciando sesión de trading...")
    
    # Crear contexto con posiciones simuladas
    positions = (
        PortfolioPosition(
            symbol="NVDA",
            quantity=10,
            avg_entry_price=140.50,
            current_price=145.20,
            unrealized_pnl=47.0,
            unrealized_pnl_pct=3.34,
            holding_days=3
        ),
        PortfolioPosition(
            symbol="AAPL",
            quantity=15,
            avg_entry_price=178.00,
            current_price=175.50,
            unrealized_pnl=-37.50,
            unrealized_pnl_pct=-1.40,
            holding_days=5
        ),
    )
    
    context = AgentContext(
        context_id=f"session_{datetime.now().strftime('%Y%m%d')}",
        timestamp=datetime.now(timezone.utc),
        regime=RegimeInfo(
            regime="BULL",
            confidence=0.72,
            probabilities={"BULL": 0.72, "BEAR": 0.08, "SIDEWAYS": 0.15, "VOLATILE": 0.05},
            model_id="hmm_v1",
            days_in_regime=5
        ),
        market=MarketContext(
            spy_change_pct=0.45,
            qqq_change_pct=0.68,
            vix_level=15.8,
            vix_change_pct=-3.2,
            market_breadth=0.58,
            sector_rotation={"Technology": 1.2, "Healthcare": 0.3, "Energy": -0.5}
        ),
        portfolio=PortfolioSummary(
            total_value=26250.0,  # Empezamos con 25k + ganancias
            cash_available=18500.0,
            invested_value=7750.0,
            positions=positions,
            daily_pnl=125.0,
            daily_pnl_pct=0.48,
            total_pnl=1250.0,
            total_pnl_pct=5.0
        ),
        watchlist=(),  # El agente usará web search
        risk_limits=RiskLimits(
            max_position_pct=20.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=3,
            max_daily_loss_pct=2.0,
            current_daily_trades=0,
            current_daily_pnl_pct=0.48
        ),
        autonomy_level=AutonomyLevel.MODERATE,
        notes="Sesión de demo. El sector tech muestra fortaleza. Buscar oportunidades en semiconductores."
    )
    
    print("\n🤖 Ejecutando análisis del agente...")
    print("   (El agente usará web search para obtener información actualizada)")
    print("   (Esto puede tardar 1-3 minutos)")
    
    decision = await agent.decide(context)
    
    # =========================================================================
    # 4. MOSTRAR RESULTADOS
    # =========================================================================
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DE LA SESIÓN")
    print("=" * 70)
    
    print(f"\n🆔 Decision ID: {decision.decision_id}")
    print(f"📈 Market View: {decision.market_view.value}")
    print(f"🎯 Confidence: {decision.confidence:.0%}")
    print(f"⏱️ Execution Time: {decision.execution_time_ms}ms")
    
    print(f"\n📝 Reasoning:")
    print("-" * 50)
    print(decision.reasoning[:1500] + "..." if len(decision.reasoning) > 1500 else decision.reasoning)
    
    print(f"\n📊 Signals Generated: {len(decision.signals)}")
    if decision.signals:
        for i, sig in enumerate(decision.signals, 1):
            print(f"\n   Signal #{i}:")
            print(f"   Symbol: {sig.symbol}")
            print(f"   Direction: {sig.direction.value}")
            print(f"   Entry: ${sig.entry_price:.2f}")
            print(f"   Stop Loss: ${sig.stop_loss:.2f}")
            print(f"   Take Profit: ${sig.take_profit:.2f}")
            print(f"   Size: {sig.size_suggestion:.1%} of portfolio")
            print(f"   Confidence: {sig.confidence:.0%}")
            print(f"   Reasoning: {sig.reasoning[:200]}...")
    
    # =========================================================================
    # 5. MOSTRAR ESTADO DE LA COMPETICIÓN
    # =========================================================================
    print("\n" + "=" * 70)
    print("🏆 ESTADO DE LA COMPETICIÓN")
    print("=" * 70)
    
    status = agent.get_competition_status()
    print(f"   Día: {status['day']}")
    print(f"   Score: {status['score']:.1f}")
    print(f"   Retorno Total: {status['metrics']['total_return']:.2f}%")
    print(f"   Sharpe Ratio: {status['metrics']['sharpe']:.2f}")
    print(f"   Max Drawdown: {status['metrics']['max_drawdown']:.2f}%")
    print(f"   Win Rate: {status['metrics']['win_rate']:.1f}%")
    print(f"   Total Trades: {status['metrics']['total_trades']}")
    
    # =========================================================================
    # 6. SIMULAR CIERRE DE TRADE (para actualizar métricas)
    # =========================================================================
    print("\n" + "=" * 70)
    print("💹 SIMULANDO CIERRE DE TRADE...")
    print("=" * 70)
    
    # Simular que cerramos NVDA con ganancia
    closed_trades = [
        {
            "symbol": "NVDA",
            "direction": "LONG",
            "entry_price": 140.50,
            "exit_price": 148.00,
            "pnl": 75.0,
            "pnl_pct": 5.34
        }
    ]
    
    agent.update_trade_results(closed_trades)
    print(f"   ✅ Trade cerrado: NVDA +5.34%")
    
    # Avanzar día
    await agent.advance_day(daily_return=0.8)
    
    final_status = agent.get_competition_status()
    print(f"\n   📈 Nuevo estado:")
    print(f"   Día: {final_status['day']}")
    print(f"   Retorno Total: {final_status['metrics']['total_return']:.2f}%")
    print(f"   Win Rate: {final_status['metrics']['win_rate']:.1f}%")
    
    print("\n" + "=" * 70)
    print("✅ DEMO COMPLETADA")
    print("=" * 70)
    print("\nEl estado se ha guardado. La próxima ejecución continuará")
    print("desde el día actual sin necesidad de hacer onboarding de nuevo.")
    print("\nPara reiniciar la competición, usa: agent.reset_competition()")


if __name__ == "__main__":
    asyncio.run(run_competition_example())
