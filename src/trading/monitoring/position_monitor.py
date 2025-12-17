"""
Monitor de Posiciones - Verifica SL/TP periódicamente.

Este módulo se encarga de:
1. Verificar cada X minutos si alguna posición tocó SL o TP
2. Ejecutar cierres automáticos cuando se activan
3. Cancelar órdenes límite expiradas
4. Registrar eventos para métricas
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class CloseReason(str, Enum):
    """Razón por la que se cerró una posición."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    MANUAL = "manual"
    AGENT_DECISION = "agent_decision"
    END_OF_DAY = "end_of_day"
    EXPIRED_ORDER = "expired_order"


@dataclass
class MonitoredPosition:
    """Posición siendo monitoreada."""
    symbol: str
    direction: str  # LONG o SHORT
    entry_price: float
    current_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    entry_time: datetime
    position_id: str = ""
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calcula P&L no realizado en %."""
        if self.direction == "LONG":
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:  # SHORT
            return ((self.entry_price - self.current_price) / self.entry_price) * 100
    
    def check_stop_loss(self) -> bool:
        """Verifica si se activó el stop loss."""
        if self.direction == "LONG":
            return self.current_price <= self.stop_loss
        else:  # SHORT
            return self.current_price >= self.stop_loss
    
    def check_take_profit(self) -> bool:
        """Verifica si se activó el take profit."""
        if self.direction == "LONG":
            return self.current_price >= self.take_profit
        else:  # SHORT
            return self.current_price <= self.take_profit


@dataclass
class PendingOrder:
    """Orden límite pendiente de ejecución."""
    order_id: str
    symbol: str
    direction: str
    limit_price: float
    quantity: int
    stop_loss: float
    take_profit: float
    created_at: datetime
    expires_at: datetime
    
    def is_expired(self, now: datetime = None) -> bool:
        """Verifica si la orden expiró."""
        now = now or datetime.now(timezone.utc)
        return now >= self.expires_at
    
    def should_execute(self, current_price: float, tolerance_pct: float = 1.0) -> bool:
        """
        Verifica si la orden debe ejecutarse.
        
        Args:
            current_price: Precio actual del mercado
            tolerance_pct: Tolerancia en % para ejecutar
        """
        if self.direction == "LONG":
            # Para LONG, ejecutar si precio <= límite + tolerancia
            max_price = self.limit_price * (1 + tolerance_pct / 100)
            return current_price <= max_price
        else:  # SHORT
            # Para SHORT, ejecutar si precio >= límite - tolerancia
            min_price = self.limit_price * (1 - tolerance_pct / 100)
            return current_price >= min_price


@dataclass
class MonitorEvent:
    """Evento generado por el monitor."""
    timestamp: datetime
    event_type: str  # "SL_TRIGGERED", "TP_TRIGGERED", "ORDER_FILLED", "ORDER_EXPIRED"
    symbol: str
    details: Dict = field(default_factory=dict)


class PositionMonitor:
    """
    Monitor de posiciones con verificación periódica de SL/TP.
    
    Uso:
        monitor = PositionMonitor(
            get_price_func=my_price_fetcher,
            close_position_func=my_closer,
            interval_minutes=5
        )
        
        # Añadir posición a monitorear
        monitor.add_position(position)
        
        # Iniciar monitoreo
        await monitor.start()
        
        # Detener
        await monitor.stop()
    """
    
    def __init__(
        self,
        get_price_func: Callable[[str], Awaitable[float]],
        close_position_func: Callable[[str, CloseReason, float], Awaitable[bool]],
        execute_order_func: Callable[[PendingOrder, float], Awaitable[bool]] = None,
        interval_minutes: int = 5,
        entry_tolerance_pct: float = 1.0,
    ):
        """
        Inicializa el monitor.
        
        Args:
            get_price_func: Función async que obtiene precio actual de un símbolo
            close_position_func: Función async que cierra una posición
            execute_order_func: Función async que ejecuta una orden pendiente
            interval_minutes: Intervalo de verificación en minutos
            entry_tolerance_pct: Tolerancia % para ejecutar órdenes límite
        """
        self._get_price = get_price_func
        self._close_position = close_position_func
        self._execute_order = execute_order_func
        self._interval = interval_minutes * 60  # Convertir a segundos
        self._tolerance = entry_tolerance_pct
        
        self._positions: Dict[str, MonitoredPosition] = {}
        self._pending_orders: Dict[str, PendingOrder] = {}
        self._events: List[MonitorEvent] = []
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        
    # =========================================================================
    # GESTIÓN DE POSICIONES
    # =========================================================================
    
    def add_position(self, position: MonitoredPosition):
        """Añade una posición al monitoreo."""
        key = f"{position.symbol}_{position.direction}"
        self._positions[key] = position
        logger.info(f"Position added to monitor: {position.symbol} {position.direction}")
    
    def remove_position(self, symbol: str, direction: str = "LONG"):
        """Elimina una posición del monitoreo."""
        key = f"{symbol}_{direction}"
        if key in self._positions:
            del self._positions[key]
            logger.info(f"Position removed from monitor: {symbol} {direction}")
    
    def update_position_price(self, symbol: str, direction: str, new_price: float):
        """Actualiza el precio actual de una posición."""
        key = f"{symbol}_{direction}"
        if key in self._positions:
            self._positions[key].current_price = new_price
    
    def get_positions(self) -> List[MonitoredPosition]:
        """Retorna lista de posiciones monitoreadas."""
        return list(self._positions.values())
    
    # =========================================================================
    # GESTIÓN DE ÓRDENES PENDIENTES
    # =========================================================================
    
    def add_pending_order(self, order: PendingOrder):
        """Añade una orden límite pendiente."""
        self._pending_orders[order.order_id] = order
        logger.info(f"Pending order added: {order.symbol} {order.direction} @ {order.limit_price}")
    
    def remove_pending_order(self, order_id: str):
        """Elimina una orden pendiente."""
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]
    
    def get_pending_orders(self) -> List[PendingOrder]:
        """Retorna lista de órdenes pendientes."""
        return list(self._pending_orders.values())
    
    # =========================================================================
    # CICLO DE MONITOREO
    # =========================================================================
    
    async def start(self):
        """Inicia el ciclo de monitoreo."""
        if self._running:
            logger.warning("Monitor already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info(f"Position monitor started (interval: {self._interval}s)")
    
    async def stop(self):
        """Detiene el ciclo de monitoreo."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Position monitor stopped")
    
    async def _monitor_loop(self):
        """Bucle principal de monitoreo."""
        while self._running:
            try:
                await self._check_all()
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
            
            await asyncio.sleep(self._interval)
    
    async def check_now(self):
        """Ejecuta una verificación inmediata (útil para testing)."""
        await self._check_all()
    
    async def _check_all(self):
        """Verifica todas las posiciones y órdenes pendientes."""
        now = datetime.now(timezone.utc)
        
        # 1. Verificar posiciones abiertas
        positions_to_close = []
        
        for key, position in list(self._positions.items()):
            try:
                # Obtener precio actual
                current_price = await self._get_price(position.symbol)
                position.current_price = current_price
                
                # Verificar SL
                if position.check_stop_loss():
                    positions_to_close.append((position, CloseReason.STOP_LOSS, current_price))
                    self._record_event("SL_TRIGGERED", position.symbol, {
                        "stop_loss": position.stop_loss,
                        "trigger_price": current_price,
                        "pnl_pct": position.unrealized_pnl_pct
                    })
                    
                # Verificar TP
                elif position.check_take_profit():
                    positions_to_close.append((position, CloseReason.TAKE_PROFIT, current_price))
                    self._record_event("TP_TRIGGERED", position.symbol, {
                        "take_profit": position.take_profit,
                        "trigger_price": current_price,
                        "pnl_pct": position.unrealized_pnl_pct
                    })
                    
            except Exception as e:
                logger.error(f"Error checking position {position.symbol}: {e}")
        
        # Ejecutar cierres
        for position, reason, price in positions_to_close:
            try:
                success = await self._close_position(position.symbol, reason, price)
                if success:
                    self.remove_position(position.symbol, position.direction)
                    logger.info(f"Position closed: {position.symbol} ({reason.value}) @ {price}")
            except Exception as e:
                logger.error(f"Error closing position {position.symbol}: {e}")
        
        # 2. Verificar órdenes pendientes
        orders_to_process = []
        
        for order_id, order in list(self._pending_orders.items()):
            try:
                # Verificar expiración
                if order.is_expired(now):
                    orders_to_process.append((order, "EXPIRED", 0))
                    self._record_event("ORDER_EXPIRED", order.symbol, {
                        "order_id": order_id,
                        "limit_price": order.limit_price
                    })
                    continue
                
                # Verificar si debe ejecutarse
                current_price = await self._get_price(order.symbol)
                if order.should_execute(current_price, self._tolerance):
                    orders_to_process.append((order, "FILL", current_price))
                    self._record_event("ORDER_FILLED", order.symbol, {
                        "order_id": order_id,
                        "limit_price": order.limit_price,
                        "fill_price": current_price
                    })
                    
            except Exception as e:
                logger.error(f"Error checking order {order_id}: {e}")
        
        # Procesar órdenes
        for order, action, price in orders_to_process:
            try:
                if action == "EXPIRED":
                    self.remove_pending_order(order.order_id)
                    logger.info(f"Order expired: {order.symbol} {order.direction}")
                    
                elif action == "FILL" and self._execute_order:
                    success = await self._execute_order(order, price)
                    if success:
                        self.remove_pending_order(order.order_id)
                        # Añadir como posición monitoreada
                        self.add_position(MonitoredPosition(
                            symbol=order.symbol,
                            direction=order.direction,
                            entry_price=price,
                            current_price=price,
                            quantity=order.quantity,
                            stop_loss=order.stop_loss,
                            take_profit=order.take_profit,
                            entry_time=datetime.now(timezone.utc),
                            position_id=order.order_id
                        ))
                        logger.info(f"Order filled: {order.symbol} {order.direction} @ {price}")
                        
            except Exception as e:
                logger.error(f"Error processing order {order.order_id}: {e}")
    
    # =========================================================================
    # EVENTOS Y MÉTRICAS
    # =========================================================================
    
    def _record_event(self, event_type: str, symbol: str, details: Dict):
        """Registra un evento."""
        event = MonitorEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=event_type,
            symbol=symbol,
            details=details
        )
        self._events.append(event)
        
        # Mantener solo últimos 1000 eventos
        if len(self._events) > 1000:
            self._events = self._events[-1000:]
    
    def get_events(self, since: datetime = None) -> List[MonitorEvent]:
        """Obtiene eventos, opcionalmente desde una fecha."""
        if since is None:
            return self._events.copy()
        return [e for e in self._events if e.timestamp >= since]
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del monitor."""
        sl_events = [e for e in self._events if e.event_type == "SL_TRIGGERED"]
        tp_events = [e for e in self._events if e.event_type == "TP_TRIGGERED"]
        
        return {
            "positions_monitored": len(self._positions),
            "pending_orders": len(self._pending_orders),
            "total_events": len(self._events),
            "stop_losses_triggered": len(sl_events),
            "take_profits_triggered": len(tp_events),
            "orders_filled": len([e for e in self._events if e.event_type == "ORDER_FILLED"]),
            "orders_expired": len([e for e in self._events if e.event_type == "ORDER_EXPIRED"]),
        }
