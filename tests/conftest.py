"""
Pytest configuration and fixtures for root-level tests.

Provides common fixtures for testing agents and other src modules.
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
from dotenv import load_dotenv

# Load environment for tests
load_dotenv()

# # Add src to path (backup to pytest.ini configuration)
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root / "src"))

# Directorio donde está este conftest.py (tests o subcarpeta)
THIS_FILE = Path(__file__).resolve()
CURRENT_DIR = THIS_FILE.parent

# Buscamos hacia arriba un directorio que tenga "src"
for parent in [CURRENT_DIR, *CURRENT_DIR.parents]:
    candidate = parent / "src"
    
    if candidate.is_dir():
        print('Añadiendo raiz al sys.path: ' + str(parent))
        sys.path.insert(0, str(parent))
        break
else:
    # Si llegamos aquí, es que no hemos encontrado src
    raise RuntimeError("No se ha encontrado el directorio 'src' para añadirlo al sys.path")




@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def redis_url():
    """Redis URL fixture."""
    return os.getenv('REDIS_URL', 'redis://localhost:6379/0')


@pytest.fixture
def db_url():
    """Database URL fixture."""
    return os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost/trading_test')


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock = MagicMock()
    mock.ping.return_value = True
    mock.from_url.return_value = mock
    mock.pubsub.return_value = MagicMock()
    return mock


@pytest.fixture
def mock_message_bus(mock_redis_client, monkeypatch):
    """Mock MessageBus for testing."""
    from agents.messaging import MessageBus
    
    # Mock redis module
    monkeypatch.setattr('agents.messaging.redis', mock_redis_client)
    
    bus = MessageBus("redis://localhost:6379/0")
    return bus


@pytest.fixture
def sample_trading_signal():
    """Sample TradingSignal for testing."""
    from agents.schemas import TradingSignal, Direction
    
    return TradingSignal(
        from_agent="technical_analyst",
        symbol="SAN.MC",
        direction=Direction.LONG,
        confidence=0.75,
        entry_price=4.50,
        stop_loss=4.30,
        take_profit=5.00,
        timeframe="1d",
        reasoning="RSI oversold + MACD bullish",
        indicators={"RSI": 28, "MACD_hist": 0.05}
    )


@pytest.fixture
def sample_risk_request(sample_trading_signal):
    """Sample RiskRequest for testing."""
    from agents.schemas import RiskRequest
    
    return RiskRequest(
        signal=sample_trading_signal,
        capital=100000.0,
        current_positions=[]
    )


@pytest.fixture
def sample_config():
    """Sample agent configuration."""
    return {
        "technical_analyst": {
            "symbols": ["SAN.MC", "ITX.MC", "IBE.MC"],
            "interval_seconds": 300,
            "confidence_threshold": 0.50
        },
        "risk_manager": {
            "base_risk_per_trade": 0.01,
            "kelly_fraction": 0.25
        },
        "orchestrator": {
            "decision_threshold": 0.65,
            "reduced_threshold": 0.50
        }
    }
