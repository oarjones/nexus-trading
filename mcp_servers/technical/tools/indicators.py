"""
Technical indicators calculation tool.

Calculates technical indicators for a symbol using IndicatorEngine.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.data.indicators import IndicatorEngine

logger = logging.getLogger(__name__)


async def calculate_indicators_tool(args: Dict[str, Any], engine) -> Dict[str, Any]:
    """
    Calculate technical indicators for a symbol.
    
    Uses IndicatorEngine to compute SMA, EMA, RSI, MACD, BB, ATR, ADX.
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
            - timeframe (str): Timeframe - default '1d'
            - period (int): Number of days to analyze - default 60
        engine: SQLAlchemy engine instance (from connection pool)
        
    Returns:
        Dictionary with:
        - symbol: Symbol ticker
        - timeframe: Timeframe string
        - period: Analysis period
        - indicators: Dictionary of latest indicator values
        - timestamp: Analysis timestamp
        
    Example:
        >>> await calculate_indicators_tool({
        ...     "symbol": "AAPL",
        ...     "period": 30
        ... }, db_url)
        {
            "symbol": "AAPL",
            "timeframe": "1d",
            "period": 30,
            "indicators": {
                "sma_20": 175.43,
                "sma_50": 172.88,
                "rsi_14": 58.32,
                "macd_line": 1.23,
                "adx_14": 28.5,
                ...
            },
            "timestamp": "2024-12-03T10:00:00"
        }
    """
    symbol = args.get('symbol')
    timeframe = args.get('timeframe', '1d')
    period = args.get('period', 60)
    
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    try:
        # Load OHLCV data for analysis (need enough for longest indicator = SMA200)
        lookback_days = max(period, 250)  # Need 250 for SMA200
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        query = text("""
            SELECT time, open, high, low, close, volume
            FROM market_data.ohlcv
            WHERE symbol = :symbol 
              AND timeframe = :timeframe
              AND time >= :start
            ORDER BY time
        """)
        
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'start': start_date
                }
            )
        
        if df.empty:
            raise ValueError(f"No OHLCV data found for {symbol}")
        
        if len(df) < 200:
            logger.warning(f"Insufficient data for {symbol}: {len(df)} rows (need 200+)")
        
        df.set_index('time', inplace=True)
        
        # Calculate indicators using IndicatorEngine
        # Note: IndicatorEngine creates its own engine internally
        # TODO: Refactor IndicatorEngine to accept engine parameter
        from sqlalchemy import create_engine
        db_url = str(engine.url)  # Get URL from pooled engine
        indicator_engine = IndicatorEngine(db_url)
        indicators_df = indicator_engine.calculate_all(df, symbol, timeframe)
        
        # Get latest values (most recent non-NaN)
        latest_indicators = {}
        
        for indicator_name in indicators_df['indicator'].unique():
            indicator_values = indicators_df[
                indicators_df['indicator'] == indicator_name
            ]['value']
            
            # Get last non-NaN value
            non_nan = indicator_values.dropna()
            if not non_nan.empty:
                latest_indicators[indicator_name] = float(non_nan.iloc[-1])
        
        logger.info(f"Calculated {len(latest_indicators)} indicators for {symbol}")
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'period': period,
            'indicators': latest_indicators,
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error calculating indicators for {symbol}: {e}")
        raise
