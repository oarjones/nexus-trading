"""
Symbols list tool.

Retrieves list of available symbols from symbol registry.
"""

import logging
from typing import Dict, Any, List
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.symbols import SymbolRegistry

logger = logging.getLogger(__name__)


async def get_symbols_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get list of available trading symbols.
    
    Retrieves symbols from the symbol registry, optionally filtered by market.
    
    Args:
        args: Tool arguments containing:
            - market (str, optional): Filter by market ('EU', 'US', 'FX', 'CRYPTO')
        
    Returns:
        Dictionary with:
        - count: Number of symbols
        - symbols: List of symbol dictionaries
        
    Example:
        >>> await get_symbols_tool({"market": "US"})
        {
            "count": 5,
            "symbols": [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "market": "US",
                    "currency": "USD"
                },
                ...
            ]
        }
    """
    market_filter = args.get('market')
    
    try:
        # Load symbol registry
        registry = SymbolRegistry('config/symbols.yaml')
        symbols = registry.get_all()
        
        # Filter by market if specified
        if market_filter:
            symbols = [s for s in symbols if s.market == market_filter.upper()]
        
        # Convert to dict format
        symbols_data = []
        for symbol in symbols:
            symbols_data.append({
                'ticker': symbol.ticker,
                'name': symbol.name,
                'market': symbol.market,
                'currency': symbol.currency,
                'description': symbol.description
            })
        
        logger.info(f"Retrieved {len(symbols_data)} symbols" + 
                   (f" (market={market_filter})" if market_filter else ""))
        
        return {
            'count': len(symbols_data),
            'symbols': symbols_data
        }
    
    except Exception as e:
        logger.error(f"Error retrieving symbols: {e}")
        raise
