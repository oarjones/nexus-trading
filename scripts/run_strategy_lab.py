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
        
        # Paper Trading
        self.portfolio_manager = PaperPortfolioManager()
        self.order_simulator = OrderSimulator(
            portfolio_manager=self.portfolio_manager,
            market_data_client=self.mcp_client # In MVP we use MCP for market data
        )
        
        # Reporter
        self.reporter = CSVReporter()
        
        # Runner (Manual wiring)
        self.runner = StrategyRunner(
            mcp_client=self.mcp_client,
            config_path="config/strategies.yaml"
        )
        
        # Inject simulator and portfolio manager into runner to support Paper Execution
        # Note: StrategyRunner needs to be updated or we monkey-patch for MVP 
        # In this step we added support for single runs, but we also need to link the simulator.
        # The updated runner code in prev step has:
        # if hasattr(self, 'order_simulator') and self.order_simulator:
        self.runner.order_simulator = self.order_simulator
        self.runner.portfolio_manager = self.portfolio_manager
        
        # Scheduler
        self.scheduler = StrategyScheduler(
            runner=self.runner,
            config=self.runner.config.config # Access the raw config dict
        )

    async def start(self):
        """Start the Strategy Lab."""
        logger.info("Initializing Nexus Trading Strategy Lab...")
        self.running = True
        
        # Start Scheduler
        self.scheduler.start()
        
        logger.info("Strategy Lab Running. Press Ctrl+C to exit.")
        logger.info("Waiting for scheduled jobs...")
        
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
        # Windows: Wait indefinitely, rely on KeyboardInterrupt caught in __main__
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
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
        # Windows specific event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
        # Signal handling on Windows is different, using simple try/except for KeyboardInterrupt
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            pass
    else:
        asyncio.run(main())
