
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.strategies.runner import StrategyRunner
from src.agents.mcp_client import MCPClient
from src.universe.manager import UniverseManager
from src.universe.mcp_data_adapter import MCPDataProviderAdapter, MCPServers
from src.data.symbols import SymbolRegistry
from src.trading.paper.portfolio import PaperPortfolioManager
from src.trading.paper.order_simulator import OrderSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("test_simulation.log")
    ]
)
logger = logging.getLogger("test_simulation")

async def run_test():
    logger.info("STARTING TEST SIMULATION")
    
    try:
        # Initialize components
        mcp_client = MCPClient(timeout=10.0)
        mcp_servers = MCPServers.from_env()
        
        # Check MCP health
        logger.info("Checking MCP Servers health...")
        servers = [
            ("MarketData", mcp_servers.market_data),
            ("Technical", mcp_servers.technical),
            ("Risk", mcp_servers.risk),
            ("ML Models", mcp_servers.ml_models)
        ]
        
        for name, url in servers:
            try:
                healthy = await mcp_client.health_check(url)
                status = "UP" if healthy else "DOWN"
                logger.info(f"{name} ({url}): {status}")
            except Exception as e:
                logger.warning(f"{name} check error: {e}")

        # Universe
        registry = SymbolRegistry('config/symbols.yaml')
        data_adapter = MCPDataProviderAdapter(mcp_client, mcp_servers)
        universe_manager = UniverseManager(registry, data_adapter)
        
        # Paper Trading
        portfolio_manager = PaperPortfolioManager()
        order_simulator = OrderSimulator(portfolio_manager, mcp_client)
        
        # Runner
        runner = StrategyRunner(
            mcp_client=mcp_client,
            config_path="config/strategies.yaml",
            universe_manager=universe_manager
        )
        runner.order_simulator = order_simulator
        runner.portfolio_manager = portfolio_manager
        
        from src.strategies.interfaces import MarketRegime
        
        logger.info("1. Updating Universe (Screening)...")
        # Assume BULL regime for testing to get max candidates
        await universe_manager.run_daily_screening(MarketRegime.BULL)
        logger.info(f"Active User Symbols: {len(universe_manager.active_symbols)}")
        
        logger.info("2. Running Strategy Cycle...")
        # Get active strategies from config
        strategies = runner.config.get("strategies", {})
        active_strategies = [sid for sid, s in strategies.items() if s.get("enabled", False)]
        
        logger.info(f"Active Strategies to test: {active_strategies}")
        
        for strategy_id in active_strategies:
            logger.info(f"--- Testing {strategy_id} ---")
            try:
                signals = await runner.run_single_strategy(strategy_id)
                logger.info(f"Signals generated for {strategy_id}: {len(signals)}")
            except Exception as e:
                logger.error(f"ERROR running {strategy_id}: {e}", exc_info=True)
                
        logger.info("TEST SIMULATION COMPLETED")
        return True
        
    except Exception as e:
        logger.error(f"CRITICAL ERROR: {e}", exc_info=True)
        return False
    finally:
        await mcp_client.close()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_test())
