# ⚙️ Arquitectura Técnica - Documento 4/7

## Motor de Trading

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Estrategias Implementadas

### 1.1 Catálogo de Estrategias

| ID | Nombre | Tipo | Mercados | Régimen Compatible |
|----|--------|------|----------|-------------------|
| `swing_momentum_eu` | Momentum EU | Swing | Acciones EU | Trending Bull |
| `mean_reversion_pairs` | Pairs Trading | Mean Reversion | Acciones EU | Range-bound |
| `trend_follow_forex` | Trend Following | Tendencia | Forex majors | Trending Bull/Bear |
| `breakout_volume` | Breakout con Volumen | Breakout | Acciones EU, US | Trending Bull |

### 1.2 Configuración: `swing_momentum_eu`

**Timeframe:** 1d | **Holding:** 3-10 días | **Max posiciones:** 5

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| rsi_oversold | 35 | Entrada long si RSI < valor |
| rsi_overbought | 65 | Salida si RSI > valor |
| sma_filter | 50 | Precio debe estar > SMA(n) |
| volume_mult | 1.5 | Volumen > n × media 20d |
| atr_stop_mult | 2.0 | Stop = entrada - n × ATR(14) |
| risk_reward | 3.0 | TP = entrada + n × riesgo |

**Señal de entrada (pseudocódigo):**
```
IF rsi_14 < 35 AND close > sma_50 AND volume > 1.5 * vol_avg_20:
    IF macd_hist > macd_hist[-1]:  # MACD mejorando
        signal = LONG
        stop = close - 2 * atr_14
        target = close + 3 * (close - stop)
```

### 1.3 Configuración: `mean_reversion_pairs`

**Timeframe:** 1h | **Holding:** 1-5 días | **Pares:** SAN/BBVA, SAP/ASML

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| zscore_entry | 2.0 | Entrada si \|z-score\| > valor |
| zscore_exit | 0.5 | Salida si \|z-score\| < valor |
| lookback | 60 | Ventana para calcular spread |
| max_holding_days | 5 | Cierre forzado si no revierte |
| hedge_ratio | dynamic | Calculado por regresión rolling |

**Requisito:** Cointegración verificada (p-value < 0.05 en test ADF del spread).

### 1.4 Configuración: `trend_follow_forex`

**Timeframe:** 4h | **Holding:** 5-20 días | **Pares:** EUR/USD, GBP/USD, USD/JPY

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| ema_fast | 20 | EMA rápida |
| ema_slow | 50 | EMA lenta |
| adx_min | 25 | Solo operar si ADX > valor |
| atr_stop_mult | 1.5 | Stop inicial |
| trailing_atr | 2.0 | Trailing stop = n × ATR |

### 1.5 Configuración: `breakout_volume`

**Timeframe:** 1d | **Holding:** 2-7 días

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| consolidation_days | 10 | Días mínimos en rango |
| range_atr_mult | 1.5 | Rango < n × ATR = consolidación |
| breakout_pct | 1.02 | Cierre > 2% sobre resistencia |
| volume_mult | 2.0 | Volumen > 2× media |

---

## 2. Strategy Registry

### 2.1 Estructura de Registro

Cada estrategia se registra en PostgreSQL (`config.strategies`) y tiene estado en Redis.

**Estados de estrategia:**

| Estado | Descripción | Puede operar |
|--------|-------------|--------------|
| `active` | Funcionando normal | Sí |
| `paused` | Pausada manualmente | No |
| `regime_disabled` | Desactivada por régimen incompatible | No |
| `drawdown_disabled` | DD de estrategia > límite | No |
| `paper_only` | Solo genera señales, no ejecuta | No |

### 2.2 Activación por Régimen

Referencia: Doc 1, sección 4.6 para definición de regímenes.

| Régimen | Estrategias Activas |
|---------|---------------------|
| Trending Bull | `swing_momentum_eu`, `trend_follow_forex`, `breakout_volume` |
| Trending Bear | `trend_follow_forex` (shorts) |
| Range-bound | `mean_reversion_pairs` |
| High Volatility | Ninguna nueva entrada; gestionar existentes |
| Crisis | Solo cierres; cash |

### 2.3 Asignación Dinámica de Pesos

Strategy Manager (Doc 1, sec 4.3) asigna capital entre estrategias activas:

```
peso_raw = sharpe_3m * (1 - dd_actual / dd_max_tolerado)
IF régimen incompatible: peso_raw = 0
peso_final = peso_raw / sum(pesos_raw)  # Normalizar
```

**Límites:**
- Min peso por estrategia activa: 10%
- Max peso por estrategia: 50%
- Rebalanceo: semanal o si peso deriva > 10%

---

## 3. Backtesting Framework

### 3.1 Principios Anti-Overfitting

| Técnica | Implementación |
|---------|----------------|
| Purged K-Fold | Embargo de 5 días entre train/test |
| Walk-Forward | Re-entrenar cada 3 meses, testear 1 mes |
| Out-of-Sample | 20% datos finales nunca vistos hasta evaluación final |
| Multiple Testing | Corrección Bonferroni si > 5 estrategias |

### 3.2 División Temporal

```
|---- Train (60%) ----|-- Val (20%) --|-- Test (20%) --|
|     2018-2021       |   2022-2023   |   2024         |
                      |<- embargo 5d ->|
```

**Regla:** Test set se usa UNA vez. Si modificas estrategia, vuelves a Val.

### 3.3 Pipeline de Backtesting

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Config    │────▶│  Backtest   │────▶│   Report    │
│  Strategy   │     │   Engine    │     │  Generator  │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Cost Model    Slippage    Fill Simulation
```

### 3.4 Modelo de Costes

Referencia: Doc 1, sección 4.8 para Cost Model Module.

| Componente | Estimación |
|------------|------------|
| Comisión IBKR | 0.05% acciones EU, $0.005/share US |
| Spread | 0.02-0.10% según liquidez |
| Slippage | `spread × (1 + vol_normalizada × 0.5)` |
| Market impact | +0.1% si orden > 1% vol diario |

**En backtest:** Aplicar costes pesimistas (1.5× estimación).

### 3.5 Métricas de Evaluación

| Métrica | Fórmula resumida | Threshold |
|---------|------------------|-----------|
| Sharpe | (ret - rf) / std | > 1.0 |
| Sortino | (ret - rf) / downside_std | > 1.5 |
| Max DD | max(peak - trough) / peak | < 15% |
| Calmar | CAGR / MaxDD | > 1.0 |
| Win Rate | wins / total | > 45% |
| Profit Factor | gross_profit / gross_loss | > 1.5 |
| Avg Trade | net_profit / num_trades | > 0.5% |

### 3.6 Walk-Forward Optimization

```
FOR cada ventana in rolling_windows:
    train_data = ventana[:-test_period]
    test_data = ventana[-test_period:]
    
    params_optimos = optimize(strategy, train_data)
    resultado = backtest(strategy, params_optimos, test_data)
    
    resultados.append(resultado)

IF std(resultados) > 0.5 * mean(resultados):
    WARN "Alta varianza - posible overfitting"
```

---

## 4. Order Lifecycle

### 4.1 Estados de Orden

Referencia: Doc 2, sección 2.1 para esquema de BD.

```
┌─────────┐    ┌──────┐    ┌─────────┐    ┌────────┐
│ PENDING │───▶│ SENT │───▶│ PARTIAL │───▶│ FILLED │
└────┬────┘    └──┬───┘    └────┬────┘    └────────┘
     │            │             │
     │            ▼             │
     │       ┌────────┐         │
     └──────▶│REJECTED│◀────────┘
             └────────┘
                 │
                 ▼
            ┌──────────┐
            │CANCELLED │
            └──────────┘
```

### 4.2 Transiciones y Timeouts

| Transición | Trigger | Timeout |
|------------|---------|---------|
| PENDING → SENT | Envío a broker exitoso | 5s (retry o fail) |
| SENT → PARTIAL | Primer fill recibido | - |
| SENT → FILLED | Fill completo | 5min (luego market complete) |
| SENT → REJECTED | Broker rechaza | - |
| * → CANCELLED | Cancelación manual/automática | - |

### 4.3 Manejo de Fills Parciales

```
IF status == PARTIAL AND time_since_first_fill > 5min:
    remaining = order.quantity - order.filled_qty
    IF remaining < min_order_size:
        cancel_remaining()
    ELSE:
        convert_to_market(remaining)
```

### 4.4 Reconciliación

Proceso diario post-cierre (ver Doc 2, sec 8.2):

1. Obtener posiciones de broker via API
2. Comparar con `trading.positions` en PostgreSQL
3. Si diferencia > 0.1%: alerta CRITICAL
4. Log de reconciliación en `audit.system_events`

---

## 5. Gestión de Señales

### 5.1 Flujo de Señal

```
Strategy → Signal → Orchestrator → Risk Check → Size → Execute
```

### 5.2 Estructura de Señal

Referencia: Doc 3, sección 2.3 para payload completo.

| Campo | Requerido | Descripción |
|-------|-----------|-------------|
| strategy_id | Sí | Origen de la señal |
| symbol | Sí | Activo |
| direction | Sí | long/short/close |
| confidence | Sí | 0.0 - 1.0 |
| entry_price | Sí | Precio objetivo entrada |
| stop_loss | Sí | Nivel de stop |
| take_profit | No | Nivel de TP (o trailing) |
| ttl_seconds | Sí | Validez de señal (default: 300) |

### 5.3 Deduplicación

Evitar señales duplicadas:

```
signal_key = f"{strategy}:{symbol}:{direction}"
IF redis.exists(f"signal_lock:{signal_key}"):
    DISCARD signal
ELSE:
    redis.setex(f"signal_lock:{signal_key}", 3600, "1")
    PROCESS signal
```

### 5.4 Conflicto de Señales

| Situación | Acción |
|-----------|--------|
| Misma dirección, múltiples estrategias | Usar mayor confianza |
| Direcciones opuestas | Descartar ambas, log conflicto |
| Nueva señal con posición abierta | Ignorar si misma dirección; evaluar si cierre |

---

## 6. Paper Trading → Live

### 6.1 Criterios de Promoción

| Criterio | Threshold | Período |
|----------|-----------|---------|
| Sharpe en paper | > 1.0 | 6 meses |
| Max DD en paper | < 12% | 6 meses |
| Trades ejecutados | > 50 | - |
| Win rate | > 45% | - |
| Profit factor | > 1.3 | - |
| Correlación con backtest | > 0.7 | - |

### 6.2 Fases de Transición

| Fase | Capital | Duración | Criterio avance |
|------|---------|----------|-----------------|
| Paper | 0€ (simulado) | 6+ meses | Cumple 6.1 |
| Pilot | 500€ (5% max) | 2 meses | Sin pérdida > 5% |
| Ramp-up | 2000€ (20%) | 2 meses | Sharpe > 0.8 |
| Full | 100% disponible | Indefinido | - |

### 6.3 Checklist Pre-Live

```
□ Backtest validado en múltiples períodos
□ Paper trading > 6 meses con métricas OK
□ Reconciliación diaria funcionando
□ Alertas configuradas (Telegram)
□ Kill switch probado
□ Capital de riesgo separado
□ Runbook documentado
□ Contacto de emergencia definido
```

### 6.4 Rollback Triggers

Volver a fase anterior si:

| Condición | Acción |
|-----------|--------|
| DD > 10% en fase Pilot/Ramp-up | Volver a Paper |
| 3 días consecutivos con pérdida | Reducir 50% |
| Error técnico con pérdida | Pausa + revisión |

---

## 7. Integración con Otros Componentes

### 7.1 Dependencias

| Componente | Documento | Interacción |
|------------|-----------|-------------|
| Feature Store | Doc 2, sec 6 | Input para señales |
| MCP Servers | Doc 3, sec 7 | Ejecución de tools |
| Risk Manager | Doc 3, sec 5 | Validación pre-trade |
| Regime Detection | Doc 1, sec 4.6 | Activación estrategias |
| Cost Model | Doc 1, sec 4.8 | Backtesting realista |

### 7.2 Configuración Centralizada

Archivo `config/strategies/` con un YAML por estrategia:

```yaml
# swing_momentum_eu.yaml
id: swing_momentum_eu
name: "Momentum Swing EU"
enabled: true
markets: [BME, XETRA]
regime_filter: [trending_bull]
params:
  rsi_oversold: 35
  rsi_overbought: 65
  # ... resto de params
risk:
  max_positions: 5
  max_pct_per_position: 0.15
```

Cargado al inicio; cambios requieren restart o comando de reload.

---

## 8. Monitorización del Motor

### 8.1 Métricas Clave

| Métrica | Frecuencia | Alerta si |
|---------|------------|-----------|
| Señales generadas/hora | 1 min | < 1 en mercado abierto |
| Latencia señal→orden | Por orden | > 5s |
| Fill rate | Diario | < 90% |
| Slippage promedio | Diario | > 2× estimado |
| Estrategias activas | 1 min | 0 en mercado abierto |

### 8.2 Dashboard Panels

Referencia: Doc 7 (Operaciones) para Grafana completo.

| Panel | Contenido |
|-------|-----------|
| Strategy Performance | P&L por estrategia, rolling |
| Signal Flow | Señales/hora, ratio ejecutadas |
| Order Status | Órdenes pendientes, fills hoy |
| Regime | Estado actual, historial |

---

## 9. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Esquema órdenes/trades | Doc 2 | 2.1 |
| Feature Store | Doc 2 | 6 |
| MCP tools de ejecución | Doc 3 | 7.5, 7.6 |
| Risk Manager | Doc 3 | 5 |
| Regime Detection | Doc 1 | 4.6 |
| Cost Model | Doc 1 | 4.8 |
| Circuit breakers | Doc 1 | 5 |

---

*Documento 4 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
