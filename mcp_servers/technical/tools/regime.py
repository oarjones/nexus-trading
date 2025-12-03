"""
Market regime detection tool.

Detects current market regime using simple rules:
- ADX for trend strength
- SMA200 for trend direction
- Volatility for risk assessment
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine, text
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)


async def get_regime_tool(args: Dict[str, Any], db_url: str) -> Dict[str, Any]:
    """
    Detect current market regime for a symbol.
    
    Uses simple rule-based detection:
    - ADX > 25: Trending market
    - ADX < 25: Ranging market
    - Price vs SMA200: Trend direction (bullish/bearish)
    - Volatility: Risk level (low/medium/high)
    
    Args:
        args: Tool arguments containing:
            - symbol (str): Stock symbol
        db_url: PostgreSQL connection string
        
    Returns:
        Dictionary with:
        - symbol: Symbol ticker
        - regime: Regime type ('trending_bullish', 'trending_bearish', 
                  'ranging', 'volatile')
        - confidence: Confidence score (0-1)
        - metrics: Supporting metrics (ADX, price vs SMA200, volatility)
        - timestamp: Analysis timestamp
        
    Example:
        >>> await get_regime_tool({"symbol": "AAPL"}, db_url)
        {
            "symbol": "AAPL",
            "regime": "trending_bullish",
            "confidence": 0.85,
            "metrics": {
                "adx": 32.5,
                "price_vs_sma200": 1.08,
                "volatility_20d": 0.18,
                "trend_strength": "strong"
            },
            "timestamp": "2024-12-03T10:00:00"
        }
    """
    symbol = args.get('symbol')
    
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    try:
        # Load recent data and indicators
        engine = create_engine(db_url)
        
        # Get latest OHLCV (need 200+ for SMA200)
        ohlcv_query = text("""
            SELECT time, close
            FROM market_data.ohlcv
            WHERE symbol = :symbol AND timeframe = '1d'
            ORDER BY time DESC
            LIMIT 250
        """)
        
        with engine.connect() as conn:
            ohlcv_df = pd.read_sql(ohlcv_query, conn, params={'symbol': symbol})
        
        if ohlcv_df.empty:
            raise ValueError(f"No OHLCV data found for {symbol}")
        
        # Get latest indicators
        indicators_query = text("""
            SELECT indicator, value
            FROM market_data.indicators
            WHERE symbol = :symbol 
              AND timeframe = '1d'
              AND time = (
                  SELECT MAX(time) 
                  FROM market_data.indicators 
                  WHERE symbol = :symbol
              )
        """)
        
        with engine.connect() as conn:
            indicators_df = pd.read_sql(indicators_query, conn, params={'symbol': symbol})
        
        # Extract key indicators
        indicators = {}
        for _, row in indicators_df.iterrows():
            indicators[row['indicator']] = float(row['value'])
        
        # Calculate metrics
        current_price = float(ohlcv_df['close'].iloc[0])  # Most recent
        
        # SMA200 (calculate if not in indicators)
        if 'sma_200' in indicators:
            sma_200 = indicators['sma_200']
        else:
            # Calculate from OHLCV
            sma_200 = ohlcv_df['close'].rolling(200).mean().iloc[0]
        
        # ADX
        adx = indicators.get('adx_14', 0)
        
        # Volatility (annualized)
        returns = ohlcv_df['close'].pct_change()
        volatility = returns.rolling(20).std().iloc[0] * np.sqrt(252)
        
        # Regime detection logic
        price_vs_sma200 = current_price / sma_200 if sma_200 > 0 else 1.0
        
        # Determine regime
        regime = None
        confidence = 0.0
        
        if adx > 25:  # Trending market
            if price_vs_sma200 > 1.02:  # 2% above SMA200
                regime = 'trending_bullish'
                confidence = min(adx / 50, 1.0)  # Higher ADX = higher confidence
            elif price_vs_sma200 < 0.98:  # 2% below SMA200
                regime = 'trending_bearish'
                confidence = min(adx / 50, 1.0)
            else:
                regime = 'ranging'  # Trending but unclear direction
                confidence = 0.5
        else:  # ADX < 25: Ranging market
            if volatility > 0.30:  # High volatility
                regime = 'volatile_ranging'
                confidence = 0.6
            else:
                regime = 'ranging'
                confidence = 0.7
        
        # Trend strength classification
        if adx > 40:
            trend_strength = 'very_strong'
        elif adx > 25:
            trend_strength = 'strong'
        elif adx > 15:
            trend_strength = 'weak'
        else:
            trend_strength = 'no_trend'
        
        logger.info(f"Regime for {symbol}: {regime} (confidence={confidence:.2f})")
        
        return {
            'symbol': symbol,
            'regime': regime,
            'confidence': round(confidence, 3),
            'metrics': {
                'adx': round(adx, 2),
                'price_vs_sma200': round(price_vs_sma200, 4),
                'volatility_20d': round(volatility, 4),
                'trend_strength': trend_strength,
                'current_price': round(current_price, 2),
                'sma_200': round(sma_200, 2)
            },
            'timestamp': datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error detecting regime for {symbol}: {e}")
        raise
    
    finally:
        engine.dispose()
