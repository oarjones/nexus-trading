"""
Unit tests for Symbol Registry module

Tests the Symbol dataclass and SymbolRegistry functionality including
loading from YAML, filtering by market/source, and validation.
"""

import pytest
from pathlib import Path
import tempfile
import yaml
from src.data.symbols import Symbol, SymbolRegistry


class TestSymbol:
    """Test cases for Symbol dataclass."""
    
    def test_symbol_creation(self):
        """Test creating a valid symbol."""
        symbol = Symbol(
            ticker='AAPL',
            name='Apple Inc.',
            market='US',
            source='yahoo',
            timezone='America/New_York',
            currency='USD',
            asset_type='stock'
        )
        
        assert symbol.ticker == 'AAPL'
        assert symbol.name == 'Apple Inc.'
        assert symbol.market == 'US'
        assert symbol.source == 'yahoo'
    
    def test_symbol_empty_ticker_raises(self):
        """Test that empty ticker raises ValueError."""
        with pytest.raises(ValueError, match="ticker cannot be empty"):
            Symbol(
                ticker='',
                name='Test',
                market='US',
                source='yahoo',
                timezone='America/New_York',
                currency='USD'
            )


class TestSymbolRegistry:
    """Test cases for SymbolRegistry."""
    
    @pytest.fixture
    def sample_config(self):
        """Create a temporary YAML config file for testing."""
        config_data = {
            'symbols': [
                {
                    'ticker': 'AAPL',
                    'name': 'Apple Inc.',
                    'market': 'US',
                    'source': 'yahoo',
                    'timezone': 'America/New_York',
                    'currency': 'USD',
                    'asset_type': 'stock'
                },
                {
                    'ticker': 'SAN.MC',
                    'name': 'Banco Santander',
                    'market': 'EU',
                    'source': 'yahoo',
                    'timezone': 'Europe/Madrid',
                    'currency': 'EUR',
                    'asset_type': 'stock'
                },
                {
                    'ticker': 'EURUSD=X',
                    'name': 'EUR/USD',
                    'market': 'FOREX',
                    'source': 'yahoo',
                    'timezone': 'UTC',
                    'currency': 'USD',
                    'asset_type': 'forex'
                },
                {
                    'ticker': 'BTC-EUR',
                    'name': 'Bitcoin EUR',
                    'market': 'CRYPTO',
                    'source': 'yahoo',
                    'timezone': 'UTC',
                    'currency': 'EUR',
                    'asset_type': 'crypto'
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        Path(temp_path).unlink()
    
    def test_load_symbols(self, sample_config):
        """Test loading symbols from YAML config."""
        registry = SymbolRegistry(sample_config)
        
        assert registry.count() == 4
        assert len(registry.get_all()) == 4
    
    def test_file_not_found(self):
        """Test that missing config file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            SymbolRegistry('nonexistent_file.yaml')
    
    def test_get_by_market(self, sample_config):
        """Test filtering symbols by market."""
        registry = SymbolRegistry(sample_config)
        
        us_symbols = registry.get_by_market('US')
        assert len(us_symbols) == 1
        assert us_symbols[0].ticker == 'AAPL'
        
        eu_symbols = registry.get_by_market('EU')
        assert len(eu_symbols) == 1
        assert eu_symbols[0].ticker == 'SAN.MC'
        
        forex_symbols = registry.get_by_market('FOREX')
        assert len(forex_symbols) == 1
        
        crypto_symbols = registry.get_by_market('CRYPTO')
        assert len(crypto_symbols) == 1
    
    def test_get_by_source(self, sample_config):
        """Test filtering symbols by data source."""
        registry = SymbolRegistry(sample_config)
        
        yahoo_symbols = registry.get_by_source('yahoo')
        assert len(yahoo_symbols) == 4  # All are from yahoo in test data
    
    def test_get_by_ticker(self, sample_config):
        """Test getting symbol by ticker."""
        registry = SymbolRegistry(sample_config)
        
        symbol = registry.get_by_ticker('AAPL')
        assert symbol is not None
        assert symbol.name == 'Apple Inc.'
        
        missing = registry.get_by_ticker('INVALID')
        assert missing is None
    
    def test_get_by_asset_type(self, sample_config):
        """Test filtering symbols by asset type."""
        registry = SymbolRegistry(sample_config)
        
        stocks = registry.get_by_asset_type('stock')
        assert len(stocks) == 2
        
        forex = registry.get_by_asset_type('forex')
        assert len(forex) == 1
        
        crypto = registry.get_by_asset_type('crypto')
        assert len(crypto) == 1
    
    def test_get_tickers(self, sample_config):
        """Test getting list of tickers."""
        registry = SymbolRegistry(sample_config)
        
        tickers = registry.get_tickers()
        assert len(tickers) == 4
        assert 'AAPL' in tickers
        assert 'SAN.MC' in tickers
        assert 'EURUSD=X' in tickers
        assert 'BTC-EUR' in tickers
    
    def test_invalid_yaml(self):
        """Test handling of invalid YAML."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                SymbolRegistry(temp_path)
        finally:
            Path(temp_path).unlink()
    
    def test_missing_symbols_key(self):
        """Test config file without 'symbols' key."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'wrong_key': []}, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="must contain 'symbols' key"):
                SymbolRegistry(temp_path)
        finally:
            Path(temp_path).unlink()
    
    def test_repr(self, sample_config):
        """Test string representation of registry."""
        registry = SymbolRegistry(sample_config)
        repr_str = repr(registry)
        
        assert 'SymbolRegistry' in repr_str
        assert 'symbols=4' in repr_str
