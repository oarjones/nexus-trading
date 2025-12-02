# 🧠 Arquitectura Técnica - Documento 5/7

## Machine Learning

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Visión General

### 1.1 Rol del ML en el Sistema

| Componente | Modelo | Propósito |
|------------|--------|-----------|
| Predicción de retornos | TFT (Temporal Fusion Transformer) | Dirección y magnitud esperada |
| Detección de régimen | HMM (Hidden Markov Model) | Estado del mercado |
| Meta-labeling | Gradient Boosting | Filtrar señales de baja calidad |
| Sentiment | FinBERT | Clasificación de noticias |

### 1.2 Principio Fundamental

**No predecir precios exactos.** Predecir:
- Probabilidad de movimiento > X% en horizonte Y
- Régimen actual (trending/ranging/volatile)
- Confianza de señales técnicas

---

## 2. Modelos Implementados

### 2.1 Temporal Fusion Transformer (TFT)

**Uso:** Predicción probabilística de retornos a 1-5 días.

| Aspecto | Especificación |
|---------|----------------|
| Input estático | Sector, país, market cap bucket |
| Input conocido futuro | Día semana, es earnings, es festivo |
| Input observado | Features técnicos (30+), ver Doc 2 sec 6.2 |
| Output | Cuantiles p10, p50, p90 de retorno |
| Horizonte | 1d, 3d, 5d (modelos separados) |

**Ventajas:** Interpretabilidad (attention weights), maneja múltiples horizontes, predicciones con incertidumbre.

**Hiperparámetros base:**

| Parámetro | Valor |
|-----------|-------|
| hidden_size | 64 |
| attention_heads | 4 |
| dropout | 0.1 |
| learning_rate | 1e-3 |
| batch_size | 64 |
| max_epochs | 100 (early stopping patience=10) |

### 2.2 Hidden Markov Model (Régimen)

**Uso:** Detectar estado del mercado. Referencia: Doc 1, sección 4.6.

| Estado | Características observadas |
|--------|---------------------------|
| Trending Bull | ADX alto, retornos positivos, vol baja |
| Trending Bear | ADX alto, retornos negativos, vol alta |
| Range-bound | ADX bajo, retornos ~0, vol baja |
| High Volatility | VIX elevado, vol alta |

**Features de entrada:** ADX(14), retorno 20d, volatilidad 20d, VIX (si disponible).

**Output:** Probabilidad de cada estado. Usar estado con p > 0.6; si ninguno, asumir Range-bound.

### 2.3 Meta-Labeling (Filtro de Señales)

**Concepto:** Modelo secundario que predice si una señal del modelo primario será rentable.

| Aspecto | Especificación |
|---------|----------------|
| Input | Señal primaria + features de contexto |
| Output | Probabilidad de trade ganador |
| Modelo | LightGBM |
| Threshold | Solo ejecutar si p > 0.55 |

**Features de contexto:**
- Confianza de señal primaria
- Régimen actual
- Volatilidad relativa (actual / media 60d)
- Distancia a soporte/resistencia
- Volumen relativo

**Beneficio:** Reduce false positives ~30%, mejora profit factor.

### 2.4 FinBERT (Sentiment)

**Uso:** Clasificar noticias. Referencia: Doc 3, sección 4.3.

| Aspecto | Especificación |
|---------|----------------|
| Modelo base | ProsusAI/finbert |
| Input | Título + primeras 200 palabras |
| Output | {positive, negative, neutral} + score |
| Agregación | Media ponderada por recencia (decay 12h) |

---

## 3. Feature Engineering

### 3.1 Catálogo de Features

Referencia completa: Doc 2, sección 6.2. Resumen:

| Categoría | Ejemplos | Count |
|-----------|----------|-------|
| Momentum | returns_1d/5d/20d, rsi_14, macd_hist | 8 |
| Volatilidad | volatility_20d, atr_14, bb_width | 5 |
| Volumen | volume_ratio_20d, obv_slope | 4 |
| Tendencia | sma_ratio_50/200, adx_14 | 5 |
| Cross-sectional | sector_momentum, market_beta_60d | 3 |
| Sentiment | news_sentiment_24h (si disponible) | 1 |
| Régimen | regime_probs (del HMM) | 4 |
| **Total** | | **~30** |

### 3.2 Transformaciones

| Transformación | Aplicación | Razón |
|----------------|------------|-------|
| Z-score rolling (60d) | Todos los features numéricos | Estacionariedad |
| Winsorization (1%, 99%) | Antes de z-score | Outliers |
| Log transform | Volumen, market cap | Distribución sesgada |
| One-hot | Sector, día semana | Categóricos |

**Crítico:** Z-score debe ser rolling, NO global. Evita data leakage.

### 3.3 Labeling (Triple Barrier Method)

En lugar de clasificar retorno simple, usar triple barrier:

```
upper_barrier = entry_price * (1 + profit_target)
lower_barrier = entry_price * (1 - stop_loss)
time_barrier = entry_time + max_holding_days

Label:
  +1 si toca upper primero
  -1 si toca lower primero
   0 si expira tiempo (o precio final)
```

**Parámetros default:** profit_target=2%, stop_loss=1%, max_days=5

---

## 4. Pipeline de Training

### 4.1 División Temporal

```
2018 ─────────────── 2021 ──── 2023 ──── 2024
|      TRAIN (60%)      | VAL (20%) | TEST (20%)|
                        |← embargo →|
```

| Set | Uso | Reglas |
|-----|-----|--------|
| Train | Entrenar modelo | OK re-usar múltiples veces |
| Validation | Tuning hiperparámetros | Re-usar con cautela |
| Test | Evaluación final | UNA sola vez por modelo |

**Embargo:** 5 días entre sets para evitar leakage temporal.

### 4.2 Purged K-Fold Cross-Validation

Para tuning en Train set:

| Parámetro | Valor |
|-----------|-------|
| n_splits | 5 |
| embargo_days | 5 |
| purge_days | max(feature_lookback) |

**Proceso:** Eliminar datos en ventana de purge/embargo entre train/val de cada fold.

### 4.3 Walk-Forward Validation

Simula deployment real:

```
FOR window in rolling_windows(train_data, size=2y, step=3m):
    model = train(window)
    result = evaluate(model, next_3_months)
    results.append(result)

final_metrics = aggregate(results)
varianza = std(results)

IF varianza > 0.5 * mean(results):
    WARN "Overfitting probable"
```

### 4.4 Proceso de Training

1. **Cargar features** desde Feature Store (Doc 2, sec 6)
2. **Generar labels** con triple barrier
3. **Split temporal** con embargo
4. **Purged CV** para hiperparámetros (Optuna, 50 trials)
5. **Entrenar modelo final** en Train completo
6. **Evaluar en Validation**
7. **Si métricas OK** → guardar modelo versionado
8. **Test** solo cuando modelo va a producción

---

## 5. Validación y Anti-Overfitting

### 5.1 Señales de Overfitting

| Señal | Indicador | Acción |
|-------|-----------|--------|
| Train >> Val performance | Sharpe train 2x Sharpe val | Simplificar modelo, más regularización |
| Alta varianza en WF | std(results) > 0.5 * mean | Reducir complejidad |
| Degradación en producción | Live << Paper | Revertir, investigar |

### 5.2 Técnicas de Regularización

| Técnica | Implementación |
|---------|----------------|
| Dropout | 0.1-0.3 en TFT |
| Early stopping | patience=10 en val loss |
| L2 regularization | weight_decay=1e-4 |
| Feature selection | Eliminar MDI < 0.01 |
| Ensemble | Bagging temporal (5 modelos, windows distintas) |

### 5.3 Calibración de Probabilidades

**Problema:** Modelo dice "70% confianza" pero acierta solo 55%.

**Métrica:** Expected Calibration Error (ECE)

```
ECE = Σ (|accuracy_bin - confidence_bin| * samples_bin / total)
```

**Target:** ECE < 0.05

**Solución si mal calibrado:**
1. Platt scaling (regresión logística post-hoc)
2. Isotonic regression
3. Temperature scaling (para neural nets)

**Monitoreo:** Risk Manager verifica calibración rolling 30d (Doc 1, sec 4.5).

---

## 6. MLOps Pragmático

### 6.1 Fases de Madurez

Referencia: Doc 1, sección 9.

| Fase | Herramientas | Trigger |
|------|--------------|---------|
| 1 (Actual) | DVC, YAML logs, timestamps en nombres | Inicio |
| 2 | MLflow local, model registry básico | 2+ modelos en prod |
| 3 | MLflow completo, A/B testing, auto-retrain | Sistema rentable |

### 6.2 Fase 1: Versionado Básico

**Estructura de archivos:**

```
models/
├── tft_1d/
│   ├── v1_20241201_abc123/
│   │   ├── model.pt
│   │   ├── config.yaml
│   │   ├── metrics.json
│   │   └── features_used.json
│   └── v2_20241215_def456/
├── hmm_regime/
└── metalabel/
```

**Convención de nombres:** `v{N}_{YYYYMMDD}_{hash_config[:6]}`

**Metadata mínima (metrics.json):**

```json
{
  "train_period": "2018-01-01/2021-12-31",
  "val_period": "2022-01-01/2023-12-31",
  "sharpe_val": 1.23,
  "ece": 0.04,
  "feature_count": 30,
  "trained_at": "2024-12-01T10:30:00Z"
}
```

### 6.3 Retraining Schedule

| Modelo | Frecuencia | Trigger adicional |
|--------|------------|-------------------|
| TFT | Trimestral | Sharpe rolling 3m < 0.5 |
| HMM | Semestral | Cambio estructural detectado |
| Meta-label | Mensual | Win rate < 40% en mes |
| FinBERT | No retrain | Modelo pre-entrenado |

**Proceso de retrain:**

1. Incluir datos nuevos en Train
2. Mover Val antiguo a Train, nuevo período a Val
3. Entrenar con mismos hiperparámetros (o re-tune si degradación)
4. Comparar métricas vs modelo actual
5. Si mejora > 5%: promover; si no: mantener actual

### 6.4 Rollback

**Criterio:** Modelo nuevo underperforma > 2 semanas en paper.

**Proceso:**
1. Revertir a versión anterior en config
2. Restart del MCP server `mcp-ml-models`
3. Log en audit con razón
4. Investigar causa antes de siguiente intento

---

## 7. Integración con Sistema

### 7.1 MCP Server: mcp-ml-models

Referencia: Doc 3, sección 7.4.

| Tool | Input | Output |
|------|-------|--------|
| `predict` | model_name, features | prediction, confidence, calibration_score |
| `get_model_info` | model_name | version, metrics, last_trained |
| `ensemble_predict` | model_names[], features | combined_prediction, individual |
| `get_regime` | - | regime, probability, since |

### 7.2 Flujo de Predicción

```
Feature Store → mcp-ml-models → Technical Agent → Orchestrator
                     ↓
              Redis cache (TTL 5min)
```

**Cache:** Predicciones se cachean en Redis con TTL 5min para evitar llamadas repetidas.

### 7.3 Ejemplo de Llamada

```python
# Desde Technical Analyst Agent
response = mcp_client.call_tool(
    "mcp-ml-models",
    "predict",
    {
        "model_name": "tft_1d",
        "features": feature_vector,
        "symbol": "AAPL"
    }
)
# response: {"prediction": 0.65, "confidence": 0.72, "calibration": 0.95}
```

---

## 8. Métricas de Monitoreo

### 8.1 Métricas en Producción

| Métrica | Frecuencia | Alerta si |
|---------|------------|-----------|
| Prediction latency | Por request | > 500ms |
| Calibration error (rolling 30d) | Diario | ECE > 0.10 |
| Feature drift | Diario | KS test p < 0.01 |
| Model staleness | Diario | > 90 días sin retrain |

### 8.2 Feature Drift Detection

Comparar distribución de features en producción vs training:

```
FOR each feature:
    ks_stat, p_value = ks_test(prod_distribution, train_distribution)
    IF p_value < 0.01:
        ALERT f"Drift detectado en {feature}"
```

**Acción:** Si > 20% features con drift → trigger retraining.

---

## 9. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Feature Store completo | Doc 2 | 6 |
| Catálogo de features | Doc 2 | 6.2 |
| Régimen detection uso | Doc 1 | 4.6 |
| Calibration-aware throttle | Doc 1 | 4.5 |
| MCP server tools | Doc 3 | 7.4 |
| Métricas de trading | Doc 4 | 3.5 |
| Estrategias que usan ML | Doc 4 | 1 |

---

*Documento 5 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
