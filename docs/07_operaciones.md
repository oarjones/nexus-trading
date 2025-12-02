# 🚀 Arquitectura Técnica - Documento 7/7

## Operaciones

**Versión:** 1.0  
**Fecha:** Diciembre 2024  
**Proyecto:** Bot de Trading Autónomo con IA

---

## 1. Entornos

### 1.1 Matriz de Entornos

| Entorno | Propósito | Datos | Trading | Infra |
|---------|-----------|-------|---------|-------|
| **dev** | Desarrollo local | Mock/sample | No | Docker local |
| **staging** | Paper trading | Real-time | Paper | Docker local/VPS |
| **prod** | Trading real | Real-time | Sí | VPS dedicado |

### 1.2 Requisitos por Entorno

| Recurso | dev | staging | prod |
|---------|-----|---------|------|
| CPU | 4 cores | 4 vCPU | 8 vCPU |
| RAM | 8 GB | 8 GB | 16 GB |
| Disco | 50 GB | 200 GB SSD | 500 GB NVMe |
| Red | Local | 100 Mbps | 1 Gbps, <50ms broker |

### 1.3 Variables de Entorno

Archivo `.env.{entorno}`:

```env
# Común
ENVIRONMENT=prod
LOG_LEVEL=INFO

# Base de datos (ver Doc 2, sec 9.5)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
INFLUXDB_URL=http://...

# Brokers
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
KRAKEN_API_KEY=xxx
KRAKEN_API_SECRET=xxx

# Alertas
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx
ALERT_EMAIL=xxx@xxx.com
```

---

## 2. Docker Compose - Producción

### 2.1 Arquitectura de Contenedores

```
┌─────────────────────────────────────────────────────────┐
│                      NGINX (proxy)                      │
├─────────┬─────────┬─────────┬─────────┬────────────────┤
│ trading │ mcp-*   │ grafana │ prom    │ alertmanager   │
│  -core  │ servers │         │ etheus  │                │
├─────────┴─────────┴─────────┴─────────┴────────────────┤
│     postgres/timescale  │  redis  │  influxdb          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 docker-compose.prod.yml

```yaml
version: '3.8'

services:
  # === DATOS (ver Doc 2, sec 9.1) ===
  postgres:
    image: timescale/timescaledb:latest-pg15
    environment:
      POSTGRES_USER: trading
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "trading"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

  influxdb:
    image: influxdb:2.7
    environment:
      DOCKER_INFLUXDB_INIT_MODE: setup
      DOCKER_INFLUXDB_INIT_USERNAME: admin
      DOCKER_INFLUXDB_INIT_PASSWORD: ${INFLUX_PASSWORD}
      DOCKER_INFLUXDB_INIT_ORG: trading
      DOCKER_INFLUXDB_INIT_BUCKET: trading
    volumes:
      - influx_data:/var/lib/influxdb2
    restart: always

  # === APLICACIÓN ===
  trading-core:
    build: .
    env_file: .env.prod
    depends_on:
      - postgres
      - redis
    volumes:
      - ./config:/app/config:ro
      - ./logs:/app/logs
      - ./data:/app/data
    restart: always

  mcp-market-data:
    build: ./mcp-servers/market-data
    env_file: .env.prod
    depends_on:
      - redis
    restart: always

  mcp-trading:
    build: ./mcp-servers/trading
    env_file: .env.prod
    restart: always

  # === MONITORING ===
  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./config/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    restart: always

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./config/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    ports:
      - "3000:3000"
    restart: always

  alertmanager:
    image: prom/alertmanager:latest
    volumes:
      - ./config/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    restart: always

volumes:
  postgres_data:
  redis_data:
  influx_data:
  prometheus_data:
  grafana_data:
```

### 2.3 Comandos Operativos

| Acción | Comando |
|--------|---------|
| Iniciar todo | `docker-compose -f docker-compose.prod.yml up -d` |
| Ver logs | `docker-compose logs -f trading-core` |
| Restart servicio | `docker-compose restart trading-core` |
| Stop graceful | `docker-compose stop` |
| Backup BD | Ver sección 8 |

---

## 3. CI/CD Básico

### 3.1 Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to server
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_KEY }}
          script: |
            cd /opt/trading-bot
            git pull
            docker-compose -f docker-compose.prod.yml up -d --build
```

### 3.2 Flujo de Deployment

| Paso | Entorno | Trigger | Duración |
|------|---------|---------|----------|
| Tests | CI | Push a cualquier rama | ~2 min |
| Deploy staging | staging | Push a `develop` | ~5 min |
| Deploy prod | prod | Push a `main` (manual approve) | ~5 min |

### 3.3 Checklist Pre-Deploy

```
□ Tests pasan en CI
□ Sin alertas críticas en staging últimas 24h
□ Backup de BD realizado
□ Mercados cerrados (preferible)
□ Kill switch accesible
```

---

## 4. Monitoring

### 4.1 Stack de Monitoring

| Componente | Función | Puerto |
|------------|---------|--------|
| Prometheus | Recolección métricas | 9090 |
| Grafana | Dashboards | 3000 |
| Alertmanager | Gestión alertas | 9093 |
| InfluxDB | Métricas trading | 8086 |

### 4.2 Métricas Clave

Referencia: Doc 6, sección 9.2 para alertas.

| Categoría | Métrica | Alerta si |
|-----------|---------|-----------|
| **Sistema** | CPU % | > 80% 5min |
| | RAM % | > 85% |
| | Disco % | > 90% |
| **Trading** | Drawdown | > 10% (warn), > 15% (crit) |
| | P&L diario | < -2% (warn), < -3% (crit) |
| | Posiciones abiertas | Info |
| **Conectividad** | Broker connection | Desconectado > 2 min |
| | Data feed | Sin datos > 5 min |
| | API latency | > 1s |
| **ML** | Calibration ECE | > 0.10 (warn), > 0.15 (crit) |

### 4.3 Dashboards Grafana

| Dashboard | Paneles principales |
|-----------|---------------------|
| **Overview** | P&L, drawdown, posiciones, estado sistema |
| **Trading** | Órdenes/día, fill rate, slippage |
| **Risk** | Exposiciones, VaR, correlaciones |
| **System** | CPU, RAM, latencias, errores |
| **ML** | Calibración, predicciones, drift |

### 4.4 prometheus.yml

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'trading-core'
    static_configs:
      - targets: ['trading-core:8000']

  - job_name: 'mcp-servers'
    static_configs:
      - targets: ['mcp-market-data:8001', 'mcp-trading:8002']

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - '/etc/prometheus/alerts.yml'
```

---

## 5. Sistema de Alertas

### 5.1 Canales por Severidad

| Severidad | Canal | Respuesta esperada |
|-----------|-------|-------------------|
| INFO | Log only | - |
| WARNING | Telegram | < 4 horas |
| ERROR | Telegram + Email | < 1 hora |
| CRITICAL | Telegram + Email + SMS | Inmediato |

### 5.2 alertmanager.yml

```yaml
global:
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'trading-alerts@xxx.com'
  smtp_auth_username: 'xxx'
  smtp_auth_password: 'xxx'

route:
  receiver: 'default'
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: 'critical'
      repeat_interval: 15m

receivers:
  - name: 'default'
    telegram_configs:
      - bot_token: 'xxx'
        chat_id: xxx
        message: '{{ .CommonAnnotations.summary }}'

  - name: 'critical'
    telegram_configs:
      - bot_token: 'xxx'
        chat_id: xxx
    email_configs:
      - to: 'xxx@xxx.com'
```

### 5.3 Alertas Definidas

```yaml
# alerts.yml
groups:
  - name: trading
    rules:
      - alert: HighDrawdown
        expr: trading_drawdown_pct > 0.10
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Drawdown > 10%: {{ $value | printf \"%.1f\" }}%"

      - alert: CriticalDrawdown
        expr: trading_drawdown_pct > 0.15
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "CRITICAL: Drawdown > 15%"

      - alert: BrokerDisconnected
        expr: broker_connected == 0
        for: 2m
        labels:
          severity: error
        annotations:
          summary: "Broker desconectado > 2 min"

      - alert: DataFeedStale
        expr: time() - data_feed_last_update > 300
        for: 1m
        labels:
          severity: error
        annotations:
          summary: "Sin datos de mercado > 5 min"
```

---

## 6. Runbooks

### 6.1 Startup del Sistema

| Paso | Comando/Acción | Verificación |
|------|----------------|--------------|
| 1 | `docker-compose up -d postgres redis influxdb` | `docker-compose ps` muestra healthy |
| 2 | Esperar 30s para BD ready | - |
| 3 | `docker-compose up -d` (resto) | Todos los servicios up |
| 4 | Verificar Grafana | http://localhost:3000 accesible |
| 5 | Verificar conexión broker | Log sin errores de conexión |
| 6 | Verificar modo sistema | Debe estar en NORMAL o OBSERVATION |

### 6.2 Shutdown Graceful

| Paso | Comando/Acción | Nota |
|------|----------------|------|
| 1 | Activar modo PAUSE | `/pause` en Telegram o API |
| 2 | Esperar cierre de órdenes pendientes | Max 5 min |
| 3 | `docker-compose stop trading-core mcp-*` | Aplicación primero |
| 4 | `docker-compose stop` | Infra después |

### 6.3 Incidente: Broker Desconectado

| Paso | Acción | Timeout |
|------|--------|---------|
| 1 | Verificar estado TWS/Gateway | - |
| 2 | Si TWS caído → reiniciar TWS | 2 min |
| 3 | `docker-compose restart mcp-trading` | 1 min |
| 4 | Verificar reconexión en logs | 2 min |
| 5 | Si persiste → modo PAUSE manual | - |
| 6 | Contactar soporte IBKR si necesario | - |

### 6.4 Incidente: Drawdown > 15%

| Paso | Acción |
|------|--------|
| 1 | Sistema activa Kill Switch automáticamente |
| 2 | Verificar que todas las posiciones cerradas |
| 3 | Revisar log de decisiones (audit.decisions) |
| 4 | Identificar causa (estrategia, mercado, bug) |
| 5 | Documentar incident report |
| 6 | NO reactivar sin revisión completa |

### 6.5 Incidente: Discrepancia en Reconciliación

Referencia: Doc 2, sección 8.2.

| Paso | Acción |
|------|--------|
| 1 | Activar modo PAUSE inmediatamente |
| 2 | Obtener posiciones de broker via TWS manual |
| 3 | Comparar con `trading.positions` |
| 4 | Identificar discrepancia específica |
| 5 | Corregir BD si error de sincronización |
| 6 | Si discrepancia real → investigar trades perdidos |

### 6.6 Rollback de Deployment

| Paso | Comando |
|------|---------|
| 1 | `git log --oneline -5` (identificar commit anterior) |
| 2 | `git checkout <commit-anterior>` |
| 3 | `docker-compose up -d --build` |
| 4 | Verificar funcionamiento |
| 5 | Si OK → `git revert` del commit problemático |

---

## 7. Mantenimiento Programado

### 7.1 Calendario

| Tarea | Frecuencia | Ventana | Duración |
|-------|------------|---------|----------|
| Backup BD | Diario | 00:00 UTC | 15 min |
| Vacuum PostgreSQL | Semanal | Domingo 02:00 | 30 min |
| Rotación logs | Diario | 00:30 UTC | 5 min |
| Actualización deps | Mensual | Fin de semana | 1-2h |
| Retrain ML | Trimestral | Fin de semana | 4-8h |
| Stress testing | Trimestral | Mercado cerrado | 2h |

### 7.2 Scripts de Mantenimiento

**Backup diario (cron):**
```bash
#!/bin/bash
# /opt/trading-bot/scripts/backup.sh
DATE=$(date +%Y%m%d)
BACKUP_DIR=/backups

# PostgreSQL
docker exec trading_db pg_dump -U trading trading | gzip > $BACKUP_DIR/pg_$DATE.sql.gz

# Redis
docker exec trading_redis redis-cli BGSAVE
cp /var/lib/docker/volumes/trading_redis_data/_data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Retención 30 días
find $BACKUP_DIR -mtime +30 -delete
```

**Crontab:**
```
0 0 * * * /opt/trading-bot/scripts/backup.sh
30 0 * * * /opt/trading-bot/scripts/rotate_logs.sh
0 2 * * 0 /opt/trading-bot/scripts/vacuum_db.sh
```

### 7.3 Actualización de Dependencias

| Paso | Acción |
|------|--------|
| 1 | Crear rama `update-deps` |
| 2 | `pip-compile --upgrade` |
| 3 | Ejecutar tests localmente |
| 4 | Deploy a staging |
| 5 | 48h en staging sin issues |
| 6 | Merge a main, deploy prod |

---

## 8. Backup y Recuperación

### 8.1 Estrategia de Backup

| Dato | Método | Retención | RPO |
|------|--------|-----------|-----|
| PostgreSQL | pg_dump diario | 30 días | 24h |
| Redis | RDB snapshot | 7 días | 1h |
| Config | Git | Indefinido | 0 |
| Logs | Rotación + archivo | 90 días | - |
| Modelos ML | Versionados en /models | Indefinido | - |

### 8.2 Procedimiento de Recuperación

**Recuperar PostgreSQL:**
```bash
# Parar aplicación
docker-compose stop trading-core mcp-*

# Restaurar
gunzip -c /backups/pg_20241215.sql.gz | docker exec -i trading_db psql -U trading trading

# Reiniciar
docker-compose up -d
```

**Recuperar Redis:**
```bash
docker-compose stop redis
cp /backups/redis_20241215.rdb /var/lib/docker/volumes/trading_redis_data/_data/dump.rdb
docker-compose start redis
```

### 8.3 Test de Recuperación

| Frecuencia | Acción |
|------------|--------|
| Mensual | Restaurar backup en entorno aislado |
| Trimestral | Simulacro completo de disaster recovery |

---

## 9. Seguridad Operacional

### 9.1 Accesos

| Recurso | Método | Usuarios |
|---------|--------|----------|
| Servidor | SSH + key | Solo admin |
| Grafana | Usuario/pass + 2FA | Admin |
| BD directa | Solo localhost | Ninguno externo |
| Telegram bot | Chat ID específico | Solo propietario |

### 9.2 Secrets Management

| Secret | Almacenamiento |
|--------|----------------|
| DB passwords | `.env` (no en git) + permisos 600 |
| API keys brokers | `.env` + encriptado en reposo |
| Telegram token | `.env` |

### 9.3 Checklist de Seguridad

```
□ SSH solo con key, no password
□ Firewall: solo puertos necesarios (22, 3000)
□ .env en .gitignore
□ Permisos 600 en archivos sensibles
□ Actualizaciones de seguridad automáticas (unattended-upgrades)
□ Logs de acceso monitoreados
```

---

## 10. Checklist Operativo Diario

### 10.1 Pre-Mercado (08:00 CET)

```
□ Verificar sistema en modo NORMAL
□ Revisar alertas nocturnas
□ Confirmar conexión broker
□ Verificar data feed activo
□ Revisar posiciones abiertas
□ Check calendario económico (eventos de riesgo)
```

### 10.2 Durante Mercado

```
□ Monitoreo pasivo via Grafana/Telegram
□ Responder alertas según severidad
□ No intervenir manualmente salvo emergencia
```

### 10.3 Post-Mercado (18:30 CET)

```
□ Revisar P&L del día
□ Verificar reconciliación exitosa
□ Revisar órdenes ejecutadas vs señales
□ Confirmar backup completado
□ Documentar cualquier incidente
```

---

## 11. Contactos y Escalado

| Nivel | Contacto | Uso |
|-------|----------|-----|
| L1 | Telegram bot | Alertas automáticas |
| L2 | Email personal | Alertas críticas |
| L3 | IBKR soporte | Problemas de broker |
| L3 | VPS provider | Problemas de infra |

---

## 12. Referencias Cruzadas

| Tema | Documento | Sección |
|------|-----------|---------|
| Docker Compose base | Doc 2 | 9.1 |
| Variables entorno | Doc 2 | 9.5 |
| Alertas de riesgo | Doc 6 | 9.2 |
| Reconciliación | Doc 2 | 8.2 |
| Kill switch | Doc 6 | 6.3 |
| Modos del sistema | Doc 1 | 5.3 |
| Retrain ML | Doc 5 | 6.3 |

---

*Documento 7 de 7 - Arquitectura Técnica del Bot de Trading*  
*Versión 1.0*
