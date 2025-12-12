"""
Dashboard Application Entry Point.

FastAPI app serving the monitoring dashboard.
"""

import sys
from pathlib import Path

# Add project root to python path to allow importing dashboard modules
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from dashboard.services.data_service import get_data_service
from dashboard.services.log_service import get_log_service

app = FastAPI(title="Nexus Trading Dashboard")

# Paths
BASE_DIR = Path(__file__).resolve().parent

# Static & Templates
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Services
data_service = get_data_service()
log_service = get_log_service()


@app.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Render main dashboard page."""
    status = data_service.get_system_status()
    universe = data_service.get_active_universe()
    costs = data_service.get_todays_costs()
    pf_data = data_service.get_paper_portfolio()
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status,
            "universe": universe,
            "costs": costs,
            "portfolios": pf_data.get("portfolios", {})
        }
    )


@app.get("/components/status")
async def get_status_component(request: Request):
    """HTMX component: System Status."""
    status = data_service.get_system_status()
    return templates.TemplateResponse(
        "components/status_card.html",
        {"request": request, "status": status}
    )

@app.get("/components/universe")
async def get_universe_component(request: Request):
    """HTMX component: Active Universe."""
    universe = data_service.get_active_universe()
    return templates.TemplateResponse(
        "components/universe_card.html",
        {"request": request, "universe": universe}
    )

@app.get("/components/signals")
async def get_signals_component(request: Request):
    """HTMX component: Recent Signals."""
    data = data_service.get_recent_signals()
    signals = data.get("signals", [])
    return templates.TemplateResponse(
        "components/signals_list.html",
        {"request": request, "signals": signals}
    )


@app.get("/components/logs")
async def get_logs_component(request: Request):
    """HTMX component: Logs."""
    logs = log_service.get_recent_logs(limit=50)
    # Reverse to show newest first if desired, or keep chronological
    # Usually console logs read top-down (oldest first). We'll keep as is.
    return templates.TemplateResponse(
        "components/logs_panel.html",
        {"request": request, "logs": logs}
    )

# --- Dashboard 2.0 Endpoints ---

@app.get("/components/portfolio_summary")
async def get_portfolio_summary_component(request: Request):
    """HTMX component: Global Portfolio Summary."""
    pf_data = data_service.get_paper_portfolio()
    status = data_service.get_system_status()
    
    # Calculate global totals
    total_aum = 0.0
    total_cash = 0.0
    portfolios = pf_data.get("portfolios", {})
    
    for _, pf in portfolios.items():
        total_aum += pf.get("total_value", 0)
        total_cash += pf.get("cash", 0)
        
    return templates.TemplateResponse(
        "components/portfolio_summary.html",
        {
            "request": request,             
            "total_aum": total_aum,
            "total_cash": total_cash,
            "status": status,
            "strategies_count": len(portfolios)
        }
    )

@app.get("/components/strategy/{strategy_id}")
async def get_strategy_card_component(request: Request, strategy_id: str):
    """HTMX component: Individual Strategy Card."""
    details = data_service.get_strategy_details(strategy_id)
    if not details:
        return HTMLResponse(f"Strategy {strategy_id} not found", status_code=404)
        
    return templates.TemplateResponse(
        "components/strategy_card.html",
        {"request": request, "strategy": details}
    )

@app.get("/api/history/{strategy_id}")
async def get_strategy_history(strategy_id: str):
    """JSON API: Get history for charting."""
    return data_service.get_portfolio_history(strategy_id, days=7)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True)
