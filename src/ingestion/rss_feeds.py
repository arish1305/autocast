import feedparser
from typing import List
from datetime import datetime
import time
from src.core.logger import logger
from src.core.models import NewsArticle

RSS_FEEDS = [
    "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml",
    "https://feeds.feedburner.com/TechCrunch/",
    "https://www.theverge.com/rss/index.xml"
]

def fetch_rss_stories() -> List[NewsArticle]:
    """Fetches stories from predefined technology RSS feeds."""
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            logger.info(f"Fetching RSS feed: {feed_url}")
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                # Parse published date
                published_at = None
                if hasattr(entry, 'published_parsed'):
                    published_at = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                
                articles.append(NewsArticle(
                    title=entry.title,
                    url=entry.link,
                    summary=entry.get("summary"),
                    published_at=published_at,
                    source_name=feed_url,
                    engagement_count=0  # RSS usually doesn't have engagement metrics easily accessible
                ))
        except Exception as e:
            logger.error(f"Error fetching RSS feed {feed_url}: {e}")
    return articles
