"""
Quote retrieval tool.

Retrieves current quote (price) for a symbol from Redis cache,
falling back to latest OHLCV data from database if not cached.
"""

import logging
import json
from typing import Dict, Any
import redis
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)


async def get_quote_tool(args: Dict[str, Any], db_url: str, redis_url: str) -> Dict[str, Any]:
    """
    Get current quote for a symbol.
    
    Checks Redis cache first for real-time quote, falls back to latest
    OHLCV close price if not available.
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol (e.g., 'AAPL', 'SAN.MC')
        db_url: PostgreSQL connection string
        redis_url: Redis connection string
        
    Returns:
        Dictionary with quote data:
        - symbol: Symbol ticker
        - last: Last traded price
        - bid: Bid price (if available)
        - ask: Ask price (if available)
        - volume: Volume (if available)
        - timestamp: Quote timestamp
        - source: 'cache' or 'database'
        
    Example:
        >>> await get_quote_tool({"symbol": "AAPL"}, db_url, redis_url)
        {
            "symbol": "AAPL",
            "last": 175.43,
            "timestamp": "2024-12-03T10:30:00",
            "source": "cache"
        }
    """
    symbol = args.get('symbol')
    
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    # Try Redis cache first
    try:
        redis_client = redis.from_url(redis_url, decode_responses=True)
        cache_key = f"quote:{symbol}"
        cached_quote = redis_client.hgetall(cache_key)
        
        if cached_quote:
            logger.info(f"Quote for {symbol} found in cache")
            return {
                'symbol': symbol,
                'last': float(cached_quote.get('last', 0)),
                'bid': float(cached_quote.get('bid', 0)) if cached_quote.get('bid') else None,
                'ask': float(cached_quote.get('ask', 0)) if cached_quote.get('ask') else None,
                'volume': int(cached_quote.get('volume', 0)) if cached_quote.get('volume') else None,
                'timestamp': cached_quote.get('timestamp', ''),
                'source': 'cache'
            }
    
    except Exception as e:
        logger.warning(f"Redis cache error for {symbol}: {e}")
    
    # Fallback to latest OHLCV from database
    try:
        engine = create_engine(db_url)
        
        query = text("""
            SELECT time, close, volume
            FROM market_data.ohlcv
            WHERE symbol = :symbol AND timeframe = '1d'
            ORDER BY time DESC
            LIMIT 1
        """)
        
        with engine.connect() as conn:
            result = conn.execute(query, {'symbol': symbol})
            row = result.fetchone()
            
            if row:
                logger.info(f"Quote for {symbol} loaded from database (latest close)")
                return {
                    'symbol': symbol,
                    'last': float(row[1]),
                    'volume': int(row[2]) if row[2] else None,
                    'timestamp': row[0].isoformat(),
                    'source': 'database'
                }
            else:
                raise ValueError(f"No data found for symbol: {symbol}")
    
    except Exception as e:
        logger.error(f"Database error getting quote for {symbol}: {e}")
        raise
    
    finally:
        engine.dispose()
