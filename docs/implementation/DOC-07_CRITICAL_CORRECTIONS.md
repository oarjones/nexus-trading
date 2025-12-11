# DOC-07: Correcciones Críticas

> **Propósito**: Corregir inconsistencias arquitectónicas identificadas antes de implementar  
> **Prioridad**: 🔴 CRÍTICA - Aplicar ANTES de implementar DOC-01 a DOC-06  
> **Origen**: Análisis del agente desarrollador

---

## 1. Resumen del Problema

El análisis ha identificado una **inconsistencia arquitectónica crítica**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROBLEMA IDENTIFICADO                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Terminal 2                           Terminal 3                          │
│   ┌─────────────────┐                  ┌─────────────────┐                 │
│   │  StrategyLab    │                  │    Dashboard    │                 │
│   │  (Proceso A)    │      ????        │   (Proceso B)   │                 │
│   │                 │ ◄──────────────► │                 │                 │
│   │ • portfolio_mgr │   No pueden      │ • DataService   │                 │
│   │ • universe_mgr  │   compartir      │   intenta       │                 │
│   │ • scheduler     │   memoria        │   acceder a     │                 │
│   │                 │                  │   objetos       │                 │
│   └─────────────────┘                  └─────────────────┘                 │
│                                                                             │
│   DOC-03 asume acceso a memoria ──► IMPOSIBLE entre procesos Python        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**DOC-03** define un `DataService` que intenta inyectar instancias de `portfolio_manager`, `universe_manager` y `scheduler` en memoria. Pero **DOC-06** (Manual de Usuario) indica claramente que el Dashboard se ejecuta en un proceso separado (Terminal 3).

**Consecuencia**: El Dashboard mostrará datos vacíos o fallará al intentar acceder a objetos que no existen en su espacio de memoria.

---

## 2. Solución: Comunicación via Archivos JSON

La solución es simple y robusta: **toda la comunicación entre procesos será via archivos JSON**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ARQUITECTURA CORREGIDA                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   StrategyLab (Proceso A)              Dashboard (Proceso B)               │
│   ┌─────────────────────┐              ┌─────────────────────┐             │
│   │                     │              │                     │             │
│   │  Escribe archivos:  │              │  Lee archivos:      │             │
│   │                     │   ──────►    │                     │             │
│   │  • system_status    │   Archivos   │  • system_status    │             │
│   │  • portfolios       │    JSON      │  • portfolios       │             │
│   │  • active_universe  │   ◄──────    │  • active_universe  │             │
│   │  • costs            │              │  • costs            │             │
│   │  • signals          │              │  • signals          │             │
│   │                     │              │                     │             │
│   └─────────────────────┘              └─────────────────────┘             │
│                                                                             │
│                         data/                                               │
│                         ├── system_status.json    (NUEVO)                  │
│                         ├── active_universe.json  (NUEVO)                  │
│                         ├── signals_cache.json    (NUEVO)                  │
│                         ├── paper_portfolios.json (existente)              │
│                         └── costs/YYYY-MM-DD.json (existente)              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Nuevos Archivos JSON Requeridos

### 3.1. system_status.json (NUEVO)

**Escritor**: `StrategyLab` (cada 30 segundos y en cambios de estado)  
**Lector**: `Dashboard.DataService`

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "is_running": true,
  "uptime_seconds": 3600,
  "regime": {
    "current": "BULL",
    "confidence": 0.72,
    "probabilities": {
      "BULL": 0.72,
      "BEAR": 0.08,
      "SIDEWAYS": 0.15,
      "VOLATILE": 0.05
    },
    "days_in_regime": 5,
    "last_change": "2024-01-10T09:00:00Z"
  },
  "scheduler": {
    "next_hmm_rules": "2024-01-16T10:00:00Z",
    "next_ai_agent": "2024-01-15T14:00:00Z",
    "last_execution": {
      "strategy": "ai_agent_swing",
      "timestamp": "2024-01-15T10:00:00Z",
      "signals_generated": 1
    }
  },
  "active_symbols_count": 35,
  "errors_last_hour": 0
}
```

### 3.2. active_universe.json (NUEVO)

**Escritor**: `UniverseManager` (después de cada screening diario)  
**Lector**: `Dashboard.DataService`

```json
{
  "screening_timestamp": "2024-01-15T06:00:00Z",
  "regime_used": "BULL",
  "master_universe_count": 150,
  "filters_applied": {
    "liquidity_passed": 120,
    "trend_passed": 85,
    "volatility_passed": 78,
    "final_count": 35
  },
  "active_symbols": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "sector": "technology",
      "liquidity_tier": 1,
      "last_price": 185.50,
      "atr_pct": 2.1
    },
    {
      "ticker": "NVDA",
      "name": "NVIDIA Corporation",
      "sector": "semiconductors",
      "liquidity_tier": 1,
      "last_price": 875.00,
      "atr_pct": 3.5
    }
  ],
  "excluded_reasons": {
    "low_volume": ["XYZ", "ABC"],
    "high_spread": ["DEF"],
    "wrong_trend": ["GHI", "JKL"]
  }
}
```

### 3.3. signals_cache.json (NUEVO)

**Escritor**: `StrategyRunner` (después de cada ejecución)  
**Lector**: `Dashboard.DataService`

```json
{
  "last_updated": "2024-01-15T10:00:15Z",
  "signals": [
    {
      "id": "sig_a1b2c3",
      "timestamp": "2024-01-15T10:00:15Z",
      "strategy_id": "ai_agent_swing",
      "symbol": "NVDA",
      "direction": "LONG",
      "confidence": 0.85,
      "entry_price": 875.50,
      "stop_loss": 850.00,
      "take_profit": 925.00,
      "reasoning": "Strong earnings beat, positive analyst revisions",
      "status": "executed",
      "execution": {
        "fill_price": 875.94,
        "fill_time": "2024-01-15T10:00:16Z",
        "shares": 1,
        "commission": 1.00
      }
    }
  ],
  "max_signals": 100
}
```

---

## 4. Correcciones por Documento

### 4.1. Correcciones a DOC-01 (UniverseManager)

**Añadir** método `save_state()` a `UniverseManager`:

```python
# Añadir a src/universe/manager.py

import json
from pathlib import Path
from datetime import datetime, timezone

class UniverseManager:
    # ... código existente ...
    
    def __init__(self, ...):
        # ... código existente ...
        self.state_file = Path("data/active_universe.json")
    
    async def run_daily_screening(self, regime: str) -> List[str]:
        """Ejecutar screening diario."""
        # ... código existente de screening ...
        
        # NUEVO: Guardar estado después del screening
        await self.save_state(regime)
        
        return active_symbols
    
    async def save_state(self, regime: str):
        """
        Persistir estado del universo activo para el Dashboard.
        
        CRÍTICO: Este método permite que el Dashboard (proceso separado)
        vea el resultado del screening.
        """
        state = {
            "screening_timestamp": datetime.now(timezone.utc).isoformat(),
            "regime_used": regime,
            "master_universe_count": len(self.symbol_registry.get_all_symbols()),
            "filters_applied": {
                "liquidity_passed": self._liquidity_passed_count,
                "trend_passed": self._trend_passed_count,
                "volatility_passed": self._volatility_passed_count,
                "final_count": len(self.active_symbols),
            },
            "active_symbols": [
                {
                    "ticker": sym.ticker,
                    "name": sym.name,
                    "sector": sym.sector,
                    "liquidity_tier": sym.liquidity_tier,
                    "last_price": self._last_prices.get(sym.ticker, 0),
                    "atr_pct": self._atr_values.get(sym.ticker, 0),
                }
                for sym in self.active_symbols
            ],
            "excluded_reasons": self._exclusion_reasons,
        }
        
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Universe state saved: {len(self.active_symbols)} active symbols")
```

---

### 4.2. Correcciones a DOC-02 (Web Search)

**Sin cambios estructurales necesarios**. El diseño es correcto.

**Recomendación adicional**: Añadir límite explícito en el prompt para evitar loops infinitos de búsqueda:

```python
# Añadir al prompt en src/agents/llm/prompts/base.py

SEARCH_LIMITS_INSTRUCTION = """
## Límites de Búsqueda

IMPORTANTE: Tienes un máximo de 3 búsquedas por decisión.
- Usa búsquedas solo cuando realmente necesites información actual
- Si ya tienes suficiente información, NO busques más
- Después de 2 búsquedas, debes proporcionar tu decisión final
- NUNCA hagas más de 3 búsquedas en una sola decisión
"""
```

---

### 4.3. Correcciones a DOC-03 (Dashboard) - CRÍTICAS

**REFACTORIZAR COMPLETAMENTE** `DataService` para eliminar dependencias de memoria:

```python
# REEMPLAZAR dashboard/services/data_service.py

"""
Data Service - Acceso a datos via archivos JSON.

IMPORTANTE: Este servicio NO tiene acceso a objetos en memoria del StrategyLab.
Toda la comunicación es via archivos JSON en el directorio data/.
"""

import json
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

# Rutas de archivos (única fuente de datos)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Archivos JSON que el StrategyLab escribe
SYSTEM_STATUS_FILE = DATA_DIR / "system_status.json"
PORTFOLIOS_FILE = DATA_DIR / "paper_portfolios.json"
UNIVERSE_FILE = DATA_DIR / "active_universe.json"
SIGNALS_FILE = DATA_DIR / "signals_cache.json"
COSTS_DIR = DATA_DIR / "costs"


@dataclass
class SystemStatus:
    """Estado general del sistema (leído de system_status.json)."""
    is_running: bool = False
    regime: str = "UNKNOWN"
    regime_confidence: float = 0.0
    last_execution: Optional[str] = None
    next_execution: Optional[str] = None
    active_symbols_count: int = 0
    uptime_seconds: int = 0
    last_heartbeat: Optional[str] = None


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
    status: str


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
    Servicio de acceso a datos basado ÚNICAMENTE en archivos.
    
    ARQUITECTURA:
    - StrategyLab (Proceso A) escribe archivos JSON
    - Dashboard (Proceso B) lee archivos JSON via este servicio
    - NO hay acceso a memoria compartida entre procesos
    
    Archivos monitorizados:
    - data/system_status.json    → Estado del sistema (heartbeat)
    - data/paper_portfolios.json → Estado de las cuentas
    - data/active_universe.json  → Símbolos activos tras screening
    - data/signals_cache.json    → Señales recientes
    - data/costs/YYYY-MM-DD.json → Costes del AI Agent
    """
    
    def __init__(self):
        """
        Inicializar servicio.
        
        NOTA: No se inyectan dependencias de memoria.
        Todo se lee de archivos.
        """
        # Cache para evitar lecturas excesivas
        self._cache = {}
        self._cache_ttl = 5  # segundos
        self._cache_timestamps = {}
    
    def _read_json_file(self, file_path: Path, default: Any = None) -> Any:
        """
        Leer archivo JSON con manejo de errores.
        
        Returns:
            Contenido del JSON o default si no existe/error
        """
        if not file_path.exists():
            return default if default is not None else {}
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return default if default is not None else {}
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return default if default is not None else {}
    
    # =========================================================================
    # System Status (desde system_status.json)
    # =========================================================================
    
    def get_system_status(self) -> SystemStatus:
        """
        Obtener estado del sistema desde archivo.
        
        El StrategyLab escribe este archivo cada 30 segundos.
        Si el archivo no existe o es muy antiguo, asumimos que el sistema
        no está corriendo.
        """
        data = self._read_json_file(SYSTEM_STATUS_FILE, {})
        
        if not data:
            return SystemStatus(is_running=False)
        
        # Verificar si el heartbeat es reciente (< 2 minutos)
        last_heartbeat = data.get("timestamp")
        is_running = False
        
        if last_heartbeat:
            try:
                heartbeat_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
                age = (datetime.now(timezone.utc) - heartbeat_time).total_seconds()
                is_running = age < 120  # Consideramos "running" si heartbeat < 2 min
            except:
                pass
        
        regime_data = data.get("regime", {})
        scheduler_data = data.get("scheduler", {})
        
        return SystemStatus(
            is_running=is_running,
            regime=regime_data.get("current", "UNKNOWN"),
            regime_confidence=regime_data.get("confidence", 0.0),
            last_execution=scheduler_data.get("last_execution", {}).get("timestamp"),
            next_execution=scheduler_data.get("next_ai_agent") or scheduler_data.get("next_hmm_rules"),
            active_symbols_count=data.get("active_symbols_count", 0),
            uptime_seconds=data.get("uptime_seconds", 0),
            last_heartbeat=last_heartbeat,
        )
    
    # =========================================================================
    # Accounts & Positions (desde paper_portfolios.json)
    # =========================================================================
    
    def get_accounts_summary(self) -> List[AccountSummary]:
        """Obtener resumen de todas las cuentas desde archivo."""
        data = self._read_json_file(PORTFOLIOS_FILE, {})
        accounts = []
        
        for strategy_id, portfolio_data in data.get("portfolios", {}).items():
            accounts.append(self._dict_to_account_summary(strategy_id, portfolio_data))
        
        return accounts
    
    def _dict_to_account_summary(self, strategy_id: str, data: dict) -> AccountSummary:
        """Convertir dict de JSON a AccountSummary."""
        positions = data.get("positions", {})
        cash = data.get("cash", 0)
        
        invested = sum(
            pos.get("quantity", 0) * pos.get("current_price", pos.get("avg_price", 0))
            for pos in positions.values()
        )
        total_value = cash + invested
        
        initial_capital = data.get("initial_capital", 25000)
        pnl_total = total_value - initial_capital
        pnl_total_pct = (pnl_total / initial_capital) * 100 if initial_capital > 0 else 0
        
        return AccountSummary(
            strategy_id=strategy_id,
            total_value=total_value,
            cash=cash,
            invested=invested,
            pnl_total=pnl_total,
            pnl_total_pct=pnl_total_pct,
            pnl_today=data.get("pnl_today", 0),
            pnl_today_pct=data.get("pnl_today_pct", 0),
            positions_count=len(positions),
            last_trade=data.get("last_trade_time"),
        )
    
    def get_positions(self, strategy_id: str = None) -> List[Position]:
        """Obtener posiciones abiertas desde archivo."""
        data = self._read_json_file(PORTFOLIOS_FILE, {})
        positions = []
        
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
        
        return positions
    
    # =========================================================================
    # Signals (desde signals_cache.json)
    # =========================================================================
    
    def get_recent_signals(self, limit: int = 20) -> List[SignalRecord]:
        """Obtener señales recientes desde archivo."""
        data = self._read_json_file(SIGNALS_FILE, {"signals": []})
        
        signals = []
        for sig in data.get("signals", [])[:limit]:
            signals.append(SignalRecord(
                timestamp=sig.get("timestamp", ""),
                strategy_id=sig.get("strategy_id", ""),
                symbol=sig.get("symbol", ""),
                direction=sig.get("direction", ""),
                confidence=sig.get("confidence", 0),
                entry_price=sig.get("entry_price"),
                stop_loss=sig.get("stop_loss"),
                take_profit=sig.get("take_profit"),
                reasoning=sig.get("reasoning", ""),
                status=sig.get("status", "generated"),
            ))
        
        return signals
    
    # =========================================================================
    # Universe (desde active_universe.json)
    # =========================================================================
    
    def get_active_universe(self) -> dict:
        """Obtener información del universo activo."""
        return self._read_json_file(UNIVERSE_FILE, {
            "active_symbols": [],
            "filters_applied": {},
            "screening_timestamp": None,
        })
    
    # =========================================================================
    # Costs (desde data/costs/YYYY-MM-DD.json)
    # =========================================================================
    
    def get_cost_summary(self) -> CostSummary:
        """Obtener resumen de costes del AI Agent."""
        today_cost = 0.0
        today_tokens = 0
        today_searches = 0
        today_decisions = 0
        month_cost = 0.0
        month_decisions = 0
        
        # Costes del día
        today_file = COSTS_DIR / f"{date.today().isoformat()}.json"
        if today_file.exists():
            data = self._read_json_file(today_file, {})
            summary = data.get("summary", {})
            today_cost = summary.get("total_cost_usd", 0)
            today_tokens = summary.get("total_tokens", 0)
            today_searches = summary.get("total_searches", 0)
            today_decisions = summary.get("total_records", 0)
        
        # Costes del mes
        month_prefix = date.today().strftime("%Y-%m")
        for cost_file in COSTS_DIR.glob(f"{month_prefix}-*.json"):
            data = self._read_json_file(cost_file, {})
            summary = data.get("summary", {})
            month_cost += summary.get("total_cost_usd", 0)
            month_decisions += summary.get("total_records", 0)
        
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
            "universe": self.get_active_universe(),
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


# ELIMINADO: init_data_service() con inyección de dependencias
# Ya no es necesario porque todo se lee de archivos
```

---

### 4.4. Correcciones a DOC-05 (Configuration Guide)

**Añadir** verificación de `BRAVE_SEARCH_API_KEY` al script de verificación:

```python
# Añadir a scripts/verify_config.py en la sección de variables recomendadas

print("\n[2] Environment Variables (Recommended)")
check(
    os.getenv("BRAVE_SEARCH_API_KEY"),
    "BRAVE_SEARCH_API_KEY is set (enables web search for AI Agent)",
    critical=False
)

# Si está habilitado web search, es más importante
if os.getenv("AI_AGENT_WEB_SEARCH_ENABLED", "true").lower() == "true":
    if not os.getenv("BRAVE_SEARCH_API_KEY"):
        print(f"  {YELLOW}⚠{RESET} Web search enabled but BRAVE_SEARCH_API_KEY not set")
        print(f"      AI Agent will work but without news/search capability")
```

---

### 4.5. Nuevo Componente: StatusWriter para StrategyLab

**Añadir** a `scripts/run_strategy_lab.py` o crear `src/monitoring/status_writer.py`:

```python
# src/monitoring/status_writer.py

"""
Status Writer - Escribe heartbeat para el Dashboard.

Este componente permite que el Dashboard (proceso separado) 
vea el estado del StrategyLab en tiempo real.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StatusWriter:
    """
    Escribe estado del sistema a archivo JSON periódicamente.
    
    El Dashboard lee este archivo para mostrar:
    - Si el sistema está corriendo
    - Régimen actual
    - Próximas ejecuciones
    - Conteo de símbolos activos
    """
    
    def __init__(
        self,
        output_file: str = "data/system_status.json",
        interval_seconds: int = 30,
    ):
        self.output_file = Path(output_file)
        self.interval_seconds = interval_seconds
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Estado interno (actualizado por StrategyLab)
        self._start_time = datetime.now(timezone.utc)
        self._is_running = False
        self._regime = "UNKNOWN"
        self._regime_confidence = 0.0
        self._regime_probabilities = {}
        self._days_in_regime = 0
        self._active_symbols_count = 0
        self._next_hmm_rules: Optional[str] = None
        self._next_ai_agent: Optional[str] = None
        self._last_execution: Optional[dict] = None
        self._errors_last_hour = 0
        
        # Task de escritura periódica
        self._write_task: Optional[asyncio.Task] = None
    
    def start(self):
        """Iniciar escritura periódica."""
        self._is_running = True
        self._write_task = asyncio.create_task(self._write_loop())
        logger.info(f"StatusWriter started, writing to {self.output_file}")
    
    async def stop(self):
        """Detener escritura y escribir estado final."""
        self._is_running = False
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
        
        # Escribir estado final (is_running = False)
        await self._write_status()
        logger.info("StatusWriter stopped")
    
    async def _write_loop(self):
        """Loop de escritura periódica."""
        while self._is_running:
            await self._write_status()
            await asyncio.sleep(self.interval_seconds)
    
    async def _write_status(self):
        """Escribir estado actual a archivo."""
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_running": self._is_running,
            "uptime_seconds": int(uptime),
            "regime": {
                "current": self._regime,
                "confidence": self._regime_confidence,
                "probabilities": self._regime_probabilities,
                "days_in_regime": self._days_in_regime,
            },
            "scheduler": {
                "next_hmm_rules": self._next_hmm_rules,
                "next_ai_agent": self._next_ai_agent,
                "last_execution": self._last_execution,
            },
            "active_symbols_count": self._active_symbols_count,
            "errors_last_hour": self._errors_last_hour,
        }
        
        try:
            with open(self.output_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write status: {e}")
    
    # =========================================================================
    # Métodos para actualizar estado (llamados por StrategyLab)
    # =========================================================================
    
    def update_regime(
        self,
        regime: str,
        confidence: float,
        probabilities: dict = None,
        days_in_regime: int = 0
    ):
        """Actualizar información de régimen."""
        self._regime = regime
        self._regime_confidence = confidence
        self._regime_probabilities = probabilities or {}
        self._days_in_regime = days_in_regime
    
    def update_active_symbols(self, count: int):
        """Actualizar conteo de símbolos activos."""
        self._active_symbols_count = count
    
    def update_scheduler(
        self,
        next_hmm_rules: str = None,
        next_ai_agent: str = None
    ):
        """Actualizar próximas ejecuciones programadas."""
        if next_hmm_rules:
            self._next_hmm_rules = next_hmm_rules
        if next_ai_agent:
            self._next_ai_agent = next_ai_agent
    
    def record_execution(self, strategy: str, signals_generated: int):
        """Registrar última ejecución."""
        self._last_execution = {
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signals_generated": signals_generated,
        }
    
    def increment_errors(self):
        """Incrementar contador de errores."""
        self._errors_last_hour += 1
```

---

### 4.6. Integración de StatusWriter en StrategyLab

**Modificar** `scripts/run_strategy_lab.py`:

```python
# Añadir imports
from src.monitoring.status_writer import StatusWriter

class StrategyLab:
    def __init__(self):
        # ... código existente ...
        
        # NUEVO: StatusWriter para el Dashboard
        self.status_writer = StatusWriter(
            output_file="data/system_status.json",
            interval_seconds=30,
        )
    
    async def start(self):
        # ... código existente de inicialización ...
        
        # NUEVO: Iniciar StatusWriter
        self.status_writer.start()
        
        # Después del screening inicial
        self.status_writer.update_active_symbols(
            len(self.universe_manager.active_symbols)
        )
        
        # ... resto del código ...
    
    async def _run_strategy(self, strategy_id: str):
        # ... código existente ...
        
        # Después de detectar régimen
        self.status_writer.update_regime(
            regime=regime_result.regime,
            confidence=regime_result.confidence,
            probabilities=regime_result.probabilities,
        )
        
        # Después de generar señales
        self.status_writer.record_execution(
            strategy=strategy_id,
            signals_generated=len(signals),
        )
    
    async def stop(self):
        # ... código existente ...
        
        # NUEVO: Detener StatusWriter
        await self.status_writer.stop()
```

---

### 4.7. SignalsWriter para StrategyRunner

**Añadir** a `src/strategies/runner.py`:

```python
# Añadir método para persistir señales

import json
from pathlib import Path

SIGNALS_FILE = Path("data/signals_cache.json")
MAX_CACHED_SIGNALS = 100

def save_signal_to_cache(signal: Signal, execution_result: dict = None):
    """
    Guardar señal en cache para el Dashboard.
    
    Args:
        signal: Señal generada
        execution_result: Resultado de ejecución (si se ejecutó)
    """
    # Cargar cache existente
    if SIGNALS_FILE.exists():
        with open(SIGNALS_FILE, 'r') as f:
            cache = json.load(f)
    else:
        cache = {"signals": []}
    
    # Crear registro de señal
    signal_record = {
        "id": f"sig_{signal.signal_id}",
        "timestamp": signal.timestamp.isoformat(),
        "strategy_id": signal.strategy_id,
        "symbol": signal.symbol,
        "direction": signal.direction.value,
        "confidence": signal.confidence,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "reasoning": signal.reasoning,
        "status": "executed" if execution_result else "generated",
    }
    
    if execution_result:
        signal_record["execution"] = execution_result
    
    # Insertar al inicio
    cache["signals"].insert(0, signal_record)
    
    # Limitar tamaño
    cache["signals"] = cache["signals"][:MAX_CACHED_SIGNALS]
    cache["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    # Guardar
    SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SIGNALS_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
```

---

## 5. Orden de Implementación Corregido

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORDEN DE IMPLEMENTACIÓN ACTUALIZADO                      │
└─────────────────────────────────────────────────────────────────────────────┘

FASE 0: Preparación (DOC-05 + DOC-07)
├── Configurar .env con todas las variables
├── Crear directorios: data/, data/costs/, reports/
└── Verificar con scripts/verify_config.py

FASE 1: Core Logic (DOC-01 + DOC-04)
├── Implementar UniverseManager
├── ✅ AÑADIR: UniverseManager.save_state() → active_universe.json
├── Actualizar symbols.yaml con 150 símbolos
└── Validar con scripts/validate_universe.py

FASE 2: Observabilidad (DOC-07 - NUEVO)
├── Crear src/monitoring/status_writer.py
├── Crear save_signal_to_cache() en runner.py
├── Integrar StatusWriter en StrategyLab
└── Verificar que se escriben:
    ├── data/system_status.json
    ├── data/active_universe.json
    └── data/signals_cache.json

FASE 3: AI Agent (DOC-02)
├── Implementar CostTracker
├── Implementar WebSearchClient
├── Refactorizar ClaudeAgent con tool_use
└── Añadir límites de búsqueda en prompts

FASE 4: Dashboard (DOC-03 CORREGIDO)
├── Implementar FastAPI app
├── ✅ USAR: DataService solo con lectura de archivos
├── ❌ ELIMINAR: Inyección de dependencias de memoria
├── Implementar templates HTMX
└── Verificar que lee correctamente todos los JSON

FASE 5: Validación End-to-End
├── Iniciar StrategyLab (Terminal 2)
├── Iniciar Dashboard (Terminal 3)
├── Verificar que Dashboard muestra datos en tiempo real
└── Verificar actualización de todas las secciones
```

---

## 6. Checklist de Validación

Antes de considerar la implementación completa, verificar:

### Archivos JSON se escriben correctamente:

- [ ] `data/system_status.json` se actualiza cada 30 segundos
- [ ] `data/active_universe.json` se escribe después del screening
- [ ] `data/signals_cache.json` se actualiza con cada señal
- [ ] `data/paper_portfolios.json` se actualiza con cada trade
- [ ] `data/costs/YYYY-MM-DD.json` se escribe con cada decisión del AI Agent

### Dashboard lee correctamente:

- [ ] Status card muestra "Running" cuando StrategyLab está activo
- [ ] Status card muestra "Stopped" cuando el heartbeat es viejo (>2 min)
- [ ] Régimen se actualiza en tiempo real
- [ ] Cuentas muestran valores correctos
- [ ] Señales aparecen cuando se generan
- [ ] Costes del día se actualizan

### Procesos son independientes:

- [ ] Dashboard puede iniciarse antes que StrategyLab
- [ ] Dashboard puede reiniciarse sin afectar StrategyLab
- [ ] StrategyLab puede reiniciarse sin afectar Dashboard
- [ ] Si StrategyLab se detiene, Dashboard muestra "Stopped" después de 2 min

---

## 7. Resumen de Cambios

| Documento | Tipo de Cambio | Descripción |
|-----------|----------------|-------------|
| DOC-01 | **MODIFICAR** | Añadir `save_state()` a UniverseManager |
| DOC-02 | **AÑADIR** | Límites explícitos de búsqueda en prompts |
| DOC-03 | **REFACTORIZAR** | DataService solo lee archivos, eliminar inyección de memoria |
| DOC-05 | **AÑADIR** | Verificación de BRAVE_SEARCH_API_KEY |
| DOC-07 | **NUEVO** | StatusWriter, SignalsWriter, integración |

---

## 8. Diagrama Final de Comunicación

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DE COMUNICACIÓN FINAL                       │
└─────────────────────────────────────────────────────────────────────────────┘

  PROCESO A: StrategyLab                    PROCESO B: Dashboard
  ══════════════════════                    ════════════════════
  
  ┌──────────────────┐                      ┌──────────────────┐
  │   StatusWriter   │──────────────────────│                  │
  │   (cada 30s)     │  system_status.json  │                  │
  └──────────────────┘                      │                  │
                                            │   DataService    │
  ┌──────────────────┐                      │   (File Reader)  │
  │ UniverseManager  │──────────────────────│                  │
  │ (screening)      │ active_universe.json │                  │
  └──────────────────┘                      │                  │
                                            │                  │
  ┌──────────────────┐                      │                  │
  │ StrategyRunner   │──────────────────────│                  │
  │ (señales)        │  signals_cache.json  │                  │
  └──────────────────┘                      │                  │
                                            │                  │
  ┌──────────────────┐                      │                  │
  │ PaperPortfolio   │──────────────────────│                  │
  │ Manager          │ paper_portfolios.json│                  │
  └──────────────────┘                      │                  │
                                            │                  │
  ┌──────────────────┐                      │                  │
  │   CostTracker    │──────────────────────│                  │
  │   (AI Agent)     │ costs/YYYY-MM-DD.json│                  │
  └──────────────────┘                      └──────────────────┘
  
                           data/
                           ├── system_status.json     ← Heartbeat
                           ├── active_universe.json   ← Screening result
                           ├── signals_cache.json     ← Recent signals
                           ├── paper_portfolios.json  ← Account state
                           └── costs/
                               └── 2024-01-15.json    ← AI costs
```
