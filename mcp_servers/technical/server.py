"""
MCP Technical Analysis Server.

Provides technical analysis tools through MCP protocol.

Tools:
- calculate_indicators: Calculate technical indicators (SMA, RSI, MACD, etc.)
- get_regime: Detect market regime (trending/ranging)
- find_sr_levels: Find support and resistance levels

Port: 3002
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
from tools import calculate_indicators_tool, get_regime_tool, find_sr_levels_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TechnicalServer(BaseMCPServer):
    """
    Technical Analysis MCP Server.
    
    Provides technical analysis via three tools:
    1. calculate_indicators - Technical indicators (IndicatorEngine)
    2. get_regime - Market regime detection (ADX + SMA200)
    3. find_sr_levels - Support/Resistance levels (local extrema)
    """
    
    def __init__(self, db_url: str):
        """
        Initialize Technical server.
        
        Args:
            db_url: PostgreSQL connection string
        """
        super().__init__("technical")
        
        self.db_url = db_url
        
        # Register tools
        self._register_tools()
        
        logger.info("Technical Analysis Server initialized")
    
    def _register_tools(self):
        """Register all technical analysis tools."""
        
        # Tool 1: calculate_indicators
        self.register_tool(
            name="calculate_indicators",
            description="Calculate technical indicators for a symbol (SMA, EMA, RSI, MACD, BB, ATR, ADX)",
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
                    "period": {
                        "type": "integer",
                        "description": "Analysis period in days",
                        "default": 60,
                        "minimum": 20,
                        "maximum": 365
                    }
                },
                "required": ["symbol"]
            },
            handler=self._calculate_indicators
        )
        
        # Tool 2: get_regime
        self.register_tool(
            name="get_regime",
            description="Detect current market regime (trending/ranging) using ADX and SMA200",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol"
                    }
                },
                "required": ["symbol"]
            },
            handler=self._get_regime
        )
        
        # Tool 3: find_sr_levels
        self.register_tool(
            name="find_sr_levels",
            description="Find support and resistance levels using local extrema",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol"
                    },
                    "period": {
                        "type": "integer",
                        "description": "Lookback period in days",
                        "default": 60,
                        "minimum": 20,
                        "maximum": 180
                    },
                    "max_levels": {
                        "type": "integer",
                        "description": "Maximum levels to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["symbol"]
            },
            handler=self._find_sr_levels
        )
    
    async def _calculate_indicators(self, args: dict) -> dict:
        """Wrapper for calculate_indicators_tool."""
        return await calculate_indicators_tool(args, self.db_url)
    
    async def _get_regime(self, args: dict) -> dict:
        """Wrapper for get_regime_tool."""
        return await get_regime_tool(args, self.db_url)
    
    async def _find_sr_levels(self, args: dict) -> dict:
        """Wrapper for find_sr_levels_tool."""
        return await find_sr_levels_tool(args, self.db_url)


async def main():
    """Main entry point for Technical server."""
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)
    
    # Create and run server
    server = TechnicalServer(db_url)
    
    logger.info("=" * 60)
    logger.info("MCP TECHNICAL ANALYSIS SERVER")
    logger.info("=" * 60)
    logger.info(f"Tools registered: {len(server.get_tool_list())}")
    for tool_name in server.get_tool_list():
        logger.info(f"  - {tool_name}")
    logger.info("=" * 60)
    logger.info("Starting server...")
    
    await server.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)
