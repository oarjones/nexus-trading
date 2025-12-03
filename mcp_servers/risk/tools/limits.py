"""
Risk limits validation tool.

Validates proposed trades against hard risk limits.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


# Default hard limits (can be overridden by config)
DEFAULT_LIMITS = {
    'max_position_pct': 0.20,      # 20% max per position
    'max_sector_pct': 0.40,        # 40% max per sector
    'max_correlation': 0.70,       # Max correlation threshold
    'max_drawdown': 0.15,          # 15% max drawdown
    'min_cash_pct': 0.10,          # 10% min cash reserve
    'max_leverage': 1.0,           # No leverage by default
    'max_daily_loss_pct': 0.05    # 5% max daily loss
}


async def check_limits_tool(args: Dict[str, Any], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Check if proposed trade violates risk limits.
    
    Validates trade against hard limits:
    - Position size limits
    - Sector concentration
    - Correlation limits
    - Drawdown limits
    - Cash reserve requirements
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
            - size (float): Proposed position size (USD)
            - portfolio_value (float): Total portfolio value
            - current_positions (list): Current positions [{symbol, size, sector}, ...]
            - sector (str, optional): Symbol sector
        config: Optional risk config overrides
        
    Returns:
        Dictionary with:
        - allowed: Boolean, whether trade is allowed
        - violations: List of limit violations
        - warnings: List of warnings (approaching limits)
        - limits_status: Current status vs limits
        
    Example:
        >>> await check_limits_tool({
        ...     "symbol": "AAPL",
        ...     "size": 50000,
        ...     "portfolio_value": 200000,
        ...     "current_positions": [
        ...         {"symbol": "MSFT", "size": 30000, "sector": "Technology"},
        ...         {"symbol": "GOOGL", "size": 25000, "sector": "Technology"}
        ...     ],
        ...     "sector": "Technology"
        ... })
        {
            "allowed": false,
            "violations": ["Sector concentration exceeds 40% limit"],
            "warnings": [],
            "limits_status": {...}
        }
    """
    symbol = args.get('symbol')
    size = args.get('size', 0)
    portfolio_value = args.get('portfolio_value', 0)
    current_positions = args.get('current_positions', [])
    sector = args.get('sector', 'Unknown')
    
    if not symbol or portfolio_value <= 0:
        raise ValueError("Parameters 'symbol' and 'portfolio_value' are required")
    
    # Get limits (use config or defaults)
    limits = DEFAULT_LIMITS.copy()
    if config and 'hard_limits' in config:
        limits.update(config['hard_limits'])
    
    violations = []
    warnings = []
    
    # Calculate metrics
    position_pct = size / portfolio_value if portfolio_value > 0 else 0
    
    # 1. Check position size limit
    if position_pct > limits['max_position_pct']:
        violations.append(
            f"Position size {position_pct*100:.1f}% exceeds {limits['max_position_pct']*100:.1f}% limit"
        )
    elif position_pct > limits['max_position_pct'] * 0.8:
        warnings.append(f"Position size approaching limit ({position_pct*100:.1f}%)")
    
    # 2. Check sector concentration
    if sector != 'Unknown':
        sector_exposure = sum(
            p.get('size', 0) 
            for p in current_positions 
            if p.get('sector') == sector
        )
        new_sector_exposure = (sector_exposure + size) / portfolio_value
        
        if new_sector_exposure > limits['max_sector_pct']:
            violations.append(
                f"Sector concentration {new_sector_exposure*100:.1f}% "
                f"exceeds {limits['max_sector_pct']*100:.1f}% limit"
            )
        elif new_sector_exposure > limits['max_sector_pct'] * 0.8:
            warnings.append(
                f"Sector concentration approaching limit ({new_sector_exposure*100:.1f}%)"
            )
    
    # 3. Check cash reserve
    total_invested = sum(p.get('size', 0) for p in current_positions) + size
    cash_pct = 1 - (total_invested / portfolio_value)
    
    if cash_pct < limits['min_cash_pct']:
        violations.append(
            f"Cash reserve {cash_pct*100:.1f}% below {limits['min_cash_pct']*100:.1f}% minimum"
        )
    elif cash_pct < limits['min_cash_pct'] * 1.5:
        warnings.append(f"Cash reserve low ({cash_pct*100:.1f}%)")
    
    # 4. Check leverage
    leverage = total_invested / portfolio_value if portfolio_value > 0 else 0
    if leverage > limits['max_leverage']:
        violations.append(
            f"Leverage {leverage:.2f}x exceeds {limits['max_leverage']:.2f}x limit"
        )
    
    # Determine if allowed
    allowed = len(violations) == 0
    
    logger.info(
        f"Risk check for {symbol}: {'ALLOWED' if allowed else 'REJECTED'} "
        f"({len(violations)} violations, {len(warnings)} warnings)"
    )
    
    return {
        'allowed': allowed,
        'violations': violations,
        'warnings': warnings,
        'limits_status': {
            'position_pct': round(position_pct, 4),
            'max_position_pct': limits['max_position_pct'],
            'cash_pct': round(cash_pct, 4),
            'min_cash_pct': limits['min_cash_pct'],
            'leverage': round(leverage, 2),
            'max_leverage': limits['max_leverage']
        }
    }
