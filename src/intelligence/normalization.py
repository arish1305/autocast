from typing import List, Dict
from src.core.models import NewsArticle, TrendItem, SourceInfo
from src.core.logger import logger

def normalize_to_trend_items(articles: List[NewsArticle]) -> List[TrendItem]:
    """
    Groups articles by 'topic' (simplified as title for now) 
    and converts them to TrendItem models.
    """
    # Simple grouping by title to simulate de-duplication/cross-source
    # In a real system, we'd use fuzzy matching or LLM grouping.
    trend_map: Dict[str, TrendItem] = {}
    
    for article in articles:
        topic_key = article.title.lower().strip()
        
        source_info = SourceInfo(
            name=article.source_name,
            url=article.url,
            external_id=article.url, # URL as ID for now
            score=0.0,
            engagement_count=article.engagement_count,
            published_at=article.published_at,
        )
        
        if topic_key in trend_map:
            trend_map[topic_key].sources.append(source_info)
            current_latest = trend_map[topic_key].latest_published_at
            if article.published_at and (not current_latest or article.published_at > current_latest):
                trend_map[topic_key].latest_published_at = article.published_at
        else:
            trend_map[topic_key] = TrendItem(
                topic=article.title,
                summary=article.summary or article.title,
                sources=[source_info],
                latest_published_at=article.published_at,
            )
            
    return list(trend_map.values())
