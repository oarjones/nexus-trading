"""
Cost Tracker for AI Agents.

Tracks token usage, api calls, and estimates costs for LLM operations
and search queries.
"""

import logging
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, List, Optional
import os

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""
    input_tokens: int
    output_tokens: int
    model_id: str
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class AgentCostRecord:
    """
    Record of a cost-incurring event.
    """
    timestamp: str  # ISO format
    event_type: str  # "decision", "search", "tool_use"
    agent_id: str
    model: str
    tokens: Optional[TokenUsage] = None
    search_queries: int = 0
    cost_usd: float = 0.0
    context: str = ""


class CostTracker:
    """
    Tracks and persists AI agent costs.
    
    Persists data to: data/costs/YYYY-MM-DD.json
    """
    
    # Cost constants (approximate, check provider for latest)
    COSTS = {
        # Anthropic (Input / Output per 1M tokens)
        "claude-3-5-sonnet-20240620": {"input": 3.0, "output": 15.0},
        "claude-3-sonnet-20240229": {"input": 3.0, "output": 15.0},
        "claude-3-opus-20240229":   {"input": 15.0, "output": 75.0},
        "claude-3-haiku-20240307":  {"input": 0.25, "output": 1.25},
        
        # Search API
        "brave_search": 0.005,  # $5 per 1000 queries roughly = $0.005 per query
    }
    
    def __init__(self, data_dir: str = "data/costs"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._current_records: List[AgentCostRecord] = []
        
    def track_llm_call(
        self, 
        agent_id: str, 
        model: str, 
        input_tokens: int, 
        output_tokens: int,
        context: str = ""
    ) -> float:
        """
        Track an LLM API call.
        
        Returns:
            Estimated cost in USD
        """
        usage = TokenUsage(input_tokens, output_tokens, model)
        cost = self._calculate_llm_cost(model, input_tokens, output_tokens)
        
        record = AgentCostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="llm_call",
            agent_id=agent_id,
            model=model,
            tokens=usage,
            cost_usd=cost,
            context=context
        )
        
        self.save_record(record)
        return cost
        
    def track_search(
        self,
        agent_id: str,
        query_count: int = 1,
        context: str = ""
    ) -> float:
        """
        Track web search queries.
        
        Returns:
            Estimated cost in USD
        """
        cost = query_count * self.COSTS["brave_search"]
        
        record = AgentCostRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type="web_search",
            agent_id=agent_id,
            model="brave_search",
            search_queries=query_count,
            cost_usd=cost,
            context=context
        )
        
        self.save_record(record)
        return cost
        
    def save_record(self, record: AgentCostRecord):
        """Save a record to today's cost file."""
        today = date.today().isoformat()
        file_path = self.data_dir / f"{today}.json"
        
        try:
            # Load existing
            data = {"records": [], "summary": {}}
            if file_path.exists():
                with open(file_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            # Append new record
            # Convert TokenUsage to dict for JSON serialization
            record_dict = asdict(record)
            data["records"].append(record_dict)
            
            # Update summary
            summary = data.get("summary", {})
            summary["total_cost_usd"] = summary.get("total_cost_usd", 0) + record.cost_usd
            summary["total_tokens"] = summary.get("total_tokens", 0)
            if record.tokens:
                summary["total_tokens"] += (record.tokens.input_tokens + record.tokens.output_tokens)
            summary["total_searches"] = summary.get("total_searches", 0) + record.search_queries
            summary["total_records"] = len(data["records"])
            summary["last_updated"] = datetime.now(timezone.utc).isoformat()
            
            data["summary"] = summary
            
            # Write back
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save cost record: {e}")

    def _calculate_llm_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost for LLM usage."""
        # Find closest matching model pricing
        pricing = None
        for key in self.COSTS:
            if key in model or model in key:
                if isinstance(self.COSTS[key], dict):
                    pricing = self.COSTS[key]
                    break
        
        if not pricing:
            logger.warning(f"Unknown pricing for model {model}, using default (sonnet)")
            pricing = self.COSTS["claude-3-5-sonnet-20240620"]
            
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost

    def get_daily_summary(self, day: date = None) -> Dict:
        """Get cost summary for a specific day (default: today)."""
        if day is None:
            day = date.today()
            
        file_path = self.data_dir / f"{day.isoformat()}.json"
        if not file_path.exists():
            return {"total_cost_usd": 0.0, "total_tokens": 0, "total_searches": 0}
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return data.get("summary", {})
        except Exception:
            return {}

# Singleton instance
_tracker_instance = None

def get_cost_tracker() -> CostTracker:
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = CostTracker()
    return _tracker_instance
