"""
MCP Client helper for communicating with MCP servers.

Provides a simple HTTP client for calling MCP server tools.
"""

import httpx
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for calling MCP server tools via HTTP.
    
    Provides a simple interface to call tools on running MCP servers.
    
    Example:
        >>> client = MCPClient()
        >>> result = await client.call(
        ...     "http://localhost:3002",
        ...     "calculate_indicators",
        ...     {"symbol": "SAN.MC", "indicators": ["RSI", "MACD"]}
        ... )
    """
    
    def __init__(self, timeout: float = 30.0):
        """
        Initialize MCP client.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def call(
        self,
        server_url: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server.
        
        Args:
            server_url: Base URL of MCP server (e.g., "http://localhost:3002")
            tool_name: Name of tool to call
            arguments: Tool arguments as dictionary
            
        Returns:
            Tool response as dictionary
            
        Raises:
            httpx.HTTPError: If request fails
            
        Example:
            >>> result = await client.call(
            ...     "http://localhost:3002",
            ...     "get_regime",
            ...     {"symbol": "SAN.MC"}
            ... )
        """
        url = f"{server_url}/tools/{tool_name}"
        
        try:
            logger.debug(f"Calling MCP tool: {url} with args: {arguments}")
            
            response = await self.client.post(
                url,
                json=arguments,
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.debug(f"MCP tool {tool_name} returned: {result}")
            return result
        
        except httpx.HTTPError as e:
            logger.error(f"MCP call failed: {tool_name} at {server_url}: {e}")
            raise
    
    async def health_check(self, server_url: str) -> bool:
        """
        Check if an MCP server is healthy.
        
        Args:
            server_url: Base URL of MCP server
            
        Returns:
            True if server is healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{server_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed for {server_url}: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


class MCPServers:
    """
    Container for MCP server URLs.
    
    Centralizes server URL configuration.
    """
    
    def __init__(
        self,
        market_data_url: str = "http://localhost:3001",
        technical_url: str = "http://localhost:3002",
        risk_url: str = "http://localhost:3003"
    ):
        """
        Initialize MCP servers configuration.
        
        Args:
            market_data_url: Market data server URL
            technical_url: Technical analysis server URL
            risk_url: Risk management server URL
        """
        self.market_data = market_data_url
        self.technical = technical_url
        self.risk = risk_url
    
    @classmethod
    def from_env(cls):
        """
        Create from environment variables.
        
        Looks for:
        - MCP_MARKET_DATA_URL
        - MCP_TECHNICAL_URL
        - MCP_RISK_URL
        """
        import os
        
        return cls(
            market_data_url=os.getenv("MCP_MARKET_DATA_URL", "http://localhost:3001"),
            technical_url=os.getenv("MCP_TECHNICAL_URL", "http://localhost:3002"),
            risk_url=os.getenv("MCP_RISK_URL", "http://localhost:3003")
        )
