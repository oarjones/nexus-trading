# Prompt Template - Roadmap de Implementación

## Contexto del Proyecto

- **Capital inicial:** 1.000 €
- **Aportaciones:** 300‑500 €/mes
- **Horizonte:** 3‑5 años
- **Experiencia:** MCP y proyecto *auriga*
- **Brokers:** Interactive Brokers, Kraken (crypto)
- **Objetivo:** Independencia financiera a largo plazo

---

## Documentación Técnica Completada

| Documento | Archivo | Contenido |
|-----------|---------|-----------|
| Base conceptual | `trading_bot_concept.md` | Visión, estrategias, restricciones |
| Doc 1 | `01_arquitectura_vision_general.md` | Arquitectura alto nivel, KPIs, modos |
| Doc 2 | `02_arquitectura_datos.md` | BD, schemas, feature store, pipelines |
| Doc 3 | `03_sistema_agentes_mcp.md` | Agentes, MCP servers, comunicación |
| Doc 4 | `04_motor_trading.md` | Estrategias, backtesting, órdenes |
| Doc 5 | `05_machine_learning.md` | Modelos, training, validación |
| Doc 6 | `06_gestion_riesgo.md` | Límites, position sizing, circuit breakers |
| Doc 7 | `07_operaciones.md` | Deployment, monitoring, runbooks |

---

## Estructura de Implementación (2 Niveles)

### Nivel 1: Roadmap (índice maestro)
- Vista global de fases
- Dependencias entre fases
- Estado general del proyecto
- Timeline estimado

### Nivel 2: Documentos de Fase (autocontenidos)

| Fase | Nombre | Dependencias | Docs Técnicos |
|------|--------|--------------|---------------|
| 0 | Infraestructura Base | - | Doc 2, 7 |
| 1 | Data Pipeline | Fase 0 | Doc 2 |
| 2 | MCP Servers | Fase 0 | Doc 3 |
| 3 | Agentes Core | Fase 1, 2 | Doc 3, 6 |
| 4 | Motor de Trading | Fase 3 | Doc 4 |
| 5 | ML Pipeline | Fase 1, 3 | Doc 5 |
| 6 | Integración y Validación | Fase 4, 5 | Doc 1, 7 |

---

## Reglas para Generación de Documentos

### Generales
1. **Concisión:** Explicaciones de 2-3 líneas máximo
2. **Sin redundancia:** Referencias cruzadas a docs técnicos, no copiar
3. **Tamaño:** Roadmap ~200-300 líneas, Fases ~400-600 líneas

### Para Tareas
1. **Granularidad:** Tareas completables en 1-4 horas de trabajo de agente
2. **Autocontenidas:** Cada tarea tiene contexto suficiente
3. **Pseudocódigo:** Preferible a código completo (agentes generarán implementación)
4. **Criterio de éxito:** Cada tarea define cómo saber que está completada

### Para Agentes IA
1. **Instrucciones claras:** Qué hacer, no cómo pensar
2. **Referencias explícitas:** "Ver Doc X, sección Y" cuando necesario
3. **Inputs/Outputs definidos:** Qué recibe, qué debe producir
4. **Tests verificables:** Cómo validar que funciona

---

## Formato de Checklist

```markdown
### Tarea X.Y: Nombre de la Tarea

**Estado:** ⬜ Pendiente | 🔄 En curso | ✅ Completado

**Objetivo:** [1 línea]

**Referencias:** Doc X sec Y, Doc Z sec W

**Subtareas:**
- [ ] Subtarea 1
- [ ] Subtarea 2
- [ ] Subtarea 3

**Input:** [Qué necesita para empezar]

**Output:** [Qué debe producir]

**Validación:** [Cómo saber que está bien]

**Pseudocódigo:** (si aplica)
```python
# Estructura general, no implementación completa
class NombreClase:
    def metodo_principal(self, param):
        # 1. Paso uno
        # 2. Paso dos
        # 3. Retornar resultado
        pass
```
```

---

## Documentos Pendientes de Generar

| # | Documento | Estado |
|---|-----------|--------|
| R | `00_roadmap.md` | ✅ Completado |
| F0 | `fase_0_infraestructura.md` | ✅ Completado |
| F1 | `fase_1_data_pipeline.md` | ✅ Completado |
| F2 | `fase_2_mcp_servers.md` | ✅ Completado  |
| F3 | `fase_3_agentes_core.md` | ✅ Completado |
| F4 | `fase_4_motor_trading.md` | ✅ Completado |
| F5 | `fase_5_ml_pipeline.md` | ✅ Completado |
| F6 | `fase_6_integracion.md` | ✅ Completado |

---

## Solicitud Actual

> **Generar:** `[NOMBRE_DOCUMENTO]`
>
> **Instrucciones específicas:**
> - [Instrucción 1]
> - [Instrucción 2]
>
> **Confirmar comprensión antes de generar.**

---

## Ejemplo de Uso

### Para generar el Roadmap:
```
> **Generar:** `00_roadmap.md`
>
> **Instrucciones específicas:**
> - Incluir diagrama de dependencias entre fases
> - Estimar timeline en semanas
> - Marcar hitos clave de validación
```

### Para generar una Fase:
```
> **Generar:** `fase_0_infraestructura.md`
>
> **Instrucciones específicas:**
> - Foco en Docker + PostgreSQL + Redis
> - Incluir scripts de inicialización
> - Tareas para Windows 11 (entorno desarrollo)
```

---

## Notas para el Asistente

1. **Siempre revisar** los documentos técnicos del proyecto antes de generar
2. **Mantener consistencia** con nomenclatura y estructura existente
3. **Pedir confirmación** antes de generar documento completo
4. **Actualizar** tabla de documentos pendientes tras cada generación
