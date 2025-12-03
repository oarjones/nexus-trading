"""
Portfolio exposure analysis tool.

Calculates current portfolio exposure across various dimensions.
"""

import logging
from typing import Dict, Any, List
from collections import defaultdict

logger = logging.getLogger(__name__)


async def get_exposure_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate portfolio exposure breakdown.
    
    Analyzes current portfolio to show:
    - Position-level exposure
    - Sector concentration
    - Geographic exposure
    - Asset class distribution
    - Currency exposure
    
    Args:
        args: Tool arguments containing:
            - portfolio_value (float): Total portfolio value
            - positions (list): List of positions
              [{symbol, size, sector, market, currency}, ...]
        
    Returns:
        Dictionary with:
        - total_value: Total portfolio value
        - total_invested: Total invested amount
        - cash_pct: Cash percentage
        - positions_count: Number of positions
        - exposure_by_sector: Sector breakdown
        - exposure_by_market: Market breakdown
        - exposure_by_currency: Currency breakdown
        - top_positions: Largest positions
        - concentration_metrics: HHI and other metrics
        
    Example:
        >>> await get_exposure_tool({
        ...     "portfolio_value": 100000,
        ...     "positions": [
        ...         {"symbol": "AAPL", "size": 20000, "sector": "Technology", 
        ...          "market": "US", "currency": "USD"},
        ...         {"symbol": "MSFT", "size": 15000, "sector": "Technology",
        ...          "market": "US", "currency": "USD"},
        ...         {"symbol": "SAN.MC", "size": 10000, "sector": "Financial",
        ...          "market": "EU", "currency": "EUR"}
        ...     ]
        ... })
        {
            "total_value": 100000,
            "total_invested": 45000,
            "cash_pct": 0.55,
            "positions_count": 3,
            "exposure_by_sector": {
                "Technology": 0.35,
                "Financial": 0.10
            },
            ...
        }
    """
    portfolio_value = args.get('portfolio_value', 0)
    positions = args.get('positions', [])
    
    if portfolio_value <= 0:
        raise ValueError("Parameter 'portfolio_value' must be positive")
    
    # Calculate total invested
    total_invested = sum(p.get('size', 0) for p in positions)
    cash = portfolio_value - total_invested
    cash_pct = cash / portfolio_value if portfolio_value > 0 else 0
    
    # Exposure by sector
    sector_exposure = defaultdict(float)
    for p in positions:
        sector = p.get('sector', 'Unknown')
        size = p.get('size', 0)
        sector_exposure[sector] += size
    
    # Convert to percentages
    exposure_by_sector = {
        sector: round(value / portfolio_value, 4)
        for sector, value in sector_exposure.items()
    }
    
    # Exposure by market
    market_exposure = defaultdict(float)
    for p in positions:
        market = p.get('market', 'Unknown')
        size = p.get('size', 0)
        market_exposure[market] += size
    
    exposure_by_market = {
        market: round(value / portfolio_value, 4)
        for market, value in market_exposure.items()
    }
    
    # Exposure by currency
    currency_exposure = defaultdict(float)
    for p in positions:
        currency = p.get('currency', 'USD')
        size = p.get('size', 0)
        currency_exposure[currency] += size
    
    exposure_by_currency = {
        currency: round(value / portfolio_value, 4)
        for currency, value in currency_exposure.items()
    }
    
    # Top positions (by size)
    sorted_positions = sorted(
        positions,
        key=lambda x: x.get('size', 0),
        reverse=True
    )
    
    top_positions = [
        {
            'symbol': p.get('symbol'),
            'size': p.get('size', 0),
            'pct': round(p.get('size', 0) / portfolio_value, 4)
        }
        for p in sorted_positions[:10]  # Top 10
    ]
    
    # Concentration metrics
    # Herfindahl-Hirschman Index (HHI) - measures concentration
    # HHI ranges from 1/N (perfectly diversified) to 1 (single position)
    position_weights = [p.get('size', 0) / total_invested for p in positions if total_invested > 0]
    hhi = sum(w**2 for w in position_weights) if position_weights else 0
    
    # Effective number of positions (1/HHI)
    effective_positions = 1 / hhi if hhi > 0 else len(positions)
    
    logger.info(
        f"Portfolio exposure: {len(positions)} positions, "
        f"{cash_pct*100:.1f}% cash, HHI={hhi:.3f}"
    )
    
    return {
        'total_value': round(portfolio_value, 2),
        'total_invested': round(total_invested, 2),
        'cash': round(cash, 2),
        'cash_pct': round(cash_pct, 4),
        'positions_count': len(positions),
        'exposure_by_sector': exposure_by_sector,
        'exposure_by_market': exposure_by_market,
        'exposure_by_currency': exposure_by_currency,
        'top_positions': top_positions,
        'concentration_metrics': {
            'hhi': round(hhi, 4),
            'effective_positions': round(effective_positions, 2),
            'largest_position_pct': round(top_positions[0]['pct'], 4) if top_positions else 0
        }
    }
