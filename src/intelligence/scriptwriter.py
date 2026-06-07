from typing import Optional, List
from pydantic import BaseModel, field_validator
from src.core.llm_client import llm_client
from src.core.logger import logger
from src.intelligence.story_understanding import StoryContext
from .prompts.script_prompts import get_script_prompt

class VideoScript(BaseModel):
    script_text: str
    estimated_runtime: int

    @field_validator('script_text', mode='before')
    def parse_script_text(cls, v):
        if isinstance(v, list):
            return " ".join(v)
        return v

def generate_script(
    topic: str,
    video_type: str,
    tone: str,
    beats: List[str],
    story_context: Optional[StoryContext] = None,
) -> Optional[VideoScript]:
    """Generates a video script based on the strategy beats using LLM."""
    logger.info(f"Generating {video_type} script for: {topic}")
    
    context_block = story_context.compact_context() if story_context else ""
    prompt = get_script_prompt(topic, video_type, tone, beats, context_block)
    result = llm_client.generate_json(prompt)
    
    if result:
        try:
            return VideoScript(**result)
        except Exception as e:
            logger.error(f"Failed to parse script JSON: {e}")
            return None
    
    # Fallback/Mock Script
    logger.warning("Using fallback script generation.")
    context_line = ""
    if story_context and story_context.key_talking_points:
        context_line = f"The key point is this: {story_context.key_talking_points[0]} "
    fallback_text = f"[HOOK] {topic} could change what happens next in tech. " \
                    f"[CONTEXT] {context_line}" \
                    f"[CONTENT] Here is the important part: {topic}. " \
                    f"It matters because the companies, products, and people involved could shape the next wave of adoption. " \
                    f"[IMPACT] Watch how this affects users, developers, and the wider market. " \
                    f"[CTA] Follow for the next update as this story develops."
    
    return VideoScript(
        script_text=fallback_text,
        estimated_runtime=30 if video_type == "short" else 180
    )
