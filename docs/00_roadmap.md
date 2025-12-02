# 🗺️ Roadmap de Implementación

## Bot de Trading Autónomo con IA

**Versión:** 1.1  
**Fecha:** Diciembre 2024  
**Estado:** En implementación

---

## 1. Visión General

### 1.1 Objetivo

Implementar el sistema de trading descrito en los documentos técnicos (Doc 1-7) de forma incremental, validando cada fase antes de avanzar.

### 1.2 Principios de Implementación

| Principio | Descripción |
|-----------|-------------|
| **Incremental** | Cada fase produce un entregable funcional |
| **Validable** | Criterios de éxito claros antes de avanzar |
| **Reversible** | Posibilidad de rollback si algo falla |
| **Documentado** | Código y decisiones trazables |

---

## 2. Diagrama de Dependencias

```
                    ┌─────────────────┐
                    │   FASE 0        │
                    │ Infraestructura │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌─────────────┐ ┌─────────────┐     │
       │   FASE 1    │ │   FASE 2    │     │
       │ Data Pipeline│ │ MCP Servers │     │
       └──────┬──────┘ └──────┬──────┘     │
              │               │             │
              └───────┬───────┘             │
                      ▼                     │
               ┌─────────────┐              │
               │   FASE 3    │◄─────────────┘
               │ Agentes Core│
               └──────┬──────┘
                      │
              ┌───────┴───────┐
              ▼               ▼
       ┌─────────────┐ ┌─────────────┐
       │   FASE 4    │ │   FASE 5    │
       │Motor Trading│ │ ML Pipeline │
       └──────┬──────┘ └──────┬──────┘
              │               │
              └───────┬───────┘
                      ▼
               ┌─────────────┐
               │   FASE 6    │
               │ Integración │
               └─────────────┘
```

---

## 3. Fases de Implementación

### 3.1 Resumen de Fases

| Fase | Nombre | Semanas | Docs Técnicos | Entregable |
|------|--------|---------|---------------|------------|
| 0 | Infraestructura Base | 2 | Doc 2, 7 | Docker + BD funcionando |
| 1 | Data Pipeline | 3 | Doc 2 | Ingesta y Feature Store |
| 2 | MCP Servers | 3 | Doc 3 | Servers desplegados |
| 3 | Agentes Core | 4 | Doc 3, 6 | Agentes comunicándose |
| 4 | Motor de Trading | 4 | Doc 4 | Estrategias + Backtesting |
| 5 | ML Pipeline | 4 | Doc 5 | Modelos entrenados |
| 6 | Integración | 4 | Doc 1, 7 | Sistema completo en paper |

**Total estimado:** 24 semanas (~6 meses)

### 3.2 Detalle por Fase

#### Fase 0: Infraestructura Base

**Objetivo:** Entorno de desarrollo y bases de datos operativos.

**Dependencias:** Ninguna

**Entregables:**
- Docker Compose funcional (PostgreSQL, TimescaleDB, Redis, InfluxDB)
- Esquemas de BD inicializados
- Scripts de verificación
- Grafana básico

**Criterio de éxito:** `docker-compose up` levanta todo, queries de prueba funcionan.

**Documento:** `fase_0_infraestructura.md`

---

#### Fase 1: Data Pipeline

**Objetivo:** Ingesta de datos de mercado y Feature Store operativo.

**Dependencias:** Fase 0

**Entregables:**
- Conectores a fuentes de datos (Yahoo Finance, IBKR)
- Pipeline de ingesta a TimescaleDB
- Feature Store con 30+ features
- Scheduler de actualización

**Criterio de éxito:** Features actualizados diariamente, queries < 100ms.

**Documento:** `fase_1_data_pipeline.md`

---

#### Fase 2: MCP Servers

**Objetivo:** Servidores MCP desplegados y respondiendo.

**Dependencias:** Fase 0

**Entregables:**
- mcp-market-data
- mcp-technical
- mcp-risk
- mcp-ibkr (modo paper)
- Tests de integración

**Criterio de éxito:** Todos los tools responden correctamente a llamadas de prueba.

**Documento:** `fase_2_mcp_servers.md`

---

#### Fase 3: Agentes Core

**Objetivo:** Agentes funcionando y comunicándose vía MCP.

**Dependencias:** Fase 1, Fase 2

**Entregables:**
- Technical Analyst Agent
- Risk Manager Agent
- Orchestrator (básico)
- Sistema de mensajería Redis pub/sub

**Criterio de éxito:** Orchestrator recibe señales y consulta Risk Manager.

**Documento:** `fase_3_agentes_core.md`

---

#### Fase 4: Motor de Trading

**Objetivo:** Estrategias implementadas y backtesting funcional.

**Dependencias:** Fase 3

**Entregables:**
- Strategy Registry
- 2 estrategias iniciales (`swing_momentum_eu`, `mean_reversion_pairs`)
- Framework de backtesting con costes
- Paper trading conectado a IBKR

**Criterio de éxito:** Backtest reproduce resultados esperados, paper trading ejecuta órdenes.

**Documento:** `fase_4_motor_trading.md`

---

#### Fase 5: ML Pipeline

**Objetivo:** Modelos entrenados y sirviendo predicciones.

**Dependencias:** Fase 1, Fase 3

**Entregables:**
- HMM para detección de régimen
- Pipeline de training con validación temporal
- mcp-ml-models sirviendo predicciones
- Monitoreo de calibración

**Criterio de éxito:** Régimen detectado correctamente, ECE < 0.10.

**Documento:** `fase_5_ml_pipeline.md`

---

#### Fase 6: Integración y Validación

**Objetivo:** Sistema completo operando en paper trading.

**Dependencias:** Fase 4, Fase 5

**Entregables:**
- Integración de todos los componentes
- Kill switch y circuit breakers
- Dashboard Grafana completo
- Alertas Telegram
- 30 días de paper trading validado

**Criterio de éxito:** Sistema opera autónomo 30 días, Sharpe > 0.5 en paper.

**Documento:** `fase_6_integracion.md`

---

## 4. Hitos de Validación

| Semana | Hito | Validación |
|--------|------|------------|
| 2 | Infra OK | BD responde, Docker estable |
| 5 | Data OK | Features generándose |
| 8 | MCP OK | Servers respondiendo |
| 12 | Agentes OK | Señales fluyendo |
| 16 | Trading OK | Backtest positivo |
| 20 | ML OK | Régimen detectado |
| 24 | Sistema OK | 30 días paper trading |

### 4.1 Gates de Avance

Cada fase requiere aprobación antes de avanzar:

| Gate | Criterio | Decisión si falla |
|------|----------|-------------------|
| G0→G1 | Infra estable 48h | Resolver antes de continuar |
| G1→G2 | Features sin NaN | Limpiar pipeline |
| G2→G3 | MCP 100% tools OK | Debuggear server fallido |
| G3→G4 | Mensajes llegando | Revisar pub/sub |
| G4→G5 | Sharpe backtest > 0 | Ajustar estrategia |
| G5→G6 | ECE < 0.15 | Re-calibrar modelo |
| G6→Prod | 30 días sin críticos | Extender paper trading |

---

## 5. Estado Actual

### 5.1 Documentos de Fase

| Fase | Documento | Estado |
|------|-----------|--------|
| R | `00_roadmap.md` | ✅ Completado |
| 0 | `fase_0_infraestructura.md` | ✅ Completado |
| 1 | `fase_1_data_pipeline.md` | ✅ Completado |
| 2 | `fase_2_mcp_servers.md` | ✅ Completado |
| 3 | `fase_3_agentes_core.md` | ✅ Completado |
| 4 | `fase_4_motor_trading.md` | ✅ Completado |
| 5 | `fase_5_ml_pipeline.md` | ✅ Completado |
| 6 | `fase_6_integracion.md` | ✅ Completado |

### 5.2 Progreso Global

```
Documentación de Fases:
═══════════════════════
Fase 0 [██████████] 100% - Documento completado
Fase 1 [██████████] 100% - Documento completado
Fase 2 [██████████] 100% - Documento completado
Fase 3 [██████████] 100% - Documento completado
Fase 4 [██████████] 100% - Documento completado
Fase 5 [██████████] 100% - Documento completado
Fase 6 [██████████] 100% - Documento completado
─────────────────────────
Documentación: 8/8 (100%)

Implementación:
═══════════════
(Pendiente de iniciar)
```

---

## 6. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| API IBKR cambia | Baja | Alto | Abstraer en capa de integración |
| Overfitting ML | Media | Alto | Validación temporal estricta |
| Datos de baja calidad | Media | Medio | Validaciones en ingesta |
| Complejidad MCP | Media | Medio | Empezar con servers simples |
| Timeline se extiende | Alta | Bajo | Fases independientes permiten pausas |

---

## 7. Recursos Requeridos

### 7.1 Infraestructura

| Recurso | Fase 0-3 | Fase 4-6 |
|---------|----------|----------|
| PC desarrollo | 16 GB RAM, 4 cores | Igual |
| VPS staging | No necesario | 4 vCPU, 8 GB |
| Cuenta IBKR Paper | Sí | Sí |
| APIs datos | Yahoo (gratis) | Alpha Vantage (gratis tier) |

### 7.2 Tiempo Estimado

| Dedicación | Duración total |
|------------|----------------|
| Full-time (40h/sem) | 6 meses |
| Part-time (20h/sem) | 12 meses |
| Hobby (10h/sem) | 18-24 meses |

---

## 8. Referencias

| Documento | Contenido relevante |
|-----------|---------------------|
| Doc 1 | Arquitectura general, KPIs, modos sistema |
| Doc 2 | BD, esquemas, feature store, Docker setup |
| Doc 3 | Agentes, MCP servers, comunicación |
| Doc 4 | Estrategias, backtesting, órdenes |
| Doc 5 | Modelos ML, training, validación |
| Doc 6 | Límites riesgo, sizing, circuit breakers |
| Doc 7 | Deployment, monitoring, runbooks |

---

## 9. Próximo Paso

**Siguiente documento a generar:** `fase_2_mcp_servers.md`

**Contenido esperado:**
- Estructura de MCP servers
- Implementación de tools por server
- Tests de integración
- Configuración y deployment

**Alternativa:** Fase 2 puede desarrollarse en paralelo con implementación de Fase 1.

---

*Roadmap v1.1 - Bot de Trading Autónomo*
