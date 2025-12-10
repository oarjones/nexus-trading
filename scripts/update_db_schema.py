
import os
import psycopg2
from urllib.parse import urlparse, unquote
from pathlib import Path

def apply_schema():
    # Helper to get connection params
    url = os.getenv('DATABASE_URL', 'postgresql://trading:V%40p%26dsY42XtKJH9ykpW%5EnQU2@127.0.0.1:5432/trading')
    parsed = urlparse(url)
    
    conn_params = {
        'host': parsed.hostname,
        'port': parsed.port,
        'user': parsed.username,
        'password': unquote(parsed.password),
        'database': parsed.path[1:]
    }

    try:
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cur = conn.cursor()
        
        sql_path = Path("init-scripts/08_universe_schema.sql")
        if not sql_path.exists():
            print(f"Error: SQL file {sql_path} not found")
            return

        print(f"Applying schema from {sql_path}...")
        with open(sql_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        cur.execute(sql_content)
        print("Schema applied successfully!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error applying schema: {e}")
        exit(1)

if __name__ == "__main__":
    apply_schema()
