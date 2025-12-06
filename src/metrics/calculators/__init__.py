"""
Módulo de calculadoras de métricas.
"""

from .risk_metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_max_drawdown
)
from .trade_metrics import (
    calculate_win_rate,
    calculate_profit_factor,
    calculate_avg_r_multiple
)

__all__ = [
    "calculate_sharpe_ratio",
    "calculate_sortino_ratio",
    "calculate_max_drawdown",
    "calculate_win_rate",
    "calculate_profit_factor",
    "calculate_avg_r_multiple"
]
