"""
Calculadoras de métricas de riesgo.
"""

import numpy as np
from typing import List, Optional


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    """
    Calcula el Ratio de Sharpe.
    
    Args:
        returns: Lista de retornos porcentuales (ej: 0.01 para 1%)
        risk_free_rate: Tasa libre de riesgo anual
        periods_per_year: Número de períodos por año (252 para diario)
        
    Returns:
        Sharpe Ratio anualizado
    """
    if not returns or len(returns) < 2:
        return 0.0
        
    returns_arr = np.array(returns)
    avg_return = np.mean(returns_arr)
    std_dev = np.std(returns_arr, ddof=1)
    
    if std_dev == 0:
        return 0.0
        
    # Ajustar tasa libre de riesgo al período
    rf_per_period = risk_free_rate / periods_per_year
    
    sharpe = (avg_return - rf_per_period) / std_dev
    
    # Anualizar
    return sharpe * np.sqrt(periods_per_year)


def calculate_sortino_ratio(returns: List[float], target_return: float = 0.0, periods_per_year: int = 252) -> float:
    """
    Calcula el Ratio de Sortino (solo considera volatilidad a la baja).
    
    Args:
        returns: Lista de retornos porcentuales
        target_return: Retorno objetivo mínimo (MAR)
        periods_per_year: Períodos por año
        
    Returns:
        Sortino Ratio anualizado
    """
    if not returns or len(returns) < 2:
        return 0.0
        
    returns_arr = np.array(returns)
    avg_return = np.mean(returns_arr)
    
    # Calcular desviación a la baja (downside deviation)
    downside_returns = returns_arr[returns_arr < target_return]
    
    if len(downside_returns) == 0:
        return 0.0  # No hay riesgo a la baja
        
    downside_std = np.std(downside_returns, ddof=1)
    
    if downside_std == 0:
        return 0.0
        
    sortino = (avg_return - target_return) / downside_std
    
    return sortino * np.sqrt(periods_per_year)


def calculate_max_drawdown(equity_curve: List[float]) -> float:
    """
    Calcula el Maximum Drawdown.
    
    Args:
        equity_curve: Lista de valores de equity (ej: [100, 105, 95, ...])
        
    Returns:
        Max Drawdown como porcentaje positivo (ej: 0.15 para 15%)
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
        
    equity_arr = np.array(equity_curve)
    
    # Calcular picos acumulados
    peaks = np.maximum.accumulate(equity_arr)
    
    # Calcular drawdowns
    drawdowns = (peaks - equity_arr) / peaks
    
    return np.max(drawdowns)
