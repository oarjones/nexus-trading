"""
Calculadoras de métricas de trades.
"""

from typing import List


def calculate_win_rate(pnl_list: List[float]) -> float:
    """
    Calcula el porcentaje de aciertos.
    
    Args:
        pnl_list: Lista de PnL (absoluto o %)
        
    Returns:
        Win rate (0.0 a 1.0)
    """
    if not pnl_list:
        return 0.0
        
    wins = sum(1 for pnl in pnl_list if pnl > 0)
    return wins / len(pnl_list)


def calculate_profit_factor(pnl_list: List[float]) -> float:
    """
    Calcula el Profit Factor (Gross Profit / Gross Loss).
    
    Args:
        pnl_list: Lista de PnL absoluto
        
    Returns:
        Profit Factor (> 1.0 es rentable)
    """
    if not pnl_list:
        return 0.0
        
    gross_profit = sum(pnl for pnl in pnl_list if pnl > 0)
    gross_loss = abs(sum(pnl for pnl in pnl_list if pnl < 0))
    
    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0
        
    return gross_profit / gross_loss


def calculate_avg_r_multiple(pnl_list: List[float], risk_per_trade_list: List[float]) -> float:
    """
    Calcula el promedio de R-Multiple.
    R = Beneficio / Riesgo Inicial
    
    Args:
        pnl_list: Lista de PnL absoluto
        risk_per_trade_list: Lista de riesgo inicial (stop loss distance * size)
        
    Returns:
        Promedio R
    """
    if not pnl_list or not risk_per_trade_list or len(pnl_list) != len(risk_per_trade_list):
        return 0.0
        
    r_multiples = []
    for pnl, risk in zip(pnl_list, risk_per_trade_list):
        if risk > 0:
            r_multiples.append(pnl / risk)
            
    if not r_multiples:
        return 0.0
        
    return sum(r_multiples) / len(r_multiples)
