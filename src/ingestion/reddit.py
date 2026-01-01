import praw
from typing import List
from src.core.logger import logger
from src.core.config import settings
from src.core.models import NewsArticle

SUBREDDITS = ["technology", "programming", "artificial"]

def fetch_reddit_stories(limit: int = 10) -> List[NewsArticle]:
    """Fetches top stories from tech-related subreddits."""
    # Redit API requires credentials which the user might not have set yet.
    # We should handle the case where credentials are missing.
    try:
        if not settings.YOUTUBE_API_KEY: # Using as placeholder for 'has credentials' check or add REDDIT_CLIENT_ID
             logger.warning("Reddit credentials not found. Skipping Reddit ingestion.")
             return []

        # Placeholder for real Reddit initialization
        # reddit = praw.Reddit(
        #     client_id=settings.REDDIT_CLIENT_ID,
        #     client_secret=settings.REDDIT_CLIENT_SECRET,
        #     user_agent="TrendPilot AI 0.1"
        # )
        
        # For now, we'll return an empty list or mock until we have credentials
        # but the structure is there.
        return []
    except Exception as e:
        logger.error(f"Error fetching Reddit stories: {e}")
        return []
