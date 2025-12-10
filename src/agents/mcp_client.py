"""
MCP Client helper for communicating with MCP servers.

Provides a simple HTTP client for calling MCP server tools with automatic retry.
"""

import httpx
import logging
from typing import Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Client for calling MCP server tools via HTTP.
    
    Provides a simple interface to call tools on running MCP servers
    with automatic retry on transient failures.
    
    Example:
        >>> client = MCPClient()
        >>> result = await client.call(
        ...     "http://localhost:3002",
        ...     "calculate_indicators",
        ...     {"symbol": "SAN.MC", "indicators": ["RSI", "MACD"]}
        ... )
    """
    
    def __init__(self, timeout: float = 30.0, max_retries: int = 3):
        """
        Initialize MCP client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(timeout=timeout)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def call(
        self,
        server_url: str,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a tool on an MCP server with automatic retry.
        
        Retries on:
        - Connection errors
        - Timeout errors  
        - Network errors
        
        Uses exponential backoff: 1s, 2s, 4s (max 10s)
        
        Args:
            server_url: Base URL of MCP server (e.g., "http://localhost:3002")
            tool_name: Name of tool to call
            arguments: Tool arguments as dictionary
            
        Returns:
            Tool response as dictionary
            
        Raises:
            httpx.HTTPError: If request fails after all retries
            
        Example:
            >>> result = await client.call(
            ...     "http://localhost:3002",
            ...     "get_regime",
            ...     {"symbol": "SAN.MC"}
            ... )
        """
        url = f"{server_url}/tools/{tool_name}"
        
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
        risk_url: str = "http://localhost:3003",
        ml_models_url: str = "http://localhost:3005",
        ibkr_url: str = "http://localhost:3004"
    ):
        """
        Initialize MCP servers configuration.
        
        Args:
            market_data_url: Market data server URL
            technical_url: Technical analysis server URL
            risk_url: Risk management server URL
            ml_models_url: ML models server URL
            ibkr_url: IBKR integration server URL
        """
        self.market_data = market_data_url
        self.technical = technical_url
        self.risk = risk_url
        self.ml_models = ml_models_url
        self.ibkr = ibkr_url
    
    @classmethod
    def from_env(cls):
        """
        Create from environment variables.
        
        Looks for:
        - MCP_MARKET_DATA_URL
        - MCP_TECHNICAL_URL
        - MCP_RISK_URL
        - MCP_ML_MODELS_URL
        - MCP_IBKR_URL
        """
        import os
        
        return cls(
            market_data_url=os.getenv("MCP_MARKET_DATA_URL", "http://localhost:3001"),
            technical_url=os.getenv("MCP_TECHNICAL_URL", "http://localhost:3002"),
            risk_url=os.getenv("MCP_RISK_URL", "http://localhost:3003"),
            ml_models_url=os.getenv("MCP_ML_MODELS_URL", "http://localhost:3005"),
            ibkr_url=os.getenv("MCP_IBKR_URL", "http://localhost:3004")
        )
