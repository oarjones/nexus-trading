from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import asdict
from datetime import datetime
from .portfolio import PaperPortfolioManager, Position

# We need to import the standard interface objects or define them if they don't exist yet
# `src.agents.llm.interfaces` has `PortfolioSummary`, `PortfolioPosition`.
# Let's import them to return standard objects.
from src.agents.llm.interfaces import PortfolioSummary, PortfolioPosition

class PortfolioProvider(ABC):
    """Abstract interface for accessing portfolio data (Real or Paper)."""
    
    @abstractmethod
    async def get_portfolio_summary(self) -> PortfolioSummary:
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[PortfolioPosition]:
        pass

class PaperPortfolioProvider(PortfolioProvider):
    """Provider that wraps PaperPortfolioManager."""
    
    def __init__(self, manager: PaperPortfolioManager, strategy_id: str):
        self.manager = manager
        self.strategy_id = strategy_id
        
    def _get_portfolio(self):
        pf = self.manager.get_portfolio(self.strategy_id)
        if not pf:
            raise ValueError(f"Portfolio {self.strategy_id} not found in manager")
        return pf
        
    async def get_portfolio_summary(self) -> PortfolioSummary:
        pf = self._get_portfolio()
        
        # Calculate totals
        positions = pf.positions.values()
        invested_value = sum(p.market_value for p in positions)
        total_value = pf.cash + invested_value
        
        # Calculate PnL (Total)
        # Assuming initial capital is static from config/init
        total_pnl = total_value - pf.initial_capital
        total_pnl_pct = (total_pnl / pf.initial_capital) * 100 if pf.initial_capital > 0 else 0.0
        
        # Daily PnL is harder to track without history, 
        # for MVP we might just use Total PnL or 0 for now if not tracked.
        daily_pnl = 0.0 # TODO: Implement daily PnL tracking
        daily_pnl_pct = 0.0
        
        # Convert positions to interface objects
        interface_positions = []
        for p in positions:
            interface_positions.append(PortfolioPosition(
                symbol=p.symbol,
                quantity=p.quantity,
                avg_entry_price=p.avg_price,
                current_price=p.current_price,
                unrealized_pnl=p.unrealized_pnl,
                unrealized_pnl_pct=p.unrealized_pnl_pct * 100, # Interface usually expects percentage
                holding_days=(datetime.now() - p.entry_time).days
            ))
            
        return PortfolioSummary(
            total_value=total_value,
            cash_available=pf.cash,
            invested_value=invested_value,
            positions=tuple(interface_positions),
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct
        )
        
    async def get_positions(self) -> List[PortfolioPosition]:
        summary = await self.get_portfolio_summary()
        return list(summary.positions)
