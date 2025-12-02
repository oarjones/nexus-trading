"""
Unit tests for Yahoo Finance data provider

Tests historical download, incremental updates, rate limiting,
error handling, and data validation.
"""

import pytest
from datetime import date, timedelta
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from src.data.providers.yahoo import YahooProvider


class TestYahooProvider:
    """Test cases for YahooProvider."""
    
    def test_initialization(self):
        """Test provider initialization with custom parameters."""
        provider = YahooProvider(rate_limit=1.0, max_retries=5)
        
        assert provider.rate_limit == 1.0
        assert provider.max_retries == 5
    
    def test_default_initialization(self):
        """Test provider initialization with defaults."""
        provider = YahooProvider()
        
        assert provider.rate_limit == 0.5
        assert provider.max_retries == 3
    
    @patch('src.data.providers.yahoo.yf.Ticker')
    def test_get_historical_success(self, mock_ticker_class):
        """Test successful historical data download."""
        # Mock yfinance response
        mock_ticker = Mock()
        mock_ticker_class.return_value = mock_ticker
        
        # Create sample data
        index = pd.date_range(start='2024-01-01', end='2024-01-05', freq='D')
        data = {
            'Open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'High': [101.0, 102.0, 103.0, 104.0, 105.0],
            'Low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'Close': [100.5, 101.5, 102.5, 103.5, 104.5],
            'Volume': [1000, 1100, 1200, 1300, 1400]
        }
        mock_df = pd.DataFrame(data, index=index)
        mock_ticker.history.return_value = mock_df
        
        # Test download
        provider = YahooProvider()
        result = provider.get_historical(
            'AAPL',
            start=date(2024, 1, 1),
            end=date(2024, 1, 5)
        )
        
        assert not result.empty
        assert len(result) == 5
        assert 'symbol' in result.columns
        assert 'timeframe' in result.columns
        assert 'open' in result.columns
        assert 'close' in result.columns
        assert (result['symbol'] == 'AAPL').all()
        assert (result['source'] == 'yahoo').all()
    
    @patch('src.data.providers.yahoo.yf.Ticker')
    def test_get_latest(self, mock_ticker_class):
        """Test latest data download."""
        mock_ticker = Mock()
        mock_ticker_class.return_value = mock_ticker
        
        # Create sample data for last 5 days
        end_date = date.today()
        start_date = end_date - timedelta(days=5)
        index = pd.date_range(start=start_date, end=end_date, freq='D')
        
        data = {
            'Open': [100.0] * len(index),
            'High': [101.0] * len(index),
            'Low': [99.0] * len(index),
            'Close': [100.5] * len(index),
            'Volume': [1000] * len(index)
        }
        mock_df = pd.DataFrame(data, index=index)
        mock_ticker.history.return_value = mock_df
        
        provider = YahooProvider()
        result = provider.get_latest('AAPL', days=5)
        
        assert not result.empty
        assert 'AAPL' in result['symbol'].values
    
    def test_standardize_dataframe(self):
        """Test DataFrame standardization."""
        provider = YahooProvider()
        
        # Create raw Yahoo-style DataFrame
        index = pd.date_range(start='2024-01-01', periods=3, freq='D')
        data = {
            'Open': [100.0, 101.0, 102.0],
            'High': [101.0, 102.0, 103.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [100.5, 101.5, 102.5],
            'Volume': [1000, 1100, 1200]
        }
        raw_df = pd.DataFrame(data, index=index)
        
        result = provider._standardize_dataframe(raw_df, 'TEST', '1d')
        
        assert len(result) == 3
        assert 'symbol' in result.columns
        assert 'timeframe' in result.columns
        assert 'open' in result.columns
        assert 'high' in result.columns
        assert 'low' in result.columns
        assert 'close' in result.columns
        assert 'volume' in result.columns
        assert 'source' in result.columns
        assert (result['symbol'] == 'TEST').all()
        assert (result['timeframe'] == '1d').all()
        assert (result['source'] == 'yahoo').all()
    
    def test_standardize_empty_dataframe(self):
        """Test standardization of empty DataFrame."""
        provider = YahooProvider()
        result = provider._standardize_dataframe(pd.DataFrame(), 'TEST')
        
        assert result.empty
    
    def test_validate_data_empty(self):
        """Test validation of empty data."""
        provider = YahooProvider()
        result = provider._validate_data(pd.DataFrame(), 'TEST')
        
        assert result is False
    
    def test_validate_data_valid(self):
        """Test validation of valid data."""
        provider = YahooProvider()
        
        data = {
            'open': [100.0, 101.0],
            'high': [101.0, 102.0],
            'low': [99.0, 100.0],
            'close': [100.5, 101.5],
            'volume': [1000, 1100]
        }
        df = pd.DataFrame(data)
        
        result = provider._validate_data(df, 'TEST')
        assert result is True
    
    @patch('src.data.providers.yahoo.time.sleep')
    def test_rate_limiting(self, mock_sleep):
        """Test that rate limiting is enforced."""
        provider = YahooProvider(rate_limit=1.0)
        
        # First call should not sleep
        provider._enforce_rate_limit()
        
        # Second immediate call should sleep
        provider._enforce_rate_limit()
        
        # Verify sleep was called
        assert mock_sleep.called
    
    @patch('src.data.providers.yahoo.yf.Ticker')
    def test_get_current_price(self, mock_ticker_class):
        """Test getting current price."""
        mock_ticker = Mock()
        mock_ticker_class.return_value = mock_ticker
        mock_ticker.info = {'currentPrice': 150.25}
        
        provider = YahooProvider()
        price = provider.get_current_price('AAPL')
        
        assert price == 150.25
    
    @patch('src.data.providers.yahoo.yf.Ticker')
    def test_get_current_price_no_data(self, mock_ticker_class):
        """Test getting current price when no data available."""
        mock_ticker = Mock()
        mock_ticker_class.return_value = mock_ticker
        mock_ticker.info = {}
        
        provider = YahooProvider()
        price = provider.get_current_price('INVALID')
        
        assert price is None
    
    @patch('src.data.providers.yahoo.yf.Ticker')
    def test_retry_on_error(self, mock_ticker_class):
        """Test retry logic on errors."""
        mock_ticker = Mock()
        mock_ticker_class.return_value = mock_ticker
        
        # First two calls fail, third succeeds
        index = pd.date_range(start='2024-01-01', periods=1, freq='D')
        data = {
            'Open': [100.0],
            'High': [101.0],
            'Low': [99.0],
            'Close': [100.5],
            'Volume': [1000]
        }
        success_df = pd.DataFrame(data, index=index)
        
        mock_ticker.history.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            success_df
        ]
        
        provider = YahooProvider(max_retries=3)
        result = provider.get_historical('AAPL', date(2024, 1, 1), date(2024, 1, 2))
        
        # Should succeed on third try
        assert not result.empty
        assert mock_ticker.history.call_count == 3
    
    def test_repr(self):
        """Test string representation."""
        provider = YahooProvider(rate_limit=1.0, max_retries=5)
        repr_str = repr(provider)
        
        assert 'YahooProvider' in repr_str
        assert '1.0' in repr_str
        assert '5' in repr_str
