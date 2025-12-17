"""
Orquestador del Sistema de Competición de Trading.

Este módulo coordina todo el flujo:
1. Sesión diaria con Claude
2. Ejecución de órdenes
3. Monitoreo de posiciones
4. Actualización de métricas
5. Reportes

Es el "cerebro" que une todos los componentes.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta, time as dt_time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import yaml

from src.agents.llm.agents.competition_agent import CompetitionClaudeAgent
from src.agents.llm.interfaces import AgentContext, AgentDecision
from src.agents.llm.prompts.competition_v2 import PositionSummary, PerformanceMetrics
from src.trading.monitoring.position_monitor import (
    PositionMonitor, 
    MonitoredPosition, 
    PendingOrder,
    CloseReason
)
from src.strategies.interfaces import Signal, SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class TradingSessionConfig:
    """Configuración de la sesión de trading."""
    # Horarios (en hora local del mercado, ET)
    session_start_time: dt_time = dt_time(10, 0)  # 10:00 ET
    trading_window_end: dt_time = dt_time(11, 30)  # 11:30 ET
    market_close_time: dt_time = dt_time(16, 0)  # 16:00 ET
    
    # Monitoreo
    monitor_interval_minutes: int = 5
    
    # Órdenes
    entry_tolerance_pct: float = 1.0
    order_expiry_hours: int = 2
    default_order_type: str = "LIMIT"  # LIMIT o MARKET
    
    # Riesgo
    max_position_pct: float = 20.0
    max_positions: int = 5
    max_daily_trades: int = 3
    max_stop_loss_pct: float = 3.0
    
    # Persistencia
    state_dir: str = "./data/competition"


@dataclass
class SessionResult:
    """Resultado de una sesión de trading."""
    session_date: datetime
    competition_day: int
    decision: Optional[AgentDecision]
    signals_generated: int
    orders_placed: int
    orders_filled: int
    positions_closed: int
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "session_date": self.session_date.isoformat(),
            "competition_day": self.competition_day,
            "decision_id": self.decision.decision_id if self.decision else None,
            "market_view": self.decision.market_view.value if self.decision else None,
            "signals_generated": self.signals_generated,
            "orders_placed": self.orders_placed,
            "orders_filled": self.orders_filled,
            "positions_closed": self.positions_closed,
            "errors": self.errors
        }


class CompetitionOrchestrator:
    """
    Orquestador principal del sistema de competición.
    
    Coordina:
    - Agente Claude (decisiones)
    - Monitor de posiciones (SL/TP)
    - Ejecución de órdenes
    - Métricas y reportes
    
    Uso:
        orchestrator = CompetitionOrchestrator(config)
        await orchestrator.initialize()
        
        # Ejecutar sesión diaria
        result = await orchestrator.run_daily_session(context)
        
        # El monitor corre en background
        # Al final del día:
        await orchestrator.end_of_day()
    """
    
    def __init__(
        self,
        config: TradingSessionConfig = None,
        portfolio_manager = None,  # PaperPortfolioManager o LiveExecutor
        price_provider = None,     # Función para obtener precios
    ):
        self.config = config or TradingSessionConfig()
        self.portfolio_manager = portfolio_manager
        self._price_provider = price_provider
        
        # Componentes (se inicializan en initialize())
        self.agent: Optional[CompetitionClaudeAgent] = None
        self.monitor: Optional[PositionMonitor] = None
        
        # Estado
        self._initialized = False
        self._session_running = False
        self._today_trades = 0
        self._session_history: List[SessionResult] = []
        
        # Crear directorio de estado si no existe
        Path(self.config.state_dir).mkdir(parents=True, exist_ok=True)
    
    # =========================================================================
    # INICIALIZACIÓN
    # =========================================================================
    
    async def initialize(self):
        """Inicializa todos los componentes."""
        if self._initialized:
            logger.warning("Orchestrator already initialized")
            return
        
        logger.info("Initializing Competition Orchestrator...")
        
        # 1. Crear agente
        self.agent = CompetitionClaudeAgent(
            timeout_seconds=180.0,
            state_file=f"{self.config.state_dir}/agent_state.json"
        )
        
        # 2. Crear monitor
        self.monitor = PositionMonitor(
            get_price_func=self._get_price,
            close_position_func=self._close_position,
            execute_order_func=self._execute_pending_order,
            interval_minutes=self.config.monitor_interval_minutes,
            entry_tolerance_pct=self.config.entry_tolerance_pct
        )
        
        # 3. Cargar estado previo
        await self._load_state()
        
        # 4. Iniciar monitor
        await self.monitor.start()
        
        self._initialized = True
        logger.info("Orchestrator initialized successfully")
    
    async def shutdown(self):
        """Detiene todos los componentes."""
        logger.info("Shutting down orchestrator...")
        
        if self.monitor:
            await self.monitor.stop()
        
        await self._save_state()
        
        self._initialized = False
        logger.info("Orchestrator shut down")
    
    # =========================================================================
    # SESIÓN DIARIA
    # =========================================================================
    
    async def run_daily_session(self, context: AgentContext) -> SessionResult:
        """
        Ejecuta la sesión diaria de trading.
        
        Este es el método principal que:
        1. Llama al agente Claude para obtener decisiones
        2. Procesa las señales de cierre
        3. Procesa las señales de entrada
        4. Retorna el resultado de la sesión
        """
        if not self._initialized:
            await self.initialize()
        
        session_start = datetime.now(timezone.utc)
        result = SessionResult(
            session_date=session_start,
            competition_day=self.agent.competition_day,
            decision=None,
            signals_generated=0,
            orders_placed=0,
            orders_filled=0,
            positions_closed=0
        )
        
        try:
            logger.info(f"Starting daily session (Day {self.agent.competition_day})...")
            self._session_running = True
            self._today_trades = 0
            
            # 1. Obtener decisión del agente
            logger.info("Requesting decision from Claude agent...")
            decision = await self.agent.decide(context)
            result.decision = decision
            result.signals_generated = len(decision.signals)
            
            logger.info(f"Decision received: {decision.market_view.value}, "
                       f"{len(decision.signals)} signals, "
                       f"confidence: {decision.confidence:.0%}")
            
            # 2. Procesar revisiones de posiciones (CLOSE)
            close_signals = [s for s in decision.signals if s.direction == SignalDirection.CLOSE]
            for signal in close_signals:
                try:
                    success = await self._process_close_signal(signal)
                    if success:
                        result.positions_closed += 1
                except Exception as e:
                    error_msg = f"Error closing {signal.symbol}: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)
            
            # 3. Verificar si estamos en ventana de trading
            if not self._is_in_trading_window():
                logger.warning("Outside trading window, skipping entry signals")
            else:
                # 4. Procesar señales de entrada (LONG/SHORT)
                entry_signals = [s for s in decision.signals 
                                if s.direction in [SignalDirection.LONG, SignalDirection.SHORT]]
                
                for signal in entry_signals:
                    # Verificar límites
                    if self._today_trades >= self.config.max_daily_trades:
                        logger.warning(f"Daily trade limit reached ({self.config.max_daily_trades})")
                        break
                    
                    if len(self.monitor.get_positions()) >= self.config.max_positions:
                        logger.warning(f"Max positions reached ({self.config.max_positions})")
                        break
                    
                    try:
                        success = await self._process_entry_signal(signal)
                        if success:
                            result.orders_placed += 1
                            self._today_trades += 1
                    except Exception as e:
                        error_msg = f"Error processing {signal.symbol}: {e}"
                        logger.error(error_msg)
                        result.errors.append(error_msg)
            
            # 5. Guardar resultado
            self._session_history.append(result)
            await self._save_state()
            
            logger.info(f"Session completed: {result.orders_placed} orders placed, "
                       f"{result.positions_closed} positions closed")
            
        except Exception as e:
            error_msg = f"Session error: {e}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            
        finally:
            self._session_running = False
        
        return result
    
    async def end_of_day(self):
        """
        Procesa el fin del día de trading.
        
        - Calcula métricas del día
        - Genera reporte
        - Avanza día de competición
        """
        logger.info("Processing end of day...")
        
        # 1. Obtener métricas del monitor
        monitor_stats = self.monitor.get_stats()
        
        # 2. Calcular retorno del día
        # TODO: Integrar con PortfolioManager para cálculo real
        daily_return = 0.0  # Placeholder
        
        # 3. Avanzar día de competición
        await self.agent.advance_day(daily_return=daily_return)
        
        # 4. Generar reporte
        report = {
            "date": datetime.now(timezone.utc).isoformat(),
            "competition_day": self.agent.competition_day,
            "monitor_stats": monitor_stats,
            "competition_status": self.agent.get_competition_status(),
            "sessions": [s.to_dict() for s in self._session_history[-5:]]
        }
        
        report_path = f"{self.config.state_dir}/reports/day_{self.agent.competition_day}.json"
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"End of day report saved: {report_path}")
        
        # 5. Reset contador diario
        self._today_trades = 0
        
        return report
    
    # =========================================================================
    # PROCESAMIENTO DE SEÑALES
    # =========================================================================
    
    async def _process_close_signal(self, signal: Signal) -> bool:
        """Procesa una señal de cierre."""
        logger.info(f"Processing CLOSE signal for {signal.symbol}")
        
        # Obtener precio actual
        current_price = await self._get_price(signal.symbol)
        
        # Cerrar posición
        success = await self._close_position(
            signal.symbol, 
            CloseReason.AGENT_DECISION,
            current_price
        )
        
        return success
    
    async def _process_entry_signal(self, signal: Signal) -> bool:
        """Procesa una señal de entrada."""
        logger.info(f"Processing {signal.direction.value} signal for {signal.symbol}")
        
        # Validar señal
        if not self._validate_signal(signal):
            return False
        
        # Obtener precio actual
        current_price = await self._get_price(signal.symbol)
        
        # Decidir tipo de orden
        price_diff_pct = abs(current_price - signal.entry_price) / signal.entry_price * 100
        
        if self.config.default_order_type == "MARKET" or price_diff_pct <= self.config.entry_tolerance_pct:
            # Ejecutar inmediatamente
            return await self._execute_market_order(signal, current_price)
        else:
            # Crear orden límite
            return await self._create_limit_order(signal)
    
    def _validate_signal(self, signal: Signal) -> bool:
        """Valida que la señal cumple los criterios."""
        
        # Verificar stop loss
        if signal.stop_loss is None:
            logger.warning(f"Signal {signal.symbol} rejected: no stop loss")
            return False
        
        # Verificar que SL no excede máximo
        sl_pct = abs(signal.entry_price - signal.stop_loss) / signal.entry_price * 100
        if sl_pct > self.config.max_stop_loss_pct:
            logger.warning(f"Signal {signal.symbol} rejected: SL {sl_pct:.1f}% > max {self.config.max_stop_loss_pct}%")
            return False
        
        # Verificar tamaño
        if signal.size_suggestion and signal.size_suggestion > self.config.max_position_pct / 100:
            logger.warning(f"Signal {signal.symbol} rejected: size {signal.size_suggestion:.0%} > max {self.config.max_position_pct}%")
            return False
        
        return True
    
    async def _execute_market_order(self, signal: Signal, current_price: float) -> bool:
        """Ejecuta una orden a mercado."""
        logger.info(f"Executing market order: {signal.symbol} {signal.direction.value} @ {current_price}")
        
        # Calcular cantidad (simplificado, debería usar PortfolioManager)
        quantity = self._calculate_quantity(signal, current_price)
        
        if self.portfolio_manager:
            # Ejecutar en portfolio real
            # TODO: Integrar con PaperPortfolioManager
            pass
        
        # Añadir al monitor
        self.monitor.add_position(MonitoredPosition(
            symbol=signal.symbol,
            direction=signal.direction.value,
            entry_price=current_price,
            current_price=current_price,
            quantity=quantity,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit or current_price * 1.06,
            entry_time=datetime.now(timezone.utc)
        ))
        
        return True
    
    async def _create_limit_order(self, signal: Signal) -> bool:
        """Crea una orden límite pendiente."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=self.config.order_expiry_hours)
        
        order = PendingOrder(
            order_id=f"ord_{signal.symbol}_{int(datetime.now().timestamp())}",
            symbol=signal.symbol,
            direction=signal.direction.value,
            limit_price=signal.entry_price,
            quantity=self._calculate_quantity(signal, signal.entry_price),
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit or signal.entry_price * 1.06,
            created_at=datetime.now(timezone.utc),
            expires_at=expiry
        )
        
        self.monitor.add_pending_order(order)
        logger.info(f"Limit order created: {signal.symbol} @ {signal.entry_price}, expires {expiry}")
        
        return True
    
    def _calculate_quantity(self, signal: Signal, price: float) -> int:
        """Calcula la cantidad de acciones a comprar."""
        # Simplificado: usar tamaño sugerido o default 10%
        size_pct = signal.size_suggestion or 0.10
        
        # TODO: Obtener valor del portfolio desde PortfolioManager
        portfolio_value = 25000  # Placeholder
        
        position_value = portfolio_value * size_pct
        quantity = int(position_value / price)
        
        return max(1, quantity)
    
    # =========================================================================
    # CALLBACKS PARA EL MONITOR
    # =========================================================================
    
    async def _get_price(self, symbol: str) -> float:
        """Obtiene el precio actual de un símbolo."""
        if self._price_provider:
            return await self._price_provider(symbol)
        
        # Fallback: usar MCP o Yahoo
        # TODO: Integrar con MCPClient
        logger.warning(f"No price provider, returning placeholder for {symbol}")
        return 100.0  # Placeholder
    
    async def _close_position(self, symbol: str, reason: CloseReason, price: float) -> bool:
        """Cierra una posición."""
        logger.info(f"Closing position: {symbol} ({reason.value}) @ {price}")
        
        if self.portfolio_manager:
            # TODO: Integrar con PaperPortfolioManager
            pass
        
        # Remover del monitor
        self.monitor.remove_position(symbol)
        
        # Registrar trade cerrado para métricas
        # TODO: Calcular P&L real
        
        return True
    
    async def _execute_pending_order(self, order: PendingOrder, price: float) -> bool:
        """Ejecuta una orden pendiente que alcanzó su precio."""
        logger.info(f"Executing pending order: {order.symbol} @ {price}")
        
        if self.portfolio_manager:
            # TODO: Integrar con PaperPortfolioManager
            pass
        
        return True
    
    # =========================================================================
    # UTILIDADES
    # =========================================================================
    
    def _is_in_trading_window(self) -> bool:
        """Verifica si estamos dentro de la ventana de trading."""
        # Simplificado: asumir que siempre estamos en horario
        # TODO: Implementar verificación real de horario ET
        return True
    
    async def _save_state(self):
        """Guarda el estado del orquestador."""
        state = {
            "today_trades": self._today_trades,
            "session_history": [s.to_dict() for s in self._session_history[-20:]],
            "monitor_stats": self.monitor.get_stats() if self.monitor else {},
            "saved_at": datetime.now(timezone.utc).isoformat()
        }
        
        state_path = f"{self.config.state_dir}/orchestrator_state.json"
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
    
    async def _load_state(self):
        """Carga el estado previo del orquestador."""
        state_path = f"{self.config.state_dir}/orchestrator_state.json"
        
        if not Path(state_path).exists():
            return
        
        try:
            with open(state_path, 'r') as f:
                state = json.load(f)
            
            self._today_trades = state.get("today_trades", 0)
            logger.info(f"Loaded orchestrator state: {self._today_trades} trades today")
            
        except Exception as e:
            logger.error(f"Error loading state: {e}")
    
    # =========================================================================
    # ESTADO Y MÉTRICAS
    # =========================================================================
    
    def get_status(self) -> dict:
        """Obtiene el estado actual del orquestador."""
        return {
            "initialized": self._initialized,
            "session_running": self._session_running,
            "competition_day": self.agent.competition_day if self.agent else 0,
            "today_trades": self._today_trades,
            "max_daily_trades": self.config.max_daily_trades,
            "positions_monitored": len(self.monitor.get_positions()) if self.monitor else 0,
            "pending_orders": len(self.monitor.get_pending_orders()) if self.monitor else 0,
            "competition_status": self.agent.get_competition_status() if self.agent else None,
            "monitor_stats": self.monitor.get_stats() if self.monitor else None
        }
