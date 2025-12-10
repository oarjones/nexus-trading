import logging
from typing import List
from datetime import datetime

from src.strategies.interfaces import Signal, SignalDirection, MarketContext, PositionInfo
from src.agents.llm.interfaces import LLMAgent, AgentContext, AgentDecision

logger = logging.getLogger(__name__)

class PortfolioReviewContext(AgentContext):
    """
    Contexto especializado para revisión de portfolio.
    Sobrescribe to_prompt_text para enfocar al agente en gestión de posiciones.
    """
    def to_prompt_text(self) -> str:
        base_text = super().to_prompt_text()
        
        review_instruction = (
            "\n\n🚨 TAREA ESPECÍFICA: REVISIÓN DE PORTFOLIO 🚨\n"
            "Tu objetivo NO es buscar nuevas entradas. Tu ÚNICO objetivo es gestionar las posiciones abiertas.\n"
            "Para CADA posición abierta, debes decidir:\n"
            "1. HOLD: Mantener la posición tal cual.\n"
            "2. CLOSE: Cerrar la posición inmediatamente (protección de beneficios o stop loss manual).\n"
            "3. ADJUST: (Opcional) Sugerir ajuste de SL/TP.\n\n"
            "Genera señales con dirección CLOSE si decides cerrar.\n"
            "Si decides mantener, NO generes señal (o genera HOLD implícito).\n"
            "Justifica cada decisión basándote en el régimen de mercado y acción del precio reciente."
        )
        
        return base_text + review_instruction

class AIPortfolioReviewer:
    """
    Revisor de portfolio basado en IA.
    Examina las posiciones abiertas y sugiere cierres o ajustes.
    """
    
    def __init__(self, agent: LLMAgent):
        self.agent = agent
        
    async def review_portfolio(self, context: AgentContext) -> List[Signal]:
        """
        Revisar portfolio completo.
        
        Args:
            context: Contexto estándar generado por ContextBuilder.
            
        Returns:
            Lista de señales (principalmente CLOSE).
        """
        # Convertir a contexto de revisión para modificar el prompt
        review_context = PortfolioReviewContext(
            context_id=context.context_id,
            timestamp=context.timestamp,
            regime=context.regime,
            market=context.market,
            portfolio=context.portfolio,
            watchlist=context.watchlist,
            risk_limits=context.risk_limits,
            autonomy_level=context.autonomy_level,
            recent_trades=context.recent_trades,
            recent_signals=context.recent_signals,
            notes=context.notes
        )
        
        if context.portfolio.num_positions == 0:
            logger.info("No hay posiciones para revisar.")
            return []
            
        logger.info(f"Iniciando revisión de portfolio ({context.portfolio.num_positions} posiciones) con {self.agent.provider}")
        
        try:
            decision: AgentDecision = await self.agent.decide(review_context)
            
            # Filtrar solo señales relevantes para gestión (CLOSE, o ajustes si soportados)
            close_signals = [s for s in decision.signals if s.direction == SignalDirection.CLOSE]
            
            if close_signals:
                logger.info(f"AI sugiere cerrar {len(close_signals)} posiciones.")
                for s in close_signals:
                    logger.info(f"  -> CERRAR {s.symbol}: {s.reasoning}")
            else:
                logger.info("AI sugiere mantener todas las posiciones (HOLD).")
                
            return close_signals
            
        except Exception as e:
            logger.error(f"Error durante revisión de portfolio: {e}")
            return []
