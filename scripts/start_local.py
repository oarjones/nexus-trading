
import sys
import os
import subprocess
import time
import platform
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv

def log(message, status="INFO"):
    """Print formatted log message"""
    timestamp = time.strftime("%H:%M:%S")
    
    colors = {
        "INFO": "\033[94m",    # Blue
        "OK": "\033[92m",      # Green
        "WARN": "\033[93m",    # Yellow
        "ERR": "\033[91m",     # Red
        "RESET": "\033[0m"
    }
    
    col = colors.get(status, colors["INFO"])
    print(f"{col}[{status}] {message}{colors['RESET']}")

def check_requirements():
    """Check if critical packages are installed locally"""
    try:
        import mcp
        import ib_insync
        import pandas_ta
        import asyncpg
    except ImportError as e:
        log(f"Missing dependency: {e.name}", "ERR")
        log("Please run: pip install -r requirements.txt", "WARN")
        return False
    return True

def start_infrastructure():
    """Start Docker infrastructure (DBs only)"""
    log("Starting Infrastructure (Postgres, Redis, InfluxDB, Grafana)...")
    services = ["postgres", "redis", "influxdb", "grafana"]
    
    try:
        cmd = ["docker-compose", "up", "-d"] + services
        subprocess.run(cmd, check=True)
        log("Infrastructure started.", "OK")
        time.sleep(5) # Give DBs a moment
    except subprocess.CalledProcessError:
        log("Failed to start Docker infrastructure.", "ERR")
        sys.exit(1)

def start_mcp_server(name, module, port, env):
    """Start an MCP server as a subprocess"""
    log(f"Starting MCP {name} on port {port}...")
    
    # Update env for this process
    proc_env = env.copy()
    proc_env["MCP_TRANSPORT"] = "http"
    proc_env["PORT"] = str(port)
    proc_env["MCP_CONFIG_PATH"] = str(project_root / "config" / "mcp-servers.yaml")
    
    # We use valid python executable
    cmd = [sys.executable, "-m", module]
    
    # On Windows, we might want new windows for debugging, or just background them
    # For now, let's spawn them in background and let them output to main console or log files
    # To keep it clean, we'll redirect stdout/stderr to files
    
    log_dir = project_root / "logs" / "mcp"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    out_file = open(log_dir / f"{name}.out", "w")
    err_file = open(log_dir / f"{name}.err", "w")
    
    process = subprocess.Popen(
        cmd,
        cwd=str(project_root / "mcp_servers"), # Important for relative imports if they assumed root
        env=proc_env,
        stdout=out_file,
        stderr=err_file
    )
    
    return process

def open_terminal(command, title):
    """Open a new visible terminal"""
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(f'start "{title}" cmd /k "{command}"', shell=True)
    elif system == "Darwin":
        subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "{command}"']
        )
    # Linux omitted for brevity/Windows focus
    
def main():
    print("==================================================")
    print("   NEXUS TRADING - LOCAL HYBRID LAUNCHER")
    print("==================================================")
    
    # 1. Load Env
    load_dotenv()
    env = os.environ.copy()
    
    # 2. Check Local Deps
    if not check_requirements():
        sys.exit(1)

    # 3. Start DBs
    start_infrastructure()
    
    # 4. Start MCP Servers
    mcp_processes = []
    
    try:
        # Market Data
        mcp_processes.append(start_mcp_server("market-data", "market_data.server", 3001, env))
        
        # Technical
        mcp_processes.append(start_mcp_server("technical", "technical.server", 3002, env))
        
        # Risk
        mcp_processes.append(start_mcp_server("risk", "risk.server", 3003, env))
        
        # IBKR (Using localhost gateway!)
        # Verify .env pointing to 127.0.0.1 (it is by default usually)
        mcp_processes.append(start_mcp_server("ibkr", "ibkr.server", 3004, env))
        
        # ML Models
        mcp_processes.append(start_mcp_server("ml-models", "ml_models.server", 3005, env))
        
        log("All MCP Servers launching in background. Logs in /logs/mcp/", "OK")
        time.sleep(5)
        
        # 5. Launch Strategy Lab
        log("Launching Strategy Lab...", "OK")
        # Run properly pointing to python src
        cmd_lab = f"{sys.executable} scripts/run_strategy_lab.py"
        open_terminal(cmd_lab, "Nexus Strategy Lab")
        
        # 6. Launch Dashboard
        log("Launching Dashboard...", "OK")
        cmd_dash = f"{sys.executable} dashboard/app.py"
        open_terminal(cmd_dash, "Nexus Dashboard")
        
        log("System is running locally.", "OK")
        log("Press Ctrl+C to stop MCP servers...", "INFO")
        
        # Keep main process alive to monitor/cleanup MCPs
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        log("\nStopping MCP Servers...", "WARN")
        for p in mcp_processes:
            p.terminate()
        log("Done.", "OK")

if __name__ == "__main__":
    main()
