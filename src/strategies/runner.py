"""
Strategy Runner - Ejecutor de estrategias de trading.

Coordina:
- Obtención del régimen actual
- Gestión del universo de símbolos (via UniverseManager)
- Selección de estrategias activas
- Generación de señales
- Evaluación de cierres
- Publicación en canal pub/sub
"""

import asyncio
from datetime import datetime, date, timezone
from typing import Optional
import logging
import json
from pathlib import Path

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
    2. Gestionar universo de símbolos (via UniverseManager)
    3. Obtener datos de mercado (via mcp-market-data)
    4. Ejecutar estrategias activas para el régimen
    5. Publicar señales generadas
    
    Uso:
        runner = StrategyRunner(mcp_client, message_bus)
        await runner.run_cycle()  # Un ciclo de análisis
        # o
        await runner.start()  # Loop continuo
        
    Con UniverseManager (recomendado):
        universe_mgr = UniverseManager(registry, data_provider)
        runner = StrategyRunner(mcp_client, message_bus, universe_manager=universe_mgr)
        # El screening se ejecuta automáticamente una vez al día
    """
    
    def __init__(
        self,
        mcp_client,           # Cliente MCP para llamar a servers
        message_bus = None,   # Bus para publicar señales (opcional)
        db_session = None,    # Sesión de BD para posiciones
        config_path: str = None,
        universe_manager = None,  # UniverseManager (opcional)
        status_writer = None,     # StatusWriter (opcional)
    ):
        """
        Inicializar runner.
        
        Args:
            mcp_client: Cliente para comunicación con MCP servers
            message_bus: Bus de mensajes para publicar señales
            db_session: Sesión de base de datos
            config_path: Ruta a configuración
            universe_manager: Gestor de universo de símbolos (opcional)
        """
        self.mcp = mcp_client
        self.bus = message_bus
        self.db = db_session
        self.config = get_strategy_config(config_path)
        self.universe_manager = universe_manager
        self.status_writer = status_writer
        self.signals_cache_file = Path("data/signals_cache.json")
        
        self._running = False
        self._last_run: Optional[datetime] = None
        self._last_universe_update: Optional[date] = None
        self._signals_generated: int = 0
        self._cycles_completed: int = 0
    
    async def run_single_strategy(self, strategy_id: str) -> list[Signal]:
        """
        Ejecutar una única estrategia por ID.
        
        Args:
            strategy_id: ID de la estrategia a ejecutar.
            
        Returns:
            Lista de señales generadas.
        """
        logger.info(f"START: Ejecutando estrategia {strategy_id}")
        start_time = datetime.now(timezone.utc)
        generated_signals = []
        
        try:
            # 1. Obtener instancia de estrategia
            strategy_config = self.config.get("strategies", {}).get(strategy_id)
            if not strategy_config or not strategy_config.get("enabled", False):
                logger.warning(f"Estrategia {strategy_id} no encontrada o deshabilitada.")
                return []
                
            strategy = StrategyRegistry.get(strategy_id, strategy_config)
            if not strategy:
                logger.error(f"No se pudo instanciar la estrategia {strategy_id}")
                return []
                
            # 2. Contexto de Mercado (Regime + Data)
            # Nota: Optimizamos obteniendo solo datos necesarios para esta estrategias
            # pero por simplicidad reutilizamos lógica general por ahora
            regime_data = await self._get_current_regime()
            regime = MarketRegime(regime_data["regime"])
            
            # Verificar si puede operar
            if not strategy.can_operate_in_regime(regime):
                logger.info(f"Estrategia {strategy_id} pausada en régimen {regime.value}")
                return []
                
            # Datos de mercado
            symbols = list(strategy.symbols) if hasattr(strategy, 'symbols') else []
            # Si tiene universo dinámico, inyectarlo (aunque run_single suele ser para específicas)
            if self.universe_manager and hasattr(strategy, 'set_universe'):
                 symbols = self.universe_manager.active_symbols
                 strategy.set_universe(symbols)
                 
            market_data = await self._get_market_data(symbols)
            positions = await self._get_current_positions()
            capital = await self._get_available_capital()
            
            context = MarketContext(
                regime=regime,
                regime_confidence=regime_data["confidence"],
                regime_probabilities=regime_data.get("probabilities", {}),
                market_data=market_data,
                capital_available=capital,
                positions=positions,
            )
            
            # 3. Generar Señales
            signals = await strategy.generate_signals(context)
            generated_signals.extend(signals)
            
            # 4. REVIEWER / SIMULATOR HOOK
            # Aquí podríamos llamar al OrderSimulator si estamos en modo Paper
            if hasattr(self, 'order_simulator') and self.order_simulator:
                logger.info(f"Simulando {len(signals)} señales para {strategy_id}")
                for sig in signals:
                    await self.order_simulator.process_signal(sig)
            
            # 5. Publicar
            for sig in signals:
                await self._publish_signal(sig)
                
            logger.info(f"END: Estrategia {strategy_id} finalizada. {len(signals)} señales.")
            
        except Exception as e:
            logger.error(f"Error ejecutando single strategy {strategy_id}: {e}", exc_info=True)
            
        return generated_signals

    async def run_cycle(self) -> list[Signal]:
        """
        Ejecutar un ciclo completo de análisis.
        
        Returns:
            Lista de señales generadas en este ciclo
        """
        cycle_start = datetime.now(timezone.utc)
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
            
            # 2. Actualizar universo si es necesario (una vez al día)
            await self._update_universe_if_needed(regime)
            
            # 3. Obtener estrategias activas para este régimen
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
            
            # 4. Inyectar dependencias (Universo, Portfolio)
            self._inject_dependencies(active_strategies)
            
            # 5. Obtener datos de mercado
            symbols = self._get_all_symbols(active_strategies)
            market_data = await self._get_market_data(symbols)
            
            # 6. Obtener posiciones actuales
            positions = await self._get_current_positions()
            capital = await self._get_available_capital()
            
            # 7. Construir contexto
            context = MarketContext(
                regime=regime,
                regime_confidence=regime_confidence,
                regime_probabilities=regime_data.get("probabilities", {}),
                market_data=market_data,
                capital_available=capital,
                positions=positions,
            )
            
            # 8. Ejecutar cada estrategia
            for strategy in active_strategies:
                try:
                    # Generar señales de entrada
                    signals = await strategy.generate_signals(context)
                    all_signals.extend(signals)
                    
                    # Evaluar cierres de posiciones existentes
                    for position in positions:
                        if position.strategy_id == strategy.strategy_id:
                            close_signal = await strategy.should_close(position, context)
                            if close_signal:
                                all_signals.append(close_signal)
                    
                except Exception as e:
                    logger.error(
                        f"Error ejecutando {strategy.strategy_id}: {e}",
                        exc_info=True
                    )
            
            # 9. Publicar señales
            for signal in all_signals:
                await self._publish_signal(signal)
            
            # 10. Actualizar métricas
            self._signals_generated += len(all_signals)
            self._cycles_completed += 1
            self._last_run = datetime.now(timezone.utc)
            
            cycle_duration = (datetime.now(timezone.utc) - cycle_start).total_seconds()
            logger.info(
                f"Ciclo completado en {cycle_duration:.2f}s, "
                f"{len(all_signals)} señales generadas"
            )
            
            # 11. Cachear señales para dashboard (DOC-07)
            await self._persist_signals_cache(all_signals)
            
            # 12. Actualizar status writer
            if self.status_writer:
                self.status_writer.record_execution("orchestrator", len(all_signals))
            
        except Exception as e:
            logger.error(f"Error en ciclo de estrategias: {e}", exc_info=True)
            if self.status_writer:
                self.status_writer.increment_error()
        
        return all_signals
    
    async def _persist_signals_cache(self, signals: list[Signal]):
        """Persist generated signals to JSON for Dashboard."""
        if not signals:
            return
            
        try:
            # Load existing if any to keep history tailored?
            # For MVP just Overwrite execution snapshots or Append?
            # DOC-07 implies recent signals. We'll overwrite with latest batch + keep some history if feasible.
            # Simplified: Overwrite with current batch for instant feedback.
            
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(signals),
                "signals": [s.to_dict() for s in signals]
            }
            
            self.signals_cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.signals_cache_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error persisting signals cache: {e}")

    async def _update_universe_if_needed(self, regime: MarketRegime) -> None:
        """
        Actualizar universo de símbolos si es necesario.
        
        El screening se ejecuta una vez al día, típicamente en el primer
        ciclo del día.
        """
        if not self.universe_manager:
            return
        
        today = date.today()
        
        # Ya actualizamos hoy?
        if self._last_universe_update == today:
            return
        
        logger.info("Ejecutando screening diario del universo...")
        
        try:
            universe = await self.universe_manager.run_daily_screening(regime)
            self._last_universe_update = today
            
            logger.info(
                f"Universo actualizado: {len(universe.active_symbols)} símbolos activos "
                f"(régimen: {regime.value})"
            )
        except Exception as e:
            logger.error(f"Error actualizando universo: {e}")
    
    def _inject_dependencies(self, strategies) -> None:
        """
        Inyectar dependencias (Universe, Portfolio) a las estrategias.
        """
        for strategy in strategies:
            # 1. Inyectar Universe
            if self.universe_manager and hasattr(strategy, 'set_universe'):
                active_symbols = self.universe_manager.active_symbols
                if active_symbols:
                    strategy.set_universe(active_symbols)
                    
            # 2. Inyectar Portfolio Provider (Si está disponible en Runner)
            if hasattr(self, 'portfolio_manager') and hasattr(strategy, 'set_portfolio_provider'):
                # Crear provider wrapper si no existe
                # Asumimos que StrategyRunner tiene un PortfolioManager (Paper o Live)
                # En este MVP es paper
                from src.trading.paper.provider import PaperPortfolioProvider
                provider = PaperPortfolioProvider(self.portfolio_manager, strategy.strategy_id)
                strategy.set_portfolio_provider(provider)
                logger.debug(f"Inyectado PortfolioProvider a {strategy.strategy_id}")

    def _inject_universe_to_strategies(self, strategies) -> None:
        # Deprecated by _inject_dependencies but kept for compatibility or routed
        self._inject_dependencies(strategies)
    
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
            # Usar active_symbols que incluye dinámicos si están
            if hasattr(strategy, 'active_symbols'):
                symbols.update(strategy.active_symbols)
            else:
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
        metrics = {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "signals_generated_total": self._signals_generated,
            "cycles_completed": self._cycles_completed,
            "registered_strategies": StrategyRegistry.get_info(),
        }
        
        # Añadir métricas del UniverseManager si está disponible
        if self.universe_manager:
            metrics["universe"] = {
                "enabled": True,
                "last_update": self._last_universe_update.isoformat() if self._last_universe_update else None,
                "active_symbols_count": len(self.universe_manager.active_symbols),
                "screening_summary": self.universe_manager.get_screening_summary(),
            }
        else:
            metrics["universe"] = {"enabled": False}
        
        return metrics
