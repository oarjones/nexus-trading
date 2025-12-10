import pytest
import shutil
from pathlib import Path
from src.trading.paper.portfolio import PaperPortfolio, PaperPortfolioManager, Position

# Setup temporary directory for tests
TEST_DATA_DIR = Path("tests/data/paper_test")

@pytest.fixture
def clean_env():
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)

def test_portfolio_buy_sell():
    pf = PaperPortfolio(strategy_id="test_strat", initial_capital=10000.0)
    
    # Buy 10 SPY @ 400
    pf.execute_buy("SPY", 10, 400.0)
    
    assert pf.cash == 6000.0
    assert "SPY" in pf.positions
    assert pf.positions["SPY"].quantity == 10
    assert pf.positions["SPY"].avg_price == 400.0
    
    # Buy 10 more @ 420
    pf.execute_buy("SPY", 10, 420.0)
    
    # Avg price should be 410
    assert pf.positions["SPY"].avg_price == 410.0
    assert pf.positions["SPY"].quantity == 20
    assert pf.cash == 1800.0
    
    # Sell 5 @ 430
    pnl = pf.execute_sell("SPY", 5, 430.0)
    
    # PnL = (430 - 410) * 5 = 100
    assert pnl == 100.0
    assert pf.positions["SPY"].quantity == 15
    assert pf.cash == 1800.0 + (5 * 430.0) # 1800 + 2150 = 3950

def test_persistence(clean_env):
    # Setup Manager with custom path
    config_path = TEST_DATA_DIR / "config.yaml" 
    # Mock config file not needed if we manually set persistence path or rely on defaults + mocking?
    # Actually Manager loads from file. We can instantiate and overwrite attributes or create a dummy config.
    
    manager = PaperPortfolioManager("non_existent_config.yaml")
    manager.persistence_path = TEST_DATA_DIR / "portfolios.json"
    
    # Add a portfolio manually
    pf = PaperPortfolio("persist_test", 1000.0)
    pf.execute_buy("AAPL", 1, 150.0)
    manager.portfolios["persist_test"] = pf
    
    # Save
    manager.save_state()
    
    # Verify file exists
    assert manager.persistence_path.exists()
    
    # Create new manager and load
    manager2 = PaperPortfolioManager("non_existent_config.yaml")
    manager2.persistence_path = TEST_DATA_DIR / "portfolios.json"
    manager2.load_state()
    
    assert "persist_test" in manager2.portfolios
    pf2 = manager2.portfolios["persist_test"]
    assert pf2.cash == 850.0
    assert "AAPL" in pf2.positions
    assert pf2.positions["AAPL"].quantity == 1
