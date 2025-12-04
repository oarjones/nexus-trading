"""
Pytest configuration and fixtures for MCP servers tests.

Provides common fixtures for testing all MCP servers.
"""

from datetime import timezone
import pytest
import asyncio
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from dotenv import load_dotenv

# Load environment for tests
load_dotenv()


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def db_url():
    """Database URL fixture."""
    return os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/trading_test')


@pytest.fixture
def redis_url():
    """Redis URL fixture."""
    return os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    import pandas as pd
    from datetime import datetime, timedelta
    
    dates = pd.date_range(end=datetime.now(timezone.utc), periods=100, freq='D')
    data = {
        'time': dates,
        'open': [100 + i * 0.5 for i in range(100)],
        'high': [102 + i * 0.5 for i in range(100)],
        'low': [99 + i * 0.5 for i in range(100)],
        'close': [101 + i * 0.5 for i in range(100)],
        'volume': [1000000 + i * 10000 for i in range(100)]
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_positions():
    """Sample portfolio positions for testing."""
    return [
        {"symbol": "AAPL", "size": 20000, "sector": "Technology", "market": "US", "currency": "USD"},
        {"symbol": "MSFT", "size": 15000, "sector": "Technology", "market": "US", "currency": "USD"},
        {"symbol": "SAN.MC", "size": 10000, "sector": "Financial", "market": "EU", "currency": "EUR"}
    ]


@pytest.fixture
def mock_ibkr_connection():
    """Mock IBKR connection for testing."""
    mock_conn = AsyncMock()
    mock_conn.is_connected.return_value = True
    
    # Mock IB instance
    mock_ib = MagicMock()
    mock_ib.isConnected.return_value = True
    mock_ib.managedAccounts.return_value = ['DU1234567']  # Paper account
    
    mock_conn.ensure_connected.return_value = mock_ib
    mock_conn.ib = mock_ib
    
    return mock_conn


@pytest.fixture
def mock_database_pool(monkeypatch):
    """Mock DatabasePool for testing without real DB."""
    mock_engine = Mock()
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine.connect.return_value = mock_conn
    
    class MockPool:
        def __init__(self, *args, **kwargs):
            self.engine = mock_engine
        
        def get_engine(self):
            return self.engine
    
    # Mock the DatabasePool import from src.database
    import sys
    if 'src.database' in sys.modules:
        monkeypatch.setattr('src.database.DatabasePool', MockPool)
    
    return mock_engine


@pytest.fixture
def config_path(tmp_path):
    """Create temporary config file for testing."""
    config_content = """
market-data:
  port: 3001
  cache_ttl: 60

technical:
  port: 3002

risk:
  port: 3003
  hard_limits:
    max_position_pct: 0.20
    max_sector_pct: 0.40
    min_cash_pct: 0.10

ibkr:
  port: 3004
  host: 127.0.0.1
  tws_port: 7497
  client_id: 1
  paper_only: true
  max_order_value: 10000
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


# Markers for conditional tests
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "ibkr: mark test as requiring IBKR connection (skip if not available)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
