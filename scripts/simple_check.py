"""Simple check for config.strategies table."""
import psycopg2
from urllib.parse import urlparse, unquote

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

# Check if config.strategies exists
cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'config' AND table_name = 'strategies'
    )
""")
exists = cur.fetchone()[0]
print(f"config.strategies exists: {exists}")

if exists:
    # Get column names
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns
        WHERE table_schema = 'config' AND table_name = 'strategies'
        ORDER BY ordinal_position
    """)
    cols = cur.fetchall()
    print(f"\nColumns in config.strategies:")
    for col in cols:
        print(f"  - {col[0]}")

# Check trading schema
cur.execute("SELECT EXISTS (SELECT FROM pg_namespace WHERE nspname = 'trading')")
trading_exists = cur.fetchone()[0]
print(f"\ntrading schema exists: {trading_exists}")

if trading_exists:
    cur.execute("""
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'trading'
    """)
    tables = cur.fetchall()
    print(f"Tables in trading schema: {[t[0] for t in tables]}")

cur.close()
conn.close()
