import asyncio
import logging
import os
import signal
import subprocess
import sys
import time
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.strategies.swing.ai_agent_strategy import AIAgentStrategy
from src.agents.llm.interfaces import MarketContext

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("E2E_Simulation")

# Server Configuration
SERVERS = {
    "market-data": {"port": 3001, "script": "mcp_servers/market_data/server.py"},
    "technical":   {"port": 3002, "script": "mcp_servers/technical/server.py"},
    "risk":        {"port": 3003, "script": "mcp_servers/risk/server.py"},
    "ibkr":        {"port": 3004, "script": "mcp_servers/ibkr/server.py"},
    "ml-models":   {"port": 3005, "script": "mcp_servers/ml_models/server.py"},
}

PROCESSES = []

def start_server(name: str, config: dict):
    """Start a server subprocess."""
    cmd = [sys.executable, config["script"]]
    env = os.environ.copy()
    env["MCP_TRANSPORT"] = "http"
    env["TWS_PORT"] = "4002"  # Ensure IBKR knows we want paper port
    env["PORT"] = str(config["port"]) # Force port from coordination script
    
    logger.info(f"Starting {name} on port {config['port']}...")
    p = subprocess.Popen(cmd, env=env)
    PROCESSES.append(p)
    return p

async def wait_for_health(name: str, port: int, timeout=30):
    """Wait for server to be healthy."""
    url = f"http://localhost:{port}/health"
    start = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    logger.info(f"✅ {name} is healthy")
                    return True
            except:
                pass
            await asyncio.sleep(1)
    
    logger.error(f"❌ {name} failed to become healthy")
    return False

def cleanup():
    """Kill all server processes."""
    logger.info("Stopping servers...")
    for p in PROCESSES:
        p.terminate()
        try:
            p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            p.kill()
    logger.info("Servers stopped")

def wait_for_db(timeout=60):
    """Wait for database to be ready."""
    logger.info("Waiting for database to be ready...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            import psycopg2
            conn = psycopg2.connect(
                dbname="trading",
                user="trading",
                password=os.getenv("DB_PASSWORD", "postgres"),
                host="localhost",
                port=5432
            )
            conn.close()
            logger.info("Database is ready!")
            return True
        except Exception:
            time.sleep(1)
    logger.error("Database connection failed after timeout")
    return False

async def run_simulation():
    """Run the main simulation loop."""
    try:
        # 1. Start Servers
        logger.info("=== Starting E2E Simulation Environment ===")
        
        # Wait for DB before starting
        if not wait_for_db():
            logger.warning("Database not ready, check Docker logs.")

        for name, config in SERVERS.items():
            start_server(name, config)
            
        # 2. Wait for Health
        logger.info("Waiting for servers to be ready...")
        tasks = [wait_for_health(n, c["port"]) for n, c in SERVERS.items()]
        results = await asyncio.gather(*tasks)
        
        if not all(results):
            logger.error("Some servers failed to start. Aborting.")
            return

        logger.info("\nIMPORTANT: Ensure IB Gateway is running on port 4002 before proceeding.\n")
        
        # 3. Initialize Strategy
        logger.info("Initializing AI Agent Strategy...")
        from src.agents.llm.config import LLMAgentConfig
        
        # Mock config
        agent_conf = LLMAgentConfig(
            active_provider="claude",
            autonomy_level="moderate",
            providers={"claude": {"model": "claude-3-opus-20240229"}}
        )
        
        config = {
            "symbols": ["SPY", "QQQ"],
            "autonomy_level": "moderate",
            "agent_config": agent_conf
        }
        
        strategy = AIAgentStrategy(config)
        
        # 4. Run Strategy Loop
        logger.info("Running simulation loop (1 iteration)...")
        
        dummy_context = MarketContext(
            spy_change_pct=0.0,
            qqq_change_pct=0.0,
            vix_level=15.0,
            vix_change_pct=0.0,
            market_breadth=0.5,
            sector_rotation={}
        )
        
        signals = await strategy.generate_signals(dummy_context)
        
        logger.info("=" * 60)
        logger.info(f"DECISION GENERATED: {len(signals)} signals")
        for sig in signals:
            logger.info(f"Signal: {sig}")
        
        if strategy._last_decision:
            logger.info("\nAgent Reasoning:")
            logger.info(strategy._last_decision.reasoning)
        logger.info("=" * 60)
        
        logger.info("Simulation completed successfully.")
        
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
    finally:
        cleanup()

if __name__ == "__main__":
    try:
        if sys.platform == 'win32':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        cleanup()
