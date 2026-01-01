from typing import List
from src.core.models import TrendItem

def generate_citations(item: TrendItem) -> str:
    """Generates a formatted citation string for the trend item."""
    if not item.sources:
        return "No sources available."
    
    citations = []
    for i, source in enumerate(item.sources[:3]): # Limit to top 3 sources
        citations.append(f"[{i+1}] {source.name}: {source.url}")
        
    return "\n".join(citations)
