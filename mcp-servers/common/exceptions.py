"""
Common exceptions for MCP servers.

Defines custom exception classes for domain-specific errors
in MCP tool execution and server operations.
"""


class MCPError(Exception):
    """Base exception for all MCP-related errors."""
    pass


class ToolError(MCPError):
    """Raised when a tool execution fails."""
    pass


class ConfigError(MCPError):
    """Raised when configuration is invalid or missing."""
    pass


class ValidationError(MCPError):
    """Raised when input validation fails."""
    pass


class ConnectionError(MCPError):
    """Raised when connection to external service fails."""
    pass
