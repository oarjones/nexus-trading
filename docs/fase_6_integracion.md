# 🔗 Fase 6: Integración y Validación

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 4 semanas  
**Dependencias:** Fase 4 (Motor Trading), Fase 5 (ML Pipeline)  
**Docs técnicos:** Doc 1 (sec 5-6), Doc 6 (sec 5-6, 9), Doc 7 (sec 4-6, 10)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| Integración end-to-end | Flujo completo: Data → Señal → Riesgo → Ejecución |
| Kill Switch operativo | Activación automática en DD>15%, manual via Telegram |
| Circuit Breakers configurados | 5 breakers activos con modo degradado |
| Dashboard Grafana completo | 5 dashboards: Overview, Trading, Risk, System, ML |
| Alertas Telegram | Bot responde a comandos, envía alertas por severidad |
| Paper trading 30 días | Sistema autónomo sin alertas críticas |
| Métricas de validación | Sharpe > 0.5, Max DD < 15%, Win Rate > 45% |

---

## 2. Prerrequisitos

### 2.1 Verificación de Fases Anteriores

Antes de iniciar Fase 6, ejecutar verificaciones:

```bash
# Fase 4: Motor de Trading
python scripts/verify_trading.py

# Fase 5: ML Pipeline
python scripts/verify_ml.py
```

**Criterios de paso:**

| Fase | Verificación | Requerido |
|------|--------------|-----------|
| 4 | Strategy Registry con ≥2 estrategias | ✓ |
| 4 | Backtest ejecuta sin errores | ✓ |
| 4 | IBKR paper conectado | ✓ |
| 5 | HMM detecta régimen | ✓ |
| 5 | mcp-ml-models responde | ✓ |
| 5 | ECE < 0.15 | ✓ |

### 2.2 Componentes Requeridos

| Componente | Fuente | Estado esperado |
|------------|--------|-----------------|
| PostgreSQL + TimescaleDB | Fase 0 | Running, schemas OK |
| Redis | Fase 0 | Running, pub/sub OK |
| Feature Store | Fase 1 | 30+ features actualizados |
| MCP Servers (5) | Fase 2 | Todos respondiendo |
| Agentes Core | Fase 3 | Orchestrator + Risk Manager OK |
| Estrategias | Fase 4 | 2 estrategias registradas |
| HMM Régimen | Fase 5 | Modelo entrenado y sirviendo |

---

## 3. Arquitectura de Integración

### 3.1 Flujo End-to-End

Referencia: Doc 1, sección 6.1

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUJO DE TRADING                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐       │
│  │ Yahoo/   │───▶│ Feature  │───▶│ Technical│───▶│ Strategy │       │
│  │ IBKR API │    │  Store   │    │  Agent   │    │ Manager  │       │
│  └──────────┘    └──────────┘    └──────────┘    └────┬─────┘       │
│                                                        │             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐         │             │
│  │   HMM    │───▶│  Regime  │───▶│ Strategy │◀────────┘             │
│  │  Model   │    │ Detector │    │  Filter  │                       │
│  └──────────┘    └──────────┘    └────┬─────┘                       │
│                                        │                             │
│                                        ▼                             │
│                               ┌──────────────┐                       │
│                               │ ORCHESTRATOR │                       │
│                               └───────┬──────┘                       │
│                                       │                              │
│                    ┌──────────────────┼──────────────────┐          │
│                    ▼                  ▼                  ▼          │
│             ┌──────────┐       ┌──────────┐       ┌──────────┐      │
│             │   Risk   │       │ Position │       │   Kill   │      │
│             │ Manager  │       │  Sizer   │       │  Switch  │      │
│             └────┬─────┘       └────┬─────┘       └────┬─────┘      │
│                  │                  │                  │             │
│                  └────────┬─────────┘                  │             │
│                           ▼                            │             │
│                    ┌──────────┐                        │             │
│                    │Execution │◀───────────────────────┘             │
│                    │  Agent   │                                      │
│                    └────┬─────┘                                      │
│                         │                                            │
│                         ▼                                            │
│                    ┌──────────┐                                      │
│                    │   IBKR   │                                      │
│                    │  Paper   │                                      │
│                    └──────────┘                                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Modos del Sistema

Referencia: Doc 1, sección 5.3; Doc 6, sección 6.2

| Modo | Descripción | Entradas | Salidas | Trigger |
|------|-------------|----------|---------|---------|
| `NORMAL` | Operativa completa | ✓ | ✓ | Default |
| `DEFENSIVE` | Exposición 50%, solo conf >0.7 | Limitadas | ✓ | DD>10%, ECE>0.15 |
| `OBSERVATION` | Señales sin ejecutar | ✗ | ✓ | Fallo parcial |
| `PAUSE` | Solo gestiona existentes | ✗ | ✓ | Kill switch manual |
| `EMERGENCY` | Cierra todo | ✗ | Forzado | DD>15%, pérdida diaria>3% |

### 3.3 Estructura de Directorios Final

```
trading-bot/
├── src/
│   ├── core/
│   │   ├── orchestrator.py      # Coordinación central
│   │   ├── system_state.py      # Gestión de modos
│   │   └── kill_switch.py       # Kill switch global
│   ├── agents/                  # Fase 3
│   ├── trading/                 # Fase 4
│   ├── ml/                      # Fase 5
│   ├── risk/
│   │   ├── circuit_breakers.py  # Circuit breakers
│   │   └── reconciliation.py    # Reconciliación diaria
│   └── notifications/
│       ├── telegram_bot.py      # Bot Telegram
│       └── alert_manager.py     # Gestión de alertas
├── mcp-servers/                 # Fase 2
├── config/
│   ├── grafana/
│   │   └── dashboards/          # JSONs de dashboards
│   ├── prometheus/
│   │   └── alerts.yml           # Reglas de alertas
│   └── alertmanager.yml         # Configuración alertas
├── scripts/
│   ├── verify_integration.py    # Verificación Fase 6
│   └── paper_trading_report.py  # Reporte diario
└── docker-compose.prod.yml      # Producción
```

---

## 4. Tareas de Implementación

### Bloque 1: Integración de Componentes

---

### Tarea 6.1: Implementar System State Manager

**Estado:** ⬜ Pendiente

**Objetivo:** Gestión centralizada del modo del sistema.

**Referencias:** Doc 1 sec 5.3, Doc 6 sec 6.2

**Subtareas:**
- [ ] Crear clase `SystemState` con máquina de estados
- [ ] Implementar transiciones válidas entre modos
- [ ] Persistir estado en Redis
- [ ] Exponer estado via API y MCP

**Input:** Triggers de cambio de modo (drawdown, errores, manual)

**Output:** Estado actual accesible por todos los componentes

**Pseudocódigo:**
```python
# src/core/system_state.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class SystemMode(Enum):
    NORMAL = "normal"
    DEFENSIVE = "defensive"
    OBSERVATION = "observation"
    PAUSE = "pause"
    EMERGENCY = "emergency"

VALID_TRANSITIONS = {
    SystemMode.NORMAL: [SystemMode.DEFENSIVE, SystemMode.OBSERVATION, 
                        SystemMode.PAUSE, SystemMode.EMERGENCY],
    SystemMode.DEFENSIVE: [SystemMode.NORMAL, SystemMode.OBSERVATION,
                           SystemMode.PAUSE, SystemMode.EMERGENCY],
    SystemMode.OBSERVATION: [SystemMode.NORMAL, SystemMode.DEFENSIVE,
                             SystemMode.PAUSE, SystemMode.EMERGENCY],
    SystemMode.PAUSE: [SystemMode.NORMAL, SystemMode.OBSERVATION],
    SystemMode.EMERGENCY: [SystemMode.PAUSE]  # Solo via PAUSE
}

@dataclass
class SystemState:
    mode: SystemMode
    changed_at: datetime
    reason: str
    changed_by: str  # "auto" | "manual" | component name

class SystemStateManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self._state = self._load_state()
    
    def _load_state(self) -> SystemState:
        # Cargar de Redis o default NORMAL
        pass
    
    def can_transition(self, target: SystemMode) -> bool:
        return target in VALID_TRANSITIONS.get(self._state.mode, [])
    
    def transition(self, target: SystemMode, reason: str, 
                   by: str = "auto") -> bool:
        # 1. Validar transición permitida
        # 2. Actualizar estado
        # 3. Persistir en Redis
        # 4. Publicar evento system:mode_changed
        # 5. Log en audit.system_events
        pass
    
    @property
    def mode(self) -> SystemMode:
        return self._state.mode
    
    def allows_new_entries(self) -> bool:
        return self._state.mode in [SystemMode.NORMAL, SystemMode.DEFENSIVE]
    
    def allows_exits(self) -> bool:
        return self._state.mode != SystemMode.EMERGENCY
```

**Validación:** 
```python
# Test de transiciones
manager = SystemStateManager(redis)
assert manager.mode == SystemMode.NORMAL
assert manager.can_transition(SystemMode.DEFENSIVE)
assert not manager.can_transition(SystemMode.PAUSE)  # EMERGENCY no va directo a PAUSE
```

---

### Tarea 6.2: Integrar Orchestrator Completo

**Estado:** ⬜ Pendiente

**Objetivo:** Orchestrator consume señales y coordina ejecución.

**Referencias:** Doc 1 sec 4.1, Doc 3 sec 3

**Subtareas:**
- [ ] Suscribir a canal Redis `signals:*`
- [ ] Consultar régimen antes de procesar señal
- [ ] Validar con Risk Manager
- [ ] Calcular sizing con Position Sizer
- [ ] Enviar a Execution Agent
- [ ] Log completo en audit.decisions

**Input:** Señales de estrategias via Redis pub/sub

**Output:** Órdenes ejecutadas o rechazadas con razón

**Pseudocódigo:**
```python
# src/core/orchestrator.py
class Orchestrator:
    def __init__(self, system_state, risk_manager, position_sizer,
                 execution_agent, mcp_clients):
        self.state = system_state
        self.risk = risk_manager
        self.sizer = position_sizer
        self.executor = execution_agent
        self.mcp = mcp_clients
    
    async def run(self):
        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("signals:*")
        
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                signal = Signal.from_json(message["data"])
                await self.process_signal(signal)
    
    async def process_signal(self, signal: Signal):
        decision = DecisionLog(signal=signal, timestamp=datetime.utcnow())
        
        # 1. Check sistema permite entradas
        if not self.state.allows_new_entries():
            decision.action = "rejected"
            decision.reason = f"System in {self.state.mode} mode"
            await self._log_decision(decision)
            return
        
        # 2. Check régimen compatible
        regime = await self.mcp["ml"].call("get_regime", {})
        if not self._is_regime_compatible(signal.strategy_id, regime):
            decision.action = "rejected"
            decision.reason = f"Regime {regime['state']} incompatible"
            await self._log_decision(decision)
            return
        
        # 3. Validación de riesgo
        risk_check = await self.risk.validate(signal)
        decision.risk_check = risk_check
        
        if not risk_check.approved:
            decision.action = "rejected"
            decision.reason = risk_check.reason
            await self._log_decision(decision)
            return
        
        # 4. Position sizing
        size = await self.sizer.calculate(
            signal=signal,
            capital=await self._get_available_capital(),
            risk_per_trade=0.01,
            regime_multiplier=regime.get("sizing_mult", 1.0)
        )
        
        if size.quantity == 0:
            decision.action = "skipped"
            decision.reason = "Size too small"
            await self._log_decision(decision)
            return
        
        # 5. Ejecutar
        order = await self.executor.submit_order(
            symbol=signal.symbol,
            side=signal.direction,
            quantity=size.quantity,
            order_type="LIMIT",
            limit_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )
        
        decision.action = "executed"
        decision.order_id = order.id
        await self._log_decision(decision)
```

**Validación:** Señal de prueba fluye hasta orden en IBKR paper.

---

### Tarea 6.3: Implementar Reconciliación Diaria

**Estado:** ⬜ Pendiente

**Objetivo:** Verificar consistencia entre BD y broker.

**Referencias:** Doc 2 sec 8.2, Doc 6 sec 9.1

**Subtareas:**
- [ ] Scheduler para ejecutar post-mercado (18:30 CET)
- [ ] Fetch posiciones de IBKR via mcp-ibkr
- [ ] Comparar con `trading.positions`
- [ ] Alertar si discrepancia > 0.1%
- [ ] Log resultado en audit

**Input:** Posiciones en BD y posiciones en broker

**Output:** Resultado de reconciliación, alerta si discrepancia

**Pseudocódigo:**
```python
# src/risk/reconciliation.py
from decimal import Decimal

class ReconciliationResult:
    def __init__(self):
        self.matches = []
        self.discrepancies = []
        self.missing_in_db = []
        self.missing_in_broker = []
    
    @property
    def is_clean(self) -> bool:
        return not (self.discrepancies or 
                    self.missing_in_db or 
                    self.missing_in_broker)

async def run_daily_reconciliation(db, mcp_ibkr, alert_manager):
    # 1. Obtener posiciones de broker
    broker_positions = await mcp_ibkr.call("get_positions", {})
    
    # 2. Obtener posiciones de BD
    db_positions = await db.fetch("""
        SELECT symbol, quantity, avg_entry_price 
        FROM trading.positions 
        WHERE quantity != 0
    """)
    
    result = ReconciliationResult()
    
    # 3. Comparar
    broker_map = {p["symbol"]: p for p in broker_positions}
    db_map = {p["symbol"]: p for p in db_positions}
    
    all_symbols = set(broker_map.keys()) | set(db_map.keys())
    
    for symbol in all_symbols:
        broker_pos = broker_map.get(symbol)
        db_pos = db_map.get(symbol)
        
        if broker_pos and not db_pos:
            result.missing_in_db.append(symbol)
        elif db_pos and not broker_pos:
            result.missing_in_broker.append(symbol)
        else:
            # Comparar cantidades
            broker_qty = Decimal(str(broker_pos["quantity"]))
            db_qty = Decimal(str(db_pos["quantity"]))
            
            diff_pct = abs(broker_qty - db_qty) / max(abs(broker_qty), 1)
            
            if diff_pct > Decimal("0.001"):  # 0.1%
                result.discrepancies.append({
                    "symbol": symbol,
                    "broker": broker_qty,
                    "db": db_qty,
                    "diff_pct": float(diff_pct)
                })
            else:
                result.matches.append(symbol)
    
    # 4. Log y alertar
    await log_reconciliation(result)
    
    if not result.is_clean:
        await alert_manager.send(
            severity="CRITICAL",
            message=f"Reconciliation failed: {len(result.discrepancies)} discrepancies"
        )
    
    return result
```

**Validación:** Ejecutar manualmente, verificar que coinciden posiciones.

---

### Bloque 2: Kill Switch y Circuit Breakers

---

### Tarea 6.4: Implementar Kill Switch

**Estado:** ⬜ Pendiente

**Objetivo:** Cierre de emergencia automático y manual.

**Referencias:** Doc 1 sec 5.1, Doc 6 sec 6.3

**Subtareas:**
- [ ] Triggers automáticos (DD>15%, pérdida diaria>3%, semanal>5%)
- [ ] Comando manual via Telegram y API
- [ ] Cerrar todas las posiciones con market orders
- [ ] Transicionar a modo EMERGENCY
- [ ] Bloquear reactivación automática

**Input:** Métricas de riesgo o comando manual

**Output:** Posiciones cerradas, sistema en EMERGENCY

**Pseudocódigo:**
```python
# src/core/kill_switch.py
class KillSwitch:
    def __init__(self, system_state, execution_agent, alert_manager):
        self.state = system_state
        self.executor = execution_agent
        self.alerts = alert_manager
        self._triggered = False
    
    async def check_auto_triggers(self, metrics: dict):
        """Llamado cada minuto por el monitor"""
        triggers = []
        
        if metrics.get("drawdown_pct", 0) > 0.15:
            triggers.append(f"Drawdown {metrics['drawdown_pct']:.1%} > 15%")
        
        if metrics.get("daily_loss_pct", 0) > 0.03:
            triggers.append(f"Daily loss {metrics['daily_loss_pct']:.1%} > 3%")
        
        if metrics.get("weekly_loss_pct", 0) > 0.05:
            triggers.append(f"Weekly loss {metrics['weekly_loss_pct']:.1%} > 5%")
        
        if triggers:
            await self.activate(
                reason="; ".join(triggers),
                triggered_by="auto"
            )
    
    async def activate(self, reason: str, triggered_by: str = "manual"):
        if self._triggered:
            return  # Ya activado
        
        self._triggered = True
        
        # 1. Transicionar a EMERGENCY
        await self.state.transition(
            SystemMode.EMERGENCY,
            reason=f"Kill switch: {reason}",
            by=triggered_by
        )
        
        # 2. Alerta inmediata
        await self.alerts.send(
            severity="CRITICAL",
            message=f"🚨 KILL SWITCH ACTIVATED\nReason: {reason}"
        )
        
        # 3. Cerrar todas las posiciones
        positions = await self._get_open_positions()
        
        for pos in positions:
            try:
                await self.executor.submit_order(
                    symbol=pos["symbol"],
                    side="sell" if pos["quantity"] > 0 else "buy",
                    quantity=abs(pos["quantity"]),
                    order_type="MARKET"
                )
            except Exception as e:
                await self.alerts.send(
                    severity="CRITICAL",
                    message=f"Failed to close {pos['symbol']}: {e}"
                )
        
        # 4. Log en audit
        await self._log_kill_switch(reason, triggered_by, positions)
    
    async def reset(self, confirmed_by: str):
        """Solo manual, requiere confirmación explícita"""
        if not self._triggered:
            return
        
        # Verificar que no hay condiciones de trigger activas
        metrics = await self._get_current_metrics()
        if metrics.get("drawdown_pct", 0) > 0.10:
            raise ValueError("Cannot reset: drawdown still > 10%")
        
        self._triggered = False
        
        # Transicionar a PAUSE (no directo a NORMAL)
        await self.state.transition(
            SystemMode.PAUSE,
            reason=f"Kill switch reset by {confirmed_by}",
            by="manual"
        )
```

**Validación:** Simular DD>15% en paper, verificar cierre automático.

---

### Tarea 6.5: Implementar Circuit Breakers

**Estado:** ⬜ Pendiente

**Objetivo:** Protección por componente con degradación controlada.

**Referencias:** Doc 1 sec 5.2, Doc 6 sec 6.1

**Subtareas:**
- [ ] Circuit breaker para data feed precios
- [ ] Circuit breaker para data feed noticias
- [ ] Circuit breaker para conexión broker
- [ ] Circuit breaker para modelos ML
- [ ] Máquina de estados: CLOSED → OPEN → HALF_OPEN

**Input:** Health checks de cada componente

**Output:** Estado de breaker, acciones degradadas

**Pseudocódigo:**
```python
# src/risk/circuit_breakers.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timedelta

class BreakerState(Enum):
    CLOSED = "closed"    # Normal
    OPEN = "open"        # Fallando
    HALF_OPEN = "half_open"  # Probando recuperación

@dataclass
class BreakerConfig:
    name: str
    failure_threshold: int  # Fallos para abrir
    recovery_timeout: int   # Segundos para probar HALF_OPEN
    success_threshold: int  # Éxitos en HALF_OPEN para cerrar

class CircuitBreaker:
    def __init__(self, config: BreakerConfig):
        self.config = config
        self.state = BreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def record_success(self):
        if self.state == BreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = BreakerState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == BreakerState.CLOSED:
            self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.state == BreakerState.HALF_OPEN:
            self.state = BreakerState.OPEN
            self.success_count = 0
        elif self.state == BreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self.state = BreakerState.OPEN
    
    def can_execute(self) -> bool:
        if self.state == BreakerState.CLOSED:
            return True
        
        if self.state == BreakerState.OPEN:
            # Check si pasó recovery_timeout
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).seconds
                if elapsed >= self.config.recovery_timeout:
                    self.state = BreakerState.HALF_OPEN
                    return True
            return False
        
        # HALF_OPEN: permitir un intento
        return True

# Configuraciones predefinidas
BREAKER_CONFIGS = {
    "data_feed_prices": BreakerConfig(
        name="data_feed_prices",
        failure_threshold=3,      # 3 fallos en 5 min
        recovery_timeout=300,     # 5 min para retry
        success_threshold=2
    ),
    "data_feed_news": BreakerConfig(
        name="data_feed_news",
        failure_threshold=5,
        recovery_timeout=600,     # 10 min
        success_threshold=2
    ),
    "broker_connection": BreakerConfig(
        name="broker_connection",
        failure_threshold=2,      # Crítico, menos tolerancia
        recovery_timeout=120,     # 2 min
        success_threshold=3
    ),
    "ml_models": BreakerConfig(
        name="ml_models",
        failure_threshold=3,
        recovery_timeout=60,
        success_threshold=2
    )
}

class CircuitBreakerManager:
    def __init__(self, system_state, alert_manager):
        self.state = system_state
        self.alerts = alert_manager
        self.breakers = {
            name: CircuitBreaker(config)
            for name, config in BREAKER_CONFIGS.items()
        }
    
    async def check_component(self, name: str, check_fn) -> bool:
        breaker = self.breakers.get(name)
        if not breaker:
            return True
        
        if not breaker.can_execute():
            return False
        
        try:
            result = await check_fn()
            if result:
                breaker.record_success()
                return True
            else:
                await self._handle_failure(name, breaker)
                return False
        except Exception as e:
            await self._handle_failure(name, breaker, str(e))
            return False
    
    async def _handle_failure(self, name: str, breaker: CircuitBreaker, 
                               error: str = None):
        was_closed = breaker.state == BreakerState.CLOSED
        breaker.record_failure()
        
        if was_closed and breaker.state == BreakerState.OPEN:
            await self.alerts.send(
                severity="ERROR",
                message=f"Circuit breaker OPEN: {name}"
            )
            await self._apply_degraded_mode(name)
    
    async def _apply_degraded_mode(self, component: str):
        """Aplicar modo degradado según componente"""
        if component == "data_feed_prices":
            # Pausar nuevas entradas, mantener stops
            await self.state.transition(
                SystemMode.OBSERVATION,
                reason="Data feed prices unavailable",
                by="circuit_breaker"
            )
        elif component == "broker_connection":
            await self.alerts.send(
                severity="CRITICAL",
                message="Broker disconnected - manual intervention required"
            )
        elif component == "ml_models":
            # Continuar sin ML, más conservador
            pass  # Risk Manager ajusta automáticamente
```

**Validación:** Simular caída de data feed, verificar transición a OBSERVATION.

---

### Bloque 3: Dashboard Grafana Completo

---

### Tarea 6.6: Crear Dashboard Overview

**Estado:** ⬜ Pendiente

**Objetivo:** Vista principal del estado del sistema.

**Referencias:** Doc 7 sec 4.3

**Subtareas:**
- [ ] Panel de P&L diario/semanal/mensual
- [ ] Panel de drawdown actual
- [ ] Panel de posiciones abiertas
- [ ] Panel de estado del sistema (modo actual)
- [ ] Panel de conexiones (broker, data feeds)

**Input:** Métricas de InfluxDB y PostgreSQL

**Output:** Dashboard JSON provisionado

**Estructura del dashboard:**
```
┌─────────────────────────────────────────────────────────────┐
│                    TRADING BOT - OVERVIEW                    │
├─────────────────────────────────────────────────────────────┤
│ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐       │
│ │   P&L Today   │ │  P&L Week     │ │  P&L Month    │       │
│ │   +1.2%       │ │  +3.5%        │ │  +8.2%        │       │
│ └───────────────┘ └───────────────┘ └───────────────┘       │
│                                                              │
│ ┌─────────────────────────────────┐ ┌───────────────────┐   │
│ │      Drawdown (30 days)         │ │   System Mode     │   │
│ │  [=========>          ] 6.2%    │ │   🟢 NORMAL       │   │
│ └─────────────────────────────────┘ └───────────────────┘   │
│                                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │                    Open Positions                        │ │
│ │  Symbol  │ Side │ Qty  │ Entry │ Current │ P&L          │ │
│ │  SAN.MC  │ LONG │  50  │ 3.45  │  3.52   │ +2.0%        │ │
│ │  BBVA.MC │ LONG │  30  │ 8.12  │  8.05   │ -0.9%        │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ ┌────────────────────────┐ ┌────────────────────────┐       │
│ │ Broker: 🟢 Connected   │ │ Data Feed: 🟢 OK       │       │
│ │ Account: Paper         │ │ Last update: 2s ago   │       │
│ └────────────────────────┘ └────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

**Queries de ejemplo:**
```sql
-- P&L diario (PostgreSQL)
SELECT 
    SUM(realized_pnl + unrealized_pnl) as total_pnl,
    SUM(realized_pnl + unrealized_pnl) / 
        LAG(SUM(realized_pnl + unrealized_pnl)) OVER (ORDER BY date) - 1 as pnl_pct
FROM daily_snapshots
WHERE date >= CURRENT_DATE

-- Drawdown (InfluxDB Flux)
from(bucket: "trading")
  |> range(start: -30d)
  |> filter(fn: (r) => r._measurement == "portfolio")
  |> filter(fn: (r) => r._field == "drawdown_pct")
```

**Validación:** Dashboard visible con datos reales de paper trading.

---

### Tarea 6.7: Crear Dashboard Trading

**Estado:** ⬜ Pendiente

**Objetivo:** Métricas operativas de trading.

**Referencias:** Doc 7 sec 4.3

**Subtareas:**
- [ ] Panel de órdenes por día (ejecutadas/rechazadas)
- [ ] Panel de fill rate
- [ ] Panel de slippage promedio
- [ ] Panel de distribución de trades por estrategia
- [ ] Panel de señales generadas vs ejecutadas

**Paneles principales:**

| Panel | Tipo | Query |
|-------|------|-------|
| Órdenes/día | Bar chart | `SELECT date, COUNT(*) FROM orders GROUP BY date` |
| Fill rate | Gauge | `filled_orders / total_orders * 100` |
| Slippage | Time series | `avg(slippage_pct) GROUP BY hour` |
| Por estrategia | Pie chart | `COUNT(*) GROUP BY strategy_id` |

**Validación:** Datos de paper trading visibles en gráficos.

---

### Tarea 6.8: Crear Dashboard Risk

**Estado:** ⬜ Pendiente

**Objetivo:** Visualización de métricas de riesgo.

**Referencias:** Doc 6 sec 9, Doc 7 sec 4.3

**Subtareas:**
- [ ] Panel de exposición por sector
- [ ] Panel de exposición por divisa
- [ ] Panel de correlación entre posiciones
- [ ] Panel de VaR diario
- [ ] Panel de histórico de drawdown

**Paneles principales:**

| Panel | Tipo | Alerta si |
|-------|------|-----------|
| Exposición total | Gauge | > 90% |
| Por sector | Stacked bar | Sector > 40% |
| Correlación max | Gauge | > 0.7 |
| VaR 1d | Stat | > 2% capital |
| Drawdown | Time series + threshold | > 10% |

---

### Tarea 6.9: Crear Dashboard System

**Estado:** ⬜ Pendiente

**Objetivo:** Health de infraestructura.

**Referencias:** Doc 7 sec 4.2

**Subtareas:**
- [ ] Panel de CPU/RAM por servicio
- [ ] Panel de latencias de API
- [ ] Panel de errores por componente
- [ ] Panel de estado de circuit breakers
- [ ] Panel de conexiones de BD

**Queries (Prometheus):**
```promql
# CPU por servicio
rate(process_cpu_seconds_total{job="trading-core"}[5m]) * 100

# Latencia de API
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Errores
sum(rate(http_requests_total{status=~"5.."}[5m])) by (service)
```

---

### Tarea 6.10: Crear Dashboard ML

**Estado:** ⬜ Pendiente

**Objetivo:** Monitoreo de modelos ML.

**Referencias:** Doc 5 sec 6, Doc 7 sec 4.3

**Subtareas:**
- [ ] Panel de régimen actual y probabilidades
- [ ] Panel de ECE (calibración) rolling
- [ ] Panel de feature drift detection
- [ ] Panel de predicciones vs resultados reales
- [ ] Panel de tiempo desde último retrain

**Paneles principales:**

| Panel | Tipo | Alerta si |
|-------|------|-----------|
| Régimen | Stat + history | - |
| ECE | Time series | > 0.10 (warn), > 0.15 (crit) |
| Feature drift | Heatmap | >20% features con drift |
| Accuracy | Gauge | < 50% |

---

### Bloque 4: Sistema de Alertas Telegram

---

### Tarea 6.11: Configurar Bot Telegram

**Estado:** ⬜ Pendiente

**Objetivo:** Bot para alertas y comandos.

**Referencias:** Doc 7 sec 5, Doc 6 sec 9.2

**Subtareas:**
- [ ] Crear bot con @BotFather
- [ ] Configurar chat_id autorizado
- [ ] Implementar handler de comandos
- [ ] Integrar con AlertManager

**Comandos a implementar:**

| Comando | Acción | Respuesta |
|---------|--------|-----------|
| `/status` | Estado del sistema | Modo, P&L, posiciones |
| `/positions` | Listar posiciones | Tabla de posiciones abiertas |
| `/pause` | Activar modo PAUSE | Confirmación |
| `/resume` | Volver a NORMAL | Confirmación (requiere PIN) |
| `/killswitch` | Activar kill switch | Confirmación (requiere PIN) |
| `/help` | Lista de comandos | Menú |

**Pseudocódigo:**
```python
# src/notifications/telegram_bot.py
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler

class TradingBot:
    def __init__(self, token: str, authorized_chat_id: int,
                 system_state, kill_switch, db):
        self.bot = Bot(token)
        self.chat_id = authorized_chat_id
        self.state = system_state
        self.kill_switch = kill_switch
        self.db = db
        self.security_pin = os.environ.get("TELEGRAM_PIN")
    
    async def cmd_status(self, update: Update, context):
        if update.effective_chat.id != self.chat_id:
            return  # Ignorar chats no autorizados
        
        mode = self.state.mode.value
        pnl = await self._get_today_pnl()
        positions = await self._get_position_count()
        
        await update.message.reply_text(
            f"🤖 *Trading Bot Status*\n\n"
            f"Mode: {mode.upper()}\n"
            f"P&L Today: {pnl:+.2%}\n"
            f"Open Positions: {positions}\n"
            f"Last Update: {datetime.now().strftime('%H:%M:%S')}",
            parse_mode="Markdown"
        )
    
    async def cmd_killswitch(self, update: Update, context):
        if update.effective_chat.id != self.chat_id:
            return
        
        # Requiere PIN: /killswitch 1234
        if not context.args or context.args[0] != self.security_pin:
            await update.message.reply_text(
                "⚠️ PIN required: /killswitch <PIN>"
            )
            return
        
        await self.kill_switch.activate(
            reason="Manual activation via Telegram",
            triggered_by="telegram"
        )
        
        await update.message.reply_text(
            "🚨 KILL SWITCH ACTIVATED\n"
            "All positions being closed..."
        )
    
    async def send_alert(self, severity: str, message: str):
        """Enviar alerta proactiva"""
        emoji = {"INFO": "ℹ️", "WARNING": "⚠️", 
                 "ERROR": "❌", "CRITICAL": "🚨"}
        
        await self.bot.send_message(
            chat_id=self.chat_id,
            text=f"{emoji.get(severity, '📢')} *{severity}*\n\n{message}",
            parse_mode="Markdown"
        )
    
    def run(self):
        app = Application.builder().token(self.token).build()
        
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("positions", self.cmd_positions))
        app.add_handler(CommandHandler("pause", self.cmd_pause))
        app.add_handler(CommandHandler("resume", self.cmd_resume))
        app.add_handler(CommandHandler("killswitch", self.cmd_killswitch))
        app.add_handler(CommandHandler("help", self.cmd_help))
        
        app.run_polling()
```

**Validación:** `/status` responde con información correcta.

---

### Tarea 6.12: Configurar Alertas por Severidad

**Estado:** ⬜ Pendiente

**Objetivo:** Routing de alertas según severidad.

**Referencias:** Doc 7 sec 5.1-5.2, Doc 6 sec 9.2

**Subtareas:**
- [ ] Configurar AlertManager con rutas por severidad
- [ ] INFO: Solo log
- [ ] WARNING: Telegram
- [ ] ERROR: Telegram + delay 1h para re-envío
- [ ] CRITICAL: Telegram + Email + retry 15min

**alertmanager.yml:**
```yaml
global:
  resolve_timeout: 5m

route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      repeat_interval: 15m
      continue: true
    
    - match:
        severity: error
      receiver: 'telegram'
      repeat_interval: 1h
    
    - match:
        severity: warning
      receiver: 'telegram'
      repeat_interval: 4h

receivers:
  - name: 'default'
    # Solo log, no notificación
    
  - name: 'telegram'
    webhook_configs:
      - url: 'http://trading-core:8000/webhooks/alertmanager'
        send_resolved: true
  
  - name: 'critical'
    webhook_configs:
      - url: 'http://trading-core:8000/webhooks/alertmanager'
        send_resolved: true
    email_configs:
      - to: '${ALERT_EMAIL}'
        from: 'trading-alerts@${DOMAIN}'
        smarthost: 'smtp.gmail.com:587'
        auth_username: '${SMTP_USER}'
        auth_password: '${SMTP_PASS}'
```

**Validación:** Generar alerta de prueba, verificar llegada a Telegram.

---

### Bloque 5: Paper Trading y Validación

---

### Tarea 6.13: Configurar Paper Trading Continuo

**Estado:** ⬜ Pendiente

**Objetivo:** Sistema operando autónomo en paper.

**Referencias:** Doc 4 sec 6, Doc 7 sec 10

**Subtareas:**
- [ ] Configurar scheduler para operativa en horario de mercado
- [ ] Verificar reconexión automática tras desconexiones
- [ ] Configurar reporte diario automático
- [ ] Habilitar todas las estrategias en modo paper

**Horarios de operación (CET):**

| Mercado | Apertura | Cierre | Estrategias |
|---------|----------|--------|-------------|
| EU (IBEX, DAX) | 09:00 | 17:30 | swing_momentum_eu |
| Forex | 24h | 24h | (futuro) |

**Scheduler:**
```python
# src/core/scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

def setup_scheduler(orchestrator, reconciliation, report_generator):
    scheduler = AsyncIOScheduler(timezone="Europe/Madrid")
    
    # Pre-mercado: verificar conexiones
    scheduler.add_job(
        orchestrator.pre_market_check,
        CronTrigger(hour=8, minute=45, day_of_week='mon-fri')
    )
    
    # Inicio de mercado: activar operativa
    scheduler.add_job(
        orchestrator.start_trading,
        CronTrigger(hour=9, minute=0, day_of_week='mon-fri')
    )
    
    # Cierre de mercado: pausar entradas
    scheduler.add_job(
        orchestrator.stop_new_entries,
        CronTrigger(hour=17, minute=30, day_of_week='mon-fri')
    )
    
    # Reconciliación diaria
    scheduler.add_job(
        reconciliation.run,
        CronTrigger(hour=18, minute=30, day_of_week='mon-fri')
    )
    
    # Reporte diario
    scheduler.add_job(
        report_generator.daily_report,
        CronTrigger(hour=19, minute=0, day_of_week='mon-fri')
    )
    
    return scheduler
```

---

### Tarea 6.14: Implementar Reporte Diario

**Estado:** ⬜ Pendiente

**Objetivo:** Resumen automático de cada día de trading.

**Subtareas:**
- [ ] Calcular métricas del día
- [ ] Generar resumen en formato texto
- [ ] Enviar via Telegram
- [ ] Guardar en BD para histórico

**Formato del reporte:**
```
📊 DAILY REPORT - 2024-12-15

Performance:
• P&L: +45.20€ (+0.45%)
• Trades: 3 executed, 1 rejected
• Win Rate: 66.7% (2/3)

Risk:
• Max Drawdown: 2.1%
• Current Exposure: 35%
• Regime: TRENDING_BULL

Positions:
• SAN.MC: +1.2% (LONG, 2 days)
• BBVA.MC: -0.5% (LONG, 1 day)

System:
• Mode: NORMAL
• Uptime: 100%
• Alerts: 0 critical, 1 warning

Tomorrow:
• No economic events scheduled
```

---

### Tarea 6.15: Ejecutar Validación de 30 Días

**Estado:** ⬜ Pendiente

**Objetivo:** Operar 30 días sin alertas críticas.

**Referencias:** Roadmap sec 4.1, Doc 4 sec 6.1

**Criterios de éxito:**

| Métrica | Target |
|---------|--------|
| Días operados | ≥ 30 |
| Alertas críticas | 0 |
| Sharpe (30d) | > 0.5 |
| Max Drawdown | < 15% |
| Win Rate | > 45% |
| Uptime sistema | > 99% |
| Reconciliaciones OK | 100% |

**Checklist diario durante validación:**

```markdown
## Día X/30 - YYYY-MM-DD

### Pre-mercado
- [ ] Sistema en modo NORMAL
- [ ] Conexión broker OK
- [ ] Data feed activo
- [ ] Sin alertas pendientes

### Post-mercado
- [ ] Revisado P&L
- [ ] Reconciliación OK
- [ ] Revisadas órdenes ejecutadas
- [ ] Sin errores en logs
- [ ] Backup completado

### Métricas acumuladas
- P&L total: ___
- Sharpe actual: ___
- Max DD alcanzado: ___
- Trades totales: ___
```

**Decisión al finalizar:**

| Resultado | Acción |
|-----------|--------|
| Pasa todos los criterios | Considerar transición a Pilot (capital real pequeño) |
| Falla 1 criterio menor | Extender 15 días más |
| Falla criterio mayor | Revisar, corregir, reiniciar 30 días |

---

## 5. Script de Verificación

### `scripts/verify_integration.py`

```python
#!/usr/bin/env python3
"""Verificación completa de Fase 6: Integración"""

import asyncio
from datetime import datetime

CHECKS = [
    ("Prerequisites: Fase 4", check_fase4),
    ("Prerequisites: Fase 5", check_fase5),
    ("System State Manager", check_system_state),
    ("Orchestrator Integration", check_orchestrator),
    ("Kill Switch", check_kill_switch),
    ("Circuit Breakers", check_circuit_breakers),
    ("Reconciliation", check_reconciliation),
    ("Grafana Dashboards", check_dashboards),
    ("Telegram Bot", check_telegram),
    ("Alert Routing", check_alerts),
    ("End-to-End Flow", check_e2e_flow),
]

async def check_fase4():
    """Verificar que Fase 4 está OK"""
    result = await run_script("scripts/verify_trading.py")
    if result.returncode == 0:
        return True, "Fase 4 verified"
    return False, "Fase 4 verification failed"

async def check_fase5():
    """Verificar que Fase 5 está OK"""
    result = await run_script("scripts/verify_ml.py")
    if result.returncode == 0:
        return True, "Fase 5 verified"
    return False, "Fase 5 verification failed"

async def check_system_state():
    """Verificar System State Manager"""
    redis = get_redis()
    
    # Verificar estado en Redis
    state = await redis.get("system:state")
    if not state:
        return False, "No system state in Redis"
    
    state_data = json.loads(state)
    if state_data.get("mode") not in ["normal", "defensive", "observation", 
                                        "pause", "emergency"]:
        return False, f"Invalid mode: {state_data.get('mode')}"
    
    return True, f"System in {state_data['mode']} mode"

async def check_orchestrator():
    """Verificar que Orchestrator procesa señales"""
    redis = get_redis()
    
    # Publicar señal de prueba
    test_signal = {
        "strategy_id": "test",
        "symbol": "TEST.XX",
        "direction": "long",
        "confidence": 0.8,
        "entry_price": 10.0,
        "stop_loss": 9.5,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await redis.publish("signals:test", json.dumps(test_signal))
    
    # Esperar procesamiento
    await asyncio.sleep(2)
    
    # Verificar log de decisión
    decision = await db.fetchrow("""
        SELECT * FROM audit.decisions 
        WHERE symbol = 'TEST.XX' 
        ORDER BY timestamp DESC LIMIT 1
    """)
    
    if decision:
        return True, f"Signal processed: {decision['final_action']}"
    return False, "Signal not processed"

async def check_kill_switch():
    """Verificar Kill Switch responde"""
    # Verificar endpoint de activación manual
    response = await http_client.post(
        "http://localhost:8000/api/kill-switch/test",
        json={"dry_run": True}
    )
    
    if response.status_code == 200:
        return True, "Kill switch endpoint OK"
    return False, f"Kill switch error: {response.status_code}"

async def check_circuit_breakers():
    """Verificar Circuit Breakers configurados"""
    redis = get_redis()
    
    breakers = ["data_feed_prices", "data_feed_news", 
                "broker_connection", "ml_models"]
    
    for name in breakers:
        state = await redis.hget("circuit_breakers", name)
        if not state:
            return False, f"Breaker {name} not configured"
    
    return True, f"{len(breakers)} breakers configured"

async def check_reconciliation():
    """Verificar que reconciliación puede ejecutarse"""
    # Ejecutar reconciliación de prueba
    result = await run_reconciliation(dry_run=True)
    
    if result.error:
        return False, f"Reconciliation error: {result.error}"
    
    return True, f"Reconciliation OK: {len(result.matches)} positions matched"

async def check_dashboards():
    """Verificar dashboards de Grafana"""
    dashboards = ["overview", "trading", "risk", "system", "ml"]
    
    for name in dashboards:
        response = await http_client.get(
            f"http://localhost:3000/api/dashboards/uid/{name}"
        )
        if response.status_code != 200:
            return False, f"Dashboard {name} not found"
    
    return True, f"{len(dashboards)} dashboards available"

async def check_telegram():
    """Verificar bot Telegram responde"""
    # Verificar que bot está corriendo
    response = await http_client.get(
        "http://localhost:8000/api/telegram/health"
    )
    
    if response.status_code == 200 and response.json().get("connected"):
        return True, "Telegram bot connected"
    return False, "Telegram bot not connected"

async def check_alerts():
    """Verificar routing de alertas"""
    # Enviar alerta de prueba
    await alert_manager.send(
        severity="INFO",
        message="Integration test alert"
    )
    
    # Verificar en log (INFO no va a Telegram)
    log_entry = await check_log_for("Integration test alert")
    
    if log_entry:
        return True, "Alert routing OK"
    return False, "Alert not logged"

async def check_e2e_flow():
    """Verificar flujo end-to-end completo"""
    # Este es el test más importante
    
    # 1. Verificar régimen
    regime = await mcp_ml.call("get_regime", {})
    if not regime.get("state"):
        return False, "Cannot get regime"
    
    # 2. Verificar feature store
    features = await redis.hgetall("features:SAN.MC:1d")
    if not features:
        return False, "No features in store"
    
    # 3. Verificar que estrategia puede generar señal
    # (no requiere que genere, solo que no falle)
    try:
        await strategy_manager.evaluate_signals(["SAN.MC"])
    except Exception as e:
        return False, f"Strategy evaluation failed: {e}"
    
    # 4. Verificar conexión broker
    status = await mcp_ibkr.call("get_connection_status", {})
    if not status.get("connected"):
        return False, "Broker not connected"
    
    return True, "End-to-end flow OK"

async def main():
    print("VERIFICACIÓN INTEGRACIÓN - FASE 6")
    print("=" * 50)
    
    all_ok = True
    for name, check_fn in CHECKS:
        try:
            ok, msg = await check_fn()
            status = "✅" if ok else "❌"
            print(f"{status} {name}: {msg}")
            if not ok:
                all_ok = False
        except Exception as e:
            print(f"❌ {name}: Error - {e}")
            all_ok = False
    
    print("=" * 50)
    if all_ok:
        print("✅ FASE 6 VERIFICADA - LISTO PARA PAPER TRADING")
    else:
        print("❌ FASE 6 TIENE ERRORES - REVISAR ANTES DE CONTINUAR")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    exit(asyncio.run(main()))
```

---

## 6. Troubleshooting

### Señales no llegan al Orchestrator

```python
# Verificar pub/sub Redis
redis-cli SUBSCRIBE "signals:*"

# Publicar señal de prueba
redis-cli PUBLISH "signals:test" '{"symbol":"TEST","direction":"long"}'

# Verificar logs del orchestrator
docker-compose logs -f trading-core | grep -i "signal"
```

### Kill Switch no cierra posiciones

```python
# Verificar conexión broker
curl http://localhost:5000/mcp-ibkr/health

# Verificar posiciones abiertas
redis-cli HGETALL "positions:open"

# Forzar cierre manual via TWS si es necesario
```

### Dashboard Grafana vacío

```bash
# Verificar datasources
curl -u admin:${GRAFANA_PASSWORD} \
  http://localhost:3000/api/datasources

# Verificar que Prometheus tiene datos
curl http://localhost:9090/api/v1/query?query=up

# Verificar que InfluxDB tiene datos
influx query 'from(bucket:"trading") |> range(start:-1h)'
```

### Telegram no envía alertas

```python
# Verificar token y chat_id
python -c "
from telegram import Bot
bot = Bot(token='$TELEGRAM_TOKEN')
print(bot.get_me())
"

# Verificar webhook de AlertManager
curl -X POST http://localhost:8000/webhooks/alertmanager \
  -H 'Content-Type: application/json' \
  -d '{"alerts":[{"status":"firing","labels":{"severity":"warning"}}]}'
```

### Reconciliación falla constantemente

```python
# Verificar posiciones en broker
curl http://localhost:5000/mcp-ibkr/positions

# Verificar posiciones en BD
psql -d trading -c "SELECT * FROM trading.positions WHERE quantity != 0"

# Comparar manualmente
# Si hay discrepancia real, sincronizar BD con broker
```

### Sistema en modo EMERGENCY y no sale

```python
# Verificar triggers activos
redis-cli GET "killswitch:triggered"

# Verificar métricas actuales
redis-cli HGETALL "metrics:current"

# Reset manual (requiere intervención)
# 1. Verificar que drawdown < 10%
# 2. Ejecutar reset via API con PIN
curl -X POST http://localhost:8000/api/kill-switch/reset \
  -H 'Authorization: Bearer $PIN'
```

---

## 7. Checklist de Promoción a Producción

### 7.1 Pre-requisitos Técnicos

```markdown
## Verificación Técnica

### Infraestructura
- [ ] 30 días de paper trading completados
- [ ] Cero alertas críticas en 30 días
- [ ] Uptime > 99%
- [ ] Backups funcionando

### Código
- [ ] Tests unitarios pasan
- [ ] Tests de integración pasan
- [ ] verify_integration.py pasa 100%
- [ ] Sin errores en logs últimos 7 días

### Seguridad
- [ ] Secrets en .env, no en código
- [ ] SSH solo con key
- [ ] Firewall configurado
- [ ] 2FA en Grafana
```

### 7.2 Pre-requisitos de Rendimiento

```markdown
## Verificación de Rendimiento

### Métricas de Trading
- [ ] Sharpe Ratio > 0.5 (30 días paper)
- [ ] Max Drawdown < 15%
- [ ] Win Rate > 45%
- [ ] Profit Factor > 1.0

### Métricas Operativas
- [ ] Reconciliación 100% OK
- [ ] Latencia < 500ms para señales
- [ ] Fill rate > 95%
```

### 7.3 Preparación para Producción

```markdown
## Checklist Pre-Live

### Capital
- [ ] Capital de riesgo separado (solo lo que puedes perder)
- [ ] Cuenta IBKR live configurada
- [ ] Límites de riesgo revisados

### Operacional
- [ ] Runbook documentado
- [ ] Contactos de emergencia definidos
- [ ] Kill switch probado
- [ ] Procedure de rollback definido

### Legal/Compliance
- [ ] Entender implicaciones fiscales
- [ ] Verificar no hay restricciones regulatorias
```

### 7.4 Fases de Transición a Live

Referencia: Doc 4, sección 6.2

| Fase | Capital | Duración | Criterio de avance |
|------|---------|----------|-------------------|
| Paper | 0€ (simulado) | 30+ días | Pasa todos los criterios |
| Pilot | 500€ (5% max) | 2 meses | Sin pérdida > 5% |
| Ramp-up | 2000€ (20%) | 2 meses | Sharpe > 0.8 |
| Full | 100% disponible | Indefinido | - |

---

## 8. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Modos del sistema | Doc 1 | 5.3 |
| Kill switch triggers | Doc 1 | 5.1 |
| Circuit breakers | Doc 1 | 5.2, Doc 6 | 6.1 |
| Flujo de trading | Doc 1 | 6.1 |
| Drawdown management | Doc 6 | 5 |
| Reconciliación | Doc 2 | 8.2, Doc 6 | 9.1 |
| Alertas | Doc 6 | 9.2, Doc 7 | 5 |
| Dashboards Grafana | Doc 7 | 4.3 |
| Runbooks | Doc 7 | 6 |
| Checklist operativo | Doc 7 | 10 |
| Paper → Live | Doc 4 | 6 |
| Criterios promoción | Doc 4 | 6.1 |

---

## 9. Conclusión del Roadmap

Una vez completada la Fase 6 y validados los 30 días de paper trading:

**El sistema está listo para:**
1. Considerar transición a Pilot con capital real pequeño
2. Continuar monitoreando y mejorando
3. Añadir estrategias adicionales gradualmente
4. Implementar modelos ML más avanzados (Meta-labeling, TFT)

**Próximos pasos post-Fase 6:**
- Mantener paper trading paralelo a live para comparación
- Evaluar nuevas fuentes de datos (Alpha Vantage, etc.)
- Considerar expansión a otros mercados (US fuera de PDT, Crypto)
- Implementar A/B testing de estrategias

---

*Fase 6 - Integración y Validación*  
*Bot de Trading Autónomo con IA*  
*Documento Final del Roadmap de Implementación*
