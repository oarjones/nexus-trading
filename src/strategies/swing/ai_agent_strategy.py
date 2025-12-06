"""
Estrategia Swing basada en AI Agent.

Esta clase actúa como un wrapper que adapta un LLMAgent (como Claude)
a la interfaz estándar TradingStrategy del sistema.
"""

import logging
import asyncio
from typing import List, Optional

from src.strategies.interfaces import (
    TradingStrategy,
    MarketRegime,
    MarketContext,
    Signal,
    PositionInfo,
    SignalDirection
)
from src.agents.llm.factory import LLMAgentFactory
from src.agents.llm.context_builder import ContextBuilder
from src.agents.llm.interfaces import AutonomyLevel

logger = logging.getLogger(__name__)


class AIAgentStrategy(TradingStrategy):
    """
    Estrategia que delega las decisiones a un AI Agent.
    """
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        
        # Configuración específica
        self.agent_config = self.config.get("agent_config", {})
        self.symbols = self.config.get("symbols", ["SPY", "QQQ", "IWM"])
        
        # Inicializar componentes
        self.agent = LLMAgentFactory.create_from_config_object(self.agent_config) if self.agent_config else LLMAgentFactory.create()
        self.context_builder = ContextBuilder()
        
        # Estado
        self._last_decision = None
        
    @property
    def strategy_id(self) -> str:
        return "ai_agent_swing"
        
    @property
    def strategy_name(self) -> str:
        return f"AI Agent Swing ({self.agent.provider})"
        
    @property
    def strategy_description(self) -> str:
        return "Estrategia swing trading gestionada por LLM con análisis contextual completo."
        
    @property
    def required_regime(self) -> List[MarketRegime]:
        # El agente puede operar en varios regímenes, configurable
        return [
            MarketRegime.BULL,
            MarketRegime.SIDEWAYS,
            # MarketRegime.BEAR  # Opcional si soporta shorting
        ]
        
    def generate_signals(self, context: MarketContext) -> List[Signal]:
        """
        Genera señales delegando al AI Agent.
        
        Nota: Este método es síncrono en la interfaz base, pero el agente es async.
        Usamos asyncio.run() o loop existente.
        """
        try:
            # Determinar nivel de autonomía desde config
            autonomy = AutonomyLevel(self.config.get("autonomy_level", "conservative"))
            
            # Ejecutar flujo del agente
            # En un entorno real, esto debería ser non-blocking si el runner lo soporta
            # Por ahora forzamos ejecución síncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            decision = loop.run_until_complete(
                self._execute_agent_flow(context, autonomy)
            )
            loop.close()
            
            if decision:
                self._last_decision = decision
                self._last_signals = decision.signals
                return decision.signals
                
            return []
            
        except Exception as e:
            logger.error(f"Error generating signals in AIAgentStrategy: {e}")
            return []
            
    async def _execute_agent_flow(self, market_context: MarketContext, autonomy: AutonomyLevel):
        """Flujo asíncrono del agente."""
        # 1. Construir contexto enriquecido
        agent_context = await self.context_builder.build(
            symbols=self.symbols,
            autonomy_level=autonomy
        )
        
        # 2. Obtener decisión
        decision = await self.agent.decide(agent_context)
        
        return decision

    def should_close(self, position: PositionInfo, context: MarketContext) -> Optional[Signal]:
        """
        Pregunta al agente si debe cerrar una posición.
        """
        # TODO: Implementar lógica específica de cierre con el agente
        # Por ahora usamos lógica simple de stop/target si están definidos
        # o delegamos a la lógica base si existiera.
        
        # En el futuro: Crear un prompt específico para gestión de posiciones
        return None
