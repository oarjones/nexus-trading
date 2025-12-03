"""
MCP Risk Management Server.

Provides risk management and position sizing through MCP protocol.

Tools:
- check_limits: Validate trades against hard risk limits
- calculate_size: Calculate position size using Kelly Criterion
- get_exposure: Analyze portfolio exposure

Port: 3003
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
from common import BaseMCPServer, load_config
from tools import check_limits_tool, calculate_size_tool, get_exposure_tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RiskServer(BaseMCPServer):
    """
    Risk Management MCP Server.
    
    Provides risk management via three tools:
    1. check_limits - Validate against hard limits
    2. calculate_size - Position sizing (Kelly)
    3. get_exposure - Portfolio exposure analysis
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize Risk server.
        
        Args:
            config_path: Optional path to config file
        """
        super().__init__("risk", config_path)
        
        # Register tools
        self._register_tools()
        
        logger.info("Risk Management Server initialized")
    
    def _register_tools(self):
        """Register all risk management tools."""
        
        # Tool 1: check_limits
        self.register_tool(
            name="check_limits",
            description="Check if proposed trade violates risk limits",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol"
                    },
                    "size": {
                        "type": "number",
                        "description": "Proposed position size (USD)"
                    },
                    "portfolio_value": {
                        "type": "number",
                        "description": "Total portfolio value"
                    },
                    "current_positions": {
                        "type": "array",
                        "description": "Current positions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "size": {"type": "number"},
                                "sector": {"type": "string"}
                            }
                        }
                    },
                    "sector": {
                        "type": "string",
                        "description": "Symbol sector"
                    }
                },
                "required": ["symbol", "size", "portfolio_value"]
            },
            handler=self._check_limits
        )
        
        # Tool 2: calculate_size
        self.register_tool(
            name="calculate_size",
            description="Calculate optimal position size using Kelly Criterion",
            schema={
                "type": "object",
                "properties": {
                    "portfolio_value": {
                        "type": "number",
                        "description": "Total portfolio value"
                    },
                    "win_rate": {
                        "type": "number",
                        "description": "Historical win rate (0-1)",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "avg_win": {
                        "type": "number",
                        "description": "Average win percentage"
                    },
                    "avg_loss": {
                        "type": "number",
                        "description": "Average loss percentage"
                    },
                    "kelly_fraction": {
                        "type": "number",
                        "description": "Kelly fraction (default 0.25)",
                        "default": 0.25,
                        "minimum": 0,
                        "maximum": 1
                    },
                    "max_risk_pct": {
                        "type": "number",
                        "description": "Max risk per trade (default 0.01)",
                        "default": 0.01
                    }
                },
                "required": ["portfolio_value", "win_rate", "avg_win", "avg_loss"]
            },
            handler=self._calculate_size
        )
        
        # Tool 3: get_exposure
        self.register_tool(
            name="get_exposure",
            description="Analyze portfolio exposure across sectors, markets, currencies",
            schema={
                "type": "object",
                "properties": {
                    "portfolio_value": {
                        "type": "number",
                        "description": "Total portfolio value"
                    },
                    "positions": {
                        "type": "array",
                        "description": "List of current positions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "size": {"type": "number"},
                                "sector": {"type": "string"},
                                "market": {"type": "string"},
                                "currency": {"type": "string"}
                            }
                        }
                    }
                },
                "required": ["portfolio_value", "positions"]
            },
            handler=self._get_exposure
        )
    
    async def _check_limits(self, args: dict) -> dict:
        """Wrapper for check_limits_tool."""
        return await check_limits_tool(args, self.config)
    
    async def _calculate_size(self, args: dict) -> dict:
        """Wrapper for calculate_size_tool."""
        return await calculate_size_tool(args, self.config)
    
    async def _get_exposure(self, args: dict) -> dict:
        """Wrapper for get_exposure_tool."""
        return await get_exposure_tool(args)


async def main():
    """Main entry point for Risk server."""
    # Load environment
    load_dotenv()
    
    # Create and run server
    config_path = 'config/mcp-servers.yaml'
    server = RiskServer(config_path)
    
    logger.info("=" * 60)
    logger.info("MCP RISK MANAGEMENT SERVER")
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
