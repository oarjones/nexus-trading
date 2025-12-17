"""
Competition Repository.

Maneja la persistencia del estado del agente de competición en PostgreSQL.
"""

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

import asyncpg

logger = logging.getLogger(__name__)

class CompetitionRepository:
    """Repositorio para el estado de la competición."""
    
    def __init__(self, dsn: str = None):
        self.dsn = dsn or os.environ.get("POSTGRES_DSN") or os.environ.get("DATABASE_URL", "postgresql://trading:trading@localhost:5432/trading")
        self._pool: Optional[asyncpg.Pool] = None
        
    async def get_pool(self) -> asyncpg.Pool:
        """Obtiene o crea el pool de conexiones."""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.dsn)
        return self._pool
        
    async def close(self):
        """Cierra el pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def save_state(self, agent_id: str, state: Dict[str, Any]):
        """
        Guarda el estado completo del agente.
        
        Args:
            agent_id: Identificador del agente
            state: Diccionario con el estado (metrics, flags, history)
        """
        pool = await self.get_pool()
        
        metrics = state.get("metrics", {})
        
        query = """
            INSERT INTO competition.agent_state (
                agent_id, 
                competition_day, 
                is_onboarded, 
                start_date,
                total_return_pct,
                daily_return_pct,
                sharpe_ratio,
                max_drawdown_pct,
                win_rate,
                metrics_json,
                trade_history,
                last_updated
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW()
            )
            ON CONFLICT (agent_id) DO UPDATE SET
                competition_day = EXCLUDED.competition_day,
                is_onboarded = EXCLUDED.is_onboarded,
                start_date = EXCLUDED.start_date,
                total_return_pct = EXCLUDED.total_return_pct,
                daily_return_pct = EXCLUDED.daily_return_pct,
                sharpe_ratio = EXCLUDED.sharpe_ratio,
                max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                win_rate = EXCLUDED.win_rate,
                metrics_json = EXCLUDED.metrics_json,
                trade_history = EXCLUDED.trade_history,
                last_updated = NOW()
        """
        
        try:
            # Prepare data
            start_date = None
            if state.get("start_date"):
                start_date = datetime.fromisoformat(state["start_date"])
                
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    agent_id,
                    state.get("competition_day", 0),
                    state.get("is_onboarded", False),
                    start_date,
                    metrics.get("total_return_pct"),
                    metrics.get("daily_return_pct"),
                    metrics.get("sharpe_ratio"),
                    metrics.get("max_drawdown_pct"),
                    metrics.get("win_rate"),
                    json.dumps(metrics),
                    json.dumps(state.get("trade_history", []))
                )
            logger.debug(f"State saved for agent {agent_id}")
            
        except Exception as e:
            logger.error(f"Error saving competition state: {e}")
            raise

    async def load_state(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Carga el estado del agente.
        
        Returns:
            Diccionario de estado o None si no existe.
        """
        pool = await self.get_pool()
        
        query = "SELECT * FROM competition.agent_state WHERE agent_id = $1"
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, agent_id)
                
            if not row:
                return None
                
            # Reconstruct state dict matching the expected format
            state = {
                "is_onboarded": row["is_onboarded"],
                "competition_day": row["competition_day"],
                "start_date": row["start_date"].isoformat() if row["start_date"] else None,
                "metrics": json.loads(row["metrics_json"]),
                "trade_history": json.loads(row["trade_history"])
            }
            
            # Ensure metrics values are float if needed (JSON loads handles this mostly)
            return state
            
        except Exception as e:
            logger.error(f"Error loading competition state: {e}")
            raise
