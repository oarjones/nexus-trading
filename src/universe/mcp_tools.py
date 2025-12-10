"""
Universe Suggestion Tool for AI Agent

Esta herramienta permite al AI Agent sugerir cambios al universo de símbolos:
- ADD: Añadir un símbolo al universo activo
- REMOVE: Quitar un símbolo del universo activo
- WATCH: Marcar un símbolo para observación

Las sugerencias se validan automáticamente antes de aplicarse.
"""

from typing import Optional
import logging
from datetime import datetime, timezone

from mcp.types import Tool, TextContent
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class UniverseSuggestionInput(BaseModel):
    """Input schema para sugerencias de universo."""
    
    symbol: str = Field(
        ...,
        description="Ticker del símbolo (ej: 'AAPL', 'SPY', 'ASML.AS')"
    )
    
    action: str = Field(
        ...,
        description="Acción a realizar: 'add', 'remove', o 'watch'"
    )
    
    reason: str = Field(
        ...,
        description="Razón detallada para la sugerencia"
    )
    
    confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Nivel de confianza (0.0 a 1.0)"
    )
    
    @field_validator('action')
    @classmethod
    def validate_action(cls, v):
        valid_actions = ['add', 'remove', 'watch']
        if v.lower() not in valid_actions:
            raise ValueError(f"action must be one of: {valid_actions}")
        return v.lower()
    
    @field_validator('symbol')
    @classmethod
    def validate_symbol(cls, v):
        if not v or len(v) < 1:
            raise ValueError("symbol cannot be empty")
        return v.upper()


class UniverseQueryInput(BaseModel):
    """Input schema para consultar el universo."""
    
    query_type: str = Field(
        default="active",
        description="Tipo de consulta: 'active', 'summary', 'suggestions', 'by_sector'"
    )
    
    sector: Optional[str] = Field(
        default=None,
        description="Sector a filtrar (solo para query_type='by_sector')"
    )


# Definición de herramientas
UNIVERSE_SUGGEST_TOOL = Tool(
    name="universe_suggest",
    description="""
    Sugiere cambios al universo de símbolos operables.
    
    El AI Agent puede usar esta herramienta para:
    - ADD: Proponer añadir un símbolo que parece prometedor
    - REMOVE: Proponer quitar un símbolo con mal rendimiento o riesgo
    - WATCH: Marcar un símbolo para observación sin cambiar el universo
    
    Las sugerencias se validan automáticamente y se procesan en el 
    siguiente screening diario. Requiere una razón detallada.
    
    Ejemplos de uso:
    - Añadir: momentum fuerte, rotura de resistencia, catalizador
    - Quitar: pérdida de momentum, riesgo elevado, baja liquidez
    - Watch: pendiente de earnings, evento próximo, configuración formándose
    """,
    inputSchema=UniverseSuggestionInput.model_json_schema()
)


UNIVERSE_QUERY_TOOL = Tool(
    name="universe_query",
    description="""
    Consulta información sobre el universo de símbolos actual.
    
    Tipos de consulta:
    - 'active': Lista de símbolos activos hoy
    - 'summary': Resumen del último screening
    - 'suggestions': Sugerencias pendientes
    - 'by_sector': Símbolos activos filtrados por sector
    """,
    inputSchema=UniverseQueryInput.model_json_schema()
)


async def handle_universe_suggest(
    universe_manager,  # UniverseManager instance
    arguments: dict
) -> list[TextContent]:
    """
    Procesar sugerencia del AI Agent.
    
    Args:
        universe_manager: Instancia del UniverseManager
        arguments: Argumentos de la herramienta
        
    Returns:
        Lista con resultado de la operación
    """
    try:
        input_data = UniverseSuggestionInput(**arguments)
        
        # Crear sugerencia
        suggestion_data = {
            "symbol": input_data.symbol,
            "type": input_data.action,
            "reason": input_data.reason,
            "confidence": input_data.confidence,
        }
        
        # Añadir al manager
        success = universe_manager.add_suggestion_from_dict(suggestion_data)
        
        if success:
            result = f"""✅ Sugerencia registrada:
- Símbolo: {input_data.symbol}
- Acción: {input_data.action.upper()}
- Confianza: {input_data.confidence:.0%}
- Razón: {input_data.reason}

La sugerencia será procesada en el próximo screening diario."""
        else:
            result = f"""⚠️ Sugerencia no aceptada:
- Símbolo: {input_data.symbol}
- Acción: {input_data.action.upper()}

Posibles razones:
- Límite diario de sugerencias alcanzado
- Confianza por debajo del umbral mínimo (0.6)
- Símbolo no válido"""
        
        return [TextContent(type="text", text=result)]
        
    except Exception as e:
        logger.error(f"Error processing universe suggestion: {e}")
        return [TextContent(
            type="text",
            text=f"❌ Error procesando sugerencia: {str(e)}"
        )]


async def handle_universe_query(
    universe_manager,  # UniverseManager instance
    arguments: dict
) -> list[TextContent]:
    """
    Procesar consulta sobre el universo.
    
    Args:
        universe_manager: Instancia del UniverseManager
        arguments: Argumentos de la herramienta
        
    Returns:
        Lista con información solicitada
    """
    try:
        input_data = UniverseQueryInput(**arguments)
        query_type = input_data.query_type
        
        if query_type == "active":
            symbols = universe_manager.active_symbols
            if not symbols:
                result = "⚠️ No hay universo activo. Ejecuta el screening diario primero."
            else:
                result = f"""📊 Universo Activo ({len(symbols)} símbolos):

{', '.join(sorted(symbols))}"""
        
        elif query_type == "summary":
            summary = universe_manager.get_screening_summary()
            if summary.get("status") == "no_screening":
                result = "⚠️ No hay screening registrado. Ejecuta run_daily_screening()."
            else:
                funnel = summary["filter_funnel"]
                ai = summary["ai_impact"]
                result = f"""📈 Resumen del Screening ({summary['date']}):

**Régimen**: {summary['regime']}
**Símbolos Activos**: {summary['active_count']}

**Funnel de Filtros**:
- Universo Maestro: {funnel['master']}
- Tras Liquidez: {funnel['after_liquidity']}
- Tras Tendencia: {funnel['after_trend']}
- Final: {funnel['final']}

**Impacto AI**:
- Sugerencias: {ai['suggestions']}
- Añadidos: {ai['additions']}
- Removidos: {ai['removals']}

Screening ejecutado: {summary['screened_at']}"""
        
        elif query_type == "suggestions":
            pending = universe_manager._pending_suggestions
            if not pending:
                result = "📝 No hay sugerencias pendientes."
            else:
                lines = ["📝 Sugerencias Pendientes:", ""]
                for s in pending:
                    status_icon = {
                        "pending": "⏳",
                        "approved": "✅",
                        "rejected": "❌",
                        "expired": "⌛"
                    }.get(s.status.value, "?")
                    lines.append(
                        f"{status_icon} {s.suggestion_type.value.upper()} {s.symbol} "
                        f"(conf: {s.confidence:.0%}) - {s.reason[:50]}..."
                    )
                result = "\n".join(lines)
        
        elif query_type == "by_sector":
            sector = input_data.sector
            if not sector:
                result = "⚠️ Debes especificar 'sector' para este tipo de consulta."
            else:
                symbols = universe_manager.get_symbols_by_sector(sector)
                if not symbols:
                    result = f"No hay símbolos activos en el sector '{sector}'."
                else:
                    result = f"""📊 Símbolos en sector '{sector}' ({len(symbols)}):

{', '.join(sorted(symbols))}"""
        
        else:
            result = f"⚠️ Tipo de consulta no reconocido: {query_type}"
        
        return [TextContent(type="text", text=result)]
        
    except Exception as e:
        logger.error(f"Error processing universe query: {e}")
        return [TextContent(
            type="text",
            text=f"❌ Error en consulta: {str(e)}"
        )]


# Registro de herramientas para el servidor MCP
UNIVERSE_TOOLS = [
    UNIVERSE_SUGGEST_TOOL,
    UNIVERSE_QUERY_TOOL,
]


def get_tool_handlers(universe_manager):
    """
    Obtener handlers de herramientas para integración con MCP server.
    
    Args:
        universe_manager: Instancia del UniverseManager
        
    Returns:
        Diccionario de tool_name -> handler_function
    """
    return {
        "universe_suggest": lambda args: handle_universe_suggest(universe_manager, args),
        "universe_query": lambda args: handle_universe_query(universe_manager, args),
    }
