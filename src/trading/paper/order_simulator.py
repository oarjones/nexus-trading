import logging
from typing import Optional, Dict

from src.strategies.interfaces import Signal
from .portfolio import PaperPortfolioManager

logger = logging.getLogger(__name__)

class OrderSimulator:
    """Simulates order execution for paper trading."""
    
    def __init__(self, portfolio_manager: PaperPortfolioManager, market_data_client=None):
        self.portfolios = portfolio_manager
        self.market_data = market_data_client # Mapped to MCP or local provider
        
    async def process_signal(self, signal: Signal) -> Optional[dict]:
        """
        Process a signal and execute a paper trade.
        
        Args:
            signal: Trading signal
            
        Returns:
            Trade record dict if executed, None otherwise
        """
        portfolio = self.portfolios.get_portfolio(signal.strategy_id)
        if not portfolio:
            logger.error(f"No portfolio found for strategy {signal.strategy_id}")
            return None
            
        # Get current price
        # If market_data_client is None, we might look at signal.entry_price or fail
        price = signal.entry_price
        if not price and self.market_data:
            # TODO: Fetch real price
            pass
            
        if not price:
            logger.warning(f"No price available for {signal.symbol}, skipping")
            return None
            
        # Execute
        try:
            if signal.direction == "LONG":
                # Calculate quantity
                # simple logic: use size_suggestion or default 5%
                capital = portfolio.total_value
                size_pct = signal.size_suggestion if signal.size_suggestion else 0.05
                target_amount = capital * size_pct
                quantity = int(target_amount / price)
                
                if quantity > 0:
                    portfolio.execute_buy(
                        signal.symbol, quantity, price, 
                        stop_loss=signal.stop_loss, 
                        take_profit=signal.take_profit
                    )
                    logger.info(f"PAPER BUY: {quantity} {signal.symbol} @ {price}")
                    self.portfolios.save_state() # Persist immediately
                    return {
                        "symbol": signal.symbol,
                        "action": "BUY",
                        "quantity": quantity,
                        "price": price,
                        "strategy_id": signal.strategy_id
                    }
                    
            elif signal.direction == "CLOSE":
                # Sell all or specific amount?
                # "CLOSE" usually means close entire position
                if signal.symbol in portfolio.positions:
                    pos = portfolio.positions[signal.symbol]
                    qty_to_sell = pos.quantity
                    pnl = portfolio.execute_sell(signal.symbol, qty_to_sell, price)
                    
                    logger.info(f"PAPER SELL: {qty_to_sell} {signal.symbol} @ {price} (PnL: {pnl:.2f})")
                    self.portfolios.save_state()
                    return {
                        "symbol": signal.symbol,
                        "action": "SELL",
                        "quantity": qty_to_sell,
                        "price": price,
                        "pnl": pnl,
                        "strategy_id": signal.strategy_id
                    }
                    
        except Exception as e:
            logger.error(f"Error executing paper trade: {e}")
            return None
            
        return None
