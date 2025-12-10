import pandas as pd
from pathlib import Path
from datetime import date, datetime
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class CSVReporter:
    """Clase para reportar métricas diarias en CSV."""
    
    def __init__(self, output_dir: str = "reports/"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def generate_daily_report(self, 
                                    portfolios: Dict[str, Any],  # Strategy ID -> Portfolio
                                    report_date: date = None):
        """Generar reportes del día."""
        report_date = report_date or date.today()
        day_dir = self.output_dir / str(report_date)
        day_dir.mkdir(exist_ok=True)
        
        logger.info(f"Generando reportes CSV en {day_dir}")
        
        try:
            # 1. Resumen de Portfolio
            portfolio_data = []
            for strat_id, portfolio in portfolios.items():
                # Asumimos que portfolio es PaperPortfolio (tiene to_dict o atributos)
                val = portfolio.get_total_value({}) # Precio actual mockeado o no necesario si saved
                portfolio_data.append({
                    "strategy_id": strat_id,
                    "total_value": val,
                    "cash": portfolio.cash,
                    "positions_count": len(portfolio.positions),
                    # "pnl_daily": portfolio.daily_pnl # TODO: Implementar tracking
                })
            
            if portfolio_data:
                pd.DataFrame(portfolio_data).to_csv(day_dir / "portfolio_summary.csv", index=False)
            
            # 2. Posiciones actuales
            positions_data = []
            for strat_id, portfolio in portfolios.items():
                for sym, pos in portfolio.positions.items():
                    positions_data.append({
                        "strategy_id": strat_id,
                        "symbol": sym,
                        "quantity": pos.quantity,
                        "avg_price": pos.avg_price,
                        "entry_time": pos.entry_time
                    })
            
            if positions_data:
                pd.DataFrame(positions_data).to_csv(day_dir / "positions.csv", index=False)

            # 3. TODO: Trades History (Necesitamos que PortfolioManager o OrderSimulator exponga historia)
            # trades_data = ...
            # pd.DataFrame(trades_data).to_csv(day_dir / "trades.csv", index=False)
            
            logger.info("Reportes generados correctamente.")
            return day_dir
            
        except Exception as e:
            logger.error(f"Error generando reporte CSV: {e}", exc_info=True)
            return None
