"""
OHLCV data retrieval tool.

Retrieves historical OHLCV (Open, High, Low, Close, Volume) data
from TimescaleDB for a given symbol and date range.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, text
import pandas as pd

logger = logging.getLogger(__name__)


async def get_ohlcv_tool(args: Dict[str, Any], db_url: str) -> Dict[str, Any]:
    """
    Get historical OHLCV data for a symbol.
    
    Retrieves candlestick data from TimescaleDB for specified date range.
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
            - timeframe (str): Timeframe ('1d', '1h', etc.) - default '1d'
            - start (str): Start date (YYYY-MM-DD)
            - end (str): End date (YYYY-MM-DD)
            - limit (int): Max number of records - default 1000
        db_url: PostgreSQL connection string
        
    Returns:
        Dictionary with:
        - symbol: Symbol ticker
        - timeframe: Timeframe string
        - count: Number of records returned
        - data: List of OHLCV records
        
    Example:
        >>> await get_ohlcv_tool({
        ...     "symbol": "AAPL",
        ...     "timeframe": "1d",
        ...     "start": "2024-01-01",
        ...     "end": "2024-01-31"
        ... }, db_url)
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "count": 21,
            "data": [
                {
                    "time": "2024-01-02T00:00:00",
                    "open": 185.64,
                    "high": 186.95,
                    "low": 183.82,
                    "close": 185.92,
                    "volume": 82488200
                },
                ...
            ]
        }
    """
    symbol = args.get('symbol')
    timeframe = args.get('timeframe', '1d')
    start = args.get('start')
    end = args.get('end')
    limit = args.get('limit', 1000)
    
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    # Build query
    query_parts = [
        "SELECT time, open, high, low, close, volume",
        "FROM market_data.ohlcv",
        "WHERE symbol = :symbol AND timeframe = :timeframe"
    ]
    
    params = {
        'symbol': symbol,
        'timeframe': timeframe,
        'limit': limit
    }
    
    if start:
        query_parts.append("AND time >= :start")
        params['start'] = start
    
    if end:
        query_parts.append("AND time <= :end")
        params['end'] = end
    
    query_parts.append("ORDER BY time DESC")
    query_parts.append("LIMIT :limit")
    
    query_str = " ".join(query_parts)
    
    # Execute query
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                text(query_str),
                conn,
                params=params
            )
        
        if df.empty:
            logger.warning(f"No OHLCV data found for {symbol}")
            return {
                'symbol': symbol,
                'timeframe': timeframe,
                'count': 0,
                'data': []
            }
        
        # Convert to list of dicts
        # Reverse to get chronological order
        df = df.iloc[::-1]
        
        data = []
        for _, row in df.iterrows():
            data.append({
                'time': row['time'].isoformat(),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': int(row['volume']) if row['volume'] else 0
            })
        
        logger.info(f"Retrieved {len(data)} OHLCV records for {symbol}")
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'count': len(data),
            'data': data
        }
    
    except Exception as e:
        logger.error(f"Error retrieving OHLCV for {symbol}: {e}")
        raise
    
    finally:
        engine.dispose()
