"""
Universe Management Module

Gestión dinámica del universo de símbolos operables.

Componentes:
- UniverseManager: Gestor principal del universo
- DailyUniverse: Universo activo para un día
- AISuggestion: Sugerencias del AI Agent
- MCP Tools: Herramientas para integración con AI Agent (opcional)

Uso típico:
    from src.universe import UniverseManager, AISuggestion, SuggestionType
    
    manager = UniverseManager(registry, data_provider)
    await manager.run_daily_screening(regime)
    
    # AI puede sugerir
    suggestion = AISuggestion(
        symbol="NVDA",
        suggestion_type=SuggestionType.ADD,
        reason="Strong momentum in AI sector",
        confidence=0.85
    )
    manager.add_suggestion(suggestion)
"""

from .manager import (
    UniverseManager,
    DailyUniverse,
    AISuggestion,
    SuggestionType,
    SuggestionStatus,
    DataProvider,
)

__all__ = [
    # Core
    "UniverseManager",
    "DailyUniverse",
    "AISuggestion",
    "SuggestionType",
    "SuggestionStatus",
    "DataProvider",
]

# MCP Tools son opcionales (requieren mcp package)
try:
    from .mcp_tools import (
        UNIVERSE_TOOLS,
        UNIVERSE_SUGGEST_TOOL,
        UNIVERSE_QUERY_TOOL,
        handle_universe_suggest,
        handle_universe_query,
        get_tool_handlers,
    )
    __all__.extend([
        "UNIVERSE_TOOLS",
        "UNIVERSE_SUGGEST_TOOL",
        "UNIVERSE_QUERY_TOOL",
        "handle_universe_suggest",
        "handle_universe_query",
        "get_tool_handlers",
    ])
except ImportError:
    # MCP package not installed, tools not available
    pass
