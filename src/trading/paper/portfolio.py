
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime, timezone
import yaml

from src.shared.infrastructure.database import get_db, PortfolioModel, PositionModel, PortfolioHistoryModel

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
                entry_time=datetime.now(timezone.utc),
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
    """Manages multiple paper portfolios with persistence (Postgres)."""
    
    def __init__(self, config_path: str = "config/paper_trading.yaml"):
        self.config_path = Path(config_path)
        self.portfolios: Dict[str, PaperPortfolio] = {}
        self.config = {}
        
        # Database connection
        try:
            self.db = get_db()
            logger.info("PaperPortfolioManager connected to Database")
        except Exception as e:
            logger.error(f"PaperPortfolioManager failed to connect to DB: {e}")
            self.db = None
        
        self._load_config()
        self._initialize_portfolios()
        self.load_state() 

    def _load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}

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
        """
        Save all portfolios to Postgres.
        Also records history snapshot for charting.
        """
        if not self.db:
            return

        session = self.db.get_session()
        try:
            for strategy_id, pf in self.portfolios.items():
                # 1. Upsert Portfolio (Current State)
                db_pf = session.query(PortfolioModel).filter_by(strategy_id=strategy_id).first()
                if not db_pf:
                    db_pf = PortfolioModel(strategy_id=strategy_id)
                    session.add(db_pf)
                
                db_pf.currency = pf.currency
                db_pf.initial_capital = pf.initial_capital
                db_pf.cash = pf.cash
                db_pf.trades_count = pf.trades_count
                db_pf.total_value = pf.total_value
                # updated_at handled by DB/Model default
                
                # 2. Update Positions
                session.query(PositionModel).filter_by(strategy_id=strategy_id).delete()
                
                for symbol, pos in pf.positions.items():
                    db_pos = PositionModel(
                        strategy_id=strategy_id,
                        symbol=pos.symbol,
                        quantity=pos.quantity,
                        avg_price=pos.avg_price,
                        current_price=pos.current_price,
                        entry_time=pos.entry_time,
                        stop_loss=pos.stop_loss,
                        take_profit=pos.take_profit
                    )
                    session.add(db_pos)

                # 3. Record History Snapshot (for Equity Curve)
                # We record a snapshot every time we save state (e.g. daily or minutely)
                # Ideally this is throttled, but for now we assume save_state is called reasonably.
                history_entry = PortfolioHistoryModel(
                    strategy_id=strategy_id,
                    total_value=pf.total_value,
                    cash=pf.cash
                    # timestamp defaults to now
                )
                session.add(history_entry)
            
            session.commit()
            logger.info("Portfolios state and history saved to Postgres")
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to save portfolios/history to DB: {e}")
        finally:
            session.close()


    def load_state(self):
        """Load portfolios from Postgres."""
        if not self.db:
            return

        session = self.db.get_session()
        try:
            db_portfolios = session.query(PortfolioModel).all()
            if not db_portfolios:
                logger.info("No saved portfolio state in DB, using initialized defaults.")
                return

            for db_pf in db_portfolios:
                sid = db_pf.strategy_id
                
                # Get existing obj provided by config or create new if found in DB only
                if sid in self.portfolios:
                    pf = self.portfolios[sid]
                else:
                    pf = PaperPortfolio(sid, db_pf.initial_capital, db_pf.currency)
                    self.portfolios[sid] = pf
                
                # Update state
                pf.cash = db_pf.cash
                pf.trades_count = db_pf.trades_count
                
                # Load Positions
                pf.positions = {}
                for db_pos in db_pf.positions:
                    pf.positions[db_pos.symbol] = Position(
                        symbol=db_pos.symbol,
                        quantity=db_pos.quantity,
                        avg_price=db_pos.avg_price,
                        entry_time=db_pos.entry_time.replace(tzinfo=timezone.utc) if db_pos.entry_time.tzinfo is None else db_pos.entry_time,
                        current_price=db_pos.current_price,
                        stop_loss=db_pos.stop_loss,
                        take_profit=db_pos.take_profit
                    )
            
            logger.info(f"Loaded {len(db_portfolios)} portfolios from DB")
        except Exception as e:
            logger.error(f"Failed to load portfolios from DB: {e}")
        finally:
            session.close()

