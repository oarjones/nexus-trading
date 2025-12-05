#!/usr/bin/env python3
"""
Metrics Schema Verification - Phase A1.1
Run: python scripts/verify_metrics_schema.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Load credentials from environment variables
DB_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "trading")
DB_USER = os.getenv("POSTGRES_USER", "trading")
DB_PASS = os.getenv("DB_PASSWORD")

if not DB_PASS:
    print("❌ Error: DB_PASSWORD environment variable not set")
    sys.exit(1)

def check_metrics_schema():
    """Verify that metrics schema exists and has all tables."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
        
        # Verify schema exists
        cur.execute("""
            SELECT schema_name FROM information_schema.schemata 
            WHERE schema_name = 'metrics'
        """)
        if not cur.fetchone():
            return False, "Schema 'metrics' does not exist"
        
        # Verify tables
        expected_tables = {
            'trades',
            'strategy_performance',
            'model_performance',
            'experiments',
            'experiment_results'
        }
        
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'metrics'
        """)
        actual_tables = {row[0] for row in cur.fetchall()}
        
        missing = expected_tables - actual_tables
        if missing:
            return False, f"Missing tables: {missing}"
        
        # Verify ENUM types
        cur.execute("""
            SELECT typname FROM pg_type 
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'metrics')
            AND typtype = 'e'
        """)
        enums = {row[0] for row in cur.fetchall()}
        expected_enums = {'trade_direction', 'trade_status', 'regime_type', 'experiment_status'}
        
        missing_enums = expected_enums - enums
        if missing_enums:
            return False, f"Missing ENUMs: {missing_enums}"
        
        # Verify views
        cur.execute("""
            SELECT table_name FROM information_schema.views 
            WHERE table_schema = 'metrics'
        """)
        views = {row[0] for row in cur.fetchall()}
        expected_views = {'v_strategy_summary', 'v_model_summary', 'v_recent_trades'}
        
        missing_views = expected_views - views
        if missing_views:
            return False, f"Missing views: {missing_views}"
        
        # Verify indexes (at least the main ones)
        cur.execute("""
            SELECT indexname FROM pg_indexes 
            WHERE schemaname = 'metrics'
        """)
        indexes = {row[0] for row in cur.fetchall()}
        
        if len(indexes) < 5:
            return False, f"Few indexes found: {len(indexes)}"
        
        conn.close()
        
        return True, f"OK: 5 tables, {len(enums)} ENUMs, {len(views)} views, {len(indexes)} indexes"
        
    except Exception as e:
        return False, str(e)


def check_metrics_function():
    """Verify that the metrics calculation function works."""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
        
        # Call function with empty data (should return without error)
        cur.execute("""
            SELECT * FROM metrics.calculate_strategy_metrics(
                'test_strategy',
                NOW() - INTERVAL '30 days',
                NOW()
            )
        """)
        result = cur.fetchone()
        
        conn.close()
        
        if result is not None:
            return True, "Function calculate_strategy_metrics OK"
        else:
            return False, "Function returns no results"
            
    except Exception as e:
        return False, str(e)


def main():
    """Run all verifications."""
    print("METRICS SCHEMA VERIFICATION - PHASE A1.1")
    print("=" * 50)
    
    checks = [
        ("Metrics schema and tables", check_metrics_schema),
        ("Metrics function", check_metrics_function),
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
        print("✅ METRICS SCHEMA OK - Task A1.1 completed")
        return 0
    else:
        print("❌ ERRORS DETECTED - Review before proceeding")
        return 1


if __name__ == "__main__":
    sys.exit(main())
