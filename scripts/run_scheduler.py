"""
Data Pipeline Scheduler Runner

Starts the data pipeline scheduler to automate daily updates.
Scheduler runs 3 jo

bs:
- 18:30 CET: OHLCV data update
- 18:35 CET: Technical indicators calculation
- 18:45 CET: Feature generation

Usage:
    # Run scheduler (foreground)
    python scripts/run_scheduler.py
    
    # Run jobs once (test mode)
    python scripts/run_scheduler.py --once
    
    # Run in background (daemon mode)
    python scripts/run_scheduler.py --daemon
"""

import sys
import os
import logging
import argparse
import time
import signal
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.data.scheduler import DataScheduler

# Configure logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run data pipeline scheduler')
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run all jobs once and exit (test mode)'
    )
    
    parser.add_argument(
        '--daemon',
        action='store_true',
        help='Run in background/daemon mode'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/scheduler.yaml',
        help='Path to scheduler configuration file'
    )
    
    return parser.parse_args()


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down scheduler...")
    sys.exit(0)


def run_once_mode(scheduler: DataScheduler):
    """
    Run all jobs once for testing.
   
    Args:
        scheduler: Data scheduler instance
    """
    logger.info("Running in ONCE mode - executing all jobs manually")
    print()
    print("=" * 70)
    print("SCHEDULER TEST MODE - Running all jobs once")
    print("=" * 70)
    print()
    
    jobs = [
        ('OHLCV Update', scheduler.job_update_ohlcv),
        ('Indicators Calculation', scheduler.job_calculate_indicators),
        ('Features Generation', scheduler.job_generate_features)
    ]
    
    results = []
    
    for job_name, job_func in jobs:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Running: {job_name}")
        print('-' * 70)
        
        try:
            start_time = time.time()
            job_func()
            duration = time.time() - start_time
            
            print(f"  ✓ {job_name} completed in {duration:.1f}s")
            results.append((job_name, True, duration))
            
        except Exception as e:
            logger.error(f"Job '{job_name}' failed: {e}")
            print(f"  ✗ {job_name} FAILED: {e}")
            results.append((job_name, False, 0))
        
        print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    successful = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"Jobs completed: {successful}/{total}")
    print()
    
    for job_name, success, duration in results:
        status = "✓ PASS" if success else "✗ FAIL"
        time_str = f"({duration:.1f}s)" if success else ""
        print(f"  {status} - {job_name} {time_str}")
    
    print()
    print("=" * 70)
    
    if successful < total:
        sys.exit(1)


def run_daemon_mode(scheduler: DataScheduler):
    """
    Run scheduler in daemon mode.
    
    Args:
        scheduler: Data scheduler instance
    """
    logger.info("Starting scheduler in DAEMON mode")
    print()
    print("=" * 70)
    print("DATA PIPELINE SCHEDULER")
    print("=" * 70)
    print()
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Scheduled jobs:")
    print("  - 18:30 CET: OHLCV Update")
    print("  - 18:35 CET: Indicators Calculation")
    print("  - 18:45 CET: Features Generation")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 70)
    print()
    
    scheduler.start()
    
    try:
        # Keep running
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("Shutdown signal received")
        print("\n\nShutting down scheduler...")
        scheduler.shutdown()
        print("✓ Scheduler stopped")


def main():
    """Main entry point."""
    args = parse_args()
    
    # Load environment
    load_dotenv()
    
    db_url = os.getenv('DATABASE_URL')
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    
    if not db_url:
        logger.error("DATABASE_URL not found in environment")
        sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize scheduler
    logger.info(f"Initializing scheduler from {args.config}")
    scheduler = DataScheduler(args.config, db_url, redis_url)
    
    # Run mode
    if args.once:
        run_once_mode(scheduler)
    else:
        run_daemon_mode(scheduler)


if __name__ == "__main__":
    main()

