"""Execute trading tables migration."""
import psycopg2
from urllib.parse import urlparse, unquote
from pathlib import Path

def run_migration():
    # Database URL
    url = 'postgresql://trading:V%40p%26dsY42XtKJH9ykpW%5EnQU2@127.0.0.1:5432/trading'
    parsed = urlparse(url)
    
    # Connect
    conn = psycopg2.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=parsed.username,
        password=unquote(parsed.password),
        database=parsed.path[1:]
    )
    
    # Read SQL file
    sql_file = Path(__file__).parent.parent / "init-scripts" / "09_trading_tables.sql"
    script = sql_file.read_text(encoding='utf-8')
    
    # Execute
    cur = conn.cursor()
    cur.execute(script)
    conn.commit()
    
    print("✅ Trading tables created successfully")
    
    # Verify
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname IN ('config', 'trading')
        ORDER BY tablename
    """)
    tables = cur.fetchall()
    print(f"✅ Created tables: {[t[0] for t in tables]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_migration()
