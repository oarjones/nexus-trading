
import json
import logging
from pathlib import Path
from datetime import datetime, date, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from src.shared.infrastructure.redis_client import get_redis_client
from src.shared.infrastructure.database import get_db, PortfolioModel, PositionModel, PortfolioHistoryModel

logger = logging.getLogger(__name__)

class DataService:
    """
    Service to read Strategy Lab state from Redis and Postgres.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.costs_dir = self.data_dir / "costs"
        self.signals_file = self.data_dir / "signals_cache.json"
        
        # Connections
        try:
            self.redis = get_redis_client()
        except Exception as e:
            logger.error(f"DataService failed to connect to Redis: {e}")
            self.redis = None
            
        try:
            self.db = get_db()
        except Exception as e:
            logger.error(f"DataService failed to connect to DB: {e}")
            self.db = None

    def get_system_status(self) -> Dict[str, Any]:
        """Get current system heartbeat from Redis."""
        if not self.redis:
            return {"is_running": False, "status": "Dashboard Error (No Redis)"}
            
        try:
            data_json = self.redis.get("nexus:system:status")
            if not data_json:
                return {
                    "is_running": False, 
                    "status": "Offline (No Heartbeat)",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
            data = json.loads(data_json)
            # If key exists, system is running (TTL ensures it dies if writer stops)
            return data
        except Exception as e:
            logger.error(f"Error reading status from Redis: {e}")
            return {"is_running": False, "error": str(e)}

    def get_active_universe(self) -> Dict[str, Any]:
        """Get active universe from Redis."""
        if not self.redis:
            return {"active_symbols": [], "status": "Error (No Redis)"}
            
        try:
            data_json = self.redis.get("nexus:universe:active")
            if not data_json:
                # Fallback to file for safety during migration
                f = self.data_dir / "active_universe.json"
                if f.exists():
                     with open(f, 'r') as file:
                        return json.load(file)
                return {"active_symbols": [], "status": "No Data"}
                
            return json.loads(data_json)
        except Exception as e:
            logger.error(f"Error reading universe from Redis: {e}")
            return {}

    def get_recent_signals(self) -> Dict[str, Any]:
        """Get most recent generated signals (File for now, TODO: Migrate to DB)."""
        if not self.signals_file.exists():
            return {"signals": []}
            
        try:
            with open(self.signals_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading signals: {e}")
            return {"signals": []}

    def get_paper_portfolio(self) -> Dict[str, Any]:
        """Get paper trading portfolio from Postgres."""
        if not self.db:
            return {"portfolios": {}, "error": "No DB"}
            
        session: Session = self.db.get_session()
        portfolios = {}
        
        try:
            db_portfolios = session.query(PortfolioModel).all()
            for p in db_portfolios:
                # Convert to dict format expected by template
                pos_dict = {}
                for pos in p.positions:
                    pos_dict[pos.symbol] = {
                        "symbol": pos.symbol,
                        "quantity": pos.quantity,
                        "avg_price": pos.avg_price,
                        "current_price": pos.current_price,
                        "market_value": pos.quantity * pos.current_price,
                        "unrealized_pnl": (pos.current_price - pos.avg_price) * pos.quantity if pos.avg_price else 0,
                        "unrealized_pnl_pct": ((pos.current_price - pos.avg_price) / pos.avg_price) if pos.avg_price else 0,
                        "entry_time": pos.entry_time.isoformat() if pos.entry_time else None
                    }
                
                portfolios[p.strategy_id] = {
                    "strategy_id": p.strategy_id,
                    "cash": p.cash,
                    "total_value": p.total_value,
                    "currency": p.currency,
                    "trades_count": p.trades_count,
                    "positions": pos_dict
                }
            
            return {"portfolios": portfolios}
        except Exception as e:
            logger.error(f"Error reading portfolio from DB: {e}")
            return {"portfolios": {}}
        finally:
            session.close()

    def get_todays_costs(self) -> Dict[str, Any]:
        """Get AI cost tracking for today (File based for now)."""
        today = date.today().isoformat()
        cost_file = self.costs_dir / f"{today}.json"
        
        if not cost_file.exists():
            return {"total_cost_usd": 0.0, "total_tokens": 0, "total_searches": 0}
            
        try:
            with open(cost_file, 'r') as f:
                data = json.load(f)
                return data.get("summary", {})

        except Exception as e:
            logger.error(f"Error reading costs: {e}")
            return {}

    def get_portfolio_history(self, strategy_id: str = None, days: int = 7) -> Dict[str, Any]:
        """Get portfolio value history for charting."""
        if not self.db:
            return {"history": []}
            
        session: Session = self.db.get_session()
        try:
            query = session.query(PortfolioHistoryModel).order_by(PortfolioHistoryModel.timestamp.asc())
            
            if strategy_id:
                query = query.filter(PortfolioHistoryModel.strategy_id == strategy_id)
            
            # Limit records based on time window (simplified)
            # In production we might downsample points here if too many
            history = query.all()
            
            result = []
            for h in history:
                result.append({
                    "timestamp": h.timestamp.isoformat(),
                    "total_value": h.total_value,
                    "cash": h.cash
                })
                
            return {"history": result}
        except Exception as e:
            logger.error(f"Error reading portfolio history: {e}")
            return {"history": []}
        finally:
            session.close()



    def get_strategy_details(self, strategy_id: str) -> Dict[str, Any]:
        """Get detailed view of a strategy."""
        portfolios = self.get_paper_portfolio().get("portfolios", {})
        pf = portfolios.get(strategy_id)
        
        if not pf:
            return None
            
        # Enrich with status
        status = self.get_system_status()
        regime = status.get("regime", {}).get("current", "UNKNOWN")
        
        # Calculate extra metrics
        total_pnl = 0.0
        invested_value = 0.0
        
        start_cap = pf.get("initial_capital", 25000)
        curr_val = pf.get("total_value", 25000)
        total_ret_pct = ((curr_val - start_cap) / start_cap) * 100
        
        positions = []
        if pf.get("positions"):
            for sym, pos in pf["positions"].items():
                pnl = pos.get("unrealized_pnl", 0)
                val = pos.get("market_value", 0)
                total_pnl += pnl
                invested_value += val
                positions.append(pos)
                
        # Sort positions by value desc
        positions.sort(key=lambda x: x.get("market_value", 0), reverse=True)
        
        return {
            "id": strategy_id,
            "regime": regime,
            "metrics": {
                "total_return_pct": total_ret_pct,
                "daily_pnl": 0.0, # TODO: Track daily specifically
                "net_liquidation": curr_val,
                "cash_balance": pf.get("cash", 0),
                "invested_pct": (invested_value / curr_val * 100) if curr_val > 0 else 0
            },
            "positions": positions
        }

# Singleton
_data_service = None

def get_data_service() -> DataService:
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service

