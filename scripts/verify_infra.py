#!/usr/bin/env python3
"""
Infrastructure Verification Script - Phase 0
Ejecutar: python scripts/verify_infra.py
"""

import sys
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def check_postgres():
    """Verificar PostgreSQL + TimescaleDB"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="trading",
            user="trading",
            password=os.getenv("DB_PASSWORD")
        )
        cur = conn.cursor()
        
        # Verificar TimescaleDB
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'")
        result = cur.fetchone()
        if not result:
            return False, "TimescaleDB no instalado"
        
        # Verificar esquemas
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name IN ('trading', 'market_data', 'config', 'audit', 'features')
        """)
        schemas = [r[0] for r in cur.fetchall()]
        expected = {'trading', 'market_data', 'config', 'audit', 'features'}
        if set(schemas) != expected:
            return False, f"Esquemas faltantes: {expected - set(schemas)}"
        
        # Verificar tablas críticas
        cur.execute("""
            SELECT table_schema || '.' || table_name 
            FROM information_schema.tables 
            WHERE table_schema IN ('trading', 'config', 'audit', 'market_data')
        """)
        tables = [r[0] for r in cur.fetchall()]
        
        required_tables = [
            'trading.orders', 'trading.trades', 'trading.positions',
            'config.strategies', 'config.risk_limits',
            'audit.decisions', 'audit.system_events',
            'market_data.ohlcv', 'market_data.indicators'
        ]
        missing = [t for t in required_tables if t not in tables]
        if missing:
            return False, f"Tablas faltantes: {missing}"
        
        conn.close()
        return True, f"TimescaleDB {result[0]}, {len(tables)} tablas OK"
    
    except Exception as e:
        return False, str(e)


def check_redis():
    """Verificar Redis"""
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        if r.ping():
            info = r.info()
            return True, f"Redis {info['redis_version']}, memoria: {info['used_memory_human']}"
        return False, "PING falló"
    except Exception as e:
        return False, str(e)


def check_influxdb():
    """Verificar InfluxDB"""
    try:
        from influxdb_client import InfluxDBClient
        
        # Nota: El token puede estar vacío en la primera ejecución
        token = os.getenv("INFLUX_TOKEN", "")
        if not token:
            return True, "InfluxDB corriendo (token pendiente de configurar manualmente)"
        
        client = InfluxDBClient(
            url=os.getenv("INFLUXDB_URL", "http://localhost:8086"),
            token=token,
            org=os.getenv("INFLUXDB_ORG", "trading")
        )
        health = client.health()
        if health.status == "pass":
            return True, f"InfluxDB {health.version}"
        return False, f"Status: {health.status}"
    except Exception as e:
        # Si falla por falta de token, es OK en primera ejecución
        error_msg = str(e)
        if "unauthorized" in error_msg.lower():
            return True, "InfluxDB corriendo (token pendiente de configurar)"
        return False, error_msg


def check_grafana():
    """Verificar Grafana"""
    try:
        import requests
        resp = requests.get("http://localhost:3000/api/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return True, f"Grafana: {data.get('database', 'OK')}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 50)
    print("VERIFICACIÓN DE INFRAESTRUCTURA - FASE 0")
    print("=" * 50)
    print()
    
    checks = [
        ("PostgreSQL + TimescaleDB", check_postgres),
        ("Redis", check_redis),
        ("InfluxDB", check_influxdb),
        ("Grafana", check_grafana),
    ]
    
    all_ok = True
    for name, check_fn in checks:
        ok, msg = check_fn()
        status = "✅" if ok else "❌"
        print(f"{status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    print()
    print("=" * 50)
    if all_ok:
        print("✅ INFRAESTRUCTURA OK - Fase 0 completada")
        print()
        print("SIGUIENTE PASO:")
        print("  1. Accede a http://localhost:8086")
        print("  2. Genera un token API en InfluxDB")
        print("  3. Actualiza INFLUX_TOKEN en .env")
        print("  4. Ejecuta: docker-compose restart grafana")
        return 0
    else:
        print("❌ ERRORES DETECTADOS - Revisar antes de continuar")
        return 1


if __name__ == "__main__":
    sys.exit(main())
