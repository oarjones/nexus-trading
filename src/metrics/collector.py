"""
Metrics Collector Service.

Escucha eventos de trades en Redis y los persiste en la base de datos.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional
from uuid import UUID

import asyncpg
import redis.asyncio as redis
from pydantic import ValidationError

from src.metrics.schemas import (
    TradeOpenEvent,
    TradeCloseEvent,
    TradeEventType,
    TradeStatus,
    TradeDirection
)

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Recolector de métricas.
    Suscribe a canales de Redis y guarda eventos en PostgreSQL.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        self.pg_dsn = os.environ.get("POSTGRES_DSN", "postgresql://trading:trading@localhost:5432/trading")
        self.channel = self.config.get("redis_channel", "trades")
        
        self._redis: Optional[redis.Redis] = None
        self._pg_pool: Optional[asyncpg.Pool] = None
        self._running = False
        
    async def start(self):
        """Inicia el servicio."""
        logger.info("Starting MetricsCollector...")
        self._redis = redis.from_url(self.redis_url)
        self._pg_pool = await asyncpg.create_pool(self.pg_dsn)
        self._running = True
        
        asyncio.create_task(self._subscribe())
        logger.info(f"Listening on channel: {self.channel}")
        
    async def stop(self):
        """Detiene el servicio."""
        logger.info("Stopping MetricsCollector...")
        self._running = False
        if self._redis:
            await self._redis.close()
        if self._pg_pool:
            await self._pg_pool.close()
            
    async def _subscribe(self):
        """Suscribe a Redis y procesa mensajes."""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(self.channel)
        
        try:
            async for message in pubsub.listen():
                if not self._running:
                    break
                    
                if message["type"] == "message":
                    await self._process_message(message["data"])
        except Exception as e:
            logger.error(f"Error in subscription loop: {e}")
            # Reconnect logic could go here
            
    async def _process_message(self, data: bytes):
        """Procesa un mensaje JSON."""
        try:
            payload = json.loads(data)
            event_type = payload.get("event_type")
            
            if event_type == TradeEventType.TRADE_OPEN:
                event = TradeOpenEvent(**payload)
                await self._handle_trade_open(event)
                
            elif event_type == TradeEventType.TRADE_CLOSE:
                event = TradeCloseEvent(**payload)
                await self._handle_trade_close(event)
                
            else:
                logger.warning(f"Unknown event type: {event_type}")
                
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    async def _handle_trade_open(self, event: TradeOpenEvent):
        """Maneja evento de apertura de trade."""
        logger.info(f"Processing TRADE_OPEN: {event.trade_id}")
        
        query = """
        INSERT INTO metrics.trades (
            trade_id, strategy_id, model_id, agent_id, experiment_id,
            symbol, direction, entry_time, entry_price, size_shares, size_value_eur,
            stop_loss, take_profit, status, regime_at_entry, regime_confidence,
            reasoning, metadata
        ) VALUES (
            $1, $2, $3, $4, $5,
            $6, $7, $8, $9, $10, $11,
            $12, $13, $14, $15, $16,
            $17, $18
        )
        """
        
        async with self._pg_pool.acquire() as conn:
            await conn.execute(
                query,
                str(event.trade_id),
                event.strategy_id,
                event.model_id,
                event.agent_id,
                str(event.experiment_id) if event.experiment_id else None,
                event.symbol,
                event.direction.value,
                event.timestamp,
                float(event.entry_price),
                float(event.size_shares),
                float(event.size_value_eur),
                float(event.stop_loss) if event.stop_loss else None,
                float(event.take_profit) if event.take_profit else None,
                TradeStatus.OPEN.value,
                event.regime_at_entry.value if event.regime_at_entry else None,
                event.regime_confidence,
                event.reasoning,
                json.dumps(event.metadata) if event.metadata else None
            )
            
    async def _handle_trade_close(self, event: TradeCloseEvent):
        """Maneja evento de cierre de trade."""
        logger.info(f"Processing TRADE_CLOSE: {event.trade_id}")
        
        # 1. Obtener datos de entrada para calcular PnL
        fetch_query = """
        SELECT entry_price, size_shares, direction 
        FROM metrics.trades 
        WHERE trade_id = $1
        """
        
        update_query = """
        UPDATE metrics.trades SET
            exit_time = $2,
            exit_price = $3,
            close_reason = $4,
            status = $5,
            pnl_eur = $6,
            pnl_pct = $7,
            commission_eur = $8,
            slippage_eur = $9,
            metadata = coalesce(metadata, '{}'::jsonb) || $10::jsonb
        WHERE trade_id = $1
        """
        
        async with self._pg_pool.acquire() as conn:
            row = await conn.fetchrow(fetch_query, str(event.trade_id))
            if not row:
                logger.error(f"Trade not found: {event.trade_id}")
                return
                
            entry_price = row['entry_price']
            size_shares = row['size_shares']
            direction = row['direction']
            
            # Calcular PnL
            if direction == TradeDirection.LONG.value:
                pnl_eur = (event.exit_price - entry_price) * size_shares
                pnl_pct = (event.exit_price - entry_price) / entry_price
            else: # SHORT
                pnl_eur = (entry_price - event.exit_price) * size_shares
                pnl_pct = (entry_price - event.exit_price) / entry_price
                
            # Ajustar por comisiones (simple)
            pnl_eur -= (event.commission_eur or 0)
            
            await conn.execute(
                update_query,
                str(event.trade_id),
                event.timestamp,
                float(event.exit_price),
                event.close_reason,
                TradeStatus.CLOSED.value,
                float(pnl_eur),
                float(pnl_pct),
                float(event.commission_eur or 0),
                float(event.slippage_eur or 0),
                json.dumps(event.metadata) if event.metadata else '{}'
            )
