"""
MCP Market Data Server.

Provides real-time and historical market data through MCP protocol.

Tools:
- get_quote: Get current quote for a symbol
- get_ohlcv: Get historical OHLCV data
- get_symbols: Get list of available symbols

Port: 3001
"""

import logging
import os
import sys
import asyncio
from pathlib import Path

# Add common and project root to path
mcp_servers_root = Path(__file__).parent.parent
project_root = mcp_servers_root.parent
sys.path.insert(0, str(mcp_servers_root))
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from common import BaseMCPServer
from .tools import get_quote_tool, get_ohlcv_tool, get_symbols_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MarketDataServer(BaseMCPServer):
    """
    Market Data MCP Server.
    
    Provides access to market data via three tools:
    1. get_quote - Current quotes (Redis cache + DB fallback)
    2. get_ohlcv - Historical OHLCV data (TimescaleDB)
    3. get_symbols - Available symbols list
    """
    
    def __init__(self, db_url: str, redis_url: str):
        """
        Initialize Market Data server.
        
        Args:
            db_url: PostgreSQL connection string
            redis_url: Redis connection string
        """
        super().__init__("market-data", db_url=db_url)
        
        self.redis_url = redis_url
        
        # Initialize IBKR Provider (Client ID 2 to avoid conflict with Execution Server)
        # We import here to avoid circular dependencies if any
        try:
            from src.data.providers.ibkr import IBKRProvider
            self.ibkr = IBKRProvider(client_id=2, port=7497) # Paper port default
            logger.info("IBKR Provider initialized for Market Data (Client ID 2)")
        except ImportError as e:
            logger.warning(f"Could not import IBKRProvider: {e}")
            self.ibkr = None
        
        # Register tools
        self._register_tools()
        
        logger.info("Market Data Server initialized")
    
    def _register_tools(self):
        """Register all market data tools."""
        
        # Tool 1: get_quote
        self.register_tool(
            name="get_quote",
            description="Get current quote (price) for a symbol",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol (e.g., 'AAPL', 'SAN.MC')"
                    }
                },
                "required": ["symbol"]
            },
            handler=self._get_quote
        )
        
        # Tool 2: get_ohlcv
        self.register_tool(
            name="get_ohlcv",
            description="Get historical OHLCV (candlestick) data",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol"
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Timeframe ('1d', '1h', etc.)",
                        "default": "1d"
                    },
                    "start": {
                        "type": "string",
                        "description": "Start date (YYYY-MM-DD)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                    },
                    "end": {
                        "type": "string",
                        "description": "End date (YYYY-MM-DD)",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of records",
                        "default": 1000
                    }
                },
                "required": ["symbol"]
            },
            handler=self._get_ohlcv
        )
        
        # Tool 3: get_symbols
        self.register_tool(
            name="get_symbols",
            description="Get list of available trading symbols",
            schema={
                "type": "object",
                "properties": {
                    "market": {
                        "type": "string",
                        "description": "Filter by market (EU, US, FX, CRYPTO)",
                        "enum": ["EU", "US", "FX", "CRYPTO"]
                    }
                }
            },
            handler=self._get_symbols
        )
    
    async def _get_quote(self, args: dict) -> dict:
        """Wrapper for get_quote_tool."""
        return await get_quote_tool(args, self.get_db_engine(), self.redis_url, self.ibkr)
    
    async def _get_ohlcv(self, args: dict) -> dict:
        """Wrapper for get_ohlcv_tool."""
        return await get_ohlcv_tool(args, self.get_db_engine())
    
    async def _get_symbols(self, args: dict) -> dict:
        """Wrapper for get_symbols_tool."""
        return await get_symbols_tool(args)


async def main():
    """Main entry point for Market Data server."""
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Create and run server
    server = MarketDataServer(db_url, redis_url)
    
    logger.info("=" * 60)
    logger.info("MCP MARKET DATA SERVER")
    logger.info("=" * 60)
    logger.info(f"Tools registered: {len(server.get_tool_list())}")
    for tool_name in server.get_tool_list():
        logger.info(f"  - {tool_name}")
    logger.info("=" * 60)
    logger.info("Starting server...")
    
    logger.info("Starting server...")
    
    # Connect IBKR if available
    if server.ibkr:
        try:
            await server.ibkr.connect()
        except Exception as e:
            logger.error(f"Failed to connect IBKR provider: {e}")

    try:
        await server.run()
    finally:
        if server.ibkr:
            server.ibkr.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
