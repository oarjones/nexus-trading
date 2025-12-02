# 🛡️ Arquitectura Técnica - Documento 6/7

## Gestión de Riesgo

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Marco de Riesgo

### 1.1 Niveles de Protección

| Nivel | Alcance | Responsable | Frecuencia |
|-------|---------|-------------|------------|
| 1. Posición | Trade individual | Position Sizer | Pre-trade |
| 2. Portfolio | Exposiciones agregadas | Risk Manager | Continuo |
| 3. Temporal | Pérdidas acumuladas | Kill Switch | Continuo |
| 4. Sistémico | Condiciones de mercado | Regime Detector | 1 min |
| 5. Operacional | Fallos técnicos | Circuit Breakers | Continuo |

### 1.2 Jerarquía de Decisiones

```
Señal de Trading
       ↓
  Risk Manager ──→ VETO (límites hardcoded)
       ↓
  Position Sizer ──→ Tamaño ajustado
       ↓
  Orchestrator ──→ Decisión final
       ↓
  Execution
```

**Principio:** Risk Manager tiene veto absoluto. Ninguna señal bypasea validación.

---

## 2. Límites Hardcoded

### 2.1 Límites de Posición

| Límite | Valor | Verificación | Acción si viola |
|--------|-------|--------------|-----------------|
| Max posición individual | 20% capital | Pre-trade | Rechazar orden |
| Max sector | 40% capital | Pre-trade | Rechazar orden |
| Max correlación entre posiciones | 0.70 | Pre-trade | Reducir sizing 50% |
| Max exposición USD | 50% capital | Pre-trade | Rechazar nuevas USD |
| Max exposición crypto | 15% capital | Pre-trade | Rechazar nuevas crypto |
| Min cash reserve | 10% capital | Pre-trade | Solo permite cierres |
| Max posiciones simultáneas | 10 | Pre-trade | Rechazar nueva |

### 2.2 Límites Temporales de Pérdida

| Período | Límite | Acción |
|---------|--------|--------|
| Diario | -2% | Modo defensivo |
| Diario | -3% | STOP global |
| Semanal | -5% | STOP global |
| Mensual | -8% | STOP global + revisión manual |
| Max Drawdown | -15% | STOP global + cierre todo |

### 2.3 Límites por Régimen

Referencia: Doc 1, sección 4.6 para definición de regímenes.

| Régimen | Max Exposición Total | Max Nueva Posición | Sizing Multiplier |
|---------|---------------------|-------------------|-------------------|
| Trending Bull | 90% | 20% | 1.0 |
| Trending Bear | 50% | 10% | 0.7 |
| Range-bound | 70% | 15% | 0.8 |
| High Volatility | 40% | 10% | 0.5 |
| Crisis | 10% | 0% (solo cierres) | 0.0 |

---

## 3. Position Sizing

### 3.1 Algoritmo Base (Kelly Fraccional)

```
risk_amount = capital × base_risk × confidence_factor × regime_factor
shares = risk_amount / distance_to_stop
position_value = shares × entry_price
final_value = min(position_value, max_position_limit)
```

| Variable | Cálculo | Rango típico |
|----------|---------|--------------|
| base_risk | 1% fijo | 0.01 |
| confidence_factor | señal.confianza | 0.5 - 1.0 |
| regime_factor | tabla 2.3 | 0.0 - 1.0 |
| distance_to_stop | \|entry - stop\| / entry | 1% - 5% |

### 3.2 Ajustes Adicionales

| Condición | Ajuste | Razón |
|-----------|--------|-------|
| Correlación con portfolio > 0.5 | × 0.7 | Diversificación |
| Drawdown actual > 10% | × 0.5 | Protección |
| Volatilidad > 2× normal | × 0.5 | Prudencia |
| Calibración ML degradada | × 0.5 | Incertidumbre |
| Posición en mismo sector | × 0.8 | Concentración |

### 3.3 Ejemplo de Cálculo

```
Capital: 10,000€
Señal: LONG AAPL @ 185€, stop @ 180€, confianza 0.75
Régimen: Trending Bull (factor 1.0)
Drawdown actual: 5% (sin ajuste)
Correlación portfolio: 0.3 (sin ajuste)

risk_amount = 10,000 × 0.01 × 0.75 × 1.0 = 75€
distance_to_stop = (185 - 180) / 185 = 2.7%
shares_raw = 75 / (185 × 0.027) = 15 shares
position_value = 15 × 185 = 2,775€ (27.7%)

Max permitido = 20% = 2,000€
Final: 10 shares (1,850€)
```

---

## 4. Value at Risk (VaR) y Expected Shortfall

### 4.1 Cálculo de VaR

| Método | Uso | Fórmula |
|--------|-----|---------|
| Paramétrico | Rápido, diario | VaR = μ - z × σ |
| Histórico | Validación semanal | Percentil de retornos históricos |
| Monte Carlo | Stress testing mensual | Simulación 10,000 paths |

**Parámetros default:**
- Nivel de confianza: 95%
- Horizonte: 1 día
- Ventana histórica: 252 días

### 4.2 Expected Shortfall (CVaR)

Más robusto que VaR para colas pesadas:

```
ES_95% = E[Pérdida | Pérdida > VaR_95%]
```

**Límite:** ES diario < 3% del capital

### 4.3 Uso en Decisiones

| Métrica | Límite | Acción si excede |
|---------|--------|------------------|
| VaR diario portfolio | 2% | Warning, reducir exposición |
| VaR diario portfolio | 3% | No nuevas posiciones |
| ES diario portfolio | 3% | Modo defensivo |
| ES diario portfolio | 5% | Reducir posiciones 25% |

---

## 5. Drawdown Management

### 5.1 Niveles y Acciones

| Drawdown | Modo | Acciones Automáticas |
|----------|------|---------------------|
| 0-5% | Normal | Operativa completa |
| 5-10% | Alerta | Warning diario, revisar estrategias underperforming |
| 10-12% | Defensivo | Exposición max 50%, solo alta confianza (>0.7) |
| 12-15% | Crítico | Solo cierres, no nuevas entradas |
| >15% | Emergencia | Cierre total, STOP global |

### 5.2 Recuperación Post-Drawdown

| Drawdown Alcanzado | Requisito para Volver a Normal |
|-------------------|-------------------------------|
| 5-10% | DD < 5% durante 5 días |
| 10-15% | DD < 8% durante 10 días + revisión manual |
| >15% | Revisión completa + aprobación manual + 2 semanas paper |

### 5.3 Matemáticas de Recuperación

| Drawdown | Ganancia Necesaria |
|----------|-------------------|
| 5% | 5.3% |
| 10% | 11.1% |
| 15% | 17.6% |
| 20% | 25.0% |
| 30% | 42.9% |

**Implicación:** Nunca permitir DD > 15%. Recuperación exponencialmente difícil.

---

## 6. Circuit Breakers

### 6.1 Consolidación de Triggers

Referencia: Doc 1, sección 5.2.

| Componente | Condición | Estado | Acción |
|------------|-----------|--------|--------|
| Data feed precios | Sin datos > 5 min | OPEN | Pausar entradas, mantener stops |
| Data feed precios | Sin datos > 15 min | OPEN | Cerrar posiciones con mercado |
| Data feed noticias | Sin datos > 1 hora | OPEN | Solo estrategias técnicas |
| Broker connection | Desconexión > 2 min | OPEN | Alerta, retry automático |
| Broker connection | Desconexión > 10 min | OPEN | STOP global |
| ML models | Error predicción | OPEN | Usar última válida o pausar |
| ML models | Calibración ECE > 0.15 | OPEN | Modo defensivo |

### 6.2 Estados del Sistema

| Estado | Descripción | Entradas | Salidas | Trigger Entrada |
|--------|-------------|----------|---------|-----------------|
| NORMAL | Operativa completa | ✓ | ✓ | Default |
| DEFENSIVE | Exposición reducida | Solo alta confianza | ✓ | DD>10%, calibración degradada |
| OBSERVATION | Genera señales sin ejecutar | ✗ | ✓ | Fallo parcial sistemas |
| PAUSE | Solo gestiona existentes | ✗ | ✓ | Kill switch manual |
| EMERGENCY | Cierra todo | ✗ | Forzado | DD>15%, pérdida diaria>3% |

### 6.3 Kill Switch

**Activación automática:**
- Drawdown > 15%
- Pérdida diaria > 3%
- Pérdida semanal > 5%
- Error crítico no recuperable

**Activación manual:** Comando Telegram `/killswitch` o API

**Acción:** Market orders para cerrar TODO. Pausa indefinida.

**Reactivación:** Solo manual, requiere:
1. Revisión de causa
2. Confirmación explícita
3. Reset de contadores de pérdida

---

## 7. Monitoreo de Calibración ML

Referencia: Doc 5, sección 5.3 para detalles de calibración.

### 7.1 Métricas Monitoreadas

| Métrica | Ventana | Alerta si | Acción |
|---------|---------|-----------|--------|
| ECE (Expected Calibration Error) | 30 días | > 0.10 | Warning |
| ECE | 30 días | > 0.15 | Modo defensivo |
| Win rate real vs predicho | 30 días | Diverge > 15% | Revisar modelo |
| Feature drift (KS test) | 7 días | p < 0.01 en >20% features | Trigger retrain |

### 7.2 Proceso de Detección

```
Diariamente:
  1. Obtener predicciones últimos 30 días
  2. Comparar con resultados reales
  3. Calcular ECE por bins de confianza
  4. Si ECE > threshold → ajustar sizing
  
Semanalmente:
  1. KS test de features prod vs train
  2. Si drift significativo → alertar
```

### 7.3 Ajuste de Sizing por Calibración

| ECE | Multiplicador de Sizing |
|-----|------------------------|
| < 0.05 | 1.0 (bien calibrado) |
| 0.05 - 0.10 | 0.8 |
| 0.10 - 0.15 | 0.5 |
| > 0.15 | 0.0 (pausar estrategia ML) |

---

## 8. Correlaciones y Exposición

### 8.1 Matriz de Correlación

Calculada diariamente sobre retornos 60 días:

```
Si nueva posición tiene correlación > 0.7 con existente:
  → Rechazar O reducir sizing 50%
  
Si correlación promedio portfolio > 0.5:
  → Warning: portfolio poco diversificado
```

### 8.2 Exposición por Dimensión

| Dimensión | Límite | Cálculo |
|-----------|--------|---------|
| Sector | 40% | Σ posiciones del sector / capital |
| Geografía | 60% | Σ posiciones por región / capital |
| Divisa | 50% | Σ posiciones en divisa / capital |
| Asset class | 70% | Acciones, forex, crypto separados |

### 8.3 Beta del Portfolio

**Target:** 0.5 - 1.2 vs benchmark (SPY o equivalente EU)

| Beta | Interpretación | Acción |
|------|----------------|--------|
| < 0.5 | Muy defensivo | OK si régimen bearish |
| 0.5 - 1.2 | Normal | Sin acción |
| > 1.2 | Agresivo | Reducir posiciones con beta alto |

---

## 9. Reconciliación y Alertas

### 9.1 Reconciliación Diaria

Referencia: Doc 2, sección 8.2.

| Paso | Hora | Acción |
|------|------|--------|
| 1 | Cierre mercado + 30 min | Fetch posiciones de broker |
| 2 | +1 min | Comparar con PostgreSQL |
| 3 | +2 min | Si diferencia > 0.1% → CRITICAL |
| 4 | +5 min | Log resultado en audit |

### 9.2 Matriz de Alertas

| Evento | Severidad | Canal | Acción requerida |
|--------|-----------|-------|------------------|
| Posición ejecutada | INFO | Log | - |
| DD > 5% | WARNING | Telegram | Revisar |
| DD > 10% | ERROR | Telegram + Email | Acción en 1h |
| DD > 15% | CRITICAL | Telegram + Email + SMS | Inmediato |
| Discrepancia reconciliación | CRITICAL | Todos | Inmediato |
| Circuit breaker activado | ERROR | Telegram | Revisar causa |
| Kill switch activado | CRITICAL | Todos | Revisión completa |

### 9.3 Escalado

| Tiempo sin respuesta | Acción |
|---------------------|--------|
| 15 min (CRITICAL) | Re-envío + llamada |
| 1 hora (CRITICAL) | STOP automático si no ACK |
| 4 horas (ERROR) | Modo defensivo automático |

---

## 10. Stress Testing

### 10.1 Escenarios Predefinidos

| Escenario | Parámetros | Frecuencia |
|-----------|------------|------------|
| Flash Crash | -10% en 1 día | Mensual |
| Volatility Spike | VIX × 3 | Mensual |
| Correlation Breakdown | Todas correlaciones → 1 | Mensual |
| Liquidity Crisis | Spread × 5, slippage × 3 | Trimestral |
| 2020 COVID | Datos reales marzo 2020 | Trimestral |
| 2022 Tech Crash | Datos reales 2022 | Trimestral |

### 10.2 Métricas de Stress Test

| Métrica | Límite Aceptable |
|---------|------------------|
| Max DD en escenario | < 20% |
| Tiempo de recuperación | < 6 meses |
| Pérdida en peor día | < 5% |

### 10.3 Acciones Post-Test

| Resultado | Acción |
|-----------|--------|
| Pasa todos | Continuar normal |
| Falla 1 escenario | Revisar, ajustar límites |
| Falla 2+ escenarios | Reducir exposición hasta corregir |

---

## 11. Configuración

### 11.1 Archivo `config/risk.yaml`

```yaml
limits:
  max_position_pct: 0.20
  max_sector_pct: 0.40
  max_correlation: 0.70
  max_drawdown: 0.15
  min_cash: 0.10

temporal:
  max_daily_loss: 0.03
  max_weekly_loss: 0.05
  max_monthly_loss: 0.08

sizing:
  base_risk_pct: 0.01
  kelly_fraction: 0.25

alerts:
  telegram_chat_id: "xxx"
  email: "xxx@xxx.com"
  critical_phone: "+34xxx"
```

### 11.2 Límites NO Configurables

Estos valores están hardcoded en código, no en config:

- Max drawdown absoluto: 15%
- Kill switch triggers
- Veto del Risk Manager

**Razón:** Evitar que error de config comprometa capital.

---

## 12. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Risk Manager Agent | Doc 3 | 5 |
| MCP tools de riesgo | Doc 3 | 7.7 |
| Régimen detection | Doc 1 | 4.6 |
| Calibración ML | Doc 5 | 5.3 |
| Esquema audit | Doc 2 | 2.3 |
| Reconciliación BD | Doc 2 | 8.2 |
| Cost Model | Doc 1 | 4.8 |
| Modos de operación | Doc 1 | 5.3 |

---

*Documento 6 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
