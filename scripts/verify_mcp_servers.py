"""
MCP Servers Verification Script.

Comprehensive verification of all MCP servers:
- Health checks
- Tool availability
- Sample executions
- Response validation

Usage:
    python scripts/verify_mcp_servers.py
    python scripts/verify_mcp_servers.py --server market-data
    python scripts/verify_mcp_servers.py --skip-ibkr
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add mcp-servers to path
project_root = Path(__file__).parent.parent
mcp_servers_root = project_root / 'mcp-servers'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(mcp_servers_root))

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print colored header."""
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{text.center(70)}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"  {text}")


class ServerVerifier:
    """Base class for server verification."""
    
    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def success(self, msg: str):
        """Record success."""
        self.passed += 1
        print_success(msg)
    
    def fail(self, msg: str):
        """Record failure."""
        self.failed += 1
        print_error(msg)
    
    def warn(self, msg: str):
        """Record warning."""
        self.warnings += 1
        print_warning(msg)
    
    async def verify(self) -> bool:
        """Run verification. Override in subclass."""
        raise NotImplementedError
    
    def print_summary(self):
        """Print verification summary."""
        total = self.passed + self.failed
        pass_rate = (self.passed / total * 100) if total > 0 else 0
        
        print(f"\n{'-'*70}")
        print(f"Server: {self.name}")
        print(f"Passed: {self.passed}/{total} ({pass_rate:.1f}%)")
        if self.warnings > 0:
            print(f"Warnings: {self.warnings}")
        print(f"Status: {'PASS' if self.failed == 0 else 'FAIL'}")
        print(f"{'-'*70}")


class MarketDataVerifier(ServerVerifier):
    """Verify Market Data Server."""
    
    def __init__(self):
        super().__init__("Market Data Server")
    
    async def verify(self) -> bool:
        """Verify market data server tools."""
        print_header("MARKET DATA SERVER (Port 3001)")
        
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            
            db_url = os.getenv('DATABASE_URL')
            redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
            
            # Import tools
            sys.path.insert(0, str(mcp_servers_root / 'market-data'))
            from tools import get_symbols_tool
            
            self.success("Tools imported successfully")
            
            # Test 1: get_symbols (no DB required)
            print_info("Testing get_symbols tool...")
            try:
                result = await get_symbols_tool({})
                if 'symbols' in result and result['count'] > 0:
                    self.success(f"get_symbols: {result['count']} symbols loaded")
                else:
                    self.fail("get_symbols: No symbols found")
            except Exception as e:
                self.fail(f"get_symbols failed: {e}")
            
            # Test 2: Filter by market
            print_info("Testing get_symbols with filter...")
            try:
                result = await get_symbols_tool({'market': 'US'})
                if 'symbols' in result:
                    self.success(f"get_symbols filter: {result['count']} US symbols")
                else:
                    self.fail("get_symbols filter failed")
            except Exception as e:
                self.fail(f"get_symbols filter failed: {e}")
            
            # Test 3: Tool structure validation
            print_info("Validating tool response structure...")
            if all(key in result for key in ['count', 'symbols']):
                self.success("Response structure valid")
            else:
                self.fail("Response structure invalid")
            
            self.warn("Database-dependent tools (get_quote, get_ohlcv) not tested")
            
        except ImportError as e:
            self.fail(f"Import failed: {e}")
            return False
        except Exception as e:
            self.fail(f"Verification failed: {e}")
            return False
        
        self.print_summary()
        return self.failed == 0


class TechnicalVerifier(ServerVerifier):
    """Verify Technical Server."""
    
    def __init__(self):
        super().__init__("Technical Server")
    
    async def verify(self) -> bool:
        """Verify technical server tools."""
        print_header("TECHNICAL SERVER (Port 3002)")
        
        try:
            # Import check
            sys.path.insert(0, str(mcp_servers_root / 'technical'))
            from tools import find_sr_levels_tool
            
            self.success("Tools imported successfully")
            
            # Check tool availability
            tools = ['calculate_indicators_tool', 'get_regime_tool', 'find_sr_levels_tool']
            for tool in tools:
                try:
                    __import__(f'tools.{tool.replace("_tool", "")}')
                    self.success(f"{tool} available")
                except ImportError:
                    self.fail(f"{tool} not found")
            
            self.warn("Database-dependent tools not tested (require OHLCV data)")
            
        except ImportError as e:
            self.fail(f"Import failed: {e}")
            return False
        except Exception as e:
            self.fail(f"Verification failed: {e}")
            return False
        
        self.print_summary()
        return self.failed == 0


class RiskVerifier(ServerVerifier):
    """Verify Risk Server."""
    
    def __init__(self):
        super().__init__("Risk Server")
    
    async def verify(self) -> bool:
        """Verify risk server tools."""
        print_header("RISK SERVER (Port 3003)")
        
        try:
            sys.path.insert(0, str(mcp_servers_root / 'risk'))
            from tools import check_limits_tool, calculate_size_tool, get_exposure_tool
            
            self.success("Tools imported successfully")
            
            # Test 1: check_limits
            print_info("Testing check_limits tool...")
            try:
                result = await check_limits_tool({
                    'symbol': 'AAPL',
                    'size': 10000,
                    'portfolio_value': 100000,
                    'current_positions': []
                })
                if 'allowed' in result and isinstance(result['allowed'], bool):
                    self.success("check_limits: Valid response")
                else:
                    self.fail("check_limits: Invalid response structure")
            except Exception as e:
                self.fail(f"check_limits failed: {e}")
            
            # Test 2: calculate_size
            print_info("Testing calculate_size tool...")
            try:
                result = await calculate_size_tool({
                    'portfolio_value': 100000,
                    'win_rate': 0.55,
                    'avg_win': 0.02,
                    'avg_loss': 0.01
                })
                if 'suggested_size' in result and result['suggested_size'] > 0:
                    self.success(f"calculate_size: ${result['suggested_size']:.2f}")
                else:
                    self.fail("calculate_size: Invalid response")
            except Exception as e:
                self.fail(f"calculate_size failed: {e}")
            
            # Test 3: get_exposure
            print_info("Testing get_exposure tool...")
            try:
                result = await get_exposure_tool({
                    'portfolio_value': 100000,
                    'positions': [
                        {'symbol': 'AAPL', 'size': 20000, 'sector': 'Tech', 'market': 'US', 'currency': 'USD'}
                    ]
                })
                if 'total_value' in result and 'concentration_metrics' in result:
                    self.success(f"get_exposure: HHI={result['concentration_metrics']['hhi']:.3f}")
                else:
                    self.fail("get_exposure: Invalid response")
            except Exception as e:
                self.fail(f"get_exposure failed: {e}")
            
        except ImportError as e:
            self.fail(f"Import failed: {e}")
            return False
        except Exception as e:
            self.fail(f"Verification failed: {e}")
            return False
        
        self.print_summary()
        return self.failed == 0


class IBKRVerifier(ServerVerifier):
    """Verify IBKR Server."""
    
    def __init__(self, skip: bool = False):
        super().__init__("IBKR Server")
        self.skip = skip
    
    async def verify(self) -> bool:
        """Verify IBKR server tools."""
        print_header("IBKR SERVER (Port 3004)")
        
        if self.skip:
            self.warn("IBKR verification skipped (--skip-ibkr flag)")
            self.print_summary()
            return True
        
        try:
            sys.path.insert(0, str(mcp_servers_root / 'ibkr'))
            from tools import get_account_tool
            from tools.connection import IBKRConnection
            
            self.success("Tools imported successfully")
            
            # Test connection
            print_info("Testing IBKR Gateway connection...")
            conn = IBKRConnection(host='127.0.0.1', port=4002, client_id=1)
            
            try:
                ib = await conn.connect()
                self.success("Connected to IB Gateway")
                
                # Verify paper trading
                accounts = ib.managedAccounts()
                if accounts and accounts[0].startswith('DU'):
                    self.success(f"Paper trading account: {accounts[0]}")
                else:
                    self.warn(f"Account type unclear: {accounts[0] if accounts else 'None'}")
                
                # Test get_account
                print_info("Testing get_account tool...")
                result = await get_account_tool({}, conn)
                if 'account_id' in result and 'net_liquidation' in result:
                    self.success(f"get_account: ${result['net_liquidation']:,.2f}")
                else:
                    self.fail("get_account: Invalid response")
                
                await conn.disconnect()
                
            except Exception as e:
                self.fail(f"IBKR connection failed: {e}")
                self.warn("Is IB Gateway running?")
                self.warn("Is API enabled in Gateway settings?")
                return False
            
        except ImportError as e:
            self.fail(f"Import failed: {e}")
            return False
        except Exception as e:
            self.fail(f"Verification failed: {e}")
            return False
        
        self.print_summary()
        return self.failed == 0


async def main():
    """Main verification routine."""
    parser = argparse.ArgumentParser(description='Verify MCP Servers')
    parser.add_argument('--server', choices=['market-data', 'technical', 'risk', 'ibkr'],
                       help='Verify specific server only')
    parser.add_argument('--skip-ibkr', action='store_true',
                       help='Skip IBKR verification')
    args = parser.parse_args()
    
    print_header("MCP SERVERS VERIFICATION")
    
    verifiers = []
    
    if args.server is None or args.server == 'market-data':
        verifiers.append(MarketDataVerifier())
    if args.server is None or args.server == 'technical':
        verifiers.append(TechnicalVerifier())
    if args.server is None or args.server == 'risk':
        verifiers.append(RiskVerifier())
    if args.server is None or args.server == 'ibkr':
        verifiers.append(IBKRVerifier(skip=args.skip_ibkr))
    
    # Run verifications
    results = []
    for verifier in verifiers:
        result = await verifier.verify()
        results.append(result)
    
    # Final summary
    print_header("OVERALL SUMMARY")
    
    total_passed = sum(v.passed for v in verifiers)
    total_failed = sum(v.failed for v in verifiers)
    total_tests = total_passed + total_failed
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed} ({total_passed/total_tests*100:.1f}%)")
    print(f"Failed: {total_failed}")
    print()
    
    if all(results):
        print(f"{GREEN}✅ ALL SERVERS VERIFIED SUCCESSFULLY{RESET}")
        return 0
    else:
        print(f"{RED}❌ SOME VERIFICATIONS FAILED{RESET}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
