from typing import List, Dict, Optional
from pydantic import BaseModel
from src.core.llm_client import llm_client
from src.core.logger import logger
from src.media.pexels_client import pexels_client
from src.media.pixabay_client import pixabay_client

class VisualScene(BaseModel):
    segment_text: str
    keywords: List[str]
    asset_path: Optional[str] = None
    asset_type: str = "video" # video or image

def break_script_into_scenes(script_text: str) -> List[VisualScene]:
    """Uses LLM to segment the script and extract keywords for each visual scene."""
    logger.info("Breaking script into visual scenes...")
    
    prompt = f"""
Break the following video script into logical visual scenes (3-5 scenes).
For each scene, provide:
1. segment_text: The portion of the script for this scene.
2. keywords: List of 3 descriptive keywords for stock footage search.
3. asset_type: Either "video" or "image".

Script:
{script_text}

Output a JSON array of objects.
"""
    result = llm_client.generate_json(prompt)
    
    scenes = []
    if result and isinstance(result, list):
        for item in result:
            try:
                scenes.append(VisualScene(**item))
            except Exception as e:
                logger.error(f"Failed to parse scene: {e}")
    
    if not scenes:
        logger.warning("Using fallback scene breakdown.")
        scenes = [VisualScene(segment_text=script_text, keywords=["technology", "innovation"])]
        
    return scenes

def source_visual_assets(scenes: List[VisualScene]) -> List[VisualScene]:
    """Sourcing assets for each scene using Pexels."""
    for i, scene in enumerate(scenes):
        query = " ".join(scene.keywords)
        videos = pexels_client.search_videos(query, limit=1)
        
        if videos:
            # Pick the best Pexels link
            video_url = videos[0]["video_files"][0]["link"]
            scene.asset_path = pexels_client.download_asset(video_url, f"scene_{i}.mp4")
        else:
            logger.info(f"Pexels failed for scene {i}. Trying Pixabay...")
            pixabay_videos = pixabay_client.search_videos(query, limit=1)
            if pixabay_videos:
                video_url = pixabay_videos[0].get("videos", {}).get("medium", {}).get("url")
                if video_url:
                    scene.asset_path = pexels_client.download_asset(video_url, f"scene_{i}.mp4")
            
        if not scene.asset_path:
            logger.warning(f"No asset found for scene {i} with keywords: {query}")
            
    return scenes
