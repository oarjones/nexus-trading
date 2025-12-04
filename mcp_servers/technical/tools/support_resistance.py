"""
Support and resistance levels detection tool.

Finds support and resistance levels using local extrema (peaks and troughs).
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np
from scipy.signal import argrelextrema

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


async def find_sr_levels_tool(args: Dict[str, Any], engine) -> Dict[str, Any]:
    """
    Find support and resistance levels for a symbol.
    
    Uses local extrema detection (peaks for resistance, troughs for support).
    Groups nearby levels and ranks by strength (number of touches).
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
            - period (int): Lookback period in days - default 60
            - max_levels (int): Maximum levels to return - default 5
        engine: SQLAlchemy engine instance (from connection pool)
        
    Returns:
        Dictionary with:
        - symbol: Symbol ticker
        - period: Analysis period
        - current_price: Current price
        - support_levels: List of support levels (sorted by strength)
        - resistance_levels: List of resistance levels (sorted by strength)
        - timestamp: Analysis timestamp
        
    Example:
        >>> await find_sr_levels_tool({
        ...     "symbol": "AAPL",
        ...     "period": 90
        ... }, db_url)
        {
            "symbol": "AAPL",
            "period": 90,
            "current_price": 175.43,
            "support_levels": [
                {"price": 170.50, "strength": 3, "distance_pct": -2.8},
                {"price": 165.00, "strength": 2, "distance_pct": -5.9}
            ],
            "resistance_levels": [
                {"price": 180.00, "strength": 4, "distance_pct": 2.6},
                {"price": 185.50, "strength": 2, "distance_pct": 5.7}
            ],
            "timestamp": "2024-12-03T10:00:00"
        }
    """
    symbol = args.get('symbol')
    period = args.get('period', 60)
    max_levels = args.get('max_levels', 5)
    
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    try:
        # Load OHLCV data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period)
        
        query = text("""
            SELECT time, high, low, close
            FROM market_data.ohlcv
            WHERE symbol = :symbol 
              AND timeframe = '1d'
              AND time >= :start
            ORDER BY time
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={'symbol': symbol, 'start': start_date}
            )
        
        if df.empty:
            raise ValueError(f"No OHLCV data found for {symbol}")
        
        if len(df) < 20:
            raise ValueError(f"Insufficient data for {symbol}: need at least 20 days")
        
        current_price = float(df['close'].iloc[-1])
        
        # Find local maxima (resistance) and minima (support)
        # Using order=5 means we look 5 days on each side
        order = min(5, len(df) // 10)  # Adaptive window
        
        # Resistance levels (local maxima in high prices)
        resistance_indices = argrelextrema(df['high'].values, np.greater, order=order)[0]
        resistance_prices = df['high'].iloc[resistance_indices].values
        
        # Support levels (local minima in low prices)
        support_indices = argrelextrema(df['low'].values, np.less, order=order)[0]
        support_prices = df['low'].iloc[support_indices].values
        
        # Cluster nearby levels (within 1% of each other)
        def cluster_levels(prices, tolerance=0.01):
            """Group nearby price levels."""
            if len(prices) == 0:
                return []
            
            prices_sorted = sorted(prices)
            clusters = []
            current_cluster = [prices_sorted[0]]
            
            for price in prices_sorted[1:]:
                if abs(price - current_cluster[-1]) / current_cluster[-1] < tolerance:
                    current_cluster.append(price)
                else:
                    clusters.append(current_cluster)
                    current_cluster = [price]
            
            clusters.append(current_cluster)
            
            # Return cluster mean and strength (count)
            return [
                {
                    'price': round(np.mean(cluster), 2),
                    'strength': len(cluster),
                    'distance_pct': round((np.mean(cluster) / current_price - 1) * 100, 2)
                }
                for cluster in clusters
            ]
        
        # Cluster and rank levels
        resistance_levels = cluster_levels(resistance_prices)
        support_levels = cluster_levels(support_prices)
        
        # Sort by strength (descending) and limit
        resistance_levels = sorted(
            resistance_levels,
            key=lambda x: x['strength'],
            reverse=True
        )[:max_levels]
        
        support_levels = sorted(
            support_levels,
            key=lambda x: x['strength'],
            reverse=True
        )[:max_levels]
        
        logger.info(
            f"Found {len(support_levels)} support and "
            f"{len(resistance_levels)} resistance levels for {symbol}"
        )
        
        return {
            'symbol': symbol,
            'period': period,
            'current_price': round(current_price, 2),
            'support_levels': support_levels,
            'resistance_levels': resistance_levels,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error finding S/R levels for {symbol}: {e}")
        raise
