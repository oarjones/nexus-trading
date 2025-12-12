#!/usr/bin/env python3
"""
Nexus Trading - System Launcher
===============================

Automates the startup of the entire Nexus Trading ecosystem:
1. Verifies prerequisites (Docker running, IBKR Gateway active).
2. Starts infrastructure (Docker Compose).
3. Waits for services to be ready (Postgres, Redis, Influx, MCPs).
4. Launches Strategy Lab and Dashboard in separate console windows.
"""

import os
import sys
import time
import socket
import subprocess
import shutil
import platform
from pathlib import Path

# Colors
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log(msg, type="INFO"):
    if type == "INFO":
        print(f"{Colors.BLUE}[INFO]{Colors.END} {msg}")
    elif type == "OK":
        print(f"{Colors.GREEN}[OK]{Colors.END} {msg}")
    elif type == "WARN":
        print(f"{Colors.YELLOW}[WARN]{Colors.END} {msg}")
    elif type == "ERR":
        print(f"{Colors.RED}[ERR]{Colors.END} {msg}")

def check_port(host, port, timeout=2):
    """Check if a TCP port is open."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return result == 0
    except:
        return False

def is_docker_running():
    """Check if Docker daemon is running."""
    try:
        subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def wait_for_service(name, host, port, max_retries=30, delay=1):
    """Wait for a service to become available."""
    print(f"Waiting for {name} ({host}:{port})... ", end="", flush=True)
    for _ in range(max_retries):
        if check_port(host, port):
            print(f"{Colors.GREEN}UP{Colors.END}")
            return True
        time.sleep(delay)
        print(".", end="", flush=True)
    print(f"{Colors.RED}TIMEOUT{Colors.END}")
    return False

def open_new_terminal(command, title="Nexus Service"):
    """Open a new terminal window for a command (Windows/Linux/Mac)."""
    system = platform.system()
    
    if system == "Windows":
        # Use 'start' command to open new cmd window
        # /k is a switch for cmd.exe, so we must start cmd.exe
        subprocess.Popen(f'start "{title}" cmd /k "{command}"', shell=True)
    elif system == "Darwin":  # macOS
        subprocess.Popen(
            ["osascript", "-e", f'tell application "Terminal" to do script "{command}"']
        )
    elif system == "Linux":
        # Try common terminal emulators
        terminals = ["gnome-terminal", "xterm", "konsole"]
        for term in terminals:
            if shutil.which(term):
                if term == "gnome-terminal":
                    subprocess.Popen([term, "--", "bash", "-c", f"{command}; exec bash"])
                else:
                    subprocess.Popen([term, "-e", command])
                return

def main():
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== Nexus Trading System Launcher ==={Colors.END}\n")
    
    # 1. Check Docker
    log("Checking Docker...")
    if not is_docker_running():
        log("Docker is NOT running. Please start Docker Desktop first.", "ERR")
        sys.exit(1)
    log("Docker daemon is running.", "OK")
    
    # 2. Check IBKR Gateway
    ibkr_host = os.getenv("IBKR_HOST", "127.0.0.1")
    ibkr_port = int(os.getenv("IBKR_PORT", 4002))
    
    log(f"Checking IBKR Gateway at {ibkr_host}:{ibkr_port}...")
    if check_port(ibkr_host, ibkr_port):
        log("IBKR Gateway is connected and listening.", "OK")
    else:
        log(f"Could not connect to IBKR Gateway at {ibkr_host}:{ibkr_port}.", "WARN")
        print(f"{Colors.YELLOW}  Please ensure IB Gateway/TWS is running and API is enabled.{Colors.END}")
        print(f"{Colors.YELLOW}  Warning: Trading execution will fail without IBKR connection.{Colors.END}")
        if input("  Continue anyway? (y/n): ").lower() != 'y':
            sys.exit(1)
            
    # 3. Start Infrastructure
    log("Starting infrastructure with Docker Compose...")
    try:
        subprocess.run(["docker-compose", "up", "-d", "--build"], check=True)
        log("Docker services started (or already running).", "OK")
    except subprocess.CalledProcessError:
        log("Failed to start docker-compose.", "ERR")
        sys.exit(1)
        
    # 4. Wait for Critical Services
    services = [
        ("PostgreSQL", "127.0.0.1", 5432),
        ("Redis", "127.0.0.1", 6379),
        ("InfluxDB", "127.0.0.1", 8086),
        # MCP Servers (Internal docker network, but we can verify container status if needed, 
        # simplistically we assume if DBs are up, MCPs will follow shortly)
    ]
    
    for name, host, port in services:
        if not wait_for_service(name, host, port):
            log(f"Service {name} failed to start.", "ERR")
            if input("  Continue anyway? (y/n): ").lower() != 'y':
                sys.exit(1)
                
    log("Infrastructure is ready.", "OK")
    
    # 5. Launch Strategy Lab
    log("Launching Strategy Lab in new terminal...")
    python_cmd = sys.executable
    lab_script = Path("scripts/run_strategy_lab.py").absolute()
    cmd_lab = f"{python_cmd} {lab_script}"
    open_new_terminal(cmd_lab, "Nexus Strategy Lab")
    
    # 6. Launch Dashboard
    log("Launching Dashboard in new terminal...")
    app_script = Path("dashboard/app.py").absolute()
    cmd_dashboard = f"{python_cmd} {app_script}"
    open_new_terminal(cmd_dashboard, "Nexus Dashboard")
    
    # 7. Final Instructions
    print(f"\n{Colors.BOLD}{Colors.GREEN}=== System Startup Initiated ==={Colors.END}")
    print(f"1. {Colors.BLUE}Strategy Lab{Colors.END}: Monitor the new terminal window for trading logs.")
    print(f"2. {Colors.BLUE}Dashboard{Colors.END}: Open http://localhost:8000 in your browser.")
    print(f"3. {Colors.BLUE}IBKR{Colors.END}: Ensure Gateway remains open.")
    print("\nTo stop the system:")
    print(" - Close the terminal windows.")
    print(" - Run 'docker-compose down' to stop infrastructure.")

if __name__ == "__main__":
    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
        
    main()
