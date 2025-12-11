"""
Log Service for Dashboard.

Reads application logs for display in the UI.
"""

import logging
from pathlib import Path
from collections import deque
from typing import List

logger = logging.getLogger(__name__)

class LogService:
    """
    Service to read logs from the log file.
    """
    
    def __init__(self, log_file: str = "strategy_lab.log"):
        self.log_file = Path(log_file)
        
    def get_recent_logs(self, limit: int = 100) -> List[str]:
        """
        Get the last N lines from the log file.
        Efficient implementation using deque with maxlen.
        """
        if not self.log_file.exists():
            return ["Log file not found."]
            
        try:
            # Efficiently read last N lines without reading whole file
            # For simplicity in this implementation we read line by line but use deque to keep last N
            # For very large files, 'seek' approach is better, but this suffices for < 100MB logs
            with open(self.log_file, 'r', encoding='utf-8', errors='replace') as f:
                return list(deque(f, maxlen=limit))
        except Exception as e:
            logger.error(f"Error reading logs: {e}")
            return [f"Error reading logs: {e}"]

# Singleton
_log_service = None

def get_log_service() -> LogService:
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service
