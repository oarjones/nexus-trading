"""
Health check tool for ML Models Server
"""

import mcp.types as types

async def handle_health_check(arguments: dict | None) -> list[types.TextContent]:
    """Handle health check request."""
    return [
        types.TextContent(
            type="text",
            text="ML Models Server is HEALTHY. Ready to serve predictions."
        )
    ]

TOOL_DEF = types.Tool(
    name="health_check",
    description="Verify ML models server status",
    inputSchema={
        "type": "object",
        "properties": {},
    },
)
