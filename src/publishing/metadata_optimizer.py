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
You are a YouTube metadata editor for AutoCast AI, a technology-news video channel.
Create metadata that is searchable, accurate, and not misleading.

VIDEO TOPIC
{topic}

SCRIPT EXCERPT
{script_text[:1200]}

METADATA GOAL
Help viewers and YouTube understand the exact story:
- main company/product/entity
- practical impact
- technology category
- relevant region, market, or policy angle if present

TITLE RULES
1. Max 70 characters.
2. Clear and specific.
3. High curiosity, but factual.
4. Do not use fake urgency like "You Won't Believe" or "This Changes Everything".
5. Do not include URLs, hashtags, or unsupported numbers.

DESCRIPTION RULES
1. 2-4 short paragraphs.
2. Summarize what happened and why it matters.
3. Include relevant keywords naturally.
4. Mention that the video is a tech-news explainer/update.
5. Do not include unsupported claims, fake citations, or raw source URLs.

TAG RULES
1. Provide 10-15 tags.
2. Include company/product names, technology category, and story angle.
3. Use lowercase or title case consistently.
4. No URLs, no irrelevant viral tags, no competitor bait.

Return only valid JSON with this exact shape:
{{
  "title": "specific title under 70 chars",
  "description": "2-4 short paragraphs of accurate YouTube description text",
  "tags": ["tag one", "tag two", "tag three"],
  "category_id": "28"
}}
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
