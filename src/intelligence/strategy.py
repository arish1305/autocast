from typing import Optional, List
from pydantic import BaseModel
from src.core.models import TrendItem
from src.core.llm_client import llm_client
from src.core.logger import logger
from .prompts.strategy_prompts import get_strategy_prompt

class ContentStrategy(BaseModel):
    video_type: str
    duration_seconds: int
    tone: str
    narrative_beats: List[str]

def create_content_strategy(item: TrendItem) -> Optional[ContentStrategy]:
    """Uses LLM to decide the best strategy for a trend topic."""
    logger.info(f"Creating content strategy for: {item.topic}")
    
    source_urls = [s.url for s in item.sources]
    prompt = get_strategy_prompt(item.topic, item.summary, source_urls)
    
    result = llm_client.generate_json(prompt)
    
    if result:
        try:
            return ContentStrategy(**result)
        except Exception as e:
            logger.error(f"Failed to parse strategy JSON: {e}")
            return None
    
    # Fallback/Mock Strategy if LLM fails or is disabled
    logger.warning("Using fallback content strategy.")
    return ContentStrategy(
        video_type="short",
        duration_seconds=60,
        tone="informative",
        narrative_beats=["Hook", "Problem", "Solution", "Impact", "CTA"]
    )
