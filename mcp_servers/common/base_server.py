"""
Base MCP Server class.

Provides common functionality for all MCP servers including:
- Tool registration and management
- Request handling
- Server lifecycle management
"""

import logging
from typing import Any, Callable, Dict, List, Optional
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .exceptions import ToolError, ConfigError
from .config import load_config

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """
    Base class for all MCP servers.
    
    Provides common infrastructure for tool registration,
    request handling, and server management.
    
    Attributes:
        name: Server name
        config: Server configuration dictionary
        server: MCP Server instance
        tools: Registered tool handlers
        
    Example:
        >>> class MyServer(BaseMCPServer):
        ...     def __init__(self, config_path: str):
        ...         super().__init__("my-server", config_path)
        ...         self.register_tool("get_data", "Get data", {...}, self.get_data)
        ...
        ...     async def get_data(self, args: dict) -> dict:
        ...         return {"data": "example"}
    """
    
    def __init__(self, name: str, config_path: Optional[str] = None):
        """
        Initialize MCP server.
        
        Args:
            name: Server name
            config_path: Optional path to YAML configuration file
            
        Raises:
            ConfigError: If config file is invalid
        """
        self.name = name
        self.config = load_config(config_path) if config_path else {}
        self.server = Server(name)
        self.tools: Dict[str, Callable] = {}
        
        # Register list_tools handler
        @self.server.list_tools()
        async def _list_tools():
            """List all registered tools."""
            tool_list = []
            for tool_name, handler in self.tools.items():
                # Get tool metadata from handler
                tool_info = getattr(handler, '_tool_info', {})
                tool_list.append(Tool(
                    name=tool_name,
                    description=tool_info.get('description', ''),
                    inputSchema=tool_info.get('schema', {
                        "type": "object",
                        "properties": {}
                    })
                ))
            return tool_list
        
        # Register call_tool handler
        @self.server.call_tool()
        async def _call_tool(name: str, arguments: dict):
            """Call a registered tool."""
            if name not in self.tools:
                raise ToolError(f"Unknown tool: {name}")
            
            try:
                logger.info(f"[{self.name}] Calling tool: {name}")
                logger.debug(f"[{self.name}] Arguments: {arguments}")
                
                # Execute tool
                result = await self.tools[name](arguments)
                
                logger.info(f"[{self.name}] Tool {name} completed successfully")
                
                # Return as TextContent
                import json
                return [TextContent(
                    type="text",
                    text=json.dumps(result, indent=2)
                )]
                
            except Exception as e:
                logger.error(f"[{self.name}] Tool {name} failed: {e}", exc_info=True)
                raise ToolError(f"Tool execution failed: {e}")
        
        logger.info(f"MCP Server '{name}' initialized")
    
    def register_tool(
        self,
        name: str,
        description: str,
        schema: Dict[str, Any],
        handler: Callable
    ):
        """
        Register a tool with the server.
        
        Args:
            name: Tool name (unique identifier)
            description: Human-readable tool description
            schema: JSON Schema for tool input parameters
            handler: Async function to handle tool calls
            
        Example:
            >>> server.register_tool(
            ...     "get_quote",
            ...     "Get current stock quote",
            ...     {
            ...         "type": "object",
            ...         "properties": {
            ...             "symbol": {"type": "string"}
            ...         },
            ...         "required": ["symbol"]
            ...     },
            ...     self.get_quote
            ... )
        """
        # Attach metadata to handler
        handler._tool_info = {
            'description': description,
            'schema': schema
        }
        
        self.tools[name] = handler
        logger.info(f"[{self.name}] Registered tool: {name}")
    
    async def run(self):
        """
        Run the MCP server using stdio transport.
        
        This starts the server and listens for requests via stdin/stdout.
        Blocks until server is stopped.
        """
        logger.info(f"[{self.name}] Starting MCP server...")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )
        
        logger.info(f"[{self.name}] Server stopped")
    
    def get_tool_list(self) -> List[str]:
        """
        Get list of registered tool names.
        
        Returns:
            List of tool names
        """
        return list(self.tools.keys())
    
    def __repr__(self) -> str:
        """String representation of server."""
        return f"BaseMCPServer(name='{self.name}', tools={len(self.tools)})"
