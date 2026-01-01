from typing import List
from datetime import datetime
from src.core.models import TrendItem
from src.core.logger import logger

def calculate_trend_score(item: TrendItem) -> float:
    """
    Calculates a trend score based on:
    - Number of sources (cross-source confirmation)
    - Engagement across sources
    - Freshness (TODO)
    """
    score = 0.0
    
    # 1. Cross-Source Confirmation (Major boost)
    # Each unique source adds a base score
    score += len(item.sources) * 20.0
    
    # 2. Engagement
    total_engagement = sum(s.engagement_count for s in item.sources)
    score += min(total_engagement / 10, 50.0) # Cap engagement contribution
    
    # 3. Freshness (Simplified)
    # Items detected more recently are prioritized (default set by detected_at)
    
    return min(score, 100.0)

def rank_trends(items: List[TrendItem]) -> List[TrendItem]:
    """Ranks trend items by their score and returns the sorted list."""
    for item in items:
        item.trend_score = calculate_trend_score(item)
    
    return sorted(items, key=lambda x: x.trend_score, reverse=True)
