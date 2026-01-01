from typing import List
from src.ingestion.hackernews import fetch_top_stories
from src.ingestion.rss_feeds import fetch_rss_stories
from src.ingestion.reddit import fetch_reddit_stories
from src.intelligence.normalization import normalize_to_trend_items
from src.intelligence.scoring import rank_trends
from src.intelligence.verifier import verify_trends
from src.core.models import TrendItem
from src.core.logger import logger

def discover_trends() -> List[TrendItem]:
    """Runs all discovery ingestors and returns a ranked list of verified trends."""
    logger.info("Starting trend discovery process...")
    
    all_articles = []
    
    # Fetch from all sources
    hn_stories = fetch_top_stories(limit=30)
    rss_stories = fetch_rss_stories()
    reddit_stories = fetch_reddit_stories()
    
    all_articles.extend(hn_stories)
    all_articles.extend(rss_stories)
    all_articles.extend(reddit_stories)
    
    logger.info(f"Total articles fetched: {len(all_articles)}")
    
    # Normalize
    trend_items = normalize_to_trend_items(all_articles)
    logger.info(f"Unique trend topics identified: {len(trend_items)}")
    
    # Scoring
    ranked_trends = rank_trends(trend_items)
    
    # Verification (Trust Layer)
    verified_trends = verify_trends(ranked_trends, threshold=0.6)
    logger.info(f"Verified trends remaining: {len(verified_trends)}")
    
    return verified_trends
