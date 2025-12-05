#!/usr/bin/env python3
"""
Global Verification Script - Phase A1
Run: python scripts/verify_fase_a1.py
"""

import sys
import os
import subprocess
from pathlib import Path

def run_check(name, script_path):
    print(f"\n>>> Running verification: {name}")
    print("-" * 50)
    
    try:
        # Force UTF-8 encoding for output capture to avoid Windows charmap errors
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            env=env
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
            
        if result.returncode == 0:
            print(f"✅ {name}: PASSED")
            return True
        else:
            print(f"❌ {name}: FAILED (Exit code {result.returncode})")
            return False
            
    except Exception as e:
        print(f"❌ {name}: ERROR - {e}")
        return False

def main():
    # Force stdout to utf-8
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    print("=" * 60)
    print("GLOBAL VERIFICATION PHASE A1: BASE EXTENSIONS")
    print("=" * 60)
    
    checks = [
        ("Metrics Schema", "scripts/verify_metrics_schema.py"),
        ("Data Configuration", "scripts/verify_data_config.py"),
        ("Provider Factory", "scripts/verify_provider_factory.py"),
        ("ML Models Server", "scripts/verify_ml_server.py")
    ]
    
    results = []
    for name, script in checks:
        if os.path.exists(script):
            success = run_check(name, script)
            results.append((name, success))
        else:
            print(f"\n❌ {name}: Script not found ({script})")
            results.append((name, False))
    
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status:<10} {name}")
        if not success:
            all_passed = False
            
    print("-" * 60)
    if all_passed:
        print("🎉 PHASE A1 COMPLETED SUCCESSFULLY")
        return 0
    else:
        print("⚠️  PENDING ERRORS")
        return 1

if __name__ == "__main__":
    sys.exit(main())
