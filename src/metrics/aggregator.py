"""
Metrics Aggregator Service.

Calcula métricas agregadas (Sharpe, Win Rate, etc.) a partir de los trades
y actualiza las tablas de rendimiento.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

import asyncpg
import numpy as np

from src.metrics.schemas import PeriodType
from src.metrics.calculators import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_profit_factor
)

logger = logging.getLogger(__name__)


class MetricsAggregator:
    """
    Agregador de métricas.
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self.pg_dsn = os.environ.get("POSTGRES_DSN", "postgresql://trading:trading@localhost:5432/trading")
        self._pg_pool: asyncpg.Pool = None
        
    async def start(self):
        self._pg_pool = await asyncpg.create_pool(self.pg_dsn)
        
    async def stop(self):
        if self._pg_pool:
            await self._pg_pool.close()
            
    async def run_aggregation(self):
        """Ejecuta el proceso de agregación completo."""
        logger.info("Running aggregation...")
        try:
            await self._aggregate_by_strategy()
            # await self._aggregate_by_model() # TODO
        except Exception as e:
            logger.error(f"Error in aggregation: {e}")
            
    async def _aggregate_by_strategy(self):
        """Calcula métricas por estrategia."""
        async with self._pg_pool.acquire() as conn:
            # 1. Obtener estrategias activas (que tengan trades)
            strategies = await conn.fetch("""
                SELECT DISTINCT strategy_id FROM metrics.trades
            """)
            
            for record in strategies:
                strategy_id = record['strategy_id']
                await self._calculate_strategy_metrics(conn, strategy_id)
                
    async def _calculate_strategy_metrics(self, conn, strategy_id: str):
        """Calcula métricas para una estrategia específica."""
        # Por ahora, calculamos "ALL_TIME"
        # TODO: Implementar ventanas de tiempo (daily, weekly, etc.)
        
        trades = await conn.fetch("""
            SELECT pnl_eur, pnl_pct, exit_time, entry_time
            FROM metrics.trades
            WHERE strategy_id = $1 AND status = 'CLOSED'
            ORDER BY exit_time ASC
        """, strategy_id)
        
        if not trades:
            return
            
        # Extraer datos para calculadoras
        pnl_eur = [float(t['pnl_eur']) for t in trades if t['pnl_eur'] is not None]
        pnl_pct = [float(t['pnl_pct']) for t in trades if t['pnl_pct'] is not None]
        
        # Calcular métricas
        metrics = {
            "total_trades": len(trades),
            "winning_trades": sum(1 for p in pnl_eur if p > 0),
            "losing_trades": sum(1 for p in pnl_eur if p <= 0),
            "win_rate": calculate_win_rate(pnl_eur),
            "profit_factor": calculate_profit_factor(pnl_eur),
            "total_pnl_eur": sum(pnl_eur),
            "total_pnl_pct": sum(pnl_pct),
            "sharpe_ratio": calculate_sharpe_ratio(pnl_pct),
            "sortino_ratio": calculate_sortino_ratio(pnl_pct),
            # Max DD requiere curva de equity
            "max_drawdown_pct": self._calculate_dd_from_pnl(pnl_pct)
        }
        
        # Guardar en DB
        await self._save_strategy_performance(conn, strategy_id, metrics)
        
    def _calculate_dd_from_pnl(self, pnl_pct: List[float]) -> float:
        if not pnl_pct:
            return 0.0
        # Reconstruir equity curve (base 100)
        equity = [100.0]
        for r in pnl_pct:
            equity.append(equity[-1] * (1 + r))
        return calculate_max_drawdown(equity)
        
    async def _save_strategy_performance(self, conn, strategy_id: str, metrics: Dict[str, Any]):
        """Guarda métricas en metrics.strategy_performance."""
        query = """
        INSERT INTO metrics.strategy_performance (
            strategy_id, period_type, period_start, period_end,
            total_trades, win_rate, profit_factor, 
            total_pnl_eur, total_pnl_pct, sharpe_ratio, sortino_ratio, max_drawdown_pct,
            updated_at
        ) VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            $8, $9, $10, $11, $12,
            NOW()
        )
        ON CONFLICT (strategy_id, period_type, period_start) DO UPDATE SET
            total_trades = EXCLUDED.total_trades,
            win_rate = EXCLUDED.win_rate,
            profit_factor = EXCLUDED.profit_factor,
            total_pnl_eur = EXCLUDED.total_pnl_eur,
            total_pnl_pct = EXCLUDED.total_pnl_pct,
            sharpe_ratio = EXCLUDED.sharpe_ratio,
            sortino_ratio = EXCLUDED.sortino_ratio,
            max_drawdown_pct = EXCLUDED.max_drawdown_pct,
            updated_at = NOW()
        """
        
        # Usamos un start date fijo para ALL_TIME por ahora
        start_date = datetime(2020, 1, 1) 
        end_date = datetime.now()
        
        await conn.execute(
            query,
            strategy_id,
            PeriodType.ALL_TIME.value,
            start_date,
            end_date,
            metrics["total_trades"],
            metrics["win_rate"],
            metrics["profit_factor"],
            metrics["total_pnl_eur"],
            metrics["total_pnl_pct"],
            metrics["sharpe_ratio"],
            metrics["sortino_ratio"],
            metrics["max_drawdown_pct"]
        )
        logger.info(f"Updated metrics for strategy {strategy_id}")
