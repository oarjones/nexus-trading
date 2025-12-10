"""
Context Builder para AI Agent.

Responsable de recopilar y estructurar toda la información necesaria
para que el LLM tome decisiones informadas.
"""

import logging
import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from src.strategies.interfaces import MarketRegime
from src.trading.paper.provider import PortfolioProvider
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
    3. Estado del portfolio (PortfolioProvider - Paper or Live)
    4. Límites de riesgo (Risk Manager)
    """
    
    def __init__(self, portfolio_provider: PortfolioProvider, mcp_client=None, servers_config=None):
        """
        Inicializar ContextBuilder.
        
        Args:
            portfolio_provider: Abstracción del portfolio (Source of Truth)
            mcp_client: Cliente MCP para acceder a servicios externos (Market Data, ML)
            servers_config: Configuración de URLs de servidores MCP
        """
        self.portfolio_provider = portfolio_provider
        self.mcp_client = mcp_client
        self.servers = servers_config
        
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
            # Intentar usar MCP si está disponible
            if self.mcp_client and self.servers:
                result = await self.mcp_client.call(
                    self.servers.ml_models,
                    "get_regime",
                    {"symbol": "SPY", "use_cache": True}
                )
                
                return RegimeInfo(
                    regime=result.get("regime", "UNCERTAIN"),
                    confidence=result.get("confidence", 0.0),
                    probabilities=result.get("probabilities", {}),
                    model_id=result.get("model_id", "mcp_hmm"),
                    days_in_regime=result.get("days_in_regime", 0)
                )
            
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
        if self.mcp_client and self.servers:
            try:
                # Paralelizar llamadas
                tasks = [
                    self.mcp_client.call(self.servers.market_data, "get_quote", {"symbol": "SPY"}),
                    self.mcp_client.call(self.servers.market_data, "get_quote", {"symbol": "QQQ"}),
                    self.mcp_client.call(self.servers.market_data, "get_quote", {"symbol": "VIX"}),
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Procesar resultados (con manejo de errores)
                spy_data = results[0] if not isinstance(results[0], Exception) else {}
                qqq_data = results[1] if not isinstance(results[1], Exception) else {}
                vix_data = results[2] if not isinstance(results[2], Exception) else {}
                
                return MarketContext(
                    spy_change_pct=spy_data.get("change_pct", 0.0),
                    qqq_change_pct=qqq_data.get("change_pct", 0.0),
                    vix_level=vix_data.get("price", 15.0),
                    vix_change_pct=vix_data.get("change_pct", 0.0),
                    market_breadth=0.5, # TODO: Implementar indicador de amplitud
                    sector_rotation={} # TODO: Implementar rotación
                )
            except Exception as e:
                logger.error(f"Error fetching market context: {e}")

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
        """Obtener estado del portfolio desde el proveedor."""
        try:
            return await self.portfolio_provider.get_portfolio_summary()
        except Exception as e:
            logger.error(f"Error getting portfolio summary: {e}")
            # Retornar objeto vacío seguro en caso de error
            return PortfolioSummary(
                total_value=0.0, cash_available=0.0, invested_value=0.0, 
                positions=(), daily_pnl=0.0, daily_pnl_pct=0.0, 
                total_pnl=0.0, total_pnl_pct=0.0
            )
        
    async def _get_watchlist_data(self, symbols: List[str]) -> List[SymbolData]:
        """Obtener datos técnicos para la watchlist."""
        data = []
        
        if self.mcp_client and self.servers:
            # Crear tareas para cada símbolo
            tasks = []
            for symbol in symbols:
                tasks.append(self.mcp_client.call(
                    self.servers.technical, 
                    "calculate_indicators", 
                    {"symbol": symbol, "period": 100}
                ))
            
            # También necesitamos precios actuales
            # Podríamos obtenerlos del endpoint calculate_indicators si los incluye,
            # o hacer llamadas adicionales a market_data. 
            # Asumiremos que technical devuelve todo lo necesario o combinamos.
            # Por simplicidad ahora, technical returns indicators.
            # We might fallback to market_data for price if missing.
            
            # Ejecutar todas las llamadas
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, symbol in enumerate(symbols):
                res = results[i]
                if isinstance(res, Exception) or not res:
                    logger.warning(f"Failed to get data for {symbol}: {res}")
                    # Agregar mock si falla
                    data.append(self._create_mock_symbol_data(symbol))
                    continue
                
                # Mapear respuesta a SymbolData
                # Nota: Asumimos la estructura de respuesta de technical server
                # Ajustar claves según la implementación real de calculate_indicators
                
                # Extraer valores seguros con defaults
                rsi_val = res.get("RSI", {}).get("value", 50.0)
                macd_data = res.get("MACD", {})
                sma_data = res.get("SMA", {})
                bb_data = res.get("BB", {})
                atr_data = res.get("ATR", {})
                adx_data = res.get("ADX", {})
                
                # Precio actual (si viene en response o default)
                # Idealmente deberíamos llamar a get_quote si no está aquí.
                current_price = res.get("price", 100.0) 
                
                data.append(SymbolData(
                    symbol=symbol,
                    name=res.get("name", f"Name for {symbol}"),
                    current_price=current_price,
                    change_pct=res.get("change_pct", 0.0),
                    volume=res.get("volume", 1000000),
                    avg_volume_20d=res.get("avg_volume", 900000),
                    rsi_14=rsi_val,
                    macd=macd_data.get("macd", 0.0),
                    macd_signal=macd_data.get("signal", 0.0),
                    macd_histogram=macd_data.get("histogram", 0.0),
                    sma_20=sma_data.get("sma_20", current_price), # Fallback to current if missing
                    sma_50=sma_data.get("sma_50", current_price),
                    sma_200=sma_data.get("sma_200", current_price),
                    bb_upper=bb_data.get("upper", current_price * 1.02),
                    bb_middle=bb_data.get("middle", current_price),
                    bb_lower=bb_data.get("lower", current_price * 0.98),
                    atr_14=atr_data.get("value", 1.0),
                    adx_14=adx_data.get("value", 20.0)
                ))
            
            return data

        for symbol in symbols:
            # Mock data
            data.append(self._create_mock_symbol_data(symbol))
        return data

    def _create_mock_symbol_data(self, symbol: str) -> SymbolData:
        """Helper para crear datos mock."""
        return SymbolData(
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
        )
        
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
