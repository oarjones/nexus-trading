# DOC-06: Manual de Usuario - Flujo del Sistema

> **Propósito**: Comprender cómo funciona Nexus Trading de principio a fin  
> **Audiencia**: Usuario/Operador que supervisa el sistema

---

## 1. Visión General del Sistema

Nexus Trading es un **laboratorio de estrategias** que ejecuta dos enfoques de trading en paralelo:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXUS TRADING STRATEGY LAB                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│    ┌─────────────────────┐              ┌─────────────────────┐            │
│    │   HMM RULES         │              │   AI AGENT SWING    │            │
│    │   STRATEGY          │              │   STRATEGY          │            │
│    │                     │              │                     │            │
│    │   💰 €25,000        │              │   💰 €25,000        │            │
│    │   🤖 Sistemática    │              │   🧠 Inteligente    │            │
│    │   📊 Reglas fijas   │              │   🔍 Web Search     │            │
│    └─────────────────────┘              └─────────────────────┘            │
│              │                                    │                        │
│              └──────────────┬───────────────────┘                         │
│                             │                                              │
│                             ▼                                              │
│                   ┌─────────────────────┐                                  │
│                   │   PAPER TRADING     │                                  │
│                   │   SIMULATOR         │                                  │
│                   │                     │                                  │
│                   │   Simula órdenes    │                                  │
│                   │   con datos reales  │                                  │
│                   └─────────────────────┘                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Comparativa de Estrategias

| Aspecto | HMM Rules | AI Agent Swing |
|---------|-----------|----------------|
| **Tipo** | Sistemática/Algorítmica | Inteligente/Discrecional |
| **Decisiones** | Reglas matemáticas fijas | Claude (LLM) analiza y decide |
| **Información** | Solo indicadores técnicos | Técnicos + Noticias (web search) |
| **Frecuencia** | 1x/día (10:00 UTC) | Cada 4 horas |
| **Objetivo** | Baseline predecible | Explorar capacidades de IA |

---

## 2. Flujo Principal del Sistema

### 2.1. Diagrama de Ciclo de Vida Diario

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CICLO DE VIDA DIARIO                               │
└─────────────────────────────────────────────────────────────────────────────┘

     06:00 UTC                                                    22:00 UTC
        │                                                            │
        ▼                                                            ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
   │SCREENING│───▶│  HMM    │───▶│   AI    │───▶│   AI    │───▶│ REPORTE │
   │ DIARIO  │    │ 10:00   │    │ 10:00   │    │ 14:00   │    │ DIARIO  │
   └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘
        │              │              │              │              │
        │              │              │              │              │
        ▼              ▼              ▼              ▼              ▼
   ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐
   │Filtrar  │    │Generar  │    │Generar  │    │Revisar  │    │Guardar  │
   │símbolos │    │señales  │    │señales  │    │portfolio│    │estado   │
   │activos  │    │(si hay) │    │(si hay) │    │(si hay) │    │final    │
   └─────────┘    └─────────┘    └─────────┘    └─────────┘    └─────────┘

                              │                      │
                              ▼                      ▼
                         ┌─────────┐           ┌─────────┐
                         │  AI     │           │   AI    │
                         │ 18:00   │           │  22:00  │
                         └─────────┘           └─────────┘
```

### 2.2. Detalle del Flujo de Ejecución

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DETALLADO DE EJECUCIÓN                             │
└─────────────────────────────────────────────────────────────────────────────┘

                              INICIO
                                │
                                ▼
                    ┌───────────────────────┐
                    │  1. CARGAR ESTADO     │
                    │  ─────────────────    │
                    │  • Portfolios JSON    │
                    │  • Config estrategias │
                    │  • Modelo HMM         │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  2. DETECTAR RÉGIMEN  │
                    │  ─────────────────    │
                    │  • Obtener datos SPY  │
                    │  • Ejecutar HMM       │
                    │  • Resultado: BULL,   │
                    │    BEAR, SIDEWAYS,    │
                    │    o VOLATILE         │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  3. SCREENING DIARIO  │
                    │  ─────────────────    │
                    │  • 150 símbolos       │
                    │  • Filtrar liquidez   │
                    │  • Filtrar tendencia  │
                    │  • Resultado: 30-50   │
                    │    símbolos activos   │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  4. SCHEDULER ACTIVO  │
                    │  ─────────────────    │
                    │  Esperando triggers:  │
                    │  • Cron (HMM 10:00)   │
                    │  • Interval (AI 4h)   │
                    └───────────────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
                ▼                               ▼
    ┌───────────────────────┐     ┌───────────────────────┐
    │  TRIGGER: HMM RULES   │     │  TRIGGER: AI AGENT    │
    └───────────────────────┘     └───────────────────────┘
                │                               │
                ▼                               ▼
    ┌───────────────────────┐     ┌───────────────────────┐
    │  5a. EJECUTAR HMM     │     │  5b. EJECUTAR AI      │
    │  ────────────────     │     │  ────────────────     │
    │  • Verificar régimen  │     │  • Construir contexto │
    │  • Aplicar reglas     │     │  • Web search (opt)   │
    │  • Generar señales    │     │  • Claude decide      │
    │  • Calcular sizing    │     │  • Generar señales    │
    └───────────────────────┘     └───────────────────────┘
                │                               │
                └───────────────┬───────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  6. SIMULAR ÓRDENES   │
                    │  ─────────────────    │
                    │  • Obtener precio     │
                    │  • Aplicar slippage   │
                    │  • Calcular comisión  │
                    │  • Actualizar cash    │
                    │  • Crear posición     │
                    └───────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  7. PERSISTIR ESTADO  │
                    │  ─────────────────    │
                    │  • Guardar portfolio  │
                    │  • Registrar trade    │
                    │  • Log de señal       │
                    │  • Tracking de coste  │
                    └───────────────────────┘
                                │
                                ▼
                       (Volver a paso 4)
```

---

## 3. Flujo del AI Agent en Detalle

El AI Agent es el componente más sofisticado. Aquí está su flujo interno:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DEL AI AGENT                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                         INICIO EJECUCIÓN
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │       1. CONSTRUIR CONTEXTO         │
              │  ───────────────────────────────    │
              │                                     │
              │  ┌─────────────┐  ┌─────────────┐  │
              │  │  Régimen    │  │  Portfolio  │  │
              │  │  BULL 0.75  │  │  €24,500    │  │
              │  └─────────────┘  └─────────────┘  │
              │                                     │
              │  ┌─────────────┐  ┌─────────────┐  │
              │  │  Mercado    │  │  Watchlist  │  │
              │  │  SPY +0.5%  │  │  30 símbolos│  │
              │  │  VIX 15.2   │  │  + técnicos │  │
              │  └─────────────┘  └─────────────┘  │
              └─────────────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │    2. PRIMERA LLAMADA A CLAUDE      │
              │  ───────────────────────────────    │
              │                                     │
              │  Sistema: "Eres un AI Trading       │
              │           Agent experto..."         │
              │                                     │
              │  Usuario: [Contexto completo]       │
              │           "Analiza y decide..."     │
              │                                     │
              │  Tools disponibles: [web_search]    │
              └─────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ ¿Claude quiere buscar?│
                    └───────────────────────┘
                          │           │
                         NO          SÍ
                          │           │
                          │           ▼
                          │  ┌─────────────────────────────────────┐
                          │  │      3. EJECUTAR WEB SEARCH         │
                          │  │  ───────────────────────────────    │
                          │  │                                     │
                          │  │  Claude pide:                       │
                          │  │  "NVDA earnings Q4 2024"            │
                          │  │                                     │
                          │  │         │                           │
                          │  │         ▼                           │
                          │  │  ┌─────────────┐                    │
                          │  │  │Brave Search │                    │
                          │  │  │    API      │                    │
                          │  │  └─────────────┘                    │
                          │  │         │                           │
                          │  │         ▼                           │
                          │  │  Resultados:                        │
                          │  │  • "NVDA beats estimates..."        │
                          │  │  • "Chip demand surges..."          │
                          │  │  • "Analysts raise targets..."      │
                          │  └─────────────────────────────────────┘
                          │           │
                          │           ▼
                          │  ┌─────────────────────────────────────┐
                          │  │   4. SEGUNDA LLAMADA A CLAUDE       │
                          │  │  ───────────────────────────────    │
                          │  │                                     │
                          │  │  [Contexto original]                │
                          │  │  +                                  │
                          │  │  [Resultados de búsqueda]           │
                          │  │                                     │
                          │  │  "Con esta información adicional,   │
                          │  │   genera tu decisión..."            │
                          │  └─────────────────────────────────────┘
                          │           │
                          └─────┬─────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │        5. PARSEAR RESPUESTA         │
              │  ───────────────────────────────    │
              │                                     │
              │  Claude responde:                   │
              │  {                                  │
              │    "market_view": "bullish",        │
              │    "confidence": 0.82,              │
              │    "reasoning": "NVDA muestra...",  │
              │    "signals": [                     │
              │      {                              │
              │        "symbol": "NVDA",            │
              │        "direction": "LONG",         │
              │        "entry_price": 875.50,       │
              │        "stop_loss": 850.00,         │
              │        "take_profit": 925.00,       │
              │        "confidence": 0.85           │
              │      }                              │
              │    ]                                │
              │  }                                  │
              └─────────────────────────────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │       6. REGISTRAR COSTES           │
              │  ───────────────────────────────    │
              │                                     │
              │  • Input tokens: 2,100              │
              │  • Output tokens: 450               │
              │  • Searches: 2                      │
              │  • Total cost: $0.028               │
              │                                     │
              │  → Guardar en data/costs/           │
              └─────────────────────────────────────┘
                                │
                                ▼
                        RETORNAR SEÑALES
```

---

## 4. Flujo del Sistema de Paper Trading

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE PAPER TRADING                                   │
└─────────────────────────────────────────────────────────────────────────────┘

              SEÑAL RECIBIDA
              (ej: LONG NVDA)
                    │
                    ▼
        ┌───────────────────────┐
        │ 1. VALIDAR SEÑAL      │
        │ ─────────────────     │
        │ • Confianza > 0.8?    │───── NO ──▶ RECHAZAR
        │ • Dentro de límites?  │
        │ • Cash disponible?    │
        └───────────────────────┘
                    │ SÍ
                    ▼
        ┌───────────────────────┐
        │ 2. OBTENER PRECIO     │
        │ ─────────────────     │
        │ • Consultar MCP       │
        │   Market Data         │
        │ • Precio actual:      │
        │   $875.50             │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ 3. SIMULAR SLIPPAGE   │
        │ ─────────────────     │
        │ • Base: 0.05%         │
        │ • $875.50 + $0.44     │
        │ • Fill price: $875.94 │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ 4. CALCULAR COMISIÓN  │
        │ ─────────────────     │
        │ • Modelo IBKR tiered  │
        │ • 10 shares × $0.005  │
        │ • = $1.00 (mínimo)    │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ 5. CALCULAR SIZING    │
        │ ─────────────────     │
        │ • Capital: €25,000    │
        │ • Max posición: 5%    │
        │ • = €1,250            │
        │ • Shares: 1           │
        │   (€1,250 ÷ $875.94)  │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ 6. EJECUTAR ORDEN     │
        │ ─────────────────     │
        │                       │
        │  ANTES:               │
        │  Cash: €24,500        │
        │  Posiciones: 2        │
        │                       │
        │  DESPUÉS:             │
        │  Cash: €23,623.06     │
        │  Posiciones: 3        │
        │  Nueva: NVDA × 1      │
        │         @ $875.94     │
        └───────────────────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │ 7. PERSISTIR          │
        │ ─────────────────     │
        │ • Actualizar JSON     │
        │ • Log del trade       │
        │ • Métricas            │
        └───────────────────────┘
                    │
                    ▼
               COMPLETADO
```

---

## 5. Flujo de Detección de Régimen (HMM)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DE DETECCIÓN DE RÉGIMEN                            │
└─────────────────────────────────────────────────────────────────────────────┘

        ┌───────────────────────────────────────────────────┐
        │                DATOS DE ENTRADA                   │
        │                                                   │
        │   SPY últimos 100 días:                          │
        │   ┌─────────────────────────────────────────┐    │
        │   │ Fecha      │ Close  │ Volume   │ ...    │    │
        │   │ 2024-01-01 │ 450.00 │ 45M      │        │    │
        │   │ 2024-01-02 │ 452.50 │ 52M      │        │    │
        │   │ ...        │ ...    │ ...      │        │    │
        │   └─────────────────────────────────────────┘    │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │            PREPARAR FEATURES                      │
        │                                                   │
        │   Para cada día calcular:                        │
        │   • Retorno diario: (close - prev) / prev        │
        │   • Volatilidad 20d: std(returns) × √252         │
        │   • Volumen relativo: volume / avg_volume        │
        │                                                   │
        │   ┌─────────────────────────────────────────┐    │
        │   │ return │ volatility │ rel_volume │       │    │
        │   │ +0.55% │   12.5%    │    1.15    │       │    │
        │   │ -0.22% │   12.8%    │    0.95    │       │    │
        │   └─────────────────────────────────────────┘    │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │              NORMALIZAR                           │
        │                                                   │
        │   Aplicar parámetros guardados del entrenamiento:│
        │   • mean = [0.0005, 0.15, 1.0]                   │
        │   • std = [0.012, 0.05, 0.3]                     │
        │                                                   │
        │   features_norm = (features - mean) / std        │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │              MODELO HMM                           │
        │                                                   │
        │   Hidden Markov Model con 4 estados:             │
        │                                                   │
        │   ┌─────┐    ┌─────┐    ┌─────┐    ┌─────┐      │
        │   │BULL │◀──▶│BEAR │◀──▶│SIDE │◀──▶│ VOL │      │
        │   │  0  │    │  1  │    │  2  │    │  3  │      │
        │   └─────┘    └─────┘    └─────┘    └─────┘      │
        │                                                   │
        │   El modelo calcula probabilidad de cada estado  │
        │   dado el historial de features                  │
        └───────────────────────────────────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────────────┐
        │              RESULTADO                            │
        │                                                   │
        │   Probabilidades:                                │
        │   ┌────────────────────────────────────┐         │
        │   │ BULL:     0.72  ████████████████░░ │         │
        │   │ BEAR:     0.08  ██░░░░░░░░░░░░░░░░ │         │
        │   │ SIDEWAYS: 0.15  ████░░░░░░░░░░░░░░ │         │
        │   │ VOLATILE: 0.05  █░░░░░░░░░░░░░░░░░ │         │
        │   └────────────────────────────────────┘         │
        │                                                   │
        │   Régimen detectado: BULL (72% confianza)        │
        └───────────────────────────────────────────────────┘
```

---

## 6. Flujo del Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FLUJO DEL DASHBOARD                                      │
└─────────────────────────────────────────────────────────────────────────────┘

     NAVEGADOR                    SERVIDOR                     DATOS
         │                           │                           │
         │   GET /                   │                           │
         │ ─────────────────────────▶│                           │
         │                           │   Leer portfolios.json    │
         │                           │ ─────────────────────────▶│
         │                           │◀─────────────────────────│
         │                           │                           │
         │                           │   Leer costs/*.json       │
         │                           │ ─────────────────────────▶│
         │                           │◀─────────────────────────│
         │                           │                           │
         │   HTML completo           │                           │
         │◀─────────────────────────│                           │
         │                           │                           │
         │   Conectar SSE            │                           │
         │   GET /sse/updates        │                           │
         │ ═══════════════════════▶ │                           │
         │                           │                           │
         │         (conexión abierta - streaming)                │
         │                           │                           │
    ┌────┴────┐                      │                           │
    │ Cada 5s │                      │                           │
    └────┬────┘                      │                           │
         │                           │   Leer estado actual      │
         │                           │ ─────────────────────────▶│
         │   SSE: {status, accounts} │◀─────────────────────────│
         │◀══════════════════════════│                           │
         │                           │                           │
         │   HTMX actualiza cards    │                           │
         │   (sin recargar página)   │                           │
         │                           │                           │
    ┌────┴────┐                      │                           │
    │ Cada 10s│                      │                           │
    └────┬────┘                      │                           │
         │   GET /partials/signals   │                           │
         │ ─────────────────────────▶│   Leer señales cache      │
         │                           │ ─────────────────────────▶│
         │   HTML tabla actualizada  │◀─────────────────────────│
         │◀─────────────────────────│                           │
         │                           │                           │
         │   Reemplazar solo tabla   │                           │
         │                           │                           │
```

---

## 7. Estados del Sistema

### 7.1. Estados Posibles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DIAGRAMA DE ESTADOS                                    │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌─────────────┐
                           │   STOPPED   │
                           │  (inicial)  │
                           └──────┬──────┘
                                  │ run_strategy_lab.py
                                  ▼
                           ┌─────────────┐
                           │INITIALIZING │
                           │             │
                           │ • Cargar    │
                           │   config    │
                           │ • Conectar  │
                           │   MCP       │
                           └──────┬──────┘
                                  │ Screening completado
                                  ▼
        ┌─────────────────────────────────────────────────┐
        │                    RUNNING                       │
        │  ┌─────────────────────────────────────────┐    │
        │  │                                         │    │
        │  │    ┌───────┐         ┌───────┐        │    │
        │  │    │ IDLE  │◀───────▶│EXECUTING│       │    │
        │  │    │       │ trigger │        │       │    │
        │  │    └───────┘         └───────┘        │    │
        │  │                                         │    │
        │  └─────────────────────────────────────────┘    │
        └─────────────────────────────────────────────────┘
                                  │ Ctrl+C / SIGTERM
                                  ▼
                           ┌─────────────┐
                           │ SHUTTING    │
                           │ DOWN        │
                           │             │
                           │ • Guardar   │
                           │   estado    │
                           │ • Generar   │
                           │   reporte   │
                           └──────┬──────┘
                                  │
                                  ▼
                           ┌─────────────┐
                           │   STOPPED   │
                           └─────────────┘
```

### 7.2. Estados de Régimen

```
                    ┌──────────────────────────┐
                    │         BULL             │
                    │  ────────────────────    │
                    │  • Estrategias activas   │
                    │  • Riesgo normal         │
                    │  • Buscar entradas       │
                    └────────────┬─────────────┘
                           ▲     │
              Retornos     │     │  Retornos
              positivos    │     │  negativos
                           │     ▼
       ┌───────────────────┴─────┴────────────────────┐
       │                                               │
       ▼                                               ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│       SIDEWAYS           │       │         BEAR             │
│  ────────────────────    │       │  ────────────────────    │
│  • Mean reversion        │       │  • Solo cierres          │
│  • Posiciones pequeñas   │◀─────▶│  • Cash máximo           │
│  • Rangos definidos      │       │  • Proteger capital      │
└──────────────────────────┘       └──────────────────────────┘
              │                                 │
              │       Alta                     │
              │     volatilidad                │
              │         │                      │
              └─────────┼──────────────────────┘
                        ▼
              ┌──────────────────────────┐
              │       VOLATILE           │
              │  ────────────────────    │
              │  • Pausar operaciones    │
              │  • Reducir exposición    │
              │  • Stops más amplios     │
              └──────────────────────────┘
```

---

## 8. Arquitectura de Componentes

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DE COMPONENTES                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAPA DE ORQUESTACIÓN                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │  StrategyLab    │  │ StrategyRunner  │  │ StrategyScheduler│            │
│  │  (main.py)      │──│  (ejecución)    │──│  (timing)       │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAPA DE ESTRATEGIAS                            │
│  ┌─────────────────────────────┐  ┌─────────────────────────────┐          │
│  │      HMMRulesStrategy       │  │      AIAgentStrategy        │          │
│  │  ┌───────────────────────┐  │  │  ┌───────────────────────┐  │          │
│  │  │ • Reglas por régimen  │  │  │  │ • ContextBuilder      │  │          │
│  │  │ • RSI thresholds      │  │  │  │ • ClaudeAgent         │  │          │
│  │  │ • Stop/Take profit    │  │  │  │ • WebSearchClient     │  │          │
│  │  └───────────────────────┘  │  │  │ • CostTracker         │  │          │
│  └─────────────────────────────┘  │  └───────────────────────┘  │          │
│                                    └─────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAPA DE DATOS                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│  │ UniverseManager │  │ PaperPortfolio  │  │  HMM Regime     │            │
│  │                 │  │    Manager      │  │   Detector      │            │
│  │ • 150 símbolos  │  │                 │  │                 │            │
│  │ • Screening     │  │ • 2 cuentas     │  │ • 4 estados     │            │
│  │ • Filtros       │  │ • Persistencia  │  │ • Probabilidad  │            │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAPA MCP (MICROSERVICIOS)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │  Market  │  │Technical │  │    ML    │  │   Risk   │  │   IBKR   │    │
│  │   Data   │  │          │  │  Models  │  │          │  │          │    │
│  │  :8001   │  │  :8002   │  │  :8003   │  │  :8004   │  │  :8005   │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAPA EXTERNA                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │  Interactive     │  │   Anthropic      │  │   Brave Search   │         │
│  │  Brokers TWS     │  │   Claude API     │  │   API            │         │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Secuencia de Comandos para Operar

### 9.1. Inicio del Sistema (Día Normal)

```bash
# Terminal 1: Servidores MCP (si no están en Docker)
cd nexus-trading
python -m mcp_servers.market_data.server &
python -m mcp_servers.technical.server &
python -m mcp_servers.ml_models.server &

# Terminal 2: Strategy Lab
python scripts/run_strategy_lab.py

# Terminal 3: Dashboard (opcional)
python scripts/run_dashboard.py
```

### 9.2. Verificación de Estado

```bash
# Ver logs en tiempo real
tail -f strategy_lab.log

# Ver estado del portfolio
cat data/paper_portfolios.json | python -m json.tool

# Ver costes del día
cat data/costs/$(date +%Y-%m-%d).json | python -m json.tool
```

### 9.3. Parada Graceful

```bash
# En la terminal del Strategy Lab
Ctrl+C

# El sistema:
# 1. Detiene el scheduler
# 2. Guarda estado del portfolio
# 3. Genera reporte del día
# 4. Sale limpiamente
```

---

## 10. Interpretación de Logs

### 10.1. Logs Normales

```
2024-01-15 10:00:00 - strategy_lab - INFO - ⏰ Scheduler activado para: hmm_rules
2024-01-15 10:00:01 - strategy.runner - INFO - START: Ejecutando estrategia hmm_rules
2024-01-15 10:00:02 - strategy.runner - INFO - Régimen actual: BULL (confianza: 0.72)
2024-01-15 10:00:03 - strategy.runner - INFO - Inyectados 35 símbolos del universo
2024-01-15 10:00:15 - strategy.hmm - INFO - Señal generada: BUY AAPL @ $185.50
2024-01-15 10:00:16 - paper.simulator - INFO - Order FILLED: BUY 5 AAPL @ $185.59
2024-01-15 10:00:16 - strategy.runner - INFO - END: Estrategia hmm_rules finalizada. 1 señales.
```

### 10.2. Logs de AI Agent

```
2024-01-15 14:00:00 - strategy_lab - INFO - ⏰ Scheduler activado para: ai_agent_swing
2024-01-15 14:00:01 - agent.claude - INFO - Building context with 35 symbols
2024-01-15 14:00:02 - agent.claude - INFO - Web search requested: 'NVDA earnings Q4 2024'
2024-01-15 14:00:03 - agent.search - INFO - Web search 'NVDA earnings Q4 2024': 5 results
2024-01-15 14:00:05 - agent.claude - INFO - Decision: bullish (confidence: 0.82)
2024-01-15 14:00:05 - cost_tracker - INFO - Cost recorded: $0.0280 | Tokens: 3200 | Searches: 1
```

### 10.3. Logs de Error

```
2024-01-15 10:00:05 - strategy.runner - ERROR - Error obteniendo datos para XYZ: Connection timeout
2024-01-15 10:00:05 - strategy.runner - WARNING - Usando símbolos de fallback
```

---

## 11. Preguntas Frecuentes

### ¿Qué pasa si el PC se reinicia?

El sistema guarda el estado en `data/paper_portfolios.json`. Al reiniciar:
1. Vuelve a cargar el estado guardado
2. Las posiciones y cash se recuperan exactamente
3. Continúa operando normalmente

### ¿Cómo sé si el sistema está funcionando?

1. **Dashboard**: Indicador verde "Running" en la esquina
2. **Logs**: Mensajes de "Scheduler activado" cada vez que toca
3. **Archivos**: `reports/YYYY-MM-DD/` se genera diariamente

### ¿Cuánto cuesta operar el AI Agent?

- **Estimado**: ~$0.024 por decisión
- **6 decisiones/día**: ~$0.15/día
- **Mensual**: ~$4.50/mes
- **Ver detalle**: Dashboard → AI Costs o `data/costs/`

### ¿Puedo pausar una estrategia sin parar todo?

Sí, edita `config/strategies.yaml`:
```yaml
ai_agent_swing:
  enabled: false  # Cambiar a false
```
Y reinicia el sistema. HMM seguirá funcionando.

### ¿Cómo añado un nuevo símbolo al universo?

1. Editar `config/symbols.yaml`
2. Añadir el símbolo con todos los campos requeridos
3. Ejecutar `python scripts/validate_universe.py`
4. Reiniciar el sistema

---

## 12. Glosario

| Término | Definición |
|---------|------------|
| **Régimen** | Estado del mercado detectado por HMM (BULL, BEAR, SIDEWAYS, VOLATILE) |
| **Screening** | Proceso de filtrar el universo maestro para obtener símbolos operables |
| **Señal** | Recomendación de trade (BUY, SELL, CLOSE) generada por una estrategia |
| **Paper Trading** | Simulación de trading con dinero ficticio pero precios reales |
| **MCP** | Model Context Protocol - Comunicación entre componentes |
| **Slippage** | Diferencia entre precio esperado y precio de ejecución |
| **ATR** | Average True Range - Medida de volatilidad |
| **RSI** | Relative Strength Index - Indicador de momentum |
| **HMM** | Hidden Markov Model - Modelo para detectar régimen |
