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
import json
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Tool imports
from tools.regime import handle_get_regime, get_regime_tool
from tools.model_info import handle_get_model_info, handle_list_models
from tools.health import handle_health_check


# MCP Tools Definition
TOOLS = [
    {
        "name": "get_regime",
        "description": "Get current market regime (BULL, BEAR, SIDEWAYS, VOLATILE)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "features": {
                    "type": "object",
                    "description": "Prediction features {name: value}. If not provided, uses current values.",
                    "additionalProperties": {"type": "number"}
                },
                "symbol": {
                    "type": "string",
                    "description": "Specific symbol (optional)"
                },
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Model type to use (optional, default: active)"
                },
                "use_cache": {
                    "type": "boolean",
                    "description": "Whether to use prediction cache (default: true)"
                }
            }
        }
    },
    {
        "name": "get_model_info",
        "description": "Get information about active or specified ML model",
        "inputSchema": {
            "type": "object",
            "properties": {
                "model_type": {
                    "type": "string",
                    "enum": ["hmm", "rules"],
                    "description": "Model type (optional)"
                }
            }
        }
    },
    {
        "name": "list_models",
        "description": "List available ML models",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "clear_cache",
        "description": "Clear prediction cache",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "health_check",
        "description": "Check ML server status",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


async def handle_tool_call(name: str, args: dict) -> dict:
    """
    Dispatcher for tool calls.
    
    Args:
        name: Tool name
        args: Tool arguments
    
    Returns:
        Tool result
    """
    handlers = {
        "get_regime": handle_get_regime,
        "get_model_info": handle_get_model_info,
        "list_models": handle_list_models,
        "clear_cache": lambda _: {"cleared": get_regime_tool().clear_cache()},
        "health_check": handle_health_check,
    }
    
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    
    return await handler(args)


async def main():
    """MCP Server Entry Point."""
    logger.info("Starting mcp-ml-models server...")
    
    # In production, this would integrate with MCP SDK
    # For now, standalone test mode
    
    print(json.dumps({
        "status": "ready",
        "tools": [t["name"] for t in TOOLS],
        "version": "1.0.0"
    }))
    
    # Keep server running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    asyncio.run(main())
