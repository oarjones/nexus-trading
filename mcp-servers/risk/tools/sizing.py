"""
Position sizing calculation tool.

Calculates optimal position size using Kelly Criterion (fractional).
"""

import logging
from typing import Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


async def calculate_size_tool(args: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Calculate position size using Kelly Criterion.
    
    Uses fractional Kelly (conservative, typically 25% Kelly) to determine
    optimal position size based on win rate, win/loss ratio, and risk tolerance.
    
    Args:
        args: Tool arguments containing:
            - portfolio_value (float): Total portfolio value
            - win_rate (float): Historical win rate (0-1)
            - avg_win (float): Average win amount/percentage
            - avg_loss (float): Average loss amount/percentage
            - kelly_fraction (float, optional): Kelly fraction - default 0.25
            - max_risk_pct (float, optional): Max risk per trade - default 0.01
        config: Optional sizing config
        
    Returns:
        Dictionary with:
        - suggested_size: Recommended position size (USD)
        - size_pct: Size as percentage of portfolio
        - kelly_pct: Full Kelly percentage
        - fractional_kelly_pct: Fractional Kelly percentage
        - risk_amount: Amount at risk
        - method: Sizing method used
        
    Example:
        >>> await calculate_size_tool({
        ...     "portfolio_value": 100000,
        ...     "win_rate": 0.55,
        ...     "avg_win": 0.02,
        ...     "avg_loss": 0.01
        ... })
        {
            "suggested_size": 2500,
            "size_pct": 0.025,
            "kelly_pct": 0.10,
            "fractional_kelly_pct": 0.025,
            "risk_amount": 25,
            "method": "fractional_kelly"
        }
    """
    portfolio_value = args.get('portfolio_value', 0)
    win_rate = args.get('win_rate', 0)
    avg_win = args.get('avg_win', 0)
    avg_loss = args.get('avg_loss', 0)
    kelly_fraction = args.get('kelly_fraction', 0.25)  # Conservative
    max_risk_pct = args.get('max_risk_pct', 0.01)      # 1% default risk
    
    if portfolio_value <= 0:
        raise ValueError("Parameter 'portfolio_value' must be positive")
    
    if not (0 <= win_rate <= 1):
        raise ValueError("Parameter 'win_rate' must be between 0 and 1")
    
    # Get config defaults if provided
    if config and 'sizing' in config:
        kelly_fraction = config['sizing'].get('kelly_fraction', kelly_fraction)
        max_risk_pct = config['sizing'].get('base_risk_pct', max_risk_pct)
    
    # Calculate Kelly percentage
    # Kelly = (p * b - q) / b
    # where p = win_rate, q = 1-p, b = avg_win/avg_loss
    
    if avg_loss <= 0:
        # If no loss data, use conservative fixed percentage
        logger.warning("No loss data, using fixed risk percentage")
        kelly_pct = max_risk_pct
        method = "fixed_risk"
    else:
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
        loss_rate = 1 - win_rate
        
        # Full Kelly formula
        kelly_pct = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio
        
        # Sanity check
        if kelly_pct < 0:
            kelly_pct = 0
            logger.warning("Negative Kelly, edge not present - position size = 0")
        elif kelly_pct > 1.0:
            kelly_pct = 1.0
            logger.warning("Kelly > 100%, capping at 100%")
        
        method = "fractional_kelly"
    
    # Apply Kelly fraction (conservative approach)
    fractional_kelly_pct = kelly_pct * kelly_fraction
    
    # Cap at max risk
    final_size_pct = min(fractional_kelly_pct, max_risk_pct)
    
    # Calculate dollar amounts
    suggested_size = portfolio_value * final_size_pct
    risk_amount = suggested_size * (avg_loss if avg_loss > 0 else 0.01)
    
    logger.info(
        f"Position size calculated: ${suggested_size:,.0f} "
        f"({final_size_pct*100:.2f}% of portfolio)"
    )
    
    return {
        'suggested_size': round(suggested_size, 2),
        'size_pct': round(final_size_pct, 4),
        'kelly_pct': round(kelly_pct, 4),
        'fractional_kelly_pct': round(fractional_kelly_pct, 4),
        'risk_amount': round(risk_amount, 2),
        'method': method,
        'inputs': {
            'portfolio_value': portfolio_value,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'kelly_fraction': kelly_fraction
        }
    }
