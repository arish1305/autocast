from typing import Optional, List
from pydantic import BaseModel, field_validator
from src.core.llm_client import llm_client
from src.core.logger import logger
from .prompts.script_prompts import get_script_prompt

class VideoScript(BaseModel):
    script_text: str
    estimated_runtime: int

    @field_validator('script_text', mode='before')
    def parse_script_text(cls, v):
        if isinstance(v, list):
            return " ".join(v)
        return v

def generate_script(topic: str, video_type: str, tone: str, beats: List[str]) -> Optional[VideoScript]:
    """Generates a video script based on the strategy beats using LLM."""
    logger.info(f"Generating {video_type} script for: {topic}")
    
    prompt = get_script_prompt(topic, video_type, tone, beats)
    result = llm_client.generate_json(prompt)
    
    if result:
        try:
            return VideoScript(**result)
        except Exception as e:
            logger.error(f"Failed to parse script JSON: {e}")
            return None
    
    # Fallback/Mock Script
    logger.warning("Using fallback script generation.")
    fallback_text = f"[HOOK] Did you hear about {topic}? This is a game-changer! " \
                    f"[CONTENT] {topic} is taking the tech world by storm. " \
                    f"It aims to solve the biggest problem in its niche by doing something revolutionary. " \
                    f"[IMPACT] We're looking at a future where this becomes standard. " \
                    f"[CTA] If you want more updates on this, hit like and subscribe!"
    
    return VideoScript(
        script_text=fallback_text,
        estimated_runtime=30 if video_type == "short" else 180
    )
