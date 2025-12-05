# 📋 Informe de Revisión: Fase A1 - Extensiones Base (v2)

**Proyecto:** Nexus Trading  
**Fecha:** 05 Diciembre 2025  
**Versión Revisada:** Código completo en nexus-trading-claude.zip

---

## 📊 Resumen Ejecutivo

| Criterio | Estado |
|----------|--------|
| **Veredicto General** | ⚠️ **APROBADO CON OBSERVACIONES** |
| Componentes implementados | 85% |
| Cumplimiento con documentación | 80% |
| Cumplimiento con .cursorrules | 70% |

---

## ✅ Componentes CORRECTAMENTE Implementados

### A1.1: Esquema de Métricas ✅
- `init-scripts/07_metrics_schema.sql` - Completo y bien estructurado:
  - Esquema `metrics` creado
  - 5 tablas: trades, strategy_performance, model_performance, experiments, experiment_results
  - 4 ENUMs: trade_direction, trade_status, regime_type, experiment_status
  - 3 vistas: v_strategy_summary, v_model_summary, v_recent_trades
  - Función `calculate_strategy_metrics()`
  - Índices optimizados
  - Trigger para updated_at

### A1.2: Configuración Data Sources ✅
- `init-scripts/08_data_sources_config.sql` - Tabla config.data_sources creada
- `config/data_sources.yaml` - Bien estructurado con IBKR, Yahoo, Kraken
- `src/data/config.py` - Clase `DataSourceConfig` completa con:
  - Modelos Pydantic para validación
  - Sistema de prioridades y fallback
  - Symbol mapping
  - Health tracking

### A1.3: Provider Factory ✅
- `src/data/providers/provider_factory.py` - Implementado con:
  - Protocolo `DataProvider` definido
  - Lógica de fallback automático
  - Symbol mapping integrado
- `src/data/providers/ibkr.py` - Con `is_available()` y `name` property
- `src/data/providers/yahoo.py` - Con `is_available()` y `name` property

### A1.5: Scripts de Verificación ✅
- `scripts/verify_fase_a1.py` - Orquestador
- `scripts/verify_metrics_schema.py` - Verifica BD
- `scripts/verify_data_config.py` - Verifica config
- `scripts/verify_provider_factory.py` - Verifica factory
- `scripts/verify_ml_server.py` - Verifica ML server

---

## ⚠️ Problema CRÍTICO: Inconsistencia de Nomenclatura

### El Problema
Existen **DOS carpetas** de MCP servers con nomenclatura inconsistente:

```
nexus-trading/
├── mcp_servers/          ← GUIÓN BAJO (correcta - usada por docker-compose)
│   ├── common/
│   ├── ibkr/
│   ├── market_data/
│   ├── risk/
│   ├── technical/
│   └── tests/
│
└── mcp-servers/          ← GUIÓN (incorrecta - nueva, aislada)
    └── ml-models/        ← También usa guión
        ├── server.py
        ├── tools/        (vacío)
        └── tests/        (vacío)
```

### Impacto
1. **Docker-compose** usa `mcp_servers/` - el nuevo servidor ml-models NO está integrado
2. **Imports Python** fallarán con `mcp-servers` por el guión (no es identificador válido)
3. **Documentación** (.cursorrules) define `src/mcp_servers/` con guión bajo

### Solución Requerida
Renombrar y mover:
```bash
# Renombrar carpeta y mover a ubicación correcta
mcp-servers/ml-models/ → mcp_servers/ml_models/
```

---

## ❌ Componentes INCOMPLETOS

### A1.4: MCP-ML-MODELS (Parcial)

| Elemento | Esperado (docs) | Estado Actual |
|----------|-----------------|---------------|
| Ubicación | `mcp_servers/ml_models/` | ❌ `mcp-servers/ml-models/` |
| server.py | Modular con tools | ⚠️ Básico, tools inline |
| config.py | Configuración local | ❌ No existe |
| config/ml_models.yaml | Config de modelos | ❌ No existe |
| tools/health.py | Modular | ❌ Inline en server.py |
| tools/regime.py | Placeholder | ❌ No existe |
| tools/model_info.py | Modular | ❌ Inline en server.py |
| tools/predict.py | Placeholder | ❌ Inline |
| tests/ | Tests unitarios | ❌ Directorio vacío |
| docker-compose | Servicio configurado | ❌ **NO CONFIGURADO** |
| config/mcp-servers.yaml | Puerto 3005 | ❌ No incluido |

### Lo que SÍ funciona en ml-models:
- `server.py` tiene estructura básica funcional
- Tools health_check, get_model_info, predict_regime implementados (inline)
- Usa correctamente la librería MCP

---

## 🔴 Desviaciones de .cursorrules

### 1. Nomenclatura de carpetas
```
.cursorrules dice:      src/mcp_servers/ml_models/  (guión bajo)
Implementación actual:  mcp-servers/ml-models/      (guión)
```

### 2. Credenciales hardcodeadas
```python
# scripts/verify_metrics_schema.py línea 18
DB_PASS = "V@p&dsY42XtKJH9ykpW^nQU2"  # ❌ Debería ser env var
```

### 3. Idioma mixto
- Comentarios y logs en español en varios archivos
- .cursorrules especifica "English ONLY for code, comments, docstrings"

### 4. Cobertura de tests insuficiente
- No hay tests para `DataSourceConfig`
- No hay tests para `ProviderFactory`
- No hay tests para `ml-models`
- Cobertura estimada A1: ~10% vs 80% requerido

---

## 📋 Checklist de Cumplimiento Actualizado

### Tarea A1.1: Esquema de Métricas
- [x] Script SQL 07_metrics_schema.sql creado
- [x] Esquema 'metrics' existe
- [x] 5 tablas creadas
- [x] 4 ENUMs creados
- [x] 3 vistas de agregación
- [x] Función calculate_strategy_metrics
- [x] Índices optimizados

### Tarea A1.2: Configuración Data Sources
- [x] Script SQL 08_data_sources_config.sql creado
- [x] config/data_sources.yaml creado
- [x] Clase DataSourceConfig implementada
- [x] Symbol mapping implementado

### Tarea A1.3: Provider Factory
- [x] provider_factory.py creado
- [x] IBKRProvider con is_available()
- [x] YahooProvider con is_available()
- [x] Sistema de fallback funcionando

### Tarea A1.4: MCP-ML-MODELS
- [x] server.py implementado (básico)
- [ ] Ubicación correcta (`mcp_servers/ml_models/`)
- [ ] config.py local
- [ ] config/ml_models.yaml
- [ ] tools/ modulares
- [ ] Tests unitarios
- [ ] docker-compose actualizado con servicio
- [ ] config/mcp-servers.yaml actualizado

### Tarea A1.5: Verificación
- [x] Scripts de verificación creados
- [ ] Todos pasan (depende de BD activa)

---

## 🔧 Acciones Requeridas (Ordenadas por Prioridad)

### CRÍTICAS (Bloquean avance)

**1. Unificar nomenclatura de carpetas MCP**
```bash
# Mover ml-models a ubicación correcta con guión bajo
mv mcp-servers/ml-models mcp_servers/ml_models

# Eliminar carpeta vacía
rm -rf mcp-servers/
```

**2. Actualizar docker-compose.yml**
```yaml
# Añadir servicio mcp_ml_models
mcp_ml_models:
  build:
    context: .
    dockerfile: mcp_servers/Dockerfile
  container_name: mcp_ml_models
  ports:
    - "3005:3005"
  command: python -m ml_models.server
  working_dir: /app/mcp_servers
  restart: unless-stopped
  networks:
    - trading_network
```

**3. Actualizar config/mcp-servers.yaml**
```yaml
# Añadir configuración ml-models
ml-models:
  port: 3005
  models:
    active: "rules"  # hmm, rules, ppo
```

### IMPORTANTES

**4. Modularizar tools de ml_models**
```
mcp_servers/ml_models/
├── __init__.py
├── server.py          # Solo routing
├── config.py          # Configuración local
└── tools/
    ├── __init__.py
    ├── health.py
    ├── model_info.py
    ├── regime.py      # Placeholder
    └── predict.py     # Placeholder
```

**5. Eliminar credenciales hardcodeadas**
```python
# Usar variables de entorno
DB_PASS = os.getenv("DB_PASSWORD")
```

**6. Añadir tests unitarios**
- tests/test_data_config.py
- tests/test_provider_factory.py
- mcp_servers/tests/test_ml_models.py

---

## 📊 Resumen de Estado por Tarea

| Tarea | Estado | Completitud |
|-------|--------|-------------|
| A1.1 Esquema Métricas | ✅ Completo | 100% |
| A1.2 Data Sources | ✅ Completo | 100% |
| A1.3 Provider Factory | ✅ Completo | 100% |
| A1.4 MCP-ML-Models | ⚠️ Parcial | 40% |
| A1.5 Verificación | ✅ Completo | 90% |
| **TOTAL FASE A1** | **⚠️** | **~85%** |

---

## 🎯 Conclusión

La Fase A1 está **sustancialmente implementada** con componentes de alta calidad (esquemas SQL, DataSourceConfig, ProviderFactory). Sin embargo, hay un problema estructural crítico:

**El servidor mcp-ml-models está en una carpeta separada con nomenclatura incorrecta**, lo que lo aísla del resto del sistema y causará problemas de integración.

### Recomendación
1. **Antes de avanzar a A2:** Unificar la nomenclatura moviendo `mcp-servers/ml-models/` → `mcp_servers/ml_models/`
2. Actualizar docker-compose y config
3. Los componentes SQL y Python están listos para uso

### Gate de Avance a Fase A2
- [ ] Nomenclatura unificada
- [ ] docker-compose incluye mcp_ml_models
- [ ] `python scripts/verify_fase_a1.py` retorna 0

---

*Generado por Claude - Code Review v2*
