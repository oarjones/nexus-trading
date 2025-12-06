"""
Prometheus Exporter.

Expone métricas de trading para ser consumidas por Prometheus y Grafana.
"""

import logging
import os
from typing import Dict, Any

from prometheus_client import start_http_server, Gauge, Counter

logger = logging.getLogger(__name__)

# Definición de métricas Prometheus
TRADES_TOTAL = Counter(
    "trading_trades_total",
    "Total number of trades",
    ["strategy_id", "symbol", "direction", "status"]
)

PNL_TOTAL = Gauge(
    "trading_pnl_total_eur",
    "Total PnL in EUR",
    ["strategy_id"]
)

CURRENT_DRAWDOWN = Gauge(
    "trading_current_drawdown_pct",
    "Current Drawdown %",
    ["strategy_id"]
)

WIN_RATE = Gauge(
    "trading_win_rate",
    "Win Rate (0-1)",
    ["strategy_id"]
)


class PrometheusExporter:
    """
    Exportador de métricas a Prometheus.
    """
    
    def __init__(self, port: int = 8000):
        self.port = port
        self._running = False
        
    def start(self):
        """Inicia el servidor HTTP de Prometheus."""
        if not self._running:
            start_http_server(self.port)
            self._running = True
            logger.info(f"Prometheus exporter started on port {self.port}")
            
    def update_metrics(self, strategy_metrics: Dict[str, Any]):
        """
        Actualiza los Gauges con los últimos valores calculados.
        """
        strategy_id = strategy_metrics.get("strategy_id", "unknown")
        
        if "total_pnl_eur" in strategy_metrics:
            PNL_TOTAL.labels(strategy_id=strategy_id).set(strategy_metrics["total_pnl_eur"])
            
        if "max_drawdown_pct" in strategy_metrics:
            CURRENT_DRAWDOWN.labels(strategy_id=strategy_id).set(strategy_metrics["max_drawdown_pct"])
            
        if "win_rate" in strategy_metrics:
            WIN_RATE.labels(strategy_id=strategy_id).set(strategy_metrics["win_rate"])
            
    def record_trade(self, strategy_id: str, symbol: str, direction: str, status: str):
        """Registra un nuevo trade (Counter)."""
        TRADES_TOTAL.labels(
            strategy_id=strategy_id,
            symbol=symbol,
            direction=direction,
            status=status
        ).inc()
