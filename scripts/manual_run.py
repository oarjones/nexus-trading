
import asyncio
import logging
import os
import sys

# Add project root to path BEFORE imports
sys.path.append(os.getcwd())

from src.strategies.runner import StrategyRunner
from src.shared.infrastructure.database import get_db
from src.universe.manager import UniverseManager
from src.strategies.interfaces import MarketRegime
from src.data.symbols import SymbolRegistry
from src.universe.mcp_data_adapter import MCPDataProviderAdapter
from src.agents.mcp_client import MCPServers

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("manual_run")

async def run_strategies():
    project_root = os.getcwd() # verification_script style
    sys.path.append(project_root)
    
    # Set Env vars for MCP
    os.environ["MCP_TRANSPORT"] = "http"
    os.environ["MCP_CONFIG_PATH"] = os.path.join(project_root, "config", "mcp-servers.yaml")
    
    config_path = os.path.join(project_root, "config", "strategies.yaml")
    
    logger.info("Initializing StrategyRunner...")
    
    # Initialize DB (context manager usually required or ensuring engine exists)
    # StrategyRunner initializes its own things, but let's be safe.
    
    from src.agents.mcp_client import MCPClient
    mcp_client = MCPClient()
    servers = MCPServers.from_env()
    
    # Initialize dependencies for UniverseManager
    symbol_registry = SymbolRegistry(os.path.join(project_root, "config", "symbols.yaml"))
    data_provider = MCPDataProviderAdapter(mcp_client, servers)
    
    # Initialize Universe Manager
    universe_manager = UniverseManager(
        symbol_registry=symbol_registry,
        data_provider=data_provider,
        db_pool=None
    )
    
    # Run daily screening to populate active universe
    logger.info("Running daily screening to populate universe...")
    # Mocking regime/context for screening if needed, or just force BULL
    daily_universe = await universe_manager.run_daily_screening(MarketRegime.BULL, force=True)
    active_symbols = daily_universe.active_symbols
    logger.info(f"Populated universe with {len(active_symbols)} symbols: {active_symbols}")

    runner = StrategyRunner(
        config_path=config_path,
        mcp_client=mcp_client,
        db_session=None,
        universe_manager=universe_manager
    ) 
    
    # We need to manually register simple logging or just run them.
    # Strategies: 'hmm_rules', 'ai_agent_swing'
    
    strategies = ['hmm_rules', 'ai_agent_swing']
    
    for strat in strategies:
        print(f"\n{'='*50}")
        print(f"Running strategy: {strat}")
        print(f"{'='*50}")
        try:
           signals = await runner.run_single_strategy(strat)
           print(f"Signals generated: {len(signals)}")
           for s in signals:
               print(f" - {s}")
        except Exception as e:
            logger.error(f"Error executing {strat}: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(run_strategies())
