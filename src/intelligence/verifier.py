from typing import List, Tuple
from src.core.models import TrendItem
from src.core.logger import logger

SOURCE_WEIGHTS = {
    "HackerNews": 0.8,
    "Reddit": 0.6,
    "OfficialNews": 1.0  # RSS feeds from major outlets
}

def calculate_confidence(item: TrendItem) -> float:
    """
    Calculates a confidence score (0-1) based on source diversity and authority.
    Req: min 0.7 for approval.
    """
    if not item.sources:
        return 0.0

    # 1. Source Diversity
    unique_platforms = set()
    for source in item.sources:
        if "hacker-news" in source.name.lower() or "hackernews" in source.name.lower():
            unique_platforms.add("hackernews")
        elif "reddit" in source.name.lower():
            unique_platforms.add("reddit")
        else:
            unique_platforms.add("official") # Default for RSS/Others

    diversity_score = min(len(unique_platforms) * 0.4, 0.8) # 2 sources = 0.8 base

    # 2. Source Authority (Avg of top 2 weights)
    weights = []
    for platform in unique_platforms:
        if platform == "hackernews": weights.append(SOURCE_WEIGHTS["HackerNews"])
        elif platform == "reddit": weights.append(SOURCE_WEIGHTS["Reddit"])
        else: weights.append(SOURCE_WEIGHTS["OfficialNews"])
    
    weights.sort(reverse=True)
    authority_score = sum(weights[:2]) / min(len(weights), 2) if weights else 0.0

    # Final Confidence calculation
    confidence = (diversity_score * 0.6) + (authority_score * 0.4)
    return min(confidence, 1.0)

def verify_trends(items: List[TrendItem], threshold: float = 0.7) -> List[TrendItem]:
    """Filters trends based on confidence threshold and marks them as verified."""
    verified_items = []
    for item in items:
        confidence = calculate_confidence(item)
        item.confidence_score = confidence
        
        if confidence >= threshold:
            item.is_verified = True
            verified_items.append(item)
            logger.info(f"Verified concept: {item.topic} (Confidence: {confidence:.2f})")
        else:
            logger.debug(f"Rejected concept: {item.topic} (Confidence: {confidence:.2f})")
            
    return sorted(verified_items, key=lambda x: x.confidence_score, reverse=True)
