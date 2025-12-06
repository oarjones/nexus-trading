"""
Context Builder para AI Agent.

Responsable de recopilar y estructurar toda la información necesaria
para que el LLM tome decisiones informadas.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from src.strategies.interfaces import MarketRegime
from src.agents.llm.interfaces import (
    AgentContext,
    RegimeInfo,
    MarketContext,
    PortfolioSummary,
    PortfolioPosition,
    SymbolData,
    RiskLimits,
    AutonomyLevel,
)

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Constructor de contexto para el AI Agent.
    
    Agrega datos de múltiples fuentes:
    1. Régimen de mercado (MCP ML Models)
    2. Datos de mercado (MCP Market Data / Local Providers)
    3. Estado del portfolio (MCP Trading / Local)
    4. Límites de riesgo (Risk Manager)
    """
    
    def __init__(self, mcp_client=None, data_provider=None):
        """
        Inicializar ContextBuilder.
        
        Args:
            mcp_client: Cliente MCP para acceder a servicios externos
            data_provider: Proveedor de datos local (fallback/alternativa)
        """
        self.mcp_client = mcp_client
        self.data_provider = data_provider
        
    async def build(
        self,
        symbols: List[str],
        autonomy_level: AutonomyLevel = AutonomyLevel.CONSERVATIVE,
        notes: Optional[str] = None
    ) -> AgentContext:
        """
        Construir el contexto completo.
        
        Args:
            symbols: Lista de símbolos a analizar (watchlist)
            autonomy_level: Nivel de autonomía actual
            notes: Notas adicionales opcionales
            
        Returns:
            AgentContext listo para el LLM
        """
        context_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        
        # 1. Obtener Régimen (Paralelizable)
        regime_info = await self._get_regime_info()
        
        # 2. Obtener Contexto de Mercado General
        market_context = await self._get_market_context()
        
        # 3. Obtener Portfolio
        portfolio_summary = await self._get_portfolio_summary()
        
        # 4. Obtener Datos de Símbolos
        watchlist_data = await self._get_watchlist_data(symbols)
        
        # 5. Obtener Límites de Riesgo
        risk_limits = await self._get_risk_limits(portfolio_summary)
        
        return AgentContext(
            context_id=context_id,
            timestamp=timestamp,
            regime=regime_info,
            market=market_context,
            portfolio=portfolio_summary,
            watchlist=tuple(watchlist_data),
            risk_limits=risk_limits,
            autonomy_level=autonomy_level,
            notes=notes
        )
    
    async def _get_regime_info(self) -> RegimeInfo:
        """Obtener información del régimen de mercado."""
        try:
            # Intentar usar MCP si está disponible
            if self.mcp_client:
                # TODO: Implementar llamada real a MCP
                # result = await self.mcp_client.call("mcp-ml-models", "get_regime")
                pass
            
            # Mock/Fallback por ahora
            return RegimeInfo(
                regime="BULL",
                confidence=0.75,
                probabilities={"BULL": 0.75, "BEAR": 0.10, "SIDEWAYS": 0.10, "VOLATILE": 0.05},
                model_id="mock_v1",
                days_in_regime=5
            )
        except Exception as e:
            logger.error(f"Error getting regime info: {e}")
            # Fallback seguro
            return RegimeInfo(
                regime="UNCERTAIN",
                confidence=0.0,
                probabilities={},
                model_id="fallback"
            )
            
    async def _get_market_context(self) -> MarketContext:
        """Obtener contexto general (SPY, VIX, etc)."""
        # Mock/Fallback
        return MarketContext(
            spy_change_pct=0.5,
            qqq_change_pct=0.8,
            vix_level=15.0,
            vix_change_pct=-2.0,
            market_breadth=0.65,
            sector_rotation={"Tech": 1.2, "Energy": -0.5}
        )
        
    async def _get_portfolio_summary(self) -> PortfolioSummary:
        """Obtener estado del portfolio."""
        # Mock/Fallback
        return PortfolioSummary(
            total_value=25000.0,
            cash_available=25000.0,
            invested_value=0.0,
            positions=(),
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            total_pnl=0.0,
            total_pnl_pct=0.0
        )
        
    async def _get_watchlist_data(self, symbols: List[str]) -> List[SymbolData]:
        """Obtener datos técnicos para la watchlist."""
        data = []
        for symbol in symbols:
            # Mock data
            data.append(SymbolData(
                symbol=symbol,
                name=f"Name for {symbol}",
                current_price=100.0,
                change_pct=0.1,
                volume=1000000,
                avg_volume_20d=900000,
                rsi_14=50.0,
                macd=0.1,
                macd_signal=0.05,
                macd_histogram=0.05,
                sma_20=98.0,
                sma_50=95.0,
                sma_200=90.0,
                bb_upper=105.0,
                bb_middle=100.0,
                bb_lower=95.0,
                atr_14=1.5,
                adx_14=20.0
            ))
        return data
        
    async def _get_risk_limits(self, portfolio: PortfolioSummary) -> RiskLimits:
        """Obtener límites de riesgo actuales."""
        return RiskLimits(
            max_position_pct=5.0,
            max_portfolio_risk_pct=2.0,
            max_daily_trades=5,
            max_daily_loss_pct=2.0,
            current_daily_trades=0,
            current_daily_pnl_pct=0.0
        )
