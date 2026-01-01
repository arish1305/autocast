import requests
from typing import List
from src.core.logger import logger
from src.core.models import NewsArticle

def fetch_top_stories(limit: int = 20) -> List[NewsArticle]:
    """Fetches top stories from Hacker News."""
    try:
        logger.info("Fetching top stories from Hacker News...")
        top_ids_url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        response = requests.get(top_ids_url)
        response.raise_for_status()
        story_ids = response.json()[:limit]

        articles = []
        for story_id in story_ids:
            item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            item_resp = requests.get(item_url)
            item_resp.raise_for_status()
            data = item_resp.json()
            
            if data.get("type") == "story" and "url" in data:
                articles.append(NewsArticle(
                    title=data["title"],
                    url=data["url"],
                    source_name="HackerNews",
                    author=data.get("by"),
                    engagement_count=data.get("score", 0)
                ))
        return articles
    except Exception as e:
        logger.error(f"Error fetching Hacker News stories: {e}")
        return []
