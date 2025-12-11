"""
Status Writer - Writes system heartbeat for Dashboard.

This component periodically writes a JSON file that allows the separate 
Dashboard process to monitor the Strategy Lab status in real-time.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class StatusWriter:
    """
    Periodically writes system status to data/system_status.json.
    """
    
    def __init__(
        self,
        output_file: str = "data/system_status.json",
        interval_seconds: int = 30,
    ):
        self.output_file = Path(output_file)
        self.interval_seconds = interval_seconds
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Internal state (updated by StrategyLab)
        self._start_time = datetime.now(timezone.utc)
        self._is_running = False
        self._regime = "UNKNOWN"
        self._regime_confidence = 0.0
        self._regime_probabilities = {}
        self._days_in_regime = 0
        self._active_symbols_count = 0
        self._next_hmm_rules: Optional[str] = None
        self._next_ai_agent: Optional[str] = None
        self._last_execution: Optional[dict] = None
        self._errors_last_hour = 0
        
        # Periodic task
        self._write_task: Optional[asyncio.Task] = None
    
    def start(self):
        """Start periodic writing."""
        self._is_running = True
        self._write_task = asyncio.create_task(self._write_loop())
        logger.info(f"StatusWriter started, writing to {self.output_file}")
    
    async def stop(self):
        """Stop writing and cleanup."""
        self._is_running = False
        if self._write_task:
            self._write_task.cancel()
            try:
                await self._write_task
            except asyncio.CancelledError:
                pass
        
        # Write final stopped status
        await self._write_status()
        logger.info("StatusWriter stopped")
    
    async def _write_loop(self):
        """Main loop."""
        while self._is_running:
            try:
                await self._write_status()
            except Exception as e:
                logger.error(f"Error in StatusWriter loop: {e}")
            await asyncio.sleep(self.interval_seconds)
    
    async def _write_status(self):
        """Write current state to file."""
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        
        status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_running": self._is_running,
            "uptime_seconds": int(uptime),
            "regime": {
                "current": self._regime,
                "confidence": self._regime_confidence,
                "probabilities": self._regime_probabilities,
                "days_in_regime": self._days_in_regime,
            },
            "scheduler": {
                "next_hmm_rules": self._next_hmm_rules,
                "next_ai_agent": self._next_ai_agent,
                "last_execution": self._last_execution,
            },
            "active_symbols_count": self._active_symbols_count,
            "errors_last_hour": self._errors_last_hour,
        }
        
        try:
            with open(self.output_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write system status: {e}")

    # Setters for external components to update state
    
    def set_regime(self, regime: str, confidence: float, probs: Dict[str, float], days: int):
        self._regime = regime
        self._regime_confidence = confidence
        self._regime_probabilities = probs
        self._days_in_regime = days
        # Trigger immediate update on major state change
        asyncio.create_task(self._write_status())

    def set_next_execution(self, hmm_time: Optional[datetime], ai_time: Optional[datetime]):
        if hmm_time:
            self._next_hmm_rules = hmm_time.isoformat()
        if ai_time:
            self._next_ai_agent = ai_time.isoformat()
            
    def set_active_symbols_count(self, count: int):
        self._active_symbols_count = count
        
    def record_execution(self, strategy: str, signals: int):
        self._last_execution = {
            "strategy": strategy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "signals_generated": signals
        }
        asyncio.create_task(self._write_status())
        
    def increment_error(self):
        self._errors_last_hour += 1
