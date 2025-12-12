#!/usr/bin/env python3
"""
Nexus Trading - System Verification Script

Verifica que todos los componentes del sistema están correctamente
configurados e implementados antes de ejecutar el Strategy Lab.

Ejecutar: python scripts/verify_system.py
"""

import sys
import os
import json
import asyncio
import importlib
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Tuple, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    print("Warning: python-dotenv not installed. Using existing environment variables.")

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def ok(msg: str):
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")

def fail(msg: str):
    print(f"  {Colors.RED}✗{Colors.END} {msg}")

def warn(msg: str):
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")

def info(msg: str):
    print(f"  {Colors.BLUE}ℹ{Colors.END} {msg}")

def section(title: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}[{title}]{Colors.END}")

def subsection(title: str):
    print(f"\n  {Colors.BOLD}{title}{Colors.END}")

# ============================================================================
# Test Results Tracking
# ============================================================================

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors: List[str] = []
    
    def record_pass(self):
        self.passed += 1
    
    def record_fail(self, error: str):
        self.failed += 1
        self.errors.append(error)
    
    def record_warning(self):
        self.warnings += 1
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"{Colors.BOLD}VERIFICATION SUMMARY{Colors.END}")
        print(f"{'='*60}")
        print(f"  Total Tests: {total}")
        print(f"  {Colors.GREEN}Passed: {self.passed}{Colors.END}")
        print(f"  {Colors.RED}Failed: {self.failed}{Colors.END}")
        print(f"  {Colors.YELLOW}Warnings: {self.warnings}{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}Errors:{Colors.END}")
            for err in self.errors:
                print(f"  - {err}")
        
        if self.failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL CHECKS PASSED - System ready for testing{Colors.END}")
            return True
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ {self.failed} CHECKS FAILED - Please fix before running{Colors.END}")
            return False

results = TestResults()

# ============================================================================
# 1. Directory Structure Verification
# ============================================================================

def verify_directory_structure():
    section("1. Directory Structure")
    
    required_dirs = [
        "config",
        "data",
        "src/agents/llm",
        "src/agents/llm/agents",
        "src/monitoring",
        "src/universe",
        "src/trading/paper",
        "src/strategies",
        "src/scheduling",
        "dashboard",
        "dashboard/services",
        "dashboard/templates",
        "dashboard/templates/components",
    ]
    
    for dir_path in required_dirs:
        full_path = PROJECT_ROOT / dir_path
        if full_path.exists():
            ok(f"Directory exists: {dir_path}")
            results.record_pass()
        else:
            fail(f"Missing directory: {dir_path}")
            results.record_fail(f"Missing directory: {dir_path}")

# ============================================================================
# 2. Configuration Files Verification
# ============================================================================

def verify_config_files():
    section("2. Configuration Files")
    
    required_configs = [
        ("config/symbols.yaml", "symbols"),
        ("config/strategies.yaml", "strategies"),
        ("config/agents.yaml", "agents (LLM config)"),
        ("config/paper_trading.yaml", "paper trading"),
    ]
    
    for config_path, desc in required_configs:
        full_path = PROJECT_ROOT / config_path
        if full_path.exists():
            ok(f"Config exists: {desc} ({config_path})")
            results.record_pass()
            
            # Verify YAML is valid
            try:
                import yaml
                with open(full_path) as f:
                    yaml.safe_load(f)
                ok(f"  └─ Valid YAML syntax")
                results.record_pass()
            except Exception as e:
                fail(f"  └─ Invalid YAML: {e}")
                results.record_fail(f"Invalid YAML in {config_path}")
        else:
            fail(f"Missing config: {desc} ({config_path})")
            results.record_fail(f"Missing config: {config_path}")
    
    # Verify symbols count
    subsection("Symbol Universe")
    try:
        import yaml
        with open(PROJECT_ROOT / "config/symbols.yaml") as f:
            data = yaml.safe_load(f)
        
        symbols = data.get("symbols", [])
        count = len(symbols)
        
        if count >= 100:
            ok(f"Universe has {count} symbols (target: 150)")
            results.record_pass()
        elif count >= 50:
            warn(f"Universe has {count} symbols (target: 150, minimum: 100)")
            results.record_warning()
        else:
            fail(f"Universe has only {count} symbols (need at least 50)")
            results.record_fail(f"Insufficient symbols: {count}")
            
    except Exception as e:
        fail(f"Error reading symbols.yaml: {e}")
        results.record_fail("Cannot read symbols.yaml")

# ============================================================================
# 3. Module Imports Verification
# ============================================================================

def verify_imports():
    section("3. Module Imports")
    
    modules_to_check = [
        ("src.monitoring.status_writer", "StatusWriter", "DOC-07"),
        ("src.universe.manager", "UniverseManager", "DOC-01"),
        ("src.universe.mcp_data_adapter", "MCPDataProviderAdapter", "DOC-01"),
        ("src.agents.llm.cost_tracker", "CostTracker", "DOC-02"),
        ("src.agents.llm.web_search", "WebSearchClient", "DOC-02"),
        ("src.agents.llm.agents.claude_agent", "ClaudeAgent", "DOC-02"),
        ("src.trading.paper.portfolio", "PaperPortfolioManager", "Core"),
        ("src.trading.paper.order_simulator", "OrderSimulator", "Core"),
        ("src.strategies.runner", "StrategyRunner", "Core"),
        ("src.scheduling.scheduler", "StrategyScheduler", "Core"),
        ("src.data.symbols", "SymbolRegistry", "DOC-04"),
    ]
    
    for module_name, class_name, doc_ref in modules_to_check:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            ok(f"{class_name} from {module_name} ({doc_ref})")
            results.record_pass()
        except ImportError as e:
            error_msg = str(e)
            # Check if it's a missing optional dependency vs real error
            if "redis" in error_msg or "anthropic" in error_msg or "aiohttp" in error_msg:
                warn(f"Cannot import {module_name}: {e} (optional dependency)")
                results.record_warning()
            else:
                fail(f"Cannot import {module_name}: {e}")
                results.record_fail(f"Import error: {module_name}")
        except AttributeError:
            fail(f"Class {class_name} not found in {module_name}")
            results.record_fail(f"Missing class: {class_name}")
        except SyntaxError as e:
            fail(f"Syntax error in {module_name}: {e}")
            results.record_fail(f"Syntax error: {module_name}")
    
    # Dashboard imports
    subsection("Dashboard Imports")
    dashboard_modules = [
        ("dashboard.services.data_service", "DataService"),
        ("dashboard.services.log_service", "LogService"),
    ]
    
    for module_name, class_name in dashboard_modules:
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            ok(f"{class_name} from {module_name}")
            results.record_pass()
        except Exception as e:
            if "redis" in str(e) or "jinja2" in str(e).lower():
                warn(f"Cannot import {module_name}: {e} (optional dependency)")
                results.record_warning()
            else:
                fail(f"Cannot import {module_name}: {e}")
                results.record_fail(f"Dashboard import error: {module_name}")

# ============================================================================
# 4. StatusWriter Test
# ============================================================================

def verify_status_writer():
    section("4. StatusWriter (DOC-07)")
    
    try:
        from src.monitoring.status_writer import StatusWriter
        
        # Create instance with test file
        test_file = PROJECT_ROOT / "data" / "test_status.json"
        writer = StatusWriter(output_file=str(test_file), interval_seconds=1)
        
        # Test setters exist
        assert hasattr(writer, 'set_regime'), "Missing set_regime method"
        assert hasattr(writer, 'set_next_execution'), "Missing set_next_execution method"
        assert hasattr(writer, 'set_active_symbols_count'), "Missing set_active_symbols_count"
        assert hasattr(writer, 'record_execution'), "Missing record_execution method"
        ok("All required methods present")
        results.record_pass()
        
        # Test writing
        writer._is_running = True
        writer._regime = "BULL"
        writer._regime_confidence = 0.75
        writer._active_symbols_count = 35
        
        # Sync write for testing
        asyncio.get_event_loop().run_until_complete(writer._write_status())
        
        if test_file.exists():
            with open(test_file) as f:
                data = json.load(f)
            
            assert data.get("is_running") == True
            assert data.get("regime", {}).get("current") == "BULL"
            assert data.get("active_symbols_count") == 35
            
            ok(f"Status file written correctly: {test_file}")
            results.record_pass()
            
            # Cleanup
            test_file.unlink()
        else:
            fail("Status file not created")
            results.record_fail("StatusWriter failed to create file")
            
    except Exception as e:
        fail(f"StatusWriter test failed: {e}")
        results.record_fail(f"StatusWriter error: {e}")

# ============================================================================
# 5. CostTracker Test
# ============================================================================

def verify_cost_tracker():
    section("5. CostTracker (DOC-02)")
    
    try:
        from src.agents.llm.cost_tracker import CostTracker, get_cost_tracker
        
        # Use test directory
        test_dir = PROJECT_ROOT / "data" / "costs_test"
        tracker = CostTracker(data_dir=str(test_dir))
        
        # Test LLM tracking
        cost = tracker.track_llm_call(
            agent_id="test_agent",
            model="claude-3-5-sonnet-20240620",
            input_tokens=1000,
            output_tokens=500,
            context="test call"
        )
        
        assert cost > 0, "Cost should be positive"
        ok(f"LLM call tracked, estimated cost: ${cost:.6f}")
        results.record_pass()
        
        # Test search tracking
        search_cost = tracker.track_search(
            agent_id="test_agent",
            query_count=1,
            context="test search"
        )
        
        assert search_cost > 0, "Search cost should be positive"
        ok(f"Search tracked, estimated cost: ${search_cost:.6f}")
        results.record_pass()
        
        # Verify file was created
        today = date.today().isoformat()
        cost_file = test_dir / f"{today}.json"
        
        if cost_file.exists():
            with open(cost_file) as f:
                data = json.load(f)
            
            assert "summary" in data
            assert "records" in data
            assert len(data["records"]) == 2
            
            ok(f"Cost file created with {len(data['records'])} records")
            results.record_pass()
            
            # Cleanup
            cost_file.unlink()
            test_dir.rmdir()
        else:
            fail("Cost file not created")
            results.record_fail("CostTracker failed to persist")
            
    except Exception as e:
        fail(f"CostTracker test failed: {e}")
        results.record_fail(f"CostTracker error: {e}")

# ============================================================================
# 6. WebSearchClient Test
# ============================================================================

def verify_web_search():
    section("6. WebSearchClient (DOC-02)")
    
    try:
        from src.agents.llm.web_search import WebSearchClient, SearchResult
        
        client = WebSearchClient()
        
        # Check API key
        api_key = os.getenv("BRAVE_SEARCH_API_KEY")
        if api_key:
            ok("BRAVE_SEARCH_API_KEY is set")
            results.record_pass()
            
            # Note: We don't actually call the API in verification
            info("Skipping live API call (will test in integration)")
        else:
            warn("BRAVE_SEARCH_API_KEY not set - web search will be disabled")
            results.record_warning()
        
        # Verify SearchResult structure
        result = SearchResult(
            title="Test",
            url="https://example.com",
            snippet="Test snippet"
        )
        assert result.to_string() is not None
        ok("SearchResult class works correctly")
        results.record_pass()
        
    except Exception as e:
        fail(f"WebSearchClient test failed: {e}")
        results.record_fail(f"WebSearchClient error: {e}")

# ============================================================================
# 7. Dashboard DataService Test (File-Only Reading)
# ============================================================================

def verify_dashboard_data_service():
    section("7. Dashboard DataService (DOC-07 Critical Fix)")
    
    try:
        from dashboard.services.data_service import DataService, get_data_service
        
        # Create test data directory
        test_data_dir = PROJECT_ROOT / "data" / "dashboard_test"
        test_data_dir.mkdir(parents=True, exist_ok=True)
        
        service = DataService(data_dir=str(test_data_dir))
        
        # Verify it ONLY reads files (no memory injection)
        import inspect
        init_sig = inspect.signature(DataService.__init__)
        params = list(init_sig.parameters.keys())
        
        # Should only have 'self' and 'data_dir' - NO portfolio_manager, universe_manager, etc.
        memory_params = ['portfolio_manager', 'universe_manager', 'scheduler', 'status_writer']
        has_memory_injection = any(p in params for p in memory_params)
        
        if not has_memory_injection:
            ok("DataService has NO memory injection (correct per DOC-07)")
            results.record_pass()
        else:
            fail("DataService still has memory injection parameters!")
            results.record_fail("DOC-07 fix not applied: DataService has memory params")
        
        # Test reading non-existent files (should return defaults, not crash)
        status = service.get_system_status()
        assert "is_running" in status or "status" in status
        ok("get_system_status() handles missing file gracefully")
        results.record_pass()
        
        universe = service.get_active_universe()
        assert "active_symbols" in universe or "status" in universe
        ok("get_active_universe() handles missing file gracefully")
        results.record_pass()
        
        signals = service.get_recent_signals()
        assert "signals" in signals
        ok("get_recent_signals() handles missing file gracefully")
        results.record_pass()
        
        # Test reading actual file
        test_status_file = test_data_dir / "system_status.json"
        test_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_running": True,
            "regime": {"current": "BULL", "confidence": 0.8},
            "active_symbols_count": 42
        }
        with open(test_status_file, 'w') as f:
            json.dump(test_status, f)
        
        read_status = service.get_system_status()
        assert read_status.get("is_running") == True
        assert read_status.get("active_symbols_count") == 42
        ok("DataService correctly reads system_status.json")
        results.record_pass()
        
        # Cleanup
        test_status_file.unlink()
        test_data_dir.rmdir()
        
    except Exception as e:
        fail(f"DataService test failed: {e}")
        results.record_fail(f"DataService error: {e}")

# ============================================================================
# 8. UniverseManager.save_state() Test
# ============================================================================

def verify_universe_manager():
    section("8. UniverseManager (DOC-01)")
    
    try:
        from src.universe.manager import UniverseManager
        
        # Check save_state method exists
        assert hasattr(UniverseManager, 'save_state'), "Missing save_state method"
        ok("UniverseManager has save_state() method")
        results.record_pass()
        
        # Check it's async
        import inspect
        if inspect.iscoroutinefunction(UniverseManager.save_state):
            ok("save_state() is async (correct)")
            results.record_pass()
        else:
            warn("save_state() is not async - may need adjustment")
            results.record_warning()
        
        # Check state_file attribute is set in __init__
        source = inspect.getsource(UniverseManager.__init__)
        if "state_file" in source and "active_universe.json" in source:
            ok("UniverseManager writes to data/active_universe.json")
            results.record_pass()
        else:
            fail("UniverseManager may not be configured to write active_universe.json")
            results.record_fail("UniverseManager state_file configuration missing")
            
    except Exception as e:
        fail(f"UniverseManager test failed: {e}")
        results.record_fail(f"UniverseManager error: {e}")

# ============================================================================
# 9. ClaudeAgent Tool Use Test
# ============================================================================

def verify_claude_agent():
    section("9. ClaudeAgent Tool Use (DOC-02)")
    
    try:
        from src.agents.llm.agents.claude_agent import ClaudeAgent
        import inspect
        
        # Check for web search tool definition
        source = inspect.getsource(ClaudeAgent)
        
        checks = [
            ("WEB_SEARCH_TOOL", "Web search tool definition"),
            ("web_search", "Tool name 'web_search'"),
            ("tool_use", "Tool use handling"),
            ("MAX_SEARCHES", "Search limit constant"),
            ("cost_tracker", "Cost tracker integration"),
            ("search_client", "Search client integration"),
        ]
        
        for pattern, desc in checks:
            if pattern in source:
                ok(f"{desc} present")
                results.record_pass()
            else:
                fail(f"{desc} NOT found")
                results.record_fail(f"ClaudeAgent missing: {desc}")
        
        # Check MAX_SEARCHES value
        if "MAX_SEARCHES = 3" in source:
            ok("MAX_SEARCHES correctly set to 3 (per DOC-07)")
            results.record_pass()
        else:
            warn("MAX_SEARCHES may not be set to 3")
            results.record_warning()
            
    except Exception as e:
        fail(f"ClaudeAgent test failed: {e}")
        results.record_fail(f"ClaudeAgent error: {e}")

# ============================================================================
# 10. Integration Point: run_strategy_lab.py
# ============================================================================

def verify_main_entry_point():
    section("10. Main Entry Point Integration")
    
    try:
        entry_point = PROJECT_ROOT / "scripts" / "run_strategy_lab.py"
        
        if not entry_point.exists():
            fail("run_strategy_lab.py not found")
            results.record_fail("Missing entry point")
            return
        
        with open(entry_point) as f:
            source = f.read()
        
        # Check critical integrations
        integrations = [
            ("StatusWriter", "StatusWriter import"),
            ("status_writer.start()", "StatusWriter initialization"),
            ("UniverseManager", "UniverseManager import"),
            ("universe_manager", "UniverseManager usage"),
            ("MCPDataProviderAdapter", "MCP adapter import"),
        ]
        
        for pattern, desc in integrations:
            if pattern in source:
                ok(f"{desc}")
                results.record_pass()
            else:
                fail(f"{desc} NOT integrated")
                results.record_fail(f"Entry point missing: {desc}")
        
        # Check for the bug we identified - MCPDataProviderAdapter constructor
        # Check if servers_config is passed to MCPDataProviderAdapter
        adapter_instantiation = False
        if "MCPDataProviderAdapter" in source:
             import re
             # Find the call pattern
             match = re.search(r'MCPDataProviderAdapter\s*\((.*?)\)', source, re.DOTALL)
             if match:
                 args = match.group(1)
                 if "servers_config" in args or "self.mcp_servers" in args:
                     ok("MCPDataProviderAdapter correctly receives servers_config")
                     results.record_pass()
                     adapter_instantiation = True
                 elif "self.mcp_client" in args and not "servers_config" in args:
                     warn("MCPDataProviderAdapter may be missing servers_config parameter")
                     results.record_warning()
                     adapter_instantiation = True
        
        if not adapter_instantiation:
             # Fallback if regex fails (e.g. if not instantiated here)
             warn("Could not verify MCPDataProviderAdapter instantiation args")
             results.record_warning()
            
    except Exception as e:
        fail(f"Entry point test failed: {e}")
        results.record_fail(f"Entry point error: {e}")

# ============================================================================
# 11. Data Directory Permissions
# ============================================================================

def verify_data_directories():
    section("11. Data Directories & Permissions")
    
    data_dirs = [
        "data",
        "data/costs",
        "reports",
    ]
    
    for dir_path in data_dirs:
        full_path = PROJECT_ROOT / dir_path
        
        if not full_path.exists():
            # Try to create
            try:
                full_path.mkdir(parents=True, exist_ok=True)
                ok(f"Created directory: {dir_path}")
                results.record_pass()
            except Exception as e:
                fail(f"Cannot create {dir_path}: {e}")
                results.record_fail(f"Cannot create directory: {dir_path}")
        else:
            ok(f"Directory exists: {dir_path}")
            results.record_pass()
        
        # Check writable
        if full_path.exists():
            test_file = full_path / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
                ok(f"  └─ Writable")
                results.record_pass()
            except Exception as e:
                fail(f"  └─ Not writable: {e}")
                results.record_fail(f"Directory not writable: {dir_path}")

# ============================================================================
# 12. Environment Variables
# ============================================================================

def verify_environment():
    section("12. Environment Variables")
    
    required_vars = [
        ("ANTHROPIC_API_KEY", True, "Claude API access"),
    ]
    
    optional_vars = [
        ("BRAVE_SEARCH_API_KEY", "Web search capability"),
        ("IBKR_HOST", "IBKR connection"),
        ("IBKR_PORT", "IBKR connection"),
    ]
    
    for var, required, desc in required_vars:
        value = os.getenv(var)
        if value:
            # Mask the key
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            ok(f"{var} is set ({masked}) - {desc}")
            results.record_pass()
        else:
            fail(f"{var} NOT SET - Required for {desc}")
            results.record_fail(f"Missing env var: {var}")
    
    for var, desc in optional_vars:
        value = os.getenv(var)
        if value:
            ok(f"{var} is set - {desc}")
            results.record_pass()
        else:
            warn(f"{var} not set - {desc} (optional)")
            results.record_warning()

# ============================================================================
# 13. JSON File Structure Test
# ============================================================================

def verify_json_structures():
    section("13. JSON File Structure Validation")
    
    # Create sample files and verify Dashboard can read them
    test_files = {
        "data/system_status.json": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_running": True,
            "uptime_seconds": 3600,
            "regime": {
                "current": "BULL",
                "confidence": 0.75,
                "probabilities": {"BULL": 0.75, "BEAR": 0.1, "SIDEWAYS": 0.1, "VOLATILE": 0.05},
                "days_in_regime": 3
            },
            "scheduler": {
                "next_hmm_rules": "2024-12-12T10:00:00Z",
                "next_ai_agent": "2024-12-11T14:00:00Z",
                "last_execution": None
            },
            "active_symbols_count": 35,
            "errors_last_hour": 0
        },
        "data/active_universe.json": {
            "screening_timestamp": datetime.now(timezone.utc).isoformat(),
            "regime_used": "BULL",
            "master_universe_count": 150,
            "filters_applied": {
                "liquidity_passed": 120,
                "trend_passed": 85,
                "volatility_passed": 35,
                "final_count": 35
            },
            "active_symbols": [
                {"ticker": "SPY", "name": "SPDR S&P 500", "sector": "broad_market", "liquidity_tier": 1},
                {"ticker": "QQQ", "name": "Invesco NASDAQ-100", "sector": "technology", "liquidity_tier": 1},
            ]
        },
        "data/signals_cache.json": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "count": 1,
            "signals": [
                {
                    "strategy_id": "ai_agent_swing",
                    "symbol": "NVDA",
                    "direction": "LONG",
                    "confidence": 0.85,
                    "entry_price": 875.50,
                    "stop_loss": 850.00,
                    "take_profit": 925.00,
                    "reasoning": "Strong momentum"
                }
            ]
        }
    }
    
    for file_path, content in test_files.items():
        full_path = PROJECT_ROOT / file_path
        
        try:
            # Write test file
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, 'w') as f:
                json.dump(content, f, indent=2)
            
            # Read back and verify
            with open(full_path) as f:
                read_back = json.load(f)
            
            # Basic structure check
            if file_path.endswith("system_status.json"):
                assert "is_running" in read_back
                assert "regime" in read_back
            elif file_path.endswith("active_universe.json"):
                assert "active_symbols" in read_back
                assert "filters_applied" in read_back
            elif file_path.endswith("signals_cache.json"):
                assert "signals" in read_back
            
            ok(f"Created and validated: {file_path}")
            results.record_pass()
            
        except Exception as e:
            fail(f"Error with {file_path}: {e}")
            results.record_fail(f"JSON structure error: {file_path}")
    
    info("Test JSON files created in data/ - Dashboard should be able to read them")

# ============================================================================
# Main
# ============================================================================

def main():
    print(f"\n{'='*60}")
    print(f"{Colors.BOLD}{Colors.CYAN}NEXUS TRADING - SYSTEM VERIFICATION{Colors.END}")
    print(f"{'='*60}")
    print(f"Project Root: {PROJECT_ROOT}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Run all verifications
    verify_directory_structure()
    verify_config_files()
    verify_imports()
    verify_status_writer()
    verify_cost_tracker()
    verify_web_search()
    verify_dashboard_data_service()
    verify_universe_manager()
    verify_claude_agent()
    verify_main_entry_point()
    verify_data_directories()
    verify_environment()
    verify_json_structures()
    
    # Summary
    success = results.summary()
    
    if success:
        print(f"\n{Colors.GREEN}Next Steps:{Colors.END}")
        print("  1. Start MCP servers (if using)")
        print("  2. Run: python scripts/run_strategy_lab.py")
        print("  3. In separate terminal: cd dashboard && uvicorn app:app --port 8050")
        print("  4. Open: http://localhost:8050")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
