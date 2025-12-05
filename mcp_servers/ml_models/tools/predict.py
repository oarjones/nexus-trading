"""
Prediction tool for ML Models Server
"""

import mcp.types as types
from ..config import config

async def handle_predict_regime(arguments: dict | None) -> list[types.TextContent]:
    """Handle predict_regime request."""
    symbol = arguments.get("symbol")
    # Placeholder logic - will be replaced by actual model inference in Phase A2
    return [
        types.TextContent(
            type="text",
            text=f"Predicted regime for {symbol}: BULL (Confidence: 0.85) [Model: {config.active_model}]"
        )
    ]

TOOL_DEF = types.Tool(
    name="predict_regime",
    description="Predict market regime for a symbol",
    inputSchema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string"},
            "date": {"type": "string"},
            "model_id": {"type": "string"}
        },
        "required": ["symbol"]
    },
)
