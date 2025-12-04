"""Check existing database schema for trading tables."""
import psycopg2
from urllib.parse import urlparse, unquote

def check_schema():
    url = 'postgresql://trading:V%40p%26dsY42XtKJH9ykpW%5EnQU2@127.0.0.1:5432/trading'
    parsed = urlparse(url)
    
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=parsed.username,
        password=unquote(parsed.password),
        database=parsed.path[1:]
    )
    
    cur = conn.cursor()
    
    # Check config schema tables
    print("=" * 70)
    print("CONFIG SCHEMA TABLES:")
    print("=" * 70)
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'config'
        ORDER BY tablename
    """)
    config_tables = cur.fetchall()
    print(f"Existing tables: {[t[0] for t in config_tables]}")
    
    # Check if config.strategies exists and its structure
    if ('strategies',) in config_tables:
        print("\n--- config.strategies columns ---")
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'config' AND table_name = 'strategies'
            ORDER BY ordinal_position
        """)
        cols = cur.fetchall()
        for col in cols:
            print(f"  {col[0]:20} {col[1]:20} NULL={col[2]}")
    
    # Check trading schema
    print("\n" + "=" * 70)
    print("TRADING SCHEMA:")
    print("=" * 70)
    cur.execute("""
        SELECT schemaname 
        FROM pg_catalog.pg_namespace n
        JOIN pg_catalog.pg_tables t ON n.nspname = t.schemaname
        WHERE schemaname = 'trading'
        LIMIT 1
    """)
    trading_schema = cur.fetchone()
    
    if trading_schema:
        print("Trading schema EXISTS")
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'trading'
            ORDER BY tablename
        """)
        trading_tables = cur.fetchall()
        print(f"Existing tables: {[t[0] for t in trading_tables]}")
        
        # Check each table structure
        for table in ['orders', 'trades', 'positions']:
            cur.execute(f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'trading' AND table_name = '{table}'
            """)
            if cur.fetchone():
                print(f"\n--- trading.{table} columns ---")
                cur.execute(f"""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'trading' AND table_name = '{table}'
                    ORDER BY ordinal_position
                """)
                cols = cur.fetchall()
                for col in cols:
                    print(f"  {col[0]:25} {col[1]:20} NULL={col[2]}")
    else:
        print("Trading schema DOES NOT EXIST")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_schema()
