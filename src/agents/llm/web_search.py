"""
Web Search Client using Brave Search API.

Provides real-time information to the AI Agent.
Requires BRAVE_SEARCH_API_KEY environment variable.
"""

import os
import aiohttp
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Single search result item."""
    title: str
    url: str
    snippet: str
    published_time: Optional[str] = None
    
    def to_string(self) -> str:
        """Format as string for LLM context."""
        date_str = f" [{self.published_time}]" if self.published_time else ""
        return f"Title: {self.title}\nURL: {self.url}{date_str}\nSnippet: {self.snippet}\n"


class WebSearchClient:
    """
    Client for Brave Search API.
    """
    
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self, api_key: str = None):
        """
        Initialize search client.
        
        Args:
            api_key: Brave Search API key. Defaults to env var BRAVE_SEARCH_API_KEY.
        """
        self.api_key = api_key or os.getenv("BRAVE_SEARCH_API_KEY")
        if not self.api_key:
            logger.warning("BRAVE_SEARCH_API_KEY not set. Web search will fail.")
            
    async def search(
        self, 
        query: str, 
        count: int = 5,
        freshness: str = None
    ) -> List[SearchResult]:
        """
        Perform a web search.
        
        Args:
            query: Search query string
            count: Number of results (max 20)
            freshness: 'pd' (day), 'pw' (week), 'pm' (month), 'py' (year), or None
            
        Returns:
            List of SearchResult objects
        """
        if not self.api_key:
            logger.error("Cannot search: API key missing")
            return []
            
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.api_key
        }
        
        params = {
            "q": query,
            "count": min(count, 20)
        }
        
        if freshness:
            params["freshness"] = freshness
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL, 
                    headers=headers, 
                    params=params, 
                    timeout=10
                ) as response:
                    
                    if response.status != 200:
                        text = await response.text()
                        logger.error(f"Search API error {response.status}: {text}")
                        return []
                        
                    data = await response.json()
                    results = self._parse_response(data)
                    logger.debug(f"SEARCH RESULTS for '{query}':\n{[r.to_string() for r in results]}")
                    return results
                    
        except Exception as e:
            logger.error(f"Search request failed: {e}")
            return []
    
    def _parse_response(self, data: dict) -> List[SearchResult]:
        """Parse Brave Search API response."""
        results = []
        
        # Web results are usually under web.results
        web = data.get("web", {})
        items = web.get("results", [])
        
        for item in items:
            try:
                # Extract publication date if available (often in age or extra_snippets)
                pub_time = item.get("age", "") 
                
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    published_time=pub_time
                ))
            except Exception as e:
                logger.warning(f"Error parsing result item: {e}")
                continue
                
        return results

    async def get_financial_news(self, symbol: str, days: int = 7) -> str:
        """
        Helper to get financial news for a symbol.
        
        Args:
            symbol: Ticker symbol (e.g. AAPL)
            days: Lookback days (converted to freshness)
            
        Returns:
            Formatted string with top news
        """
        # Map days to freshness parameter
        freshness = "pw" # Default to week
        if days <= 1:
            freshness = "pd"
        elif days > 30:
            freshness = "pm"
            
        query = f"{symbol} stock news financial analysis"
        results = await self.search(query, count=5, freshness=freshness)
        
        if not results:
            return f"No recent news found for {symbol}."
            
        formatted = f"Recent News for {symbol} (Last {days} days):\n\n"
        for i, res in enumerate(results, 1):
            formatted += f"{i}. {res.title}\n   {res.snippet}\n   Source: {res.url}\n\n"
            
        return formatted
