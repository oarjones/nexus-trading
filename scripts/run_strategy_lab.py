import asyncio
import logging
import signal
import sys
import os
from pathlib import Path

# Add project root to python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from src.strategies.runner import StrategyRunner
from src.scheduling.scheduler import StrategyScheduler
from src.metrics.exporters.csv_reporter import CSVReporter
from src.trading.paper.portfolio import PaperPortfolioManager
from src.trading.paper.order_simulator import OrderSimulator
from src.agents.mcp_client import MCPClient, MCPServers
from src.universe.manager import UniverseManager
from src.universe.mcp_data_adapter import MCPDataProviderAdapter
from src.data.symbols import SymbolRegistry
from src.monitoring.status_writer import StatusWriter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("strategy_lab.log")
    ]
)
logger = logging.getLogger("strategy_lab")

class StrategyLab:
    def __init__(self):
        self.running = False
        
        # Initialize components
        self.mcp_client = MCPClient()
        self.mcp_servers = MCPServers.from_env()
        
        # 1. Status Writer (Monitoring)
        self.status_writer = StatusWriter()
        
        # 2. Universe Manager
        self.registry = SymbolRegistry('config/symbols.yaml')
        self.data_adapter = MCPDataProviderAdapter(
            mcp_client=self.mcp_client,
            servers_config=self.mcp_servers
        )
        self.universe_manager = UniverseManager(
            symbol_registry=self.registry,
            data_provider=self.data_adapter
        )
        
        # 3. Paper Trading Infrastructure
        self.portfolio_manager = PaperPortfolioManager()
        self.order_simulator = OrderSimulator(
            portfolio_manager=self.portfolio_manager,
            market_data_client=self.mcp_client
        )
        
        # 4. Reporter
        self.reporter = CSVReporter()
        
        # 5. Runner
        self.runner = StrategyRunner(
            mcp_client=self.mcp_client,
            config_path="config/strategies.yaml",
            universe_manager=self.universe_manager,
            status_writer=self.status_writer
        )
        
        # Inject simulator and portfolio manager into runner
        self.runner.order_simulator = self.order_simulator
        self.runner.portfolio_manager = self.portfolio_manager
        
        # 6. Scheduler
        self.scheduler = StrategyScheduler(
            runner=self.runner,
            config=self.runner.config.config
        )

    async def start(self):
        """Start the Strategy Lab."""
        logger.info("Initializing Nexus Trading Strategy Lab...")
        self.running = True
        
        # Start Status Writer
        self.status_writer.start()
        
        # Start Scheduler
        self.scheduler.start()
        
        logger.info("Strategy Lab Running. Press Ctrl+C to exit.")
        logger.info(f"Registered Symbols: {self.registry.count()}")
        logger.info("Waiting for scheduled jobs...")
        
        # Initial status update
        self.status_writer.set_active_symbols_count(0) # Initially 0 until screening
        if self.scheduler.next_run_time:
             self.status_writer.set_next_execution(self.scheduler.next_run_time, None)

        # Main keep-alive loop
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Main loop cancelled.")
            
    async def stop(self):
        """Graceful shutdown."""
        logger.info("Shutting down Strategy Lab...")
        self.running = False
        self.scheduler.stop()
        await self.status_writer.stop()
        
        # Generate final report on exit
        logger.info("Generating final daily report...")
        await self.reporter.generate_daily_report(
            portfolios=self.portfolio_manager.portfolios
        )
        
        # Save persistence
        self.portfolio_manager.save_state()
        logger.info("Portfolio state saved.")
        logger.info("Shutdown complete.")

async def main():
    lab = StrategyLab()
    
    # Run lab in background
    lab_task = asyncio.create_task(lab.start())
    
    # Handle signals/stop
    if sys.platform != 'win32':
        loop = asyncio.get_running_loop()
        stop_signal = asyncio.Event()
        
        def signal_handler():
            logger.info("Signal received, stopping...")
            stop_signal.set()
            
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
            
        await stop_signal.wait()
        
    else:
        # Windows handling
        logger.info("Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
    
    # Stop lab
    await lab.stop()
    lab_task.cancel()
    try:
        await lab_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
    else:
        asyncio.run(main())
