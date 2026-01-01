from typing import List, Dict, Optional
from pydantic import BaseModel
from src.core.llm_client import llm_client
from src.core.logger import logger

class VideoMetadata(BaseModel):
    title: str
    description: str
    tags: List[str]
    category_id: str = "28" # Technology

def optimize_metadata(topic: str, script_text: str) -> Optional[VideoMetadata]:
    """
    Generates SEO-optimized title, description, and tags for YouTube.
    """
    logger.info(f"Optimizing metadata for: {topic}")
    
    prompt = f"""
    Generate YouTube metadata for a video about "{topic}".
    Script content summary: {script_text[:500]}...
    
    Provide:
    1. A catchy, high-CTR title (max 70 chars).
    2. A comprehensive description with keywords.
    3. A list of 10-15 relevant tags.
    
    Output a JSON object with keys: title, description, tags.
    """
    
    result = llm_client.generate_json(prompt)
    
    if result:
        try:
            return VideoMetadata(**result)
        except Exception as e:
            logger.error(f"Failed to parse metadata JSON: {e}")
            
    # Fallback
    logger.warning("Using fallback metadata optimization.")
    return VideoMetadata(
        title=f"The Future of {topic} (2026 Breakthrough)",
        description=f"In this video, we dive deep into {topic} and how it's changing the technology landscape.",
        tags=[topic.lower(), "technology", "innovation", "future tech"]
    )
