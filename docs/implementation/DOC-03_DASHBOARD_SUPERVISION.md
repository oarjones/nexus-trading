# DOC-03: Dashboard de Supervisión

> **Prioridad**: 🟡 MEDIA-ALTA  
> **Esfuerzo estimado**: 8-10 horas  
> **Dependencias**: DOC-02 (Cost Tracking) para mostrar costes

## 1. Contexto y Objetivo

### Problema Actual
La única forma de monitorizar el sistema es:
- Revisar logs en consola o archivo
- Abrir CSVs generados en `reports/`
- No hay visibilidad en tiempo real
- Difícil detectar problemas rápidamente

### Objetivo
Crear un **dashboard web ligero** que permita:
1. Ver estado del sistema en tiempo real
2. Monitorizar las dos cuentas (HMM Rules, AI Agent)
3. Ver señales generadas y órdenes ejecutadas
4. Detectar errores rápidamente
5. Visualizar costes del AI Agent
6. Todo sin necesidad de Grafana ni infraestructura compleja

### Stack Tecnológico
- **Backend**: FastAPI (async, ligero, fácil)
- **Frontend**: HTMX + TailwindCSS (sin build step, sin JS complejo)
- **Actualizaciones**: Server-Sent Events (SSE) para tiempo real
- **Templates**: Jinja2

---

## 2. Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DEL DASHBOARD                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Browser    │────▶│   FastAPI    │────▶│StrategyLab   │   │
│  │  HTMX+CSS    │◀────│   Server     │◀────│  (datos)     │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                    │                    │            │
│         │ SSE               │                    │            │
│         │ (tiempo real)      │                    │            │
│         ▼                    ▼                    ▼            │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                     DATOS CONSULTADOS                     │ │
│  ├──────────────────────────────────────────────────────────┤ │
│  │ • PaperPortfolioManager → Estado de cuentas              │ │
│  │ • UniverseManager → Símbolos activos                     │ │
│  │ • StrategyScheduler → Próximas ejecuciones              │ │
│  │ • CostTracker → Costes del AI Agent                      │ │
│  │ • Log files → Últimos logs/errores                       │ │
│  │ • data/paper_portfolios.json → Posiciones               │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Estructura de Archivos

```
nexus-trading/
├── dashboard/                    # NUEVO directorio
│   ├── __init__.py
│   ├── app.py                   # FastAPI application
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py              # Rutas principales
│   │   ├── api.py               # API endpoints JSON
│   │   └── sse.py               # Server-Sent Events
│   ├── services/
│   │   ├── __init__.py
│   │   ├── data_service.py      # Acceso a datos del sistema
│   │   └── log_service.py       # Lectura de logs
│   ├── templates/
│   │   ├── base.html            # Layout base
│   │   ├── index.html           # Dashboard principal
│   │   ├── partials/
│   │   │   ├── status_card.html
│   │   │   ├── accounts_card.html
│   │   │   ├── signals_table.html
│   │   │   ├── errors_list.html
│   │   │   └── costs_card.html
│   │   └── components/
│   │       └── navbar.html
│   └── static/
│       └── css/
│           └── custom.css       # Estilos adicionales
├── scripts/
│   ├── run_strategy_lab.py
│   └── run_dashboard.py         # NUEVO - Entry point del dashboard
```

---

## 3. Implementación

### 3.1. Dependencias

Añadir a `requirements.txt`:

```
# Dashboard
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
jinja2>=3.1.0
sse-starlette>=1.8.0
python-multipart>=0.0.6
aiofiles>=23.0.0
```

---

### 3.2. Servicio de Datos

**Archivo**: `dashboard/services/data_service.py`

```python
"""
Data Service - Acceso centralizado a datos del sistema.

Proporciona métodos para obtener estado actual de:
- Portfolios (Paper Trading)
- Universo activo
- Señales recientes
- Scheduler status
- Costes del AI Agent
"""

import json
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Rutas base (configurables)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
COSTS_DIR = DATA_DIR / "costs"
PORTFOLIOS_FILE = DATA_DIR / "paper_portfolios.json"


@dataclass
class SystemStatus:
    """Estado general del sistema."""
    is_running: bool = False
    regime: str = "UNKNOWN"
    regime_confidence: float = 0.0
    last_execution: Optional[str] = None
    next_execution: Optional[str] = None
    active_symbols_count: int = 0
    uptime_seconds: int = 0


@dataclass
class AccountSummary:
    """Resumen de una cuenta de trading."""
    strategy_id: str
    total_value: float
    cash: float
    invested: float
    pnl_total: float
    pnl_total_pct: float
    pnl_today: float
    pnl_today_pct: float
    positions_count: int
    last_trade: Optional[str] = None


@dataclass
class Position:
    """Posición abierta."""
    symbol: str
    quantity: int
    avg_price: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    entry_date: str
    days_held: int
    strategy_id: str


@dataclass
class SignalRecord:
    """Registro de señal generada."""
    timestamp: str
    strategy_id: str
    symbol: str
    direction: str
    confidence: float
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: str
    status: str  # "generated", "executed", "rejected"


@dataclass
class ErrorRecord:
    """Registro de error."""
    timestamp: str
    level: str
    source: str
    message: str


@dataclass 
class CostSummary:
    """Resumen de costes del AI Agent."""
    today_cost: float
    today_tokens: int
    today_searches: int
    today_decisions: int
    month_cost: float
    month_decisions: int
    avg_cost_per_decision: float


class DataService:
    """
    Servicio centralizado de acceso a datos.
    
    Uso:
        service = DataService()
        status = service.get_system_status()
        accounts = service.get_accounts_summary()
    """
    
    def __init__(
        self,
        portfolio_manager=None,
        universe_manager=None,
        scheduler=None,
        cost_tracker=None,
    ):
        """
        Args:
            portfolio_manager: Instancia de PaperPortfolioManager (opcional)
            universe_manager: Instancia de UniverseManager (opcional)
            scheduler: Instancia de StrategyScheduler (opcional)
            cost_tracker: Instancia de CostTracker (opcional)
            
        Si no se pasan instancias, lee directamente de archivos.
        """
        self.portfolio_manager = portfolio_manager
        self.universe_manager = universe_manager
        self.scheduler = scheduler
        self.cost_tracker = cost_tracker
        
        # Cache interno
        self._signals_cache: List[SignalRecord] = []
        self._max_signals_cache = 100
        
        # Estado del sistema (actualizado externamente)
        self._system_start_time: datetime = datetime.now(timezone.utc)
        self._last_regime: str = "UNKNOWN"
        self._last_regime_confidence: float = 0.0
        self._is_running: bool = False
    
    def set_running(self, is_running: bool):
        """Actualizar estado de ejecución."""
        self._is_running = is_running
    
    def update_regime(self, regime: str, confidence: float):
        """Actualizar régimen actual."""
        self._last_regime = regime
        self._last_regime_confidence = confidence
    
    def add_signal(self, signal: SignalRecord):
        """Añadir señal al cache."""
        self._signals_cache.insert(0, signal)
        if len(self._signals_cache) > self._max_signals_cache:
            self._signals_cache = self._signals_cache[:self._max_signals_cache]
    
    # =========================================================================
    # System Status
    # =========================================================================
    
    def get_system_status(self) -> SystemStatus:
        """Obtener estado general del sistema."""
        uptime = (datetime.now(timezone.utc) - self._system_start_time).seconds
        
        # Símbolos activos
        active_symbols = 0
        if self.universe_manager:
            active_symbols = len(self.universe_manager.active_symbols)
        
        # Próxima ejecución del scheduler
        next_exec = None
        if self.scheduler and hasattr(self.scheduler, 'scheduler'):
            jobs = self.scheduler.scheduler.get_jobs()
            if jobs:
                next_run = min(job.next_run_time for job in jobs if job.next_run_time)
                next_exec = next_run.isoformat() if next_run else None
        
        return SystemStatus(
            is_running=self._is_running,
            regime=self._last_regime,
            regime_confidence=self._last_regime_confidence,
            last_execution=None,  # TODO: trackear última ejecución
            next_execution=next_exec,
            active_symbols_count=active_symbols,
            uptime_seconds=uptime,
        )
    
    # =========================================================================
    # Accounts & Positions
    # =========================================================================
    
    def get_accounts_summary(self) -> List[AccountSummary]:
        """Obtener resumen de todas las cuentas."""
        accounts = []
        
        # Intentar desde portfolio_manager en memoria
        if self.portfolio_manager:
            for strategy_id, portfolio in self.portfolio_manager.portfolios.items():
                accounts.append(self._portfolio_to_summary(strategy_id, portfolio))
            return accounts
        
        # Fallback: leer de archivo
        if PORTFOLIOS_FILE.exists():
            try:
                with open(PORTFOLIOS_FILE, 'r') as f:
                    data = json.load(f)
                
                for strategy_id, portfolio_data in data.get("portfolios", {}).items():
                    accounts.append(self._dict_to_account_summary(strategy_id, portfolio_data))
                    
            except Exception as e:
                logger.error(f"Error reading portfolios file: {e}")
        
        return accounts
    
    def _portfolio_to_summary(self, strategy_id: str, portfolio) -> AccountSummary:
        """Convertir objeto Portfolio a AccountSummary."""
        # Calcular valores
        invested = sum(
            pos.quantity * pos.current_price 
            for pos in portfolio.positions.values()
        )
        total_value = portfolio.cash + invested
        
        # PnL (simplificado - necesitaría valor inicial)
        initial_capital = 25000.0  # TODO: obtener de config
        pnl_total = total_value - initial_capital
        pnl_total_pct = (pnl_total / initial_capital) * 100 if initial_capital > 0 else 0
        
        return AccountSummary(
            strategy_id=strategy_id,
            total_value=total_value,
            cash=portfolio.cash,
            invested=invested,
            pnl_total=pnl_total,
            pnl_total_pct=pnl_total_pct,
            pnl_today=0.0,  # TODO: calcular PnL del día
            pnl_today_pct=0.0,
            positions_count=len(portfolio.positions),
            last_trade=None,  # TODO: trackear último trade
        )
    
    def _dict_to_account_summary(self, strategy_id: str, data: dict) -> AccountSummary:
        """Convertir dict de JSON a AccountSummary."""
        positions = data.get("positions", {})
        cash = data.get("cash", 0)
        
        invested = sum(
            pos.get("quantity", 0) * pos.get("current_price", pos.get("avg_price", 0))
            for pos in positions.values()
        )
        total_value = cash + invested
        
        initial_capital = 25000.0
        pnl_total = total_value - initial_capital
        pnl_total_pct = (pnl_total / initial_capital) * 100 if initial_capital > 0 else 0
        
        return AccountSummary(
            strategy_id=strategy_id,
            total_value=total_value,
            cash=cash,
            invested=invested,
            pnl_total=pnl_total,
            pnl_total_pct=pnl_total_pct,
            pnl_today=0.0,
            pnl_today_pct=0.0,
            positions_count=len(positions),
        )
    
    def get_positions(self, strategy_id: str = None) -> List[Position]:
        """Obtener posiciones abiertas."""
        positions = []
        
        # Desde portfolio_manager
        if self.portfolio_manager:
            for sid, portfolio in self.portfolio_manager.portfolios.items():
                if strategy_id and sid != strategy_id:
                    continue
                    
                for symbol, pos in portfolio.positions.items():
                    positions.append(Position(
                        symbol=symbol,
                        quantity=pos.quantity,
                        avg_price=pos.avg_price,
                        current_price=pos.current_price,
                        market_value=pos.quantity * pos.current_price,
                        pnl=pos.unrealized_pnl,
                        pnl_pct=pos.unrealized_pnl_pct,
                        entry_date=pos.entry_date.isoformat() if pos.entry_date else "",
                        days_held=pos.days_held,
                        strategy_id=sid,
                    ))
            return positions
        
        # Fallback: leer de archivo
        if PORTFOLIOS_FILE.exists():
            try:
                with open(PORTFOLIOS_FILE, 'r') as f:
                    data = json.load(f)
                
                for sid, portfolio_data in data.get("portfolios", {}).items():
                    if strategy_id and sid != strategy_id:
                        continue
                        
                    for symbol, pos_data in portfolio_data.get("positions", {}).items():
                        avg_price = pos_data.get("avg_price", 0)
                        current_price = pos_data.get("current_price", avg_price)
                        quantity = pos_data.get("quantity", 0)
                        pnl = (current_price - avg_price) * quantity
                        pnl_pct = ((current_price - avg_price) / avg_price * 100) if avg_price > 0 else 0
                        
                        positions.append(Position(
                            symbol=symbol,
                            quantity=quantity,
                            avg_price=avg_price,
                            current_price=current_price,
                            market_value=quantity * current_price,
                            pnl=pnl,
                            pnl_pct=pnl_pct,
                            entry_date=pos_data.get("entry_date", ""),
                            days_held=pos_data.get("days_held", 0),
                            strategy_id=sid,
                        ))
                        
            except Exception as e:
                logger.error(f"Error reading positions: {e}")
        
        return positions
    
    # =========================================================================
    # Signals
    # =========================================================================
    
    def get_recent_signals(self, limit: int = 20) -> List[SignalRecord]:
        """Obtener señales recientes del cache."""
        return self._signals_cache[:limit]
    
    # =========================================================================
    # Costs
    # =========================================================================
    
    def get_cost_summary(self) -> CostSummary:
        """Obtener resumen de costes del AI Agent."""
        today_cost = 0.0
        today_tokens = 0
        today_searches = 0
        today_decisions = 0
        month_cost = 0.0
        month_decisions = 0
        
        # Desde cost_tracker en memoria
        if self.cost_tracker:
            daily = self.cost_tracker.get_daily_summary()
            monthly = self.cost_tracker.get_monthly_summary()
            
            today_cost = daily.get("total_cost_usd", 0)
            today_tokens = daily.get("total_tokens", 0)
            today_searches = daily.get("total_searches", 0)
            today_decisions = daily.get("total_records", 0)
            month_cost = monthly.get("total_cost_usd", 0)
            month_decisions = monthly.get("total_decisions", 0)
        
        # Fallback: leer de archivos
        elif COSTS_DIR.exists():
            today_file = COSTS_DIR / f"{date.today().isoformat()}.json"
            if today_file.exists():
                try:
                    with open(today_file, 'r') as f:
                        data = json.load(f)
                    summary = data.get("summary", {})
                    today_cost = summary.get("total_cost_usd", 0)
                    today_tokens = summary.get("total_tokens", 0)
                    today_searches = summary.get("total_searches", 0)
                    today_decisions = summary.get("total_records", 0)
                except Exception as e:
                    logger.error(f"Error reading cost file: {e}")
            
            # Sumar archivos del mes
            month_prefix = date.today().strftime("%Y-%m")
            for cost_file in COSTS_DIR.glob(f"{month_prefix}-*.json"):
                try:
                    with open(cost_file, 'r') as f:
                        data = json.load(f)
                    summary = data.get("summary", {})
                    month_cost += summary.get("total_cost_usd", 0)
                    month_decisions += summary.get("total_records", 0)
                except:
                    pass
        
        avg_cost = month_cost / max(month_decisions, 1)
        
        return CostSummary(
            today_cost=round(today_cost, 4),
            today_tokens=today_tokens,
            today_searches=today_searches,
            today_decisions=today_decisions,
            month_cost=round(month_cost, 4),
            month_decisions=month_decisions,
            avg_cost_per_decision=round(avg_cost, 4),
        )
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> Dict[str, Any]:
        """Exportar todo el estado como dict para API."""
        return {
            "status": asdict(self.get_system_status()),
            "accounts": [asdict(a) for a in self.get_accounts_summary()],
            "positions": [asdict(p) for p in self.get_positions()],
            "signals": [asdict(s) for s in self.get_recent_signals()],
            "costs": asdict(self.get_cost_summary()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Singleton global
_data_service: Optional[DataService] = None

def get_data_service() -> DataService:
    """Obtener instancia global del DataService."""
    global _data_service
    if _data_service is None:
        _data_service = DataService()
    return _data_service

def init_data_service(
    portfolio_manager=None,
    universe_manager=None,
    scheduler=None,
    cost_tracker=None,
) -> DataService:
    """Inicializar DataService con dependencias."""
    global _data_service
    _data_service = DataService(
        portfolio_manager=portfolio_manager,
        universe_manager=universe_manager,
        scheduler=scheduler,
        cost_tracker=cost_tracker,
    )
    return _data_service
```

---

### 3.3. Servicio de Logs

**Archivo**: `dashboard/services/log_service.py`

```python
"""
Log Service - Lectura de logs para el dashboard.
"""

import re
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_FILE = PROJECT_ROOT / "strategy_lab.log"


@dataclass
class LogEntry:
    """Entrada de log parseada."""
    timestamp: str
    level: str
    logger_name: str
    message: str
    
    @property
    def is_error(self) -> bool:
        return self.level in ("ERROR", "CRITICAL")
    
    @property
    def is_warning(self) -> bool:
        return self.level == "WARNING"


class LogService:
    """
    Servicio para leer y parsear logs.
    
    Uso:
        service = LogService()
        recent = service.get_recent_logs(limit=50)
        errors = service.get_recent_errors(limit=10)
    """
    
    # Patrón para parsear líneas de log
    # Formato: 2024-01-15 10:30:45,123 - strategy_lab - INFO - Message
    LOG_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"  # timestamp
        r" - (\S+)"  # logger name
        r" - (\w+)"  # level
        r" - (.+)"   # message
    )
    
    def __init__(self, log_file: Path = None):
        self.log_file = log_file or LOG_FILE
        
        # Cache de últimos logs/errores para acceso rápido
        self._recent_logs: deque = deque(maxlen=200)
        self._recent_errors: deque = deque(maxlen=50)
    
    def parse_line(self, line: str) -> Optional[LogEntry]:
        """Parsear una línea de log."""
        match = self.LOG_PATTERN.match(line.strip())
        if match:
            return LogEntry(
                timestamp=match.group(1),
                logger_name=match.group(2),
                level=match.group(3),
                message=match.group(4),
            )
        return None
    
    def get_recent_logs(self, limit: int = 50) -> List[LogEntry]:
        """
        Obtener las últimas N líneas de log.
        
        Lee del archivo si el cache está vacío.
        """
        if not self._recent_logs:
            self._load_from_file()
        
        return list(self._recent_logs)[-limit:]
    
    def get_recent_errors(self, limit: int = 10) -> List[LogEntry]:
        """Obtener los últimos errores."""
        if not self._recent_errors:
            self._load_from_file()
        
        return list(self._recent_errors)[-limit:]
    
    def _load_from_file(self):
        """Cargar logs desde archivo."""
        if not self.log_file.exists():
            return
        
        try:
            # Leer últimas 500 líneas (suficiente para el dashboard)
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-500:]
            
            for line in lines:
                entry = self.parse_line(line)
                if entry:
                    self._recent_logs.append(entry)
                    if entry.is_error:
                        self._recent_errors.append(entry)
                        
        except Exception as e:
            logger.error(f"Error reading log file: {e}")
    
    def add_entry(self, entry: LogEntry):
        """
        Añadir entrada al cache (para uso en tiempo real).
        
        Llamar desde un log handler personalizado.
        """
        self._recent_logs.append(entry)
        if entry.is_error:
            self._recent_errors.append(entry)
    
    def tail_logs(self, n: int = 20) -> List[LogEntry]:
        """
        Obtener las últimas N líneas directamente del archivo.
        
        Útil para actualización en tiempo real.
        """
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[-n:]
            
            entries = []
            for line in lines:
                entry = self.parse_line(line)
                if entry:
                    entries.append(entry)
            
            return entries
            
        except Exception as e:
            logger.error(f"Error tailing log file: {e}")
            return []


# Singleton
_log_service: Optional[LogService] = None

def get_log_service() -> LogService:
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service
```

---

### 3.4. Aplicación FastAPI

**Archivo**: `dashboard/app.py`

```python
"""
Nexus Trading Dashboard - FastAPI Application

Dashboard ligero para supervisión del sistema de paper trading.
"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from dashboard.routes import main, api, sse
from dashboard.services.data_service import get_data_service
from dashboard.services.log_service import get_log_service

logger = logging.getLogger(__name__)

# Paths
DASHBOARD_DIR = Path(__file__).parent
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
STATIC_DIR = DASHBOARD_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management."""
    logger.info("Dashboard starting up...")
    
    # Inicializar servicios
    get_data_service()
    get_log_service()
    
    yield
    
    logger.info("Dashboard shutting down...")


def create_app() -> FastAPI:
    """Factory para crear la aplicación FastAPI."""
    
    app = FastAPI(
        title="Nexus Trading Dashboard",
        description="Supervisión del Strategy Lab",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    app.state.templates = templates
    
    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Routers
    app.include_router(main.router)
    app.include_router(api.router, prefix="/api")
    app.include_router(sse.router, prefix="/sse")
    
    return app


# Instancia global para uvicorn
app = create_app()
```

---

### 3.5. Rutas Principales (HTML)

**Archivo**: `dashboard/routes/main.py`

```python
"""
Rutas principales que sirven HTML.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from dashboard.services.data_service import get_data_service
from dashboard.services.log_service import get_log_service

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Página principal del dashboard."""
    templates = request.app.state.templates
    
    data_service = get_data_service()
    log_service = get_log_service()
    
    context = {
        "request": request,
        "status": data_service.get_system_status(),
        "accounts": data_service.get_accounts_summary(),
        "positions": data_service.get_positions(),
        "signals": data_service.get_recent_signals(limit=10),
        "errors": log_service.get_recent_errors(limit=5),
        "costs": data_service.get_cost_summary(),
    }
    
    return templates.TemplateResponse("index.html", context)


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    """Página de logs completos."""
    templates = request.app.state.templates
    log_service = get_log_service()
    
    context = {
        "request": request,
        "logs": log_service.get_recent_logs(limit=100),
    }
    
    return templates.TemplateResponse("logs.html", context)


# =========================================================================
# Partials para HTMX (actualizaciones parciales)
# =========================================================================

@router.get("/partials/status", response_class=HTMLResponse)
async def partial_status(request: Request):
    """Partial: Status card."""
    templates = request.app.state.templates
    data_service = get_data_service()
    
    return templates.TemplateResponse(
        "partials/status_card.html",
        {"request": request, "status": data_service.get_system_status()}
    )


@router.get("/partials/accounts", response_class=HTMLResponse)
async def partial_accounts(request: Request):
    """Partial: Accounts cards."""
    templates = request.app.state.templates
    data_service = get_data_service()
    
    return templates.TemplateResponse(
        "partials/accounts_card.html",
        {"request": request, "accounts": data_service.get_accounts_summary()}
    )


@router.get("/partials/signals", response_class=HTMLResponse)
async def partial_signals(request: Request):
    """Partial: Signals table."""
    templates = request.app.state.templates
    data_service = get_data_service()
    
    return templates.TemplateResponse(
        "partials/signals_table.html",
        {"request": request, "signals": data_service.get_recent_signals(limit=10)}
    )


@router.get("/partials/errors", response_class=HTMLResponse)
async def partial_errors(request: Request):
    """Partial: Errors list."""
    templates = request.app.state.templates
    log_service = get_log_service()
    
    return templates.TemplateResponse(
        "partials/errors_list.html",
        {"request": request, "errors": log_service.get_recent_errors(limit=5)}
    )


@router.get("/partials/costs", response_class=HTMLResponse)
async def partial_costs(request: Request):
    """Partial: Costs card."""
    templates = request.app.state.templates
    data_service = get_data_service()
    
    return templates.TemplateResponse(
        "partials/costs_card.html",
        {"request": request, "costs": data_service.get_cost_summary()}
    )
```

---

### 3.6. API REST (JSON)

**Archivo**: `dashboard/routes/api.py`

```python
"""
API REST endpoints (JSON).

Útiles para:
- Integraciones externas
- Debugging
- Apps móviles futuras
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from dashboard.services.data_service import get_data_service
from dashboard.services.log_service import get_log_service

router = APIRouter()


@router.get("/status")
async def api_status():
    """Estado del sistema."""
    data_service = get_data_service()
    return data_service.get_system_status().__dict__


@router.get("/accounts")
async def api_accounts():
    """Resumen de cuentas."""
    data_service = get_data_service()
    return [a.__dict__ for a in data_service.get_accounts_summary()]


@router.get("/positions")
async def api_positions(strategy_id: str = None):
    """Posiciones abiertas."""
    data_service = get_data_service()
    return [p.__dict__ for p in data_service.get_positions(strategy_id)]


@router.get("/signals")
async def api_signals(limit: int = 20):
    """Señales recientes."""
    data_service = get_data_service()
    return [s.__dict__ for s in data_service.get_recent_signals(limit)]


@router.get("/costs")
async def api_costs():
    """Costes del AI Agent."""
    data_service = get_data_service()
    return data_service.get_cost_summary().__dict__


@router.get("/logs")
async def api_logs(limit: int = 50):
    """Logs recientes."""
    log_service = get_log_service()
    return [l.__dict__ for l in log_service.get_recent_logs(limit)]


@router.get("/errors")
async def api_errors(limit: int = 10):
    """Errores recientes."""
    log_service = get_log_service()
    return [e.__dict__ for e in log_service.get_recent_errors(limit)]


@router.get("/all")
async def api_all():
    """Todo el estado en una llamada."""
    data_service = get_data_service()
    return data_service.to_dict()
```

---

### 3.7. Server-Sent Events (Tiempo Real)

**Archivo**: `dashboard/routes/sse.py`

```python
"""
Server-Sent Events para actualizaciones en tiempo real.
"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from dashboard.services.data_service import get_data_service

router = APIRouter()


async def status_event_generator():
    """
    Generador de eventos de estado.
    
    Envía actualizaciones cada 5 segundos.
    """
    while True:
        data_service = get_data_service()
        
        # Crear payload con datos actualizados
        payload = {
            "status": data_service.get_system_status().__dict__,
            "accounts": [a.__dict__ for a in data_service.get_accounts_summary()],
            "costs": data_service.get_cost_summary().__dict__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        yield {
            "event": "update",
            "data": json.dumps(payload),
        }
        
        await asyncio.sleep(5)  # Actualizar cada 5 segundos


@router.get("/updates")
async def sse_updates():
    """
    Stream SSE de actualizaciones.
    
    El cliente se conecta y recibe updates cada 5 segundos.
    
    Uso en HTML:
        const evtSource = new EventSource('/sse/updates');
        evtSource.addEventListener('update', (e) => {
            const data = JSON.parse(e.data);
            // Actualizar UI
        });
    """
    return EventSourceResponse(status_event_generator())


async def signals_event_generator():
    """
    Generador de eventos de nuevas señales.
    
    Verifica cada 2 segundos si hay nuevas señales.
    """
    last_count = 0
    
    while True:
        data_service = get_data_service()
        signals = data_service.get_recent_signals(limit=1)
        
        current_count = len(data_service._signals_cache)
        
        if current_count > last_count and signals:
            # Hay nueva señal
            yield {
                "event": "new_signal",
                "data": json.dumps(signals[0].__dict__),
            }
            last_count = current_count
        
        await asyncio.sleep(2)


@router.get("/signals")
async def sse_signals():
    """Stream SSE de nuevas señales."""
    return EventSourceResponse(signals_event_generator())
```

---

### 3.8. Templates HTML

**Archivo**: `dashboard/templates/base.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Nexus Trading{% endblock %}</title>
    
    <!-- Tailwind CSS (CDN) -->
    <script src="https://cdn.tailwindcss.com"></script>
    
    <!-- HTMX -->
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    
    <!-- Custom styles -->
    <style>
        .pulse-green {
            animation: pulse-green 2s infinite;
        }
        @keyframes pulse-green {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .card {
            @apply bg-white rounded-lg shadow-md p-4;
        }
        .positive { @apply text-green-600; }
        .negative { @apply text-red-600; }
    </style>
    
    {% block head %}{% endblock %}
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- Navbar -->
    <nav class="bg-gray-800 text-white p-4">
        <div class="container mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold">
                <a href="/">🚀 Nexus Trading</a>
            </h1>
            <div class="flex items-center space-x-4">
                <span id="connection-status" class="flex items-center">
                    <span class="w-2 h-2 bg-green-500 rounded-full mr-2 pulse-green"></span>
                    <span class="text-sm">Connected</span>
                </span>
                <a href="/logs" class="text-sm hover:text-gray-300">📋 Logs</a>
            </div>
        </div>
    </nav>
    
    <!-- Main content -->
    <main class="container mx-auto p-4">
        {% block content %}{% endblock %}
    </main>
    
    <!-- Footer -->
    <footer class="text-center text-gray-500 text-sm py-4">
        Paper Trading Mode | Last update: <span id="last-update">-</span>
    </footer>
    
    <!-- SSE Connection -->
    <script>
        // Establecer conexión SSE para actualizaciones en tiempo real
        const evtSource = new EventSource('/sse/updates');
        
        evtSource.addEventListener('update', (e) => {
            const data = JSON.parse(e.data);
            document.getElementById('last-update').textContent = 
                new Date(data.timestamp).toLocaleTimeString();
            
            // HTMX puede recargar los partials automáticamente
            // o podemos actualizar manualmente aquí
        });
        
        evtSource.addEventListener('error', () => {
            document.getElementById('connection-status').innerHTML = 
                '<span class="w-2 h-2 bg-red-500 rounded-full mr-2"></span>' +
                '<span class="text-sm">Disconnected</span>';
        });
        
        // Notificación de nueva señal
        const signalSource = new EventSource('/sse/signals');
        signalSource.addEventListener('new_signal', (e) => {
            const signal = JSON.parse(e.data);
            // Mostrar notificación
            if (Notification.permission === 'granted') {
                new Notification('Nueva Señal', {
                    body: `${signal.direction} ${signal.symbol}`,
                });
            }
            // Recargar tabla de señales
            htmx.trigger('#signals-container', 'refresh');
        });
    </script>
    
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Archivo**: `dashboard/templates/index.html`

```html
{% extends "base.html" %}

{% block title %}Dashboard | Nexus Trading{% endblock %}

{% block content %}
<div class="space-y-6">
    
    <!-- Row 1: Status + Costs -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        
        <!-- Status Card -->
        <div id="status-container" 
             hx-get="/partials/status" 
             hx-trigger="every 10s"
             class="md:col-span-2">
            {% include "partials/status_card.html" %}
        </div>
        
        <!-- Costs Card -->
        <div id="costs-container"
             hx-get="/partials/costs"
             hx-trigger="every 30s">
            {% include "partials/costs_card.html" %}
        </div>
        
    </div>
    
    <!-- Row 2: Accounts -->
    <div id="accounts-container"
         hx-get="/partials/accounts"
         hx-trigger="every 15s">
        {% include "partials/accounts_card.html" %}
    </div>
    
    <!-- Row 3: Signals + Errors -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        
        <!-- Signals Table -->
        <div id="signals-container"
             hx-get="/partials/signals"
             hx-trigger="every 10s, refresh from:body">
            {% include "partials/signals_table.html" %}
        </div>
        
        <!-- Errors List -->
        <div id="errors-container"
             hx-get="/partials/errors"
             hx-trigger="every 15s">
            {% include "partials/errors_list.html" %}
        </div>
        
    </div>
    
</div>
{% endblock %}
```

---

### 3.9. Partials HTMX

**Archivo**: `dashboard/templates/partials/status_card.html`

```html
<div class="card">
    <div class="flex justify-between items-start mb-4">
        <h2 class="text-lg font-semibold text-gray-800">📊 System Status</h2>
        <span class="flex items-center">
            {% if status.is_running %}
            <span class="w-3 h-3 bg-green-500 rounded-full mr-2 pulse-green"></span>
            <span class="text-green-600 font-medium">Running</span>
            {% else %}
            <span class="w-3 h-3 bg-red-500 rounded-full mr-2"></span>
            <span class="text-red-600 font-medium">Stopped</span>
            {% endif %}
        </span>
    </div>
    
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div>
            <p class="text-sm text-gray-500">Regime</p>
            <p class="text-xl font-bold 
               {% if status.regime == 'BULL' %}text-green-600
               {% elif status.regime == 'BEAR' %}text-red-600
               {% elif status.regime == 'VOLATILE' %}text-orange-600
               {% else %}text-gray-600{% endif %}">
                {{ status.regime }}
            </p>
            <p class="text-xs text-gray-400">{{ "%.0f"|format(status.regime_confidence * 100) }}% confidence</p>
        </div>
        
        <div>
            <p class="text-sm text-gray-500">Active Symbols</p>
            <p class="text-xl font-bold text-gray-800">{{ status.active_symbols_count }}</p>
        </div>
        
        <div>
            <p class="text-sm text-gray-500">Next Execution</p>
            <p class="text-sm font-medium text-gray-800">
                {% if status.next_execution %}
                {{ status.next_execution[:19] }}
                {% else %}
                -
                {% endif %}
            </p>
        </div>
        
        <div>
            <p class="text-sm text-gray-500">Uptime</p>
            <p class="text-sm font-medium text-gray-800">
                {{ (status.uptime_seconds // 3600) }}h {{ ((status.uptime_seconds % 3600) // 60) }}m
            </p>
        </div>
    </div>
</div>
```

**Archivo**: `dashboard/templates/partials/accounts_card.html`

```html
<div class="card">
    <h2 class="text-lg font-semibold text-gray-800 mb-4">💰 Accounts</h2>
    
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        {% for account in accounts %}
        <div class="border rounded-lg p-4 {% if account.pnl_total >= 0 %}border-green-200 bg-green-50{% else %}border-red-200 bg-red-50{% endif %}">
            
            <div class="flex justify-between items-start mb-3">
                <h3 class="font-semibold text-gray-800">{{ account.strategy_id }}</h3>
                <span class="text-xs px-2 py-1 rounded 
                    {% if account.pnl_total >= 0 %}bg-green-100 text-green-800{% else %}bg-red-100 text-red-800{% endif %}">
                    {% if account.pnl_total >= 0 %}+{% endif %}{{ "%.2f"|format(account.pnl_total_pct) }}%
                </span>
            </div>
            
            <div class="space-y-2">
                <div class="flex justify-between">
                    <span class="text-sm text-gray-600">Total Value</span>
                    <span class="font-bold text-lg">€{{ "{:,.2f}"|format(account.total_value) }}</span>
                </div>
                
                <div class="flex justify-between text-sm">
                    <span class="text-gray-500">Cash</span>
                    <span class="text-gray-700">€{{ "{:,.2f}"|format(account.cash) }}</span>
                </div>
                
                <div class="flex justify-between text-sm">
                    <span class="text-gray-500">Invested</span>
                    <span class="text-gray-700">€{{ "{:,.2f}"|format(account.invested) }}</span>
                </div>
                
                <div class="flex justify-between text-sm">
                    <span class="text-gray-500">Positions</span>
                    <span class="text-gray-700">{{ account.positions_count }}</span>
                </div>
                
                <div class="flex justify-between text-sm pt-2 border-t">
                    <span class="text-gray-500">P&L Total</span>
                    <span class="font-medium {% if account.pnl_total >= 0 %}positive{% else %}negative{% endif %}">
                        {% if account.pnl_total >= 0 %}+{% endif %}€{{ "{:,.2f}"|format(account.pnl_total) }}
                    </span>
                </div>
            </div>
            
        </div>
        {% endfor %}
    </div>
</div>
```

**Archivo**: `dashboard/templates/partials/signals_table.html`

```html
<div class="card">
    <h2 class="text-lg font-semibold text-gray-800 mb-4">📈 Recent Signals</h2>
    
    {% if signals %}
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead class="bg-gray-50">
                <tr>
                    <th class="px-3 py-2 text-left">Time</th>
                    <th class="px-3 py-2 text-left">Strategy</th>
                    <th class="px-3 py-2 text-left">Symbol</th>
                    <th class="px-3 py-2 text-left">Direction</th>
                    <th class="px-3 py-2 text-left">Confidence</th>
                    <th class="px-3 py-2 text-left">Status</th>
                </tr>
            </thead>
            <tbody class="divide-y">
                {% for signal in signals %}
                <tr class="hover:bg-gray-50">
                    <td class="px-3 py-2 text-gray-500">{{ signal.timestamp[:16] }}</td>
                    <td class="px-3 py-2">
                        <span class="text-xs px-2 py-1 rounded bg-gray-100">
                            {{ signal.strategy_id[:10] }}
                        </span>
                    </td>
                    <td class="px-3 py-2 font-medium">{{ signal.symbol }}</td>
                    <td class="px-3 py-2">
                        <span class="px-2 py-1 rounded text-xs font-medium
                            {% if signal.direction == 'LONG' %}bg-green-100 text-green-800
                            {% elif signal.direction == 'SHORT' %}bg-red-100 text-red-800
                            {% else %}bg-gray-100 text-gray-800{% endif %}">
                            {{ signal.direction }}
                        </span>
                    </td>
                    <td class="px-3 py-2">
                        <div class="w-16 bg-gray-200 rounded-full h-2">
                            <div class="bg-blue-600 h-2 rounded-full" 
                                 style="width: {{ signal.confidence * 100 }}%"></div>
                        </div>
                    </td>
                    <td class="px-3 py-2">
                        <span class="text-xs px-2 py-1 rounded
                            {% if signal.status == 'executed' %}bg-green-100 text-green-800
                            {% elif signal.status == 'rejected' %}bg-red-100 text-red-800
                            {% else %}bg-yellow-100 text-yellow-800{% endif %}">
                            {{ signal.status }}
                        </span>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <p class="text-gray-500 text-center py-8">No signals generated yet</p>
    {% endif %}
</div>
```

**Archivo**: `dashboard/templates/partials/errors_list.html`

```html
<div class="card">
    <h2 class="text-lg font-semibold text-gray-800 mb-4">⚠️ Recent Errors</h2>
    
    {% if errors %}
    <div class="space-y-2">
        {% for error in errors %}
        <div class="border-l-4 border-red-500 bg-red-50 p-3 rounded-r">
            <div class="flex justify-between items-start">
                <span class="text-xs text-red-600 font-medium">{{ error.level }}</span>
                <span class="text-xs text-gray-400">{{ error.timestamp[:19] }}</span>
            </div>
            <p class="text-sm text-gray-700 mt-1">{{ error.message[:150] }}{% if error.message|length > 150 %}...{% endif %}</p>
            <p class="text-xs text-gray-400 mt-1">{{ error.logger_name }}</p>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="text-center py-8">
        <span class="text-4xl">✅</span>
        <p class="text-gray-500 mt-2">No errors detected</p>
    </div>
    {% endif %}
</div>
```

**Archivo**: `dashboard/templates/partials/costs_card.html`

```html
<div class="card">
    <h2 class="text-lg font-semibold text-gray-800 mb-4">💵 AI Costs</h2>
    
    <div class="space-y-3">
        <div class="flex justify-between items-center">
            <span class="text-sm text-gray-500">Today</span>
            <span class="font-bold text-lg">${{ "{:.4f}"|format(costs.today_cost) }}</span>
        </div>
        
        <div class="flex justify-between items-center text-sm">
            <span class="text-gray-500">Decisions</span>
            <span class="text-gray-700">{{ costs.today_decisions }}</span>
        </div>
        
        <div class="flex justify-between items-center text-sm">
            <span class="text-gray-500">Searches</span>
            <span class="text-gray-700">{{ costs.today_searches }}</span>
        </div>
        
        <div class="flex justify-between items-center text-sm">
            <span class="text-gray-500">Tokens</span>
            <span class="text-gray-700">{{ "{:,}"|format(costs.today_tokens) }}</span>
        </div>
        
        <hr class="my-2">
        
        <div class="flex justify-between items-center">
            <span class="text-sm text-gray-500">This Month</span>
            <span class="font-bold">${{ "{:.2f}"|format(costs.month_cost) }}</span>
        </div>
        
        <div class="flex justify-between items-center text-sm">
            <span class="text-gray-500">Avg/Decision</span>
            <span class="text-gray-700">${{ "{:.4f}"|format(costs.avg_cost_per_decision) }}</span>
        </div>
    </div>
</div>
```

---

### 3.10. Script de Ejecución

**Archivo**: `scripts/run_dashboard.py`

```python
#!/usr/bin/env python
"""
Entry point para ejecutar el dashboard de forma independiente.

Uso:
    python scripts/run_dashboard.py
    
    # O con opciones
    python scripts/run_dashboard.py --host 0.0.0.0 --port 8080
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Nexus Trading Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind")
    parser.add_argument("--port", type=int, default=8050, help="Port to bind")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    print(f"""
    ╔══════════════════════════════════════════════╗
    ║      NEXUS TRADING DASHBOARD                 ║
    ║                                              ║
    ║      http://{args.host}:{args.port}                  ║
    ╚══════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "dashboard.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
```

---

## 4. Integración con StrategyLab

Para que el dashboard tenga datos en tiempo real, necesita conectarse al StrategyLab. Hay dos opciones:

### Opción A: Dashboard Independiente (Recomendada para MVP)
El dashboard lee de archivos JSON y logs. No necesita el StrategyLab corriendo en el mismo proceso.

### Opción B: Dashboard Integrado
El dashboard comparte instancias con StrategyLab. Modificar `run_strategy_lab.py`:

```python
# Añadir al final de StrategyLab.__init__():

# Inicializar DataService con referencias a componentes
from dashboard.services.data_service import init_data_service
from src.agents.llm.cost_tracker import get_cost_tracker

self.data_service = init_data_service(
    portfolio_manager=self.portfolio_manager,
    universe_manager=self.universe_manager,
    scheduler=self.scheduler,
    cost_tracker=get_cost_tracker(),
)
self.data_service.set_running(True)
```

---

## 5. Checklist de Implementación

- [ ] Crear estructura de directorios `dashboard/`
- [ ] Añadir dependencias a `requirements.txt`
- [ ] Crear `dashboard/services/data_service.py`
- [ ] Crear `dashboard/services/log_service.py`
- [ ] Crear `dashboard/app.py`
- [ ] Crear `dashboard/routes/main.py`
- [ ] Crear `dashboard/routes/api.py`
- [ ] Crear `dashboard/routes/sse.py`
- [ ] Crear templates base y partials
- [ ] Crear `scripts/run_dashboard.py`
- [ ] Crear `dashboard/__init__.py` en todos los directorios
- [ ] Probar dashboard independiente con datos mock
- [ ] Integrar con StrategyLab (Opción A o B)
- [ ] Probar actualizaciones SSE en tiempo real

---

## 6. Notas Importantes

### Performance
- HTMX solo recarga los partials que cambian, no toda la página
- SSE es más eficiente que polling para tiempo real
- Los intervalos de actualización son configurables (10s status, 30s costs)

### Seguridad (MVP)
- El dashboard escucha solo en localhost por defecto
- No hay autenticación (añadir en producción)
- No exponer en red pública sin protección

### Extensibilidad
- Fácil añadir nuevos partials/cards
- API REST permite integraciones futuras
- Los templates son simples HTML, fáciles de modificar
