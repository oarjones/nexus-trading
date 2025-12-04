# Informe de Análisis: Fase 2 - MCP Servers

**Proyecto:** nexus-trading  
**Fecha:** 3 de Diciembre 2025  
**Autor:** Análisis Técnico  
**Versión:** 1.0

---

## 1. Resumen Ejecutivo

| Aspecto | Evaluación | Comentario |
|---------|------------|------------|
| Completitud | ✅ **Alta** | 4/4 servers implementados con todos los tools |
| Calidad de Código | ✅ **Buena** | Bien estructurado, documentado, patrones consistentes |
| Tests | ⚠️ **Parcial** | Tests unitarios presentes, pero cobertura limitada en DB |
| Seguridad | ✅ **Excelente** | Múltiples salvaguardas en IBKR (paper-only, límites) |
| Integración F1 | ✅ **Correcta** | Uso apropiado de IndicatorEngine y BD |

**Valoración Global: 8/10** - Implementación sólida con algunas áreas de mejora.

---

## 2. Estructura Implementada

```
mcp_servers/
├── common/                 ✅ Implementado
│   ├── base_server.py     # Clase base MCP (~170 LOC)
│   ├── config.py          # Carga YAML + env vars
│   └── exceptions.py      # Jerarquía de excepciones
├── market_data/           ✅ 3 tools
│   └── tools/
│       ├── quotes.py      # get_quote
│       ├── ohlcv.py       # get_ohlcv
│       └── symbols.py     # get_symbols
├── technical/             ✅ 3 tools
│   └── tools/
│       ├── indicators.py  # calculate_indicators
│       ├── regime.py      # get_regime
│       └── support_resistance.py  # find_sr_levels
├── risk/                  ✅ 3 tools
│   └── tools/
│       ├── limits.py      # check_limits
│       ├── sizing.py      # calculate_size (Kelly)
│       └── exposure.py    # get_exposure (HHI)
├── ibkr/                  ✅ 5 tools
│   └── tools/
│       ├── connection.py  # IBKRConnection wrapper
│       ├── account.py     # get_account
│       ├── positions.py   # get_positions
│       └── orders.py      # place/cancel/status
└── tests/                 ✅ 4 test files
```

**LOC Totales MCP:** ~2,500 líneas (excluyendo tests)

---

## 3. Análisis de Calidad del Código

### 3.1 Fortalezas

| Aspecto | Detalle |
|---------|---------|
| **Arquitectura** | Patrón consistente: BaseMCPServer → Servers específicos → Tools modulares |
| **Documentación** | Docstrings completos con ejemplos, typing hints en todas las funciones |
| **Manejo Errores** | Jerarquía de excepciones (MCPError, ToolError, ConfigError, ValidationError) |
| **Seguridad IBKR** | Triple protección: `paper_only=true`, validación puerto 7497≠7496, max_order_value |
| **Logging** | Logging estructurado en todos los módulos |

### 3.2 Métricas de Calidad

```
┌─────────────────────┬────────┬──────────────────────────────┐
│ Métrica             │ Valor  │ Evaluación                   │
├─────────────────────┼────────┼──────────────────────────────┤
│ Complejidad ciclom. │ Baja   │ Funciones simples (<10 paths)│
│ Cohesión            │ Alta   │ 1 responsabilidad por tool   │
│ Acoplamiento        │ Medio  │ Deps. a src/data, sqlalchemy │
│ Typing coverage     │ ~95%   │ Falta en algunos dicts       │
│ Docstring coverage  │ 100%   │ Todos los públicos           │
└─────────────────────┴────────┴──────────────────────────────┘
```

---

## 4. Problemas Detectados

### 4.1 Problemas Críticos ❌

| # | Problema | Ubicación | Impacto |
|---|----------|-----------|---------|
| 1 | **Engine no se reutiliza** - Se crea nuevo SQLAlchemy engine por cada llamada a tool | `ohlcv.py:100`, `regime.py:72` | Performance: conexiones no pooled |
| 2 | **Cálculo rolling incorrecto** | `regime.py:118` | `sma_200 = ...rolling(200).mean().iloc[0]` calcula sobre datos DESC, debería ser `iloc[-1]` |
| 3 | **Volatilidad calcula sobre DESC** | `regime.py:125` | `returns.rolling(20).std().iloc[0]` - misma issue, orden de datos incorrecto |

### 4.2 Problemas Menores ⚠️

| # | Problema | Ubicación |
|---|----------|-----------|
| 4 | Path sys.path manipulation repetido en cada server.py | Todos los servers |
| 5 | `mcp-servers/` (con guión) vacío, estructura real es `mcp_servers/` | Directorio raíz |
| 6 | Tests marcan `@pytest.mark.integration` pero no hay configuración CI para ejecutarlos separados | tests/ |
| 7 | `conftest.py` importa paths incorrectos (`mcp-servers` vs `mcp_servers`) | tests/conftest.py |
| 8 | Falta validación de entrada en algunos tools (ej: `avg_loss=0` en Kelly divide por 0) | sizing.py |

### 4.3 Código Problemático - Ejemplo

```python
# regime.py:118 - BUG: datos están en orden DESC
ohlcv_df = pd.read_sql(ohlcv_query, conn, params={'symbol': symbol})
# ^^ ORDER BY time DESC

# Después:
sma_200 = ohlcv_df['close'].rolling(200).mean().iloc[0]  # ❌ iloc[0] es el más reciente!
# Debería ser iloc[-1] o reordenar: ohlcv_df = ohlcv_df.iloc[::-1]
```

---

## 5. Mejoras Sugeridas

### 5.1 Alta Prioridad

1. **Corregir orden de datos en regime.py**
   ```python
   # Solución: Reordenar antes de calcular
   ohlcv_df = ohlcv_df.iloc[::-1]  # Orden cronológico
   sma_200 = ohlcv_df['close'].rolling(200).mean().iloc[-1]
   ```

2. **Pool de conexiones centralizado**
   ```python
   # En common/database.py
   from src.database import DatabasePool
   
   class BaseMCPServer:
       def __init__(self, name, config_path):
           self.db = DatabasePool(os.getenv('DATABASE_URL'))
   ```

3. **Validación de inputs robusta**
   ```python
   # En sizing.py
   if avg_loss <= 0:
       raise ValidationError("avg_loss must be positive")
   ```

### 5.2 Media Prioridad

| Mejora | Beneficio |
|--------|-----------|
| Crear `mcp_servers/__init__.py` con imports limpios | Evitar sys.path hacks |
| Añadir health check endpoint `/health` en cada server | Monitorización |
| Cache Redis para indicadores calculados | Performance |
| Métricas Prometheus en tools | Observabilidad |

### 5.3 Baja Prioridad

- Eliminar directorio vacío `mcp-servers/`
- Unificar estilo de imports (absolute vs relative)
- Añadir pre-commit hooks para linting

---

## 6. Dependencias entre Fases

### 6.1 Fase 2 → Fase 1 (Dependencias)

```
┌───────────────────────┐     ┌─────────────────────────┐
│      FASE 2           │     │        FASE 1           │
│    MCP Servers        │────▶│     Data Pipeline       │
└───────────────────────┘     └─────────────────────────┘

Dependencias concretas:
─────────────────────────────────────────────────────────
technical/tools/indicators.py ──▶ src/data/indicators.py (IndicatorEngine)
market_data/tools/ohlcv.py   ──▶ market_data.ohlcv (TimescaleDB)
technical/tools/regime.py    ──▶ market_data.indicators (TimescaleDB)
Todos los servers            ──▶ config/symbols.yaml
```

### 6.2 Uso de Componentes de Fase 1

| Componente F1 | Usado por F2 | Estado |
|---------------|--------------|--------|
| `IndicatorEngine` | technical/indicators.py | ✅ Correcto |
| `DatabasePool` | indicators.py | ✅ Correcto |
| Tabla `ohlcv` | market_data, technical | ✅ Correcto |
| Tabla `indicators` | technical/regime | ✅ Correcto |
| `symbols.yaml` | market_data/symbols | ✅ Correcto |

### 6.3 Fase 2 → Fase 3 (Consumidores)

```
Fase 3 (Agentes) consumirá:
├── mcp-market-data:3001  ──▶ Technical Analyst Agent
├── mcp-technical:3002    ──▶ Technical Analyst Agent
├── mcp-risk:3003         ──▶ Risk Manager Agent
└── mcp-ibkr:3004         ──▶ Execution Agent
```

---

## 7. Tests y Cobertura

### 7.1 Estado Actual

| Test File | Tools Cubiertos | Tipo |
|-----------|-----------------|------|
| test_risk.py | check_limits, calculate_size, get_exposure | ✅ Unit |
| test_market_data.py | get_symbols | ⚠️ Parcial (sin DB) |
| test_technical.py | Imports only | ⚠️ Stub |
| test_ibkr.py | Estructural | ⚠️ Requiere TWS |

### 7.2 Cobertura Estimada

```
Risk Server:      ~80% (buen cubrimiento)
Market Data:      ~30% (solo get_symbols)
Technical:        ~20% (solo imports)
IBKR:             ~10% (requiere Gateway)
─────────────────────────────────
Promedio:         ~35%
```

### 7.3 Recomendaciones de Testing

1. **Mocking de BD** para tests sin dependencias
2. **Fixtures de OHLCV** para technical tests
3. **Marker `@pytest.mark.ibkr`** para separar tests que requieren TWS

---

## 8. Verificación de Requisitos

Checklist según `fase_2_mcp_servers.md`:

| Tarea | Estado | Notas |
|-------|--------|-------|
| 2.1 Estructura base | ✅ | BaseMCPServer implementado |
| 2.2 mcp-market-data | ✅ | 3 tools: quote, ohlcv, symbols |
| 2.3 mcp-technical | ✅ | 3 tools: indicators, regime, S/R |
| 2.4 mcp-risk | ✅ | 3 tools: limits, sizing, exposure |
| 2.5 mcp-ibkr | ✅ | 5 tools con safety checks |
| 2.6 Tests integración | ⚠️ | Parcial, ~35% coverage |
| 2.7 Script verificación | ✅ | verify_mcp_servers.py |
| 2.8 Docker config | ⚠️ | En docker-compose pero no probado |

---

## 9. Conclusiones

### Lo que funciona bien ✅
- Arquitectura modular y extensible
- Código limpio con buena documentación
- Seguridad robusta en IBKR (paper-only, límites)
- Implementación matemática correcta de Kelly Criterion y HHI
- Script de verificación comprehensivo

### Lo que necesita atención ⚠️
- **BUG CRÍTICO**: Orden de datos en `regime.py` produce cálculos incorrectos
- Connection pooling no óptimo
- Tests con cobertura insuficiente para producción

### Prioridades para siguiente sprint
1. 🔴 Corregir bug de orden de datos en regime.py
2. 🟡 Centralizar pool de conexiones
3. 🟡 Aumentar cobertura de tests a >70%
4. 🟢 Validación de entrada en todos los tools

---

**Firma:** Análisis generado para Oscar - Proyecto nexus-trading  
**Próximo paso:** Corregir issues críticos antes de avanzar a Fase 3
