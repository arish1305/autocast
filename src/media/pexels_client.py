import requests
from src.core.config import settings
from src.core.logger import logger
from typing import List, Optional, Dict

class PexelsClient:
    """Wrapper for the Pexels API to source stock photos and videos."""
    
    BASE_URL = "https://api.pexels.com"
    
    def __init__(self):
        self.api_key = settings.PEXELS_API_KEY
        if not self.api_key or self.api_key.startswith("your_"):
            logger.warning("PEXELS_API_KEY not found. Stock sourcing will be disabled.")
            self.api_key = None
            
    def search_videos(self, query: str, limit: int = 3) -> List[Dict]:
        """Searches for videos on Pexels."""
        if not self.api_key:
            return []
            
        try:
            logger.info(f"Searching Pexels for videos: {query}")
            headers = {"Authorization": self.api_key}
            params = {"query": query, "per_page": limit}
            response = requests.get(f"{self.BASE_URL}/videos/search", headers=headers, params=params, timeout=20)
            response.raise_for_status()
            
            videos = response.json().get("videos", [])
            return videos
        except Exception as e:
            logger.error(f"Pexels video search failed: {e}")
            return []

    def download_asset(self, url: str, filename: str) -> Optional[str]:
        """Downloads an asset from a URL and saves it locally."""
        import os
        output_path = os.path.join(settings.DATA_DIR, "assets", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            logger.info(f"Downloading asset from {url} to {output_path}")
            response = requests.get(url, stream=True, timeout=60)
            response.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return output_path
        except Exception as e:
            logger.error(f"Asset download failed: {e}")
            return None

# Global instance
pexels_client = PexelsClient()
