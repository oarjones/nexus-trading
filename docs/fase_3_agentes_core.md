# 🤖 Fase 3: Agentes Core

## Documento de Implementación

**Versión:** 1.0  
**Duración estimada:** 4 semanas  
**Dependencias:** Fase 1 + Fase 2 completadas  
**Docs técnicos:** Doc 3 (secciones 3-5, 8), Doc 6 (secciones 2-6)

---

## 1. Objetivos de la Fase

| Objetivo | Criterio de éxito |
|----------|-------------------|
| Clase base Agent funcional | Agentes heredan y se registran correctamente |
| Sistema pub/sub operativo | Mensajes fluyen entre agentes vía Redis |
| Technical Analyst genera señales | Señales con dirección, confianza y niveles |
| Risk Manager valida operaciones | Aprueba/rechaza con sizing ajustado |
| Orchestrator coordina flujo | Recibe señales, consulta Risk, emite decisión |
| Integración end-to-end | Flujo completo señal → validación → decisión |

---

## 2. Arquitectura de Agentes

### 2.1 Jerarquía de Decisiones

Referencia: Doc 3, sección 1.3

```
Señal (Technical Analyst)
         ↓
    Orchestrator ──→ Risk Manager (consulta)
         ↓                  ↓
    Decisión ←──── Aprobación/Veto
         ↓
    (Fase 4: Execution)
```

**Principio:** Risk Manager tiene veto absoluto. Ninguna operación bypasea validación.

### 2.2 Comunicación Inter-Agente

| Mecanismo | Uso | Latencia |
|-----------|-----|----------|
| Redis pub/sub | Señales, alertas, broadcast | < 10ms |
| MCP tools | Consultas request-response | < 100ms |
| Redis hash | Estado compartido | < 5ms |

### 2.3 Canales Pub/Sub

Referencia: Doc 2, sección 4.2

| Canal | Publicador | Suscriptores |
|-------|------------|--------------|
| `signals` | Technical Analyst | Orchestrator |
| `risk:requests` | Orchestrator | Risk Manager |
| `risk:responses` | Risk Manager | Orchestrator |
| `decisions` | Orchestrator | Logger, (futuro: Execution) |
| `alerts` | Cualquiera | Logger, Telegram |

### 2.4 Estructura de Directorios

```
src/agents/
├── __init__.py
├── base.py              # Clase base Agent
├── messaging.py         # Sistema pub/sub
├── schemas.py           # Pydantic models para mensajes
├── technical.py         # Technical Analyst
├── risk_manager.py      # Risk Manager
├── orchestrator.py      # Orchestrator
└── config.py            # Configuración de agentes

tests/agents/
├── __init__.py
├── test_base.py
├── test_messaging.py
├── test_technical.py
├── test_risk_manager.py
├── test_orchestrator.py
└── test_integration.py
```

---

## 3. Tareas

### Tarea 3.1: Clase base Agent y sistema de mensajería

**Estado:** ⬜ Pendiente

**Objetivo:** Infraestructura común para todos los agentes.

**Referencias:** Doc 3 sec 2.2, 8.4

**Subtareas:**
- [ ] Implementar `BaseAgent` con lifecycle (start, stop, health)
- [ ] Implementar `MessageBus` para pub/sub
- [ ] Definir schemas Pydantic para mensajes
- [ ] Sistema de health checks
- [ ] Logging estructurado por agente

**Input:** Redis operativo (Fase 0)

**Output:** Módulos `base.py`, `messaging.py`, `schemas.py`

**Validación:** Agente de prueba publica y recibe mensajes

**Pseudocódigo:**
```python
# src/agents/schemas.py
from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    SIGNAL = "signal"
    APPROVAL = "approval"
    ALERT = "alert"
    STATUS = "status"

class TradingSignal(BaseModel):
    message_id: str
    timestamp: datetime
    from_agent: str
    symbol: str
    direction: str  # "long", "short", "neutral"
    confidence: float  # 0.0 - 1.0
    entry_price: float
    stop_loss: float
    take_profit: float
    timeframe: str
    reasoning: str
    indicators: dict
    ttl_seconds: int = 300

class RiskRequest(BaseModel):
    message_id: str
    signal: TradingSignal
    capital: float
    current_positions: list[dict]

class RiskResponse(BaseModel):
    message_id: str
    request_id: str
    approved: bool
    original_size: int
    adjusted_size: int
    adjustments: list[dict]
    warnings: list[str]
    rejection_reason: str | None = None

# src/agents/messaging.py
import redis
import json

class MessageBus:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
        self._handlers: dict[str, callable] = {}
    
    def subscribe(self, channel: str, handler: callable):
        # 1. Registrar handler para canal
        # 2. Suscribir pubsub al canal
        self._handlers[channel] = handler
        self.pubsub.subscribe(channel)
    
    def publish(self, channel: str, message: BaseModel):
        # 1. Serializar mensaje a JSON
        # 2. Publicar en canal
        self.redis.publish(channel, message.model_dump_json())
    
    async def listen(self):
        # 1. Loop escuchando mensajes
        # 2. Deserializar y llamar handler apropiado
        for message in self.pubsub.listen():
            if message["type"] == "message":
                channel = message["channel"].decode()
                data = json.loads(message["data"])
                if channel in self._handlers:
                    await self._handlers[channel](data)

# src/agents/base.py
from abc import ABC, abstractmethod
import asyncio

class BaseAgent(ABC):
    def __init__(self, name: str, config: dict, message_bus: MessageBus):
        self.name = name
        self.config = config
        self.bus = message_bus
        self.running = False
        self._last_activity = None
    
    @abstractmethod
    async def setup(self):
        """Inicialización específica del agente"""
        pass
    
    @abstractmethod
    async def process(self):
        """Loop principal del agente"""
        pass
    
    async def start(self):
        # 1. Llamar setup()
        # 2. Marcar running = True
        # 3. Iniciar loop de process()
        await self.setup()
        self.running = True
        asyncio.create_task(self._run_loop())
    
    async def stop(self):
        self.running = False
    
    def health(self) -> dict:
        return {
            "status": "healthy" if self.running else "stopped",
            "last_activity": self._last_activity,
            "name": self.name
        }
    
    async def _run_loop(self):
        while self.running:
            try:
                await self.process()
                self._last_activity = datetime.utcnow()
            except Exception as e:
                self._log_error(e)
            await asyncio.sleep(0.1)  # Yield control
```

---

### Tarea 3.2: Technical Analyst Agent

**Estado:** ⬜ Pendiente

**Objetivo:** Agente que genera señales de trading basadas en análisis técnico.

**Referencias:** Doc 3 sec 4.1

**Subtareas:**
- [ ] Implementar `TechnicalAnalystAgent` heredando de `BaseAgent`
- [ ] Conectar a mcp-technical para indicadores
- [ ] Implementar lógica de generación de señales
- [ ] Publicar señales en canal `signals`
- [ ] Tests unitarios

**Input:** mcp-technical operativo (Fase 2), Feature Store (Fase 1)

**Output:** Agente que genera señales periódicamente

**Validación:** Señal publicada con estructura correcta para símbolo de prueba

**Lógica de señal (simplificada):**

| Condición | Señal | Confianza base |
|-----------|-------|----------------|
| RSI < 30 AND MACD crossover up AND precio > SMA50 | LONG | 0.60 |
| RSI > 70 AND MACD crossover down AND precio < SMA50 | SHORT | 0.60 |
| Soporte cercano (< 2%) + RSI < 40 | LONG | 0.55 |
| Resistencia cercana (< 2%) + RSI > 60 | SHORT | 0.55 |
| Ninguna condición | NEUTRAL | - |

**Ajustes de confianza:**
- Volumen > 1.5x media: +0.05
- ADX > 25 (tendencia fuerte): +0.05
- Múltiples timeframes alineados: +0.10

**Pseudocódigo:**
```python
# src/agents/technical.py
from agents.base import BaseAgent
from agents.schemas import TradingSignal
import uuid

class TechnicalAnalystAgent(BaseAgent):
    def __init__(self, config: dict, message_bus: MessageBus, mcp_client):
        super().__init__("technical_analyst", config, message_bus)
        self.mcp = mcp_client
        self.symbols = config.get("symbols", [])
        self.analysis_interval = config.get("interval_seconds", 300)
    
    async def setup(self):
        # Verificar conexión a mcp-technical
        pass
    
    async def process(self):
        for symbol in self.symbols:
            signal = await self._analyze_symbol(symbol)
            if signal and signal.direction != "neutral":
                self.bus.publish("signals", signal)
        
        await asyncio.sleep(self.analysis_interval)
    
    async def _analyze_symbol(self, symbol: str) -> TradingSignal | None:
        # 1. Obtener indicadores vía MCP
        indicators = await self.mcp.call(
            "mcp-technical", 
            "calculate_indicators",
            {"symbol": symbol, "indicators": ["RSI", "MACD", "SMA_50", "ADX", "ATR"], "timeframe": "1d"}
        )
        
        # 2. Obtener precio actual
        quote = await self.mcp.call("mcp-market-data", "get_quote", {"symbol": symbol})
        
        # 3. Obtener S/R levels
        levels = await self.mcp.call(
            "mcp-technical",
            "find_sr_levels", 
            {"symbol": symbol, "lookback": 50}
        )
        
        # 4. Evaluar condiciones
        direction, confidence, reasoning = self._evaluate_conditions(indicators, quote, levels)
        
        if direction == "neutral":
            return None
        
        # 5. Calcular niveles de entrada/salida
        entry, stop, target = self._calculate_levels(direction, quote, levels, indicators)
        
        return TradingSignal(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            from_agent=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            timeframe="swing_5d",
            reasoning=reasoning,
            indicators=indicators
        )
    
    def _evaluate_conditions(self, ind: dict, quote: dict, levels: dict) -> tuple:
        rsi = ind.get("RSI", 50)
        macd_hist = ind.get("MACD_hist", 0)
        price = quote.get("last", 0)
        sma50 = ind.get("SMA_50", price)
        adx = ind.get("ADX", 20)
        
        confidence = 0.50
        direction = "neutral"
        reasons = []
        
        # Condición LONG
        if rsi < 30 and macd_hist > 0 and price > sma50:
            direction = "long"
            confidence = 0.60 + (30 - rsi) / 100
            reasons.append(f"RSI oversold ({rsi:.1f}), MACD bullish, above SMA50")
        
        # Condición SHORT
        elif rsi > 70 and macd_hist < 0 and price < sma50:
            direction = "short"
            confidence = 0.60 + (rsi - 70) / 100
            reasons.append(f"RSI overbought ({rsi:.1f}), MACD bearish, below SMA50")
        
        # Ajustes
        if adx > 25:
            confidence += 0.05
            reasons.append("Strong trend (ADX > 25)")
        
        return direction, min(confidence, 0.95), "; ".join(reasons)
    
    def _calculate_levels(self, direction: str, quote: dict, levels: dict, ind: dict) -> tuple:
        price = quote["last"]
        atr = ind.get("ATR", price * 0.02)
        
        if direction == "long":
            entry = price
            stop = price - (2 * atr)
            target = price + (3 * atr)
        else:
            entry = price
            stop = price + (2 * atr)
            target = price - (3 * atr)
        
        return entry, stop, target
```

---

### Tarea 3.3: Risk Manager Agent

**Estado:** ⬜ Pendiente

**Objetivo:** Agente que valida operaciones contra límites y calcula sizing.

**Referencias:** Doc 3 sec 5, Doc 6 sec 2-4

**Subtareas:**
- [ ] Implementar `RiskManagerAgent` heredando de `BaseAgent`
- [ ] Suscribirse a `risk:requests`
- [ ] Implementar validación contra límites hardcoded
- [ ] Implementar cálculo de position sizing
- [ ] Publicar respuestas en `risk:responses`
- [ ] Tests unitarios

**Input:** mcp-risk operativo (Fase 2), posiciones actuales en PostgreSQL

**Output:** Agente que responde a solicitudes de validación

**Validación:** Request de validación recibe response con aprobación/rechazo correcto

**Límites hardcoded (NO configurables):**

| Límite | Valor | Acción si viola |
|--------|-------|-----------------|
| Max posición individual | 20% capital | Rechazar |
| Max sector | 40% capital | Rechazar |
| Max correlación | 0.70 | Reducir 50% |
| Max drawdown | 15% | STOP global |
| Min cash | 10% capital | Rechazar |

**Pseudocódigo:**
```python
# src/agents/risk_manager.py
class RiskManagerAgent(BaseAgent):
    # Límites HARDCODED - no modificables en runtime
    MAX_POSITION_PCT = 0.20
    MAX_SECTOR_PCT = 0.40
    MAX_CORRELATION = 0.70
    MAX_DRAWDOWN = 0.15
    MIN_CASH_PCT = 0.10
    BASE_RISK_PER_TRADE = 0.01
    
    def __init__(self, config: dict, message_bus: MessageBus, mcp_client, db_engine):
        super().__init__("risk_manager", config, message_bus)
        self.mcp = mcp_client
        self.db = db_engine
    
    async def setup(self):
        self.bus.subscribe("risk:requests", self._handle_request)
    
    async def process(self):
        # Risk Manager es reactivo, solo responde a requests
        # Monitoreo continuo de drawdown se hace aquí
        await self._check_drawdown()
        await asyncio.sleep(10)  # Check cada 10s
    
    async def _handle_request(self, data: dict):
        request = RiskRequest(**data)
        
        # 1. Validar límites
        approved, rejection_reason = await self._validate_limits(request)
        
        if not approved:
            response = RiskResponse(
                message_id=str(uuid.uuid4()),
                request_id=request.message_id,
                approved=False,
                original_size=0,
                adjusted_size=0,
                adjustments=[],
                warnings=[],
                rejection_reason=rejection_reason
            )
        else:
            # 2. Calcular sizing
            size, adjustments, warnings = await self._calculate_sizing(request)
            
            response = RiskResponse(
                message_id=str(uuid.uuid4()),
                request_id=request.message_id,
                approved=True,
                original_size=size["original"],
                adjusted_size=size["adjusted"],
                adjustments=adjustments,
                warnings=warnings
            )
        
        self.bus.publish("risk:responses", response)
    
    async def _validate_limits(self, request: RiskRequest) -> tuple[bool, str | None]:
        signal = request.signal
        capital = request.capital
        
        # Obtener exposición actual
        exposure = await self.mcp.call("mcp-risk", "get_exposure", {})
        
        # 1. Verificar cash mínimo
        cash_pct = exposure.get("cash", 0) / capital
        if cash_pct < self.MIN_CASH_PCT:
            return False, f"Cash insuficiente ({cash_pct:.1%} < {self.MIN_CASH_PCT:.0%})"
        
        # 2. Verificar drawdown
        current_dd = await self._get_current_drawdown()
        if current_dd > self.MAX_DRAWDOWN:
            return False, f"Drawdown excedido ({current_dd:.1%} > {self.MAX_DRAWDOWN:.0%})"
        
        # 3. Verificar sector (simplificado)
        sector = self._get_sector(signal.symbol)
        sector_exposure = exposure.get("by_sector", {}).get(sector, 0) / capital
        if sector_exposure > self.MAX_SECTOR_PCT:
            return False, f"Exposición sector {sector} excedida ({sector_exposure:.1%})"
        
        return True, None
    
    async def _calculate_sizing(self, request: RiskRequest) -> tuple[dict, list, list]:
        signal = request.signal
        capital = request.capital
        adjustments = []
        warnings = []
        
        # Position sizing base (Doc 6 sec 3.1)
        risk_amount = capital * self.BASE_RISK_PER_TRADE * signal.confidence
        distance_to_stop = abs(signal.entry_price - signal.stop_loss)
        
        if distance_to_stop == 0:
            distance_to_stop = signal.entry_price * 0.02  # Default 2%
        
        shares = int(risk_amount / distance_to_stop)
        position_value = shares * signal.entry_price
        
        # Ajuste por límite de posición
        max_value = capital * self.MAX_POSITION_PCT
        if position_value > max_value:
            shares = int(max_value / signal.entry_price)
            adjustments.append({"reason": "max_position_limit", "factor": max_value / position_value})
        
        # Ajuste por correlación (simplificado)
        correlation = await self._get_portfolio_correlation(signal.symbol)
        if correlation > 0.5:
            factor = 0.7
            shares = int(shares * factor)
            adjustments.append({"reason": "high_correlation", "factor": factor})
        
        # Ajuste por régimen
        regime = await self.mcp.call("mcp-technical", "get_regime", {})
        if regime.get("regime") == "high_volatility":
            factor = 0.5
            shares = int(shares * factor)
            adjustments.append({"reason": "high_volatility_regime", "factor": factor})
        
        # Warnings
        exposure = await self.mcp.call("mcp-risk", "get_exposure", {})
        sector = self._get_sector(signal.symbol)
        sector_pct = exposure.get("by_sector", {}).get(sector, 0) / capital
        if sector_pct > 0.30:
            warnings.append(f"Approaching sector limit ({sector_pct:.0%}/40%)")
        
        original_shares = int(risk_amount / distance_to_stop)
        return {"original": original_shares, "adjusted": shares}, adjustments, warnings
    
    async def _check_drawdown(self):
        dd = await self._get_current_drawdown()
        if dd > self.MAX_DRAWDOWN:
            # Activar kill switch
            self.bus.publish("alerts", {
                "type": "critical",
                "message": f"KILL SWITCH: Drawdown {dd:.1%} > {self.MAX_DRAWDOWN:.0%}"
            })
```

---

### Tarea 3.4: Orchestrator Agent

**Estado:** ⬜ Pendiente

**Objetivo:** Agente central que coordina señales, valida con Risk y emite decisiones.

**Referencias:** Doc 3 sec 3

**Subtareas:**
- [ ] Implementar `OrchestratorAgent` heredando de `BaseAgent`
- [ ] Suscribirse a canal `signals`
- [ ] Implementar lógica de ponderación de señales
- [ ] Consultar Risk Manager para validación
- [ ] Publicar decisiones en canal `decisions`
- [ ] Mantener estado en Redis
- [ ] Tests unitarios

**Input:** Señales de Technical Analyst, respuestas de Risk Manager

**Output:** Decisiones de trading (o descarte) con reasoning

**Validación:** Señal recibida genera consulta a Risk y decisión final

**Criterios de decisión:**

| Score | Acción |
|-------|--------|
| ≥ 0.65 + Risk OK | Ejecutar con sizing completo |
| 0.50 - 0.65 + Risk OK | Ejecutar con sizing 50% |
| < 0.50 | Descartar señal |
| Risk rechaza | Descartar, loguear razón |

**Pseudocódigo:**
```python
# src/agents/orchestrator.py
class OrchestratorAgent(BaseAgent):
    DECISION_THRESHOLD = 0.65
    REDUCED_THRESHOLD = 0.50
    ESCALATION_THRESHOLD = 0.60
    
    # Pesos por agente (Fundamental y Sentiment = 0 hasta implementación)
    WEIGHTS = {
        "technical_analyst": 0.40,
        "fundamental_analyst": 0.30,  # Fase futura
        "sentiment_analyst": 0.30,    # Fase futura
    }
    
    def __init__(self, config: dict, message_bus: MessageBus, redis_client):
        super().__init__("orchestrator", config, message_bus)
        self.redis = redis_client
        self._pending_validations: dict[str, TradingSignal] = {}
    
    async def setup(self):
        self.bus.subscribe("signals", self._handle_signal)
        self.bus.subscribe("risk:responses", self._handle_risk_response)
        # Cargar estado previo si existe
        await self._load_state()
    
    async def process(self):
        # Limpiar señales expiradas
        await self._cleanup_expired()
        await asyncio.sleep(1)
    
    async def _handle_signal(self, data: dict):
        signal = TradingSignal(**data)
        
        # 1. Calcular score ponderado
        score = self._calculate_weighted_score(signal)
        
        # 2. Verificar umbral
        if score < self.REDUCED_THRESHOLD:
            self._log_decision(signal, "discarded", f"Score {score:.2f} < {self.REDUCED_THRESHOLD}")
            return
        
        # 3. Determinar sizing factor
        sizing_factor = 1.0 if score >= self.DECISION_THRESHOLD else 0.5
        
        # 4. Solicitar validación a Risk Manager
        request = RiskRequest(
            message_id=str(uuid.uuid4()),
            signal=signal,
            capital=await self._get_capital(),
            current_positions=await self._get_positions()
        )
        
        self._pending_validations[request.message_id] = {
            "signal": signal,
            "score": score,
            "sizing_factor": sizing_factor,
            "timestamp": datetime.utcnow()
        }
        
        self.bus.publish("risk:requests", request)
    
    async def _handle_risk_response(self, data: dict):
        response = RiskResponse(**data)
        
        pending = self._pending_validations.pop(response.request_id, None)
        if not pending:
            return  # Response huérfana, ignorar
        
        signal = pending["signal"]
        score = pending["score"]
        sizing_factor = pending["sizing_factor"]
        
        if not response.approved:
            self._log_decision(signal, "rejected", response.rejection_reason)
            return
        
        # Emitir decisión
        decision = {
            "decision_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            "signal": signal.model_dump(),
            "score": score,
            "action": "execute",
            "size": int(response.adjusted_size * sizing_factor),
            "adjustments": response.adjustments,
            "warnings": response.warnings
        }
        
        self.bus.publish("decisions", decision)
        self._log_decision(signal, "approved", f"Size: {decision['size']}, Score: {score:.2f}")
        
        # Guardar estado
        await self._save_state()
    
    def _calculate_weighted_score(self, signal: TradingSignal) -> float:
        # En esta fase, solo Technical Analyst tiene peso real
        agent_weight = self.WEIGHTS.get(signal.from_agent, 0)
        
        # Normalizar ya que solo tenemos 1 agente activo
        active_weight = self.WEIGHTS["technical_analyst"]
        normalized_weight = agent_weight / active_weight if active_weight > 0 else 0
        
        return signal.confidence * normalized_weight
    
    async def _get_capital(self) -> float:
        # Obtener capital actual de Redis o BD
        capital = self.redis.get("portfolio:capital")
        return float(capital) if capital else 1000.0  # Default inicial
    
    async def _get_positions(self) -> list:
        # Obtener posiciones actuales
        positions = self.redis.hgetall("positions")
        return list(positions.values()) if positions else []
    
    def _log_decision(self, signal: TradingSignal, action: str, reason: str):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": signal.symbol,
            "direction": signal.direction,
            "action": action,
            "reason": reason
        }
        # Log estructurado
        self.redis.lpush("audit:decisions", json.dumps(log_entry))
        self.redis.ltrim("audit:decisions", 0, 999)  # Mantener últimas 1000
```

---

### Tarea 3.5: Tests de integración

**Estado:** ⬜ Pendiente

**Objetivo:** Validar flujo completo señal → validación → decisión.

**Referencias:** Doc 3 sec 8

**Subtareas:**
- [ ] Test: Technical Analyst genera señal válida
- [ ] Test: Risk Manager aprueba operación dentro de límites
- [ ] Test: Risk Manager rechaza operación fuera de límites
- [ ] Test: Orchestrator procesa flujo completo
- [ ] Test: Mensajes fluyen correctamente por pub/sub
- [ ] Test: Estado se persiste en Redis

**Input:** Agentes implementados

**Output:** Suite de tests de integración

**Validación:** `pytest tests/agents/test_integration.py` pasa 100%

**Pseudocódigo:**
```python
# tests/agents/test_integration.py
import pytest
import asyncio

@pytest.fixture
async def agent_system(redis_client, mcp_clients, db_engine):
    """Levanta sistema completo de agentes para testing"""
    bus = MessageBus(redis_url)
    
    risk = RiskManagerAgent(config, bus, mcp_clients["risk"], db_engine)
    technical = TechnicalAnalystAgent(config, bus, mcp_clients["technical"])
    orchestrator = OrchestratorAgent(config, bus, redis_client)
    
    await risk.start()
    await orchestrator.start()
    
    yield {"risk": risk, "technical": technical, "orchestrator": orchestrator, "bus": bus}
    
    await risk.stop()
    await orchestrator.stop()

class TestIntegration:
    @pytest.mark.asyncio
    async def test_full_flow_approval(self, agent_system):
        """Test: señal válida → Risk aprueba → decisión emitida"""
        decisions = []
        
        def capture_decision(data):
            decisions.append(data)
        
        agent_system["bus"].subscribe("decisions", capture_decision)
        
        # Emitir señal de prueba
        signal = TradingSignal(
            message_id="test-1",
            timestamp=datetime.utcnow(),
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction="long",
            confidence=0.70,
            entry_price=4.50,
            stop_loss=4.30,
            take_profit=5.00,
            timeframe="swing_5d",
            reasoning="Test signal",
            indicators={"RSI": 28, "MACD_hist": 0.05}
        )
        
        agent_system["bus"].publish("signals", signal)
        
        # Esperar procesamiento
        await asyncio.sleep(1)
        
        assert len(decisions) == 1
        assert decisions[0]["action"] == "execute"
        assert decisions[0]["size"] > 0
    
    @pytest.mark.asyncio
    async def test_full_flow_rejection_low_confidence(self, agent_system):
        """Test: señal con baja confianza → descartada"""
        decisions = []
        agent_system["bus"].subscribe("decisions", lambda d: decisions.append(d))
        
        signal = TradingSignal(
            message_id="test-2",
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction="long",
            confidence=0.40,  # Bajo umbral
            # ... resto de campos
        )
        
        agent_system["bus"].publish("signals", signal)
        await asyncio.sleep(1)
        
        assert len(decisions) == 0  # No debería generar decisión
    
    @pytest.mark.asyncio
    async def test_full_flow_rejection_risk_limit(self, agent_system, monkeypatch):
        """Test: señal válida pero Risk rechaza por límites"""
        # Simular drawdown alto
        monkeypatch.setattr(
            agent_system["risk"], 
            "_get_current_drawdown", 
            lambda: 0.16  # > 15%
        )
        
        decisions = []
        agent_system["bus"].subscribe("decisions", lambda d: decisions.append(d))
        
        signal = TradingSignal(
            message_id="test-3",
            from_agent="technical_analyst",
            symbol="SAN.MC",
            direction="long",
            confidence=0.75,
            # ...
        )
        
        agent_system["bus"].publish("signals", signal)
        await asyncio.sleep(1)
        
        assert len(decisions) == 0  # Risk debería rechazar
```

---

### Tarea 3.6: Configuración y arranque ordenado

**Estado:** ⬜ Pendiente

**Objetivo:** Sistema de configuración y script de arranque con orden correcto.

**Referencias:** Doc 3 sec 8.1, 8.3

**Subtareas:**
- [ ] Crear `config/agents.yaml`
- [ ] Crear script `scripts/start_agents.py`
- [ ] Implementar arranque ordenado (Risk → Analysts → Orchestrator)
- [ ] Implementar graceful shutdown
- [ ] Health check periódico

**Input:** Agentes implementados

**Output:** Sistema arrancable con un comando

**Validación:** `python scripts/start_agents.py` levanta todos los agentes

**Orden de arranque:**
1. Risk Manager (debe estar listo antes de recibir requests)
2. Technical Analyst (puede empezar a generar señales)
3. Orchestrator (último, espera a que todos estén healthy)

**Configuración:**
```yaml
# config/agents.yaml
orchestrator:
  decision_threshold: 0.65
  reduced_threshold: 0.50
  escalation_threshold: 0.60
  weights:
    technical: 0.40
    fundamental: 0.30
    sentiment: 0.30

technical_analyst:
  symbols:
    - SAN.MC
    - ITX.MC
    - IBE.MC
    - BBVA.MC
    - TEF.MC
  interval_seconds: 300
  indicators:
    - RSI
    - MACD
    - SMA_50
    - SMA_200
    - ADX
    - ATR
  timeframes:
    - 1d
    - 4h

risk_manager:
  base_risk_per_trade: 0.01
  kelly_fraction: 0.25
  # Límites hardcoded están en código, no aquí
```

**Script de arranque:**
```python
# scripts/start_agents.py
import asyncio
import signal
import sys

async def main():
    # 1. Cargar configuración
    config = load_config("config/agents.yaml")
    
    # 2. Inicializar conexiones
    redis = Redis.from_url(os.environ["REDIS_URL"])
    mcp_clients = init_mcp_clients()
    db = create_engine(os.environ["DATABASE_URL"])
    
    # 3. Crear bus de mensajes
    bus = MessageBus(os.environ["REDIS_URL"])
    
    # 4. Crear agentes
    risk = RiskManagerAgent(config["risk_manager"], bus, mcp_clients, db)
    technical = TechnicalAnalystAgent(config["technical_analyst"], bus, mcp_clients)
    orchestrator = OrchestratorAgent(config["orchestrator"], bus, redis)
    
    agents = [risk, technical, orchestrator]
    
    # 5. Arranque ordenado
    print("Starting Risk Manager...")
    await risk.start()
    await wait_healthy(risk, timeout=30)
    
    print("Starting Technical Analyst...")
    await technical.start()
    await wait_healthy(technical, timeout=30)
    
    print("Starting Orchestrator...")
    await orchestrator.start()
    await wait_healthy(orchestrator, timeout=30)
    
    print("All agents running!")
    
    # 6. Esperar señal de parada
    stop_event = asyncio.Event()
    
    def handle_shutdown(sig, frame):
        print("Shutdown signal received...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    await stop_event.wait()
    
    # 7. Graceful shutdown (orden inverso)
    print("Stopping agents...")
    for agent in reversed(agents):
        await agent.stop()
    
    print("Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Tarea 3.7: Script de verificación de fase

**Estado:** ⬜ Pendiente

**Objetivo:** Script que valida todos los componentes de la fase funcionan.

**Subtareas:**
- [ ] Crear `scripts/verify_agents.py`
- [ ] Verificar cada agente responde a health check
- [ ] Verificar flujo de mensajes pub/sub
- [ ] Verificar decisiones se generan correctamente
- [ ] Output claro de estado

**Input:** Sistema de agentes corriendo

**Output:** Script ejecutable con resultado claro

**Validación:** Ejecutar después de arrancar agentes, todo ✅

**Pseudocódigo:**
```python
# scripts/verify_agents.py
import asyncio

CHECKS = [
    ("Redis connection", check_redis),
    ("Risk Manager health", check_risk_health),
    ("Technical Analyst health", check_technical_health),
    ("Orchestrator health", check_orchestrator_health),
    ("Pub/Sub messaging", check_pubsub),
    ("Signal → Decision flow", check_full_flow),
]

async def check_full_flow():
    """Verificar flujo completo con señal de prueba"""
    bus = MessageBus(redis_url)
    decisions = []
    
    bus.subscribe("decisions", lambda d: decisions.append(d))
    
    # Emitir señal de prueba
    test_signal = create_test_signal(confidence=0.70)
    bus.publish("signals", test_signal)
    
    # Esperar respuesta
    await asyncio.sleep(3)
    
    if decisions:
        return True, f"Decision received: {decisions[0].get('action')}"
    return False, "No decision received within timeout"

async def main():
    print("VERIFICACIÓN AGENTES - FASE 3")
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
        print("✅ FASE 3 VERIFICADA CORRECTAMENTE")
    else:
        print("❌ FASE 3 TIENE ERRORES")
    
    return 0 if all_ok else 1
```

---

## 4. Dependencias Python Adicionales

Añadir a `requirements.txt`:

```
# Messaging
redis>=5.0.0

# Async
asyncio>=3.4.3

# Validation
pydantic>=2.5.0

# MCP Client (para comunicación con servers)
httpx>=0.25.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-mock>=3.12.0
```

---

## 5. Checklist de Finalización

```
Fase 3: Agentes Core
═══════════════════════════════════

[ ] Tarea 3.1: Clase base Agent y sistema pub/sub
[ ] Tarea 3.2: Technical Analyst Agent
[ ] Tarea 3.3: Risk Manager Agent
[ ] Tarea 3.4: Orchestrator Agent
[ ] Tarea 3.5: Tests de integración
[ ] Tarea 3.6: Configuración y arranque ordenado
[ ] Tarea 3.7: Script de verificación

Gate de avance:
[ ] verify_agents.py pasa 100%
[ ] pytest tests/agents/ pasa 100%
[ ] Flujo señal → validación → decisión funciona
[ ] Health checks de todos los agentes OK
[ ] Logs de decisiones en Redis audit
```

---

## 6. Troubleshooting

### Mensajes no llegan entre agentes

```python
# Verificar suscripciones activas
redis-cli PUBSUB CHANNELS *

# Verificar que hay suscriptores
redis-cli PUBSUB NUMSUB signals risk:requests risk:responses
```

### Orchestrator no recibe respuestas de Risk

```python
# Verificar que Risk Manager está procesando
redis-cli SUBSCRIBE risk:requests
# En otra terminal, publicar mensaje de prueba
redis-cli PUBLISH risk:requests '{"message_id": "test"}'
```

### Agente se queda en estado "starting"

```python
# Verificar dependencias del agente
# Risk Manager necesita: PostgreSQL, mcp-risk
# Technical necesita: mcp-technical, mcp-market-data
# Orchestrator necesita: Redis

# Verificar conexiones
docker-compose ps  # Todos los servicios UP
```

### Señales no generan decisiones

1. Verificar confianza de señal > 0.50
2. Verificar Risk Manager no rechaza (ver logs)
3. Verificar Orchestrator está suscrito a `signals`
4. Verificar no hay timeout en validación

```python
# Ver audit log
redis-cli LRANGE audit:decisions 0 10
```

### Error de serialización en mensajes

```python
# Verificar que todos los campos son serializables
# datetime → usar .isoformat()
# Decimal → convertir a float
# UUID → convertir a str
```

---

## 7. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Arquitectura de agentes | Doc 3 | 1 |
| Protocolo de mensajes | Doc 3 | 2.2 |
| Lógica Technical Analyst | Doc 3 | 4.1 |
| Lógica Risk Manager | Doc 3 | 5 |
| Lógica Orchestrator | Doc 3 | 3 |
| Límites hardcoded | Doc 6 | 2.1 |
| Position sizing | Doc 6 | 3 |
| Circuit breakers | Doc 6 | 6 |
| Redis pub/sub | Doc 2 | 4.2 |
| Config agentes | Doc 3 | 8.1 |

---

## 8. Siguiente Fase

Una vez completada la Fase 3:
- **Verificar:** `verify_agents.py` pasa 100%
- **Verificar:** Flujo señal → decisión funciona end-to-end
- **Siguiente:** `fase_4_motor_trading.md`
- **Contenido Fase 4:** Strategy Registry, estrategias concretas, backtesting, Execution Agent

---

*Fase 3 - Agentes Core*  
*Bot de Trading Autónomo con IA*
