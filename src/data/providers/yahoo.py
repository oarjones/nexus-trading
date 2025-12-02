"""
Yahoo Finance Data Provider

Provides historical and incremental market data download from Yahoo Finance
using the yfinance library. Includes rate limiting and error handling.

Example:
    >>> provider = YahooProvider(rate_limit=0.5)
    >>> df = provider.get_historical('AAPL', start=date(2020, 1, 1), end=date(2024, 12, 1))
    >>> latest = provider.get_latest('AAPL', days=5)
"""

import time
import logging
from datetime import date, datetime, timedelta
from typing import Optional
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
    
    def _validate_data(self, df: pd.DataFrame, symbol: str) -> bool:
        """
        Validate downloaded data.
        
        Args:
            df: DataFrame to validate
            symbol: Symbol ticker
            
        Returns:
            True if data is valid, False otherwise
        """
        if df.empty:
            logger.warning(f"No data returned for {symbol}")
            return False
        
        # Check for all NaN columns
        if df.isnull().all().any():
            logger.warning(f"All NaN column detected for {symbol}")
            return False
        
        # Check for negative prices
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if (df[col] <= 0).any():
                logger.warning(f"Non-positive prices detected in {col} for {symbol}")
        
        # Check for negative volume
        if (df['volume'] < 0).any():
            logger.warning(f"Negative volume detected for {symbol}")
        
        return True
    
    def get_historical(
        self,
        symbol: str,
        start: date,
        end: date,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Download historical OHLCV data.
        
        Args:
            symbol: Yahoo Finance ticker (e.g., 'AAPL', 'SAN.MC')
            start: Start date
            end: End date
            interval: Data interval ('1d', '1h', '5m', etc.)
            
        Returns:
            Standardized DataFrame with OHLCV data
            
        Raises:
            ValueError: If download fails after max retries
        """
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
                    auto_adjust=True,  # Use adjusted close
                    actions=False  # Don't include dividends/splits
                )
                
                # Standardize format
                standardized = self._standardize_dataframe(df, symbol, interval)
                
                # Validate
                if self._validate_data(standardized, symbol):
                    logger.info(f"Downloaded {len(standardized)} records for {symbol}")
                    return standardized
                else:
                    logger.warning(f"Validation failed for {symbol}, attempt {attempt + 1}/{self.max_retries}")
                    if attempt < self.max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    
            except Exception as e:
                logger.error(f"Error downloading {symbol}: {e}, attempt {attempt + 1}/{self.max_retries}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise ValueError(f"Failed to download {symbol} after {self.max_retries} attempts") from e
        
        # Return empty DataFrame if all retries failed
        return pd.DataFrame()
    
    def get_latest(
        self,
        symbol: str,
        days: int = 5,
        interval: str = '1d'
    ) -> pd.DataFrame:
        """
        Download latest data for incremental updates.
        
        Args:
            symbol: Yahoo Finance ticker
            days: Number of days to fetch (default: 5)
            interval: Data interval (default: '1d')
            
        Returns:
            Standardized DataFrame with recent OHLCV data
        """
        end = date.today()
        start = end - timedelta(days=days)
        
        logger.info(f"Downloading latest {days} days for {symbol}")
        
        return self.get_historical(symbol, start, end, interval)
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Yahoo Finance ticker
            
        Returns:
            Current price or None if unavailable
        """
        self._enforce_rate_limit()
        
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Try different price fields
            price = info.get('currentPrice') or info.get('regularMarketPrice')
            
            if price:
                logger.debug(f"Current price for {symbol}: {price}")
                return float(price)
            else:
                logger.warning(f"No current price available for {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            return None
    
    def __repr__(self) -> str:
        """String representation of provider."""
        return f"YahooProvider(rate_limit={self.rate_limit}s, max_retries={self.max_retries})"
