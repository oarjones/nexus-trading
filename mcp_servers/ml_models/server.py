"""
MCP Server for Machine Learning Models.

Exposes tools for:
- get_regime: Get current market regime
- get_model_info: Get active model info
- list_models: List available models
- clear_cache: Clear prediction cache
"""

import asyncio
import logging
import os
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add parent directory to path to import common
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from common.base_server import BaseMCPServer
except ImportError:
    # Fallback for relative run
    sys.path.append(str(Path(__file__).parent.parent.parent))
    from mcp_servers.common.base_server import BaseMCPServer

# Tool imports
from .tools.regime import handle_get_regime, get_regime_tool
from .tools.model_info import handle_get_model_info, handle_list_models
from .tools.health import handle_health_check


class MLModelsServer(BaseMCPServer):
    """MCP Server for ML Models."""
    
    def __init__(self, config_path: str = None):
        super().__init__("ml-models", config_path)
        self._register_tools()
        
    def _register_tools(self):
        """Register all ML tools."""
        
        # 1. get_regime
        self.register_tool(
            "get_regime",
            "Get current market regime (BULL, BEAR, SIDEWAYS, VOLATILE)",
            {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "model_type": {"type": "string", "enum": ["hmm", "rules"]},
                    "use_cache": {"type": "boolean"}
                }
            },
            handle_get_regime
        )
        
        # 2. get_model_info
        self.register_tool(
            "get_model_info",
            "Get information about active or specified ML model",
            {
                "type": "object",
                "properties": {
                    "model_type": {"type": "string", "enum": ["hmm", "rules"]}
                }
            },
            handle_get_model_info
        )
        
        # 3. list_models
        self.register_tool(
            "list_models",
            "List available ML models",
            {"type": "object", "properties": {}},
            handle_list_models
        )
        
        # 4. clear_cache
        self.register_tool(
            "clear_cache",
            "Clear prediction cache",
            {"type": "object", "properties": {}},
            self.clear_cache_wrapper
        )
        
        # 5. health_check
        self.register_tool(
            "health_check",
            "Check ML server status",
            {"type": "object", "properties": {}},
            handle_health_check
        )

    async def clear_cache_wrapper(self, args: dict) -> dict:
        """Wrapper for clear_cache to match async signature."""
        return {"cleared": get_regime_tool().clear_cache()}

async def main():
    """MCP Server Entry Point."""
    # Determine config path
    config_path = os.getenv("MCP_CONFIG_PATH", "config/mcp-servers.yaml")
    
    server = MLModelsServer(config_path)
    await server.run()

if __name__ == "__main__":
    asyncio.run(main())
