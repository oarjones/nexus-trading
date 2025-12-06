"""
Strategy Runner - Ejecutor de estrategias de trading.

Coordina:
- Obtención del régimen actual
- Selección de estrategias activas
- Generación de señales
- Evaluación de cierres
- Publicación en canal pub/sub
"""

import asyncio
from datetime import datetime
from typing import Optional
import logging

from .interfaces import (
    Signal,
    SignalDirection,
    MarketRegime,
    MarketContext,
    PositionInfo,
)
from .registry import StrategyRegistry
from .config import get_strategy_config


logger = logging.getLogger("strategy.runner")


class StrategyRunner:
    """
    Ejecutor principal de estrategias.
    
    Responsabilidades:
    1. Consultar régimen de mercado (via mcp-ml-models)
    2. Obtener datos de mercado (via mcp-market-data)
    3. Ejecutar estrategias activas para el régimen
    4. Publicar señales generadas
    
    Uso:
        runner = StrategyRunner(mcp_client, message_bus)
        await runner.run_cycle()  # Un ciclo de análisis
        # o
        await runner.start()  # Loop continuo
    """
    
    def __init__(
        self,
        mcp_client,           # Cliente MCP para llamar a servers
        message_bus = None,   # Bus para publicar señales (opcional)
        db_session = None,    # Sesión de BD para posiciones
        config_path: str = None
    ):
        """
        Inicializar runner.
        
        Args:
            mcp_client: Cliente para comunicación con MCP servers
            message_bus: Bus de mensajes para publicar señales
            db_session: Sesión de base de datos
            config_path: Ruta a configuración
        """
        self.mcp = mcp_client
        self.bus = message_bus
        self.db = db_session
        self.config = get_strategy_config(config_path)
        
        self._running = False
        self._last_run: Optional[datetime] = None
        self._signals_generated: int = 0
        self._cycles_completed: int = 0
    
    async def run_cycle(self) -> list[Signal]:
        """
        Ejecutar un ciclo completo de análisis.
        
        Returns:
            Lista de señales generadas en este ciclo
        """
        cycle_start = datetime.utcnow()
        all_signals: list[Signal] = []
        
        try:
            # 1. Obtener régimen actual
            regime_data = await self._get_current_regime()
            regime = MarketRegime(regime_data["regime"])
            regime_confidence = regime_data["confidence"]
            
            logger.info(
                f"Régimen actual: {regime.value} "
                f"(confianza: {regime_confidence:.2f})"
            )
            
            # 2. Obtener estrategias activas para este régimen
            active_strategies = StrategyRegistry.get_active_for_regime(
                regime,
                self.config.config
            )
            
            if not active_strategies:
                logger.info(f"No hay estrategias activas para régimen {regime.value}")
                return all_signals
            
            logger.info(
                f"Estrategias activas: "
                f"{[s.strategy_id for s in active_strategies]}"
            )
            
            # 3. Obtener datos de mercado
            symbols = self._get_all_symbols(active_strategies)
            market_data = await self._get_market_data(symbols)
            
            # 4. Obtener posiciones actuales
            positions = await self._get_current_positions()
            capital = await self._get_available_capital()
            
            # 5. Construir contexto
            context = MarketContext(
                regime=regime,
                regime_confidence=regime_confidence,
                regime_probabilities=regime_data.get("probabilities", {}),
                market_data=market_data,
                capital_available=capital,
                positions=positions,
            )
            
            # 6. Ejecutar cada estrategia
            for strategy in active_strategies:
                try:
                    # Generar señales de entrada
                    signals = strategy.generate_signals(context)
                    all_signals.extend(signals)
                    
                    # Evaluar cierres de posiciones existentes
                    for position in positions:
                        if position.strategy_id == strategy.strategy_id:
                            close_signal = strategy.should_close(position, context)
                            if close_signal:
                                all_signals.append(close_signal)
                    
                except Exception as e:
                    logger.error(
                        f"Error ejecutando {strategy.strategy_id}: {e}",
                        exc_info=True
                    )
            
            # 7. Publicar señales
            for signal in all_signals:
                await self._publish_signal(signal)
            
            # 8. Actualizar métricas
            self._signals_generated += len(all_signals)
            self._cycles_completed += 1
            self._last_run = datetime.utcnow()
            
            cycle_duration = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(
                f"Ciclo completado en {cycle_duration:.2f}s, "
                f"{len(all_signals)} señales generadas"
            )
            
        except Exception as e:
            logger.error(f"Error en ciclo de estrategias: {e}", exc_info=True)
        
        return all_signals
    
    async def start(self, interval_seconds: int = 300):
        """
        Iniciar loop continuo de ejecución.
        
        Args:
            interval_seconds: Segundos entre ciclos (default: 5 min)
        """
        self._running = True
        logger.info(f"Strategy Runner iniciado (intervalo: {interval_seconds}s)")
        
        while self._running:
            await self.run_cycle()
            await asyncio.sleep(interval_seconds)
    
    async def stop(self):
        """Detener loop de ejecución."""
        self._running = False
        logger.info("Strategy Runner detenido")
    
    async def _get_current_regime(self) -> dict:
        """
        Obtener régimen actual desde mcp-ml-models.
        
        Returns:
            {
                "regime": "BULL",
                "confidence": 0.75,
                "probabilities": {"BULL": 0.75, ...}
            }
        """
        try:
            response = await self.mcp.call(
                server="mcp-ml-models",
                tool="get_regime",
                params={}
            )
            return response
        except Exception as e:
            logger.error(f"Error obteniendo régimen: {e}")
            # Fallback a SIDEWAYS si no hay régimen
            return {
                "regime": "SIDEWAYS",
                "confidence": 0.50,
                "probabilities": {
                    "BULL": 0.25,
                    "BEAR": 0.25,
                    "SIDEWAYS": 0.25,
                    "VOLATILE": 0.25,
                }
            }
    
    async def _get_market_data(self, symbols: list[str]) -> dict:
        """
        Obtener datos de mercado para símbolos.
        
        Returns:
            {
                "SPY": {
                    "price": 450.0,
                    "prices": [...],  # Histórico
                    "indicators": {...}
                },
                ...
            }
        """
        market_data = {}
        
        for symbol in symbols:
            try:
                # Obtener precio actual y OHLCV histórico
                ohlcv = await self.mcp.call(
                    server="mcp-market-data",
                    tool="get_ohlcv",
                    params={
                        "symbol": symbol,
                        "timeframe": "1d",
                        "limit": 300  # ~1 año
                    }
                )
                
                # Obtener indicadores técnicos
                indicators = await self.mcp.call(
                    server="mcp-technical",
                    tool="get_indicators",
                    params={
                        "symbol": symbol,
                        "indicators": [
                            "rsi_14",
                            "sma_50",
                            "sma_200",
                            "atr_14",
                            "volatility_20d"
                        ]
                    }
                )
                
                market_data[symbol] = {
                    "price": ohlcv["close"][-1] if ohlcv.get("close") else 0,
                    "prices": ohlcv.get("close", []),
                    "volume": ohlcv.get("volume", []),
                    "indicators": indicators,
                }
                
            except Exception as e:
                logger.warning(f"Error obteniendo datos para {symbol}: {e}")
        
        return market_data
    
    async def _get_current_positions(self) -> list[PositionInfo]:
        """Obtener posiciones abiertas desde BD."""
        if not self.db:
            return []
        
        # Pseudo-código - implementación real usa SQLAlchemy
        # positions = self.db.query(Position).filter(
        #     Position.status == "open"
        # ).all()
        # return [self._to_position_info(p) for p in positions]
        
        return []
    
    async def _get_available_capital(self) -> float:
        """Obtener capital disponible."""
        # Pseudo-código - implementación real consulta broker/BD
        # return await self.mcp.call("mcp-ibkr", "get_account_value")
        
        return self.config.get("global.paper_trading_capital", 25000.0)
    
    def _get_all_symbols(self, strategies) -> list[str]:
        """Obtener todos los símbolos de todas las estrategias."""
        symbols = set()
        for strategy in strategies:
            symbols.update(strategy.symbols)
        return list(symbols)
    
    async def _publish_signal(self, signal: Signal):
        """Publicar señal en bus de mensajes."""
        if not self.bus:
            logger.debug(f"Signal (no bus): {signal.symbol} {signal.direction.value}")
            return
        
        try:
            await self.bus.publish("signals", signal.to_dict())
            logger.info(
                f"Señal publicada: {signal.symbol} {signal.direction.value} "
                f"conf={signal.confidence:.2f}"
            )
        except Exception as e:
            logger.error(f"Error publicando señal: {e}")
    
    def get_metrics(self) -> dict:
        """Obtener métricas del runner."""
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "signals_generated_total": self._signals_generated,
            "cycles_completed": self._cycles_completed,
            "registered_strategies": StrategyRegistry.get_info(),
        }
