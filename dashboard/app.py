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
    
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "status": status,
            "universe": universe,
            "costs": costs,
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard.app:app", host="0.0.0.0", port=8000, reload=True)
