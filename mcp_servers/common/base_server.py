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
    
    def __init__(self, name: str, config_path: Optional[str] = None, db_url: Optional[str] = None):
        """
        Initialize MCP server.
        
        Args:
            name: Server name
            config_path: Optional path to YAML configuration file
            db_url: Optional database URL for connection pooling
            
        Raises:
            ConfigError: If config file is invalid
        """
        self.name = name
        self.config = load_config(config_path) if config_path else {}
        self.server = Server(name)
        self.tools: Dict[str, Callable] = {}
        self.tool_metadata: Dict[str, dict] = {}
        self.db_engine = None
        
        # Initialize database engine with pooling if URL provided
        if db_url:
            from sqlalchemy import create_engine
            from sqlalchemy.pool import QueuePool
            
            self.db_engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before using
                pool_recycle=3600    # Recycle connections after 1 hour
            )
            logger.info(f"[{name}] Database engine initialized with connection pooling")
        
        # Register list_tools handler
        @self.server.list_tools()
        async def _list_tools():
            """List all registered tools."""
            tool_list = []
            for tool_name, handler in self.tools.items():
                # Get tool metadata
                tool_info = self.tool_metadata.get(tool_name, {})
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
        # Store metadata in separate dict
        self.tool_metadata[name] = {
            'description': description,
            'schema': schema
        }
        
        self.tools[name] = handler
        logger.info(f"[{self.name}] Registered tool: {name}")
    
    async def run_http(self, host: str = "0.0.0.0", port: int = 8000):
        """Run as HTTP server using FastAPI."""
        try:
            import uvicorn
            from fastapi import FastAPI, HTTPException, Body
            from pydantic import BaseModel
        except ImportError:
            logger.error("FastAPI/Uvicorn not installed. Install with 'pip install fastapi uvicorn'")
            raise

        app = FastAPI(title=self.name)

        @app.post("/tools/{name}")
        async def call_tool(name: str, args: dict = Body(...)):
            if name not in self.tools:
                raise HTTPException(status_code=404, detail=f"Tool {name} not found")
            try:
                logger.debug(f"[{self.name}] HTTP Call tool: {name} args={args}")
                result = await self.tools[name](args)
                return result
            except Exception as e:
                logger.error(f"[{self.name}] Tool {name} failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/health")
        async def health():
            return {"status": "ok", "server": self.name}
            
        @app.get("/tools")
        async def list_tools():
            return self.get_tool_list()

        logger.info(f"[{self.name}] Starting HTTP server on {host}:{port}")
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    async def run(self):
        """
        Run the MCP server.
        
        Checks MCP_TRANSPORT environment variable:
        - 'http': Runs HTTP server (FastAPI)
        - 'stdio' (default): Runs Stdio server (MCP SDK)
        """
        import os
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        
        if transport == "http":
            # Determine port from config or defaulting based on name pattern if needed
            # But normally config should have it.
            # We'll use the one in config if available.
            port = self.config.get(self.name, {}).get("port", 8000)
            host = self.config.get(self.name, {}).get("host", "0.0.0.0")
            
            # Allow env override
            port = int(os.getenv("PORT", port))
            
            await self.run_http(host, port)
        else:
            logger.info(f"[{self.name}] Starting MCP server (STDIO)...")
            
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
    
    def get_db_engine(self):
        """
        Get the database engine for use by tools.
        
        Returns:
            SQLAlchemy engine instance or None if not initialized
        """
        return self.db_engine
    
    def cleanup(self):
        """Clean up resources (e.g., database connections)."""
        if self.db_engine:
            logger.info(f"[{self.name}] Disposing database engine")
            self.db_engine.dispose()
    
    def __repr__(self) -> str:
        """String representation of server."""
        return f"BaseMCPServer(name='{self.name}', tools={len(self.tools)})"
