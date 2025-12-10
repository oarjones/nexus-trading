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

from src.agents.mcp_client import MCPClient, MCPServers

from src.trading.paper import PaperPortfolioManager, PaperPortfolioProvider

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
        
        # Initialize MCP
        self.mcp_client = MCPClient()
        self.mcp_servers = MCPServers.from_env()
        
        # Initialize Portfolio Provider (Paper Trading for MVP)
        # TODO: Switch to LivePortfolioProvider based on config/mode
        self.portfolio_manager = PaperPortfolioManager()
        self.portfolio_provider = PaperPortfolioProvider(self.portfolio_manager, self.strategy_id)
        
        self.context_builder = ContextBuilder(
            portfolio_provider=self.portfolio_provider,
            mcp_client=self.mcp_client, 
            servers_config=self.mcp_servers
        )
        
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
        
    async def generate_signals(self, context: MarketContext) -> List[Signal]:
        """
        Genera señales delegando al AI Agent (Async).
        """
        try:
            # Determinar nivel de autonomía desde config
            autonomy = AutonomyLevel(self.config.get("autonomy_level", "conservative"))
            
            # Ejecutar flujo del agente directamente (ahora somos async)
            decision = await self._execute_agent_flow(context, autonomy)
            
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

    async def should_close(self, position: PositionInfo, context: MarketContext) -> Optional[Signal]:
        """
        Pregunta al agente si debe cerrar una posición.
        """
        # 1. Hard Rules (SL/TP) - Safety net
        if position.stop_loss and position.current_price <= position.stop_loss:
             return Signal(
                strategy_id=self.strategy_id, symbol=position.symbol,
                direction=SignalDirection.CLOSE, confidence=1.0,
                entry_price=position.current_price,
                reasoning=f"Hard Stop Loss triggered at {position.current_price}"
            )
            
        if position.take_profit and position.current_price >= position.take_profit:
             return Signal(
                strategy_id=self.strategy_id, symbol=position.symbol,
                direction=SignalDirection.CLOSE, confidence=1.0,
                entry_price=position.current_price,
                reasoning=f"Hard Take Profit triggered at {position.current_price}"
            )
            
        # 2. AI Agent Review (Future specific prompt)
        # For now, return None to HOLD unless hard rules are hit
        return None
