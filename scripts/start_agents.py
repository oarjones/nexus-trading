"""
Agent startup script.

Starts all autonomous trading agents in the correct order with proper
initialization and graceful shutdown handling.
"""

import asyncio
import signal
import sys
import os
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
import redis

from agents import (
    MessageBus,
    MCPServers,
    TechnicalAnalystAgent,
    RiskManagerAgent,
    OrchestratorAgent,
    load_config
)

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def wait_healthy(agent, timeout=30):
    """
    Wait for agent to become healthy.
    
    Args:
        agent: Agent to wait for
        timeout: Timeout in seconds
        
    Raises:
        TimeoutError: If agent doesn't become healthy in time
    """
    start = asyncio.get_event_loop().time()
    
    while True:
        health = agent.health()
        if health["status"] == "healthy":
            logger.info(f"Agent {agent.name} is healthy")
            return
        
        elapsed = asyncio.get_event_loop().time() - start
        if elapsed > timeout:
            raise TimeoutError(f"Agent {agent.name} did not become healthy within {timeout}s")
        
        await asyncio.sleep(1)


async def main():
    """Main startup routine."""
    logger.info("=" * 60)
    logger.info("Starting Nexus Trading Agents")
    logger.info("=" * 60)
    
    # Load configuration
    config_path = Path(__file__).parent.parent / "config" / "agents.yaml"
    logger.info(f"Loading configuration from: {config_path}")
    config = load_config(str(config_path))
    
    # Initialize Redis
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    logger.info(f"Connecting to Redis: {redis_url}")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    
    # Test Redis connection
    try:
        redis_client.ping()
        logger.info("✓ Redis connection OK")
    except Exception as e:
        logger.error(f"✗ Redis connection failed: {e}")
        return 1
    
   
    # Initialize MCP servers configuration
    mcp_servers = MCPServers.from_env()
    logger.info(f"MCP Servers configured:")
    logger.info(f"  - Market Data: {mcp_servers.market_data}")
    logger.info(f"  - Technical: {mcp_servers.technical}")
    logger.info(f"  - Risk: {mcp_servers.risk}")
    
    # Create message bus
    logger.info("Initializing message bus...")
    bus = MessageBus(redis_url)
    
    # Create agents
    logger.info("Creating agents...")
    
    risk_manager = RiskManagerAgent(
        config.get("risk_manager", {}),
        bus,
        mcp_servers,
        redis_client
    )
    
    technical_analyst = TechnicalAnalystAgent(
        config.get("technical_analyst", {}),
        bus,
        mcp_servers
    )
    
    orchestrator = OrchestratorAgent(
        config.get("orchestrator", {}),
        bus,
        redis_client,
    )
    
    agents = [risk_manager, technical_analyst, orchestrator]
    
    # Start agents in order
    logger.info("=" * 60)
    logger.info("Starting agents in order...")
    logger.info("=" * 60)
    
    try:
        # 1. Risk Manager (must be ready first)
        logger.info("Starting Risk Manager...")
        await risk_manager.start()
        await wait_healthy(risk_manager, timeout=30)
        logger.info("✓ Risk Manager ready")
        
        # 2. Technical Analyst
        logger.info("Starting Technical Analyst...")
        await technical_analyst.start()
        await wait_healthy(technical_analyst, timeout=30)
        logger.info("✓ Technical Analyst ready")
        
        # 3. Orchestrator (last, waits for all)
        logger.info("Starting Orchestrator...")
        await orchestrator.start()
        await wait_healthy(orchestrator, timeout=30)
        logger.info("✓ Orchestrator ready")
        
        # Start message bus listening
        logger.info("Starting message bus listener...")
        bus_task = asyncio.create_task(bus.listen())
        
        logger.info("=" * 60)
        logger.info("ALL AGENTS RUNNING!")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop")
        
        # Wait for shutdown signal
        stop_event = asyncio.Event()
        
        def handle_shutdown(sig, frame):
            logger.info(f"Shutdown signal received: {sig}")
            stop_event.set()
        
        signal.signal(signal.SIGINT, handle_shutdown)
        signal.signal(signal.SIGTERM, handle_shutdown)
        
        await stop_event.wait()
        
        # Graceful shutdown
        logger.info("=" * 60)
        logger.info("Shutting down agents...")
        logger.info("=" * 60)
        
        # Stop in reverse order
        for agent in reversed(agents):
            logger.info(f"Stopping {agent.name}...")
            await agent.stop()
            logger.info(f"✓ {agent.name} stopped")
        
        # Stop message bus
        bus.stop()
        bus_task.cancel()
        try:
            await bus_task
        except asyncio.CancelledError:
            pass
        
        # Close connections
        bus.close()
        redis_client.close()
        
        logger.info("=" * 60)
        logger.info("Shutdown complete")
        logger.info("=" * 60)
        return 0
    
    except Exception as e:
        logger.error(f"Fatal error during startup: {e}", exc_info=True)
        
        # Emergency shutdown
        for agent in reversed(agents):
            try:
                await agent.stop()
            except Exception as stop_error:
                logger.error(f"Error stopping {agent.name}: {stop_error}")
        
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
