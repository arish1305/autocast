from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

class SourceInfo(BaseModel):
    name: str  # reddit, hackernews, rss, etc.
    url: str
    external_id: str
    score: float = 0.0
    engagement_count: int = 0  # comments, upvotes, etc.
    published_at: Optional[datetime] = None

class TrendItem(BaseModel):
    topic: str
    summary: str
    sources: List[SourceInfo] = []
    trend_score: float = 0.0
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    latest_published_at: Optional[datetime] = None
    confidence_score: float = 0.0
    is_verified: bool = False
    
class NewsArticle(BaseModel):
    title: str
    url: str
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    source_name: str
    author: Optional[str] = None
    engagement_count: int = 0
