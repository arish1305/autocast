import re
from datetime import datetime
from typing import List, Optional

from src.core.config import settings
from src.core.logger import logger
from src.core.models import TrendItem


AUTHORITY_WEIGHTS = {
    "nytimes": 1.0,
    "theverge": 0.92,
    "verge": 0.92,
    "techcrunch": 0.9,
    "hackernews": 0.78,
    "hacker-news": 0.78,
    "reddit": 0.55,
}

EMERGING_TECH_TERMS = {
    "ai",
    "a.i.",
    "agent",
    "agents",
    "robot",
    "robotics",
    "chip",
    "gpu",
    "quantum",
    "cybersecurity",
    "ransomware",
    "datacenter",
    "data center",
    "llm",
    "space",
}

BREAKING_TERMS = {
    "breaking",
    "launches",
    "announces",
    "unveils",
    "files",
    "sues",
    "raises",
    "ipo",
    "release",
    "released",
    "arrives",
}


def calculate_trend_score(item: TrendItem) -> float:
    """
    Scores trends using the v2 formula:
    freshness 40, engagement 30, mentions/source count 20, authority 10.
    """
    freshness = _freshness_score(item) * 40.0
    engagement = _engagement_score(item) * 30.0
    mentions = _mentions_score(item) * 20.0
    authority = _authority_score(item) * 10.0
    boost = _breaking_or_emerging_boost(item)

    return round(min(freshness + engagement + mentions + authority + boost, 100.0), 2)


def rank_trends(items: List[TrendItem]) -> List[TrendItem]:
    """Filters stale items, scores trends, and returns a sorted list."""
    fresh_items = []
    stale_count = 0

    for item in items:
        if _is_stale(item):
            stale_count += 1
            logger.debug(f"Rejected stale trend: {item.topic}")
            continue
        item.trend_score = calculate_trend_score(item)
        fresh_items.append(item)

    if stale_count:
        logger.info(f"Filtered {stale_count} stale trend candidates.")

    return sorted(fresh_items, key=lambda x: x.trend_score, reverse=True)


def _is_stale(item: TrendItem) -> bool:
    published_at = _latest_published_at(item)
    if published_at:
        age_days = max((datetime.utcnow() - published_at).days, 0)
        if age_days > settings.TREND_MAX_AGE_DAYS:
            return True

    current_year = datetime.utcnow().year
    years = [int(year) for year in re.findall(r"\b20\d{2}\b", item.topic)]
    stale_years = [
        year for year in years
        if year < current_year and not _looks_like_product_year(item.topic, year)
    ]
    return bool(stale_years)


def _freshness_score(item: TrendItem) -> float:
    published_at = _latest_published_at(item)
    if not published_at:
        return 0.72

    age_days = max((datetime.utcnow() - published_at).total_seconds() / 86400, 0.0)
    if age_days <= 1:
        return 1.0
    if age_days <= 3:
        return 0.92
    if age_days <= 7:
        return 0.78
    if age_days <= settings.TREND_MAX_AGE_DAYS:
        return 0.55
    return 0.0


def _engagement_score(item: TrendItem) -> float:
    total_engagement = sum(max(source.engagement_count, 0) for source in item.sources)
    return min(total_engagement / 500.0, 1.0)


def _mentions_score(item: TrendItem) -> float:
    source_count = len({source.name for source in item.sources})
    return min(source_count / 3.0, 1.0)


def _authority_score(item: TrendItem) -> float:
    if not item.sources:
        return 0.0
    scores = [_source_authority(source.name) for source in item.sources]
    return max(scores) if scores else 0.0


def _source_authority(source_name: str) -> float:
    lowered = source_name.lower()
    for key, weight in AUTHORITY_WEIGHTS.items():
        if key in lowered:
            return weight
    return 0.72


def _breaking_or_emerging_boost(item: TrendItem) -> float:
    text = f"{item.topic} {item.summary}".lower()
    boost = 0.0
    if any(term in text for term in BREAKING_TERMS):
        boost += 4.0
    if any(term in text for term in EMERGING_TECH_TERMS):
        boost += 3.0
    return boost


def _latest_published_at(item: TrendItem) -> Optional[datetime]:
    dates = [source.published_at for source in item.sources if source.published_at]
    if dates:
        return max(dates)
    return item.latest_published_at


def _looks_like_product_year(topic: str, year: int) -> bool:
    product_patterns = [
        rf"\b(?:Xbox|PlayStation|Switch|Galaxy|iPhone|Pixel|RTX|H|B)\s*{year}\b",
        rf"\b{year}\s*(?:chip|gpu|console|phone|model)\b",
    ]
    return any(re.search(pattern, topic, flags=re.IGNORECASE) for pattern in product_patterns)
