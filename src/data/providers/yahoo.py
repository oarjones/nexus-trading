"""
Yahoo Finance Data Provider - Fase A1.3

Provides historical and incremental market data download from Yahoo Finance
using the yfinance library. Includes rate limiting and error handling.

Example:
    >>> provider = YahooProvider(rate_limit=0.5)
    >>> df = await provider.get_historical('AAPL', '1 Y', '1 day')
    >>> quote = await provider.get_quote('AAPL')
"""

import time
import logging
import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class YahooProvider:
    """
    Yahoo Finance data provider for OHLCV historical and incremental data.
    
    Features:
    - Historical data download (up to 5+ years)
    - Incremental download for daily updates
    - Rate limiting to avoid bans
    - Standardized output format
    - Error handling with retries
    - Async wrapper for blocking calls
    
    Attributes:
        rate_limit: Seconds to wait between requests (default: 0.5)
        max_retries: Maximum number of retry attempts (default: 3)
    """
    
    def __init__(self, rate_limit: float = 0.5, max_retries: int = 3):
        """
        Initialize Yahoo Finance provider.
        
        Args:
            rate_limit: Seconds between requests to avoid rate limiting
            max_retries: Maximum retry attempts for failed requests
        """
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self._last_request_time = 0.0
    
    def _enforce_rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()
    
    def _standardize_dataframe(
        self, 
        df: pd.DataFrame, 
        symbol: str,
        timeframe: str = '1d'
    ) -> pd.DataFrame:
        """
        Standardize Yahoo Finance DataFrame to common format.
        
        Args:
            df: Raw DataFrame from yfinance
            symbol: Symbol ticker
            timeframe: Timeframe string (default: '1d')
            
        Returns:
            Standardized DataFrame with columns:
            time (index), symbol, timeframe, open, high, low, close, volume, source
        """
        if df is None or df.empty:
            return pd.DataFrame()
        
        # Create standardized DataFrame
        standardized = pd.DataFrame()
        standardized['time'] = df.index
        standardized['symbol'] = symbol
        standardized['timeframe'] = timeframe
        
        # Rename columns to lowercase
        standardized['open'] = df['Open'].values
        standardized['high'] = df['High'].values
        standardized['low'] = df['Low'].values
        standardized['close'] = df['Close'].values
        standardized['volume'] = df['Volume'].values
        standardized['source'] = 'yahoo'
        
        # Set time as index
        standardized.set_index('time', inplace=True)
        
        # Remove timezone info if present for consistency
        if standardized.index.tz is not None:
            standardized.index = standardized.index.tz_localize(None)
        
        return standardized
    
    async def get_historical(
        self,
        symbol: str,
        duration: str = '1 Y',
        bar_size: str = '1 day',
        exchange: str = 'SMART'
    ) -> pd.DataFrame:
        """
        Download historical OHLCV data (Async wrapper).
        
        Args:
            symbol: Yahoo Finance ticker
            duration: Duration string (e.g., '1 Y') - Mapped to start/end
            bar_size: Bar size ('1 day', '1 hour') - Mapped to interval
            exchange: Ignored for Yahoo
            
        Returns:
            Standardized DataFrame with OHLCV data
        """
        # Map duration to start date
        end = date.today()
        start = self._parse_duration(duration)
        
        # Map bar_size to interval
        interval = self._map_interval(bar_size)
        
        # Run blocking call in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._get_historical_sync, 
            symbol, start, end, interval
        )

    def _get_historical_sync(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """Synchronous implementation of get_historical."""
        self._enforce_rate_limit()
        
        logger.info(f"Downloading historical data for {symbol} from {start} to {end}")
        
        for attempt in range(self.max_retries):
            try:
                # Download data using yfinance
                ticker = yf.Ticker(symbol)
                df = ticker.history(
                    start=start,
                    end=end,
                    interval=interval,
                    auto_adjust=True,
                    actions=False
                )
                
                standardized = self._standardize_dataframe(df, symbol, interval)
                
                if not standardized.empty:
                    logger.info(f"Downloaded {len(standardized)} records for {symbol}")
                    return standardized
                else:
                    logger.warning(f"No data for {symbol}, attempt {attempt + 1}")
                    
            except Exception as e:
                logger.error(f"Error downloading {symbol}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
        
        return pd.DataFrame()

    async def get_quote(self, symbol: str) -> Optional[Dict]:
        """
        Get current market quote (Async wrapper).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_quote_sync, symbol)

    def _get_quote_sync(self, symbol: str) -> Optional[Dict]:
        """Synchronous implementation of get_quote."""
        self._enforce_rate_limit()
        
        try:
            ticker = yf.Ticker(symbol)
            # fast_info is faster than info
            price = ticker.fast_info.last_price
            
            if price:
                return {
                    'symbol': symbol,
                    'bid': None, # Yahoo doesn't provide reliable bid/ask in free tier
                    'ask': None,
                    'last': float(price),
                    'volume': 0,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
            return None
                
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

    def _parse_duration(self, duration: str) -> date:
        """Parse duration string to start date."""
        today = date.today()
        try:
            parts = duration.split()
            value = int(parts[0])
            unit = parts[1].upper()
            
            if 'Y' in unit:
                return today - timedelta(days=value * 365)
            elif 'M' in unit:
                return today - timedelta(days=value * 30)
            elif 'D' in unit:
                return today - timedelta(days=value)
            elif 'W' in unit:
                return today - timedelta(weeks=value)
            else:
                return today - timedelta(days=365) # Default 1 year
        except:
            return today - timedelta(days=365)

    def _map_interval(self, bar_size: str) -> str:
        """Map IBKR-style bar size to Yahoo interval."""
        mapping = {
            '1 min': '1m',
            '5 mins': '5m',
            '15 mins': '15m',
            '30 mins': '30m',
            '1 hour': '1h',
            '1 day': '1d',
            '1 week': '1wk',
            '1 month': '1mo'
        }
        return mapping.get(bar_size, '1d')

    @property
    def name(self) -> str:
        return "yahoo"
        
    def is_available(self) -> bool:
        return True # Always assumed available unless rate limited

    def __repr__(self) -> str:
        return f"YahooProvider(rate_limit={self.rate_limit}s)"
