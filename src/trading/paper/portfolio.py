import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
import yaml

logger = logging.getLogger(__name__)

@dataclass
class Position:
    symbol: str
    quantity: int
    avg_price: float
    entry_time: datetime
    current_price: float = 0.0
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
        
    @property
    def unrealized_pnl(self) -> float:
        if self.avg_price == 0:
            return 0.0
        return (self.current_price - self.avg_price) * self.quantity
        
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.avg_price == 0:
            return 0.0
        return (self.current_price - self.avg_price) / self.avg_price

    def to_dict(self) -> dict:
        data = asdict(self)
        if self.entry_time:
            data['entry_time'] = self.entry_time.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        if 'entry_time' in data and isinstance(data['entry_time'], str):
            data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        return cls(**data)


class PaperPortfolio:
    """Represents a single paper trading portfolio."""
    
    def __init__(self, strategy_id: str, initial_capital: float = 25000.0, currency: str = "EUR"):
        self.strategy_id = strategy_id
        self.initial_capital = initial_capital
        self.currency = currency
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades_count = 0
        
    def can_buy(self, symbol: str, quantity: int, price: float) -> bool:
        cost = quantity * price
        # TODO: Add commission check logic if needed here, generally handled in execution
        return self.cash >= cost

    def execute_buy(self, symbol: str, quantity: int, price: float, 
                    stop_loss: float = None, take_profit: float = None) -> None:
        cost = quantity * price
        if not self.can_buy(symbol, quantity, price):
            raise ValueError(f"Insufficient funds to buy {quantity} {symbol} at {price}")
            
        self.cash -= cost
        
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            new_avg = ((pos.avg_price * pos.quantity) + (price * quantity)) / total_qty
            pos.quantity = total_qty
            pos.avg_price = new_avg
            pos.current_price = price # Update current price to execution price
        else:
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_price=price,
                entry_time=datetime.now(),
                current_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
        self.trades_count += 1
            
    def execute_sell(self, symbol: str, quantity: int, price: float) -> float:
        if symbol not in self.positions:
            raise ValueError(f"No position in {symbol}")
            
        pos = self.positions[symbol]
        if quantity > pos.quantity:
            quantity = pos.quantity # Sell all if request > held
            
        proceeds = quantity * price
        cost_basis = quantity * pos.avg_price
        pnl = proceeds - cost_basis
        
        self.cash += proceeds
        pos.quantity -= quantity
        
        if pos.quantity == 0:
            del self.positions[symbol]
            
        self.trades_count += 1
        return pnl
        
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices of held positions."""
        for symbol, price in prices.items():
            if symbol in self.positions:
                self.positions[symbol].current_price = price

    @property
    def total_value(self) -> float:
        pos_val = sum(p.market_value for p in self.positions.values())
        return self.cash + pos_val

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "initial_capital": self.initial_capital,
            "currency": self.currency,
            "cash": self.cash,
            "positions": {s: p.to_dict() for s, p in self.positions.items()},
            "trades_count": self.trades_count
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PaperPortfolio':
        pf = cls(
            strategy_id=data["strategy_id"], 
            initial_capital=data.get("initial_capital", 25000.0),
            currency=data.get("currency", "EUR")
        )
        pf.cash = data["cash"]
        pf.trades_count = data.get("trades_count", 0)
        if "positions" in data:
            for s, p_data in data["positions"].items():
                pf.positions[s] = Position.from_dict(p_data)
        return pf


class PaperPortfolioManager:
    """Manages multiple paper portfolios with persistence."""
    
    def __init__(self, config_path: str = "config/paper_trading.yaml"):
        self.config_path = Path(config_path)
        self.portfolios: Dict[str, PaperPortfolio] = {}
        self.config = {}
        self.persistence_path = Path("data/paper_portfolios.json")
        
        self._load_config()
        self._initialize_portfolios()
        self.load_state() 

    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
                
        # Update persistence path from config
        if "persistence" in self.config:
            p_path = self.config["persistence"].get("storage_path")
            if p_path:
                self.persistence_path = Path(p_path)

    def _initialize_portfolios(self):
        """Initialize portfolios from config if they don't exist."""
        p_groups = self.config.get("portfolios", {})
        for strategy_id, settings in p_groups.items():
            if strategy_id not in self.portfolios:
                self.portfolios[strategy_id] = PaperPortfolio(
                    strategy_id=strategy_id,
                    initial_capital=settings.get("initial_capital", 25000.0),
                    currency=settings.get("currency", "EUR")
                )

    def get_portfolio(self, strategy_id: str) -> Optional[PaperPortfolio]:
        return self.portfolios.get(strategy_id)

    def save_state(self):
        """Save all portfolios to disk."""
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = {sid: p.to_dict() for sid, p in self.portfolios.items()}
            with open(self.persistence_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Portfolios saved to {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to save portfolios: {e}")

    def load_state(self):
        """Load portfolios from disk."""
        if not self.persistence_path.exists():
            logger.info("No saved portfolio state found, starting fresh.")
            return

        try:
            with open(self.persistence_path, 'r') as f:
                data = json.load(f)
            
            for sid, p_data in data.items():
                if sid in self.portfolios:
                    # Update existing initialized portfolio
                    # Reuse from_dict logic but map to existing instance to preserve config? 
                    # Simpler to replace or update fields.
                    saved_pf = PaperPortfolio.from_dict(p_data)
                    # We trust saved state for cash/positions
                    self.portfolios[sid].cash = saved_pf.cash
                    self.portfolios[sid].positions = saved_pf.positions
                    self.portfolios[sid].trades_count = saved_pf.trades_count
                else:
                    # Load portfolio not in current config (maybe zombie)
                    # We load it anyway to avoid data loss
                    self.portfolios[sid] = PaperPortfolio.from_dict(p_data)
                    
            logger.info(f"Loaded {len(data)} portfolios from {self.persistence_path}")
        except Exception as e:
            logger.error(f"Failed to load portfolios: {e}")
