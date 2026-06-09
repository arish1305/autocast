import requests
from src.core.config import settings
from src.core.logger import logger
from typing import List, Optional, Dict

class PixabayClient:
    """Wrapper for the Pixabay API to source free stock videos."""
    
    BASE_URL = "https://pixabay.com/api/videos/"
    
    def __init__(self):
        self.api_key = settings.PIXABAY_API_KEY
        if not self.api_key or self.api_key.startswith("your_"):
            logger.warning("PIXABAY_API_KEY not found. Pixabay sourcing will be disabled.")
            self.api_key = None
            
    def search_videos(self, query: str, limit: int = 3) -> List[Dict]:
        """Searches for videos on Pixabay."""
        if not self.api_key:
            return []
            
        try:
            logger.info(f"Searching Pixabay for videos: {query}")
            params = {
                "key": self.api_key,
                "q": query,
                "per_page": min(limit, 20),
                "safesearch": "true"
            }
            response = requests.get(self.BASE_URL, params=params, timeout=20)
            response.raise_for_status()
            
            hits = response.json().get("hits", [])
            return hits
        except Exception as e:
            logger.error(f"Pixabay video search failed: {e}")
            return []

# Global instance
pixabay_client = PixabayClient()
