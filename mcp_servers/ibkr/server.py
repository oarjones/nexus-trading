"""
MCP IBKR Trading Server.

Provides trading functionality through Interactive Brokers MCP protocol.

CRITICAL SAFETY:
- Paper trading only by default
- Order value limits
- Connection retry logic
- Error handling

Tools:
- get_account: Account information
- get_positions: Current positions
- place_order: Place orders (PAPER ONLY)
- cancel_order: Cancel pending orders
- get_order_status: Check order status

Port: 3004
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
from .tools import (
    get_account_tool,
    get_positions_tool,
    place_order_tool,
    cancel_order_tool,
    get_order_status_tool
)
from .tools.connection import IBKRConnection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IBKRServer(BaseMCPServer):
    """
    IBKR Trading MCP Server.
    
    SAFETY FEATURES:
    - Paper trading only (blocks live accounts)
    - Max order value limits
    - Connection retry every 5 minutes
    - Fail-safe error handling
    
    Provides trading via five tools:
    1. get_account - Account info
    2. get_positions - Portfolio positions
    3. place_order - Place orders (PAPER ONLY)
    4. cancel_order - Cancel orders
    5. get_order_status - Order status
    """
    
    def __init__(self, config_path: str = None):
        """
        Initialize IBKR server.
        
        Args:
            config_path: Optional path to config file
        """
        super().__init__("ibkr", config_path)
        
        # Get IBKR config
        ibkr_config = self.config.get('ibkr', {})
        
        # CRITICAL: Safety settings
        self.paper_only = ibkr_config.get('paper_only', True)
        self.max_order_value = ibkr_config.get('max_order_value', 10000)
        
        # Connection settings
        host = ibkr_config.get('gateway_host', '127.0.0.1')
        port = ibkr_config.get('tws_port', 7497)  # 7497=paper, 7496=live
        client_id = ibkr_config.get('client_id', 1)
        timeout = ibkr_config.get('timeout', 30)
        self.retry_interval = ibkr_config.get('retry_interval', 300)  # 5 min
        
        # SAFETY CHECK: Verify paper trading port
        if self.paper_only and port == 7496:
            logger.error("BLOCKED: Live trading port (7496) detected with paper_only=true")
            raise ValueError("Configuration mismatch: paper_only=true but using live port 7496")
        
        # Initialize IBKR connection
        self.ibkr_conn = IBKRConnection(host, port, client_id, timeout)
        self._connection_task = None
        
        # Register tools
        self._register_tools()
        
        logger.info("=" * 60)
        logger.info("IBKR Trading Server initialized")
        logger.info(f"Safety Mode: {'PAPER ONLY' if self.paper_only else 'LIVE ALLOWED'}")
        logger.info(f"Max Order Value: ${self.max_order_value:,.0f}")
        logger.info(f"Connection: {host}:{port}")
        logger.info("=" * 60)
    
    def _register_tools(self):
        """Register all IBKR trading tools."""
        
        # Tool 1: get_account
        self.register_tool(
            name="get_account",
            description="Get IBKR account information and balances",
            schema={
                "type": "object",
                "properties": {}
            },
            handler=self._get_account
        )
        
        # Tool 2: get_positions
        self.register_tool(
            name="get_positions",
            description="Get current portfolio positions",
            schema={
                "type": "object",
                "properties": {}
            },
            handler=self._get_positions
        )
        
        # Tool 3: place_order
        self.register_tool(
            name="place_order",
            description=f"Place order (PAPER ONLY, max ${self.max_order_value:,.0f})",
            schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol"
                    },
                    "action": {
                        "type": "string",
                        "description": "Order action",
                        "enum": ["BUY", "SELL"]
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of shares",
                        "minimum": 1
                    },
                    "order_type": {
                        "type": "string",
                        "description": "Order type",
                        "enum": ["MARKET", "LIMIT"],
                        "default": "MARKET"
                    },
                    "limit_price": {
                        "type": "number",
                        "description": "Limit price (required for LIMIT orders)"
                    }
                },
                "required": ["symbol", "action", "quantity"]
            },
            handler=self._place_order
        )
        
        # Tool 4: cancel_order
        self.register_tool(
            name="cancel_order",
            description="Cancel a pending order",
            schema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to cancel"
                    }
                },
                "required": ["order_id"]
            },
            handler=self._cancel_order
        )
        
        # Tool 5: get_order_status
        self.register_tool(
            name="get_order_status",
            description="Get status of an order",
            schema={
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "Order ID to check"
                    }
                },
                "required": ["order_id"]
            },
            handler=self._get_order_status
        )
    
    async def _get_account(self, args: dict) -> dict:
        """Wrapper for get_account_tool."""
        return await get_account_tool(args, self.ibkr_conn)
    
    async def _get_positions(self, args: dict) -> dict:
        """Wrapper for get_positions_tool."""
        return await get_positions_tool(args, self.ibkr_conn)
    
    async def _place_order(self, args: dict) -> dict:
        """Wrapper for place_order_tool with safety checks."""
        return await place_order_tool(
            args,
            self.ibkr_conn,
            paper_only=self.paper_only,
            max_order_value=self.max_order_value
        )
    
    async def _cancel_order(self, args: dict) -> dict:
        """Wrapper for cancel_order_tool."""
        return await cancel_order_tool(args, self.ibkr_conn)
    
    async def _get_order_status(self, args: dict) -> dict:
        """Wrapper for get_order_status_tool."""
        return await get_order_status_tool(args, self.ibkr_conn)
    
    async def _connection_monitor(self):
        """Monitor IBKR connection and retry if lost."""
        while True:
            try:
                if not self.ibkr_conn.is_connected():
                    logger.warning("IBKR connection lost, attempting reconnect...")
                    try:
                        await self.ibkr_conn.connect()
                        logger.info("IBKR connection restored")
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                        logger.info(f"Will retry in {self.retry_interval} seconds")
                
                # Check every retry_interval seconds
                await asyncio.sleep(self.retry_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
                await asyncio.sleep(self.retry_interval)
    
    async def run(self):
        """Run the IBKR server with connection monitoring."""
        try:
            # Attempt initial connection (non-blocking)
            logger.info("Attempting initial connection to IBKR...")
            try:
                await self.ibkr_conn.connect()
                logger.info("✓ Connected to IBKR successfully")
            except Exception as e:
                logger.warning(f"Initial connection failed: {e}")
                logger.info("Server will start anyway and retry in background")
            
            # Start connection monitor in background
            self._connection_task = asyncio.create_task(self._connection_monitor())
            
            # Run MCP server
            await super().run()
            
        finally:
            # Cleanup
            if self._connection_task:
                self._connection_task.cancel()
            await self.ibkr_conn.disconnect()


async def main():
    """Main entry point for IBKR server."""
    # Load environment
    load_dotenv()
    
    # Create and run server
    config_path = os.getenv("MCP_CONFIG_PATH", "config/mcp-servers.yaml")
    server = IBKRServer(config_path)
    
    logger.info("=" * 60)
    logger.info("MCP IBKR TRADING SERVER")
    logger.info("=" * 60)
    logger.info(f"Tools registered: {len(server.get_tool_list())}")
    for tool_name in server.get_tool_list():
        logger.info(f"  - {tool_name}")
    logger.info("=" * 60)
    logger.info("⚠️  SAFETY: Paper trading only, max order $10,000")
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
