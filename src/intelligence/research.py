import re
from datetime import datetime
from typing import Iterable, List, Optional
from urllib.parse import urlparse

import requests
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logger import logger
from src.core.models import TrendItem
from src.intelligence.story_understanding import StoryContext

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - dependency fallback
    BeautifulSoup = None


class SourceSummary(BaseModel):
    source_name: str
    url: str
    title: str = ""
    description: str = ""
    published_at: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    """Source-backed facts used to keep scripts specific and accurate."""

    topic: str
    source_count: int = 0
    source_names: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)
    source_summaries: List[SourceSummary] = Field(default_factory=list)
    verified_facts: List[str] = Field(default_factory=list)
    statistics: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)

    def compact_context(self, max_facts: int = 8) -> str:
        source_line = ", ".join(self.source_names[:5]) or "discovery sources"
        facts = "\n".join(f"- {fact}" for fact in self.verified_facts[:max_facts])
        stats = ", ".join(self.statistics[:6]) or "none"
        notes = "; ".join(self.confidence_notes[:3]) or "none"
        return (
            f"Sources checked: {source_line}\n"
            f"Source count: {self.source_count}\n"
            f"Statistics found: {stats}\n"
            f"Source-backed facts:\n{facts or '- No extracted source facts.'}\n"
            f"Confidence notes: {notes}"
        )


def build_research_brief(
    trend: TrendItem,
    story_context: StoryContext,
    max_sources: Optional[int] = None,
) -> ResearchBrief:
    """Fetches source pages and extracts short, source-backed facts for scripting."""
    limit = max_sources or settings.RESEARCH_MAX_SOURCES
    source_infos = [source for source in trend.sources if _is_fetchable_url(source.url)][:limit]
    source_summaries: List[SourceSummary] = []
    confidence_notes: List[str] = []

    important_terms = _important_terms(trend, story_context)
    for source in source_infos:
        summary = _fetch_source_summary(source.name, source.url, important_terms)
        if summary:
            source_summaries.append(summary)
        else:
            confidence_notes.append(f"Could not extract article text from {source.name or source.url}.")

    facts = _collect_facts(trend, story_context, source_summaries, important_terms)
    statistics = _unique([
        *story_context.statistics,
        *[_stat for fact in facts for _stat in _extract_statistics(fact)],
    ])[:10]

    if source_summaries:
        confidence_notes.insert(0, f"Extracted facts from {len(source_summaries)} source page(s).")
    else:
        confidence_notes.insert(0, "Using discovery summary and story context because source pages were unavailable.")

    brief = ResearchBrief(
        topic=trend.topic,
        source_count=len(source_summaries),
        source_names=_unique([source.name for source in trend.sources if source.name])[:8],
        source_urls=_unique([source.url for source in trend.sources if source.url])[:8],
        source_summaries=source_summaries,
        verified_facts=facts[:10],
        statistics=statistics,
        confidence_notes=_unique(confidence_notes)[:5],
    )
    logger.info(
        f"Research brief ready: sources={brief.source_count}, "
        f"facts={len(brief.verified_facts)}, stats={len(brief.statistics)}"
    )
    return brief


def _fetch_source_summary(
    source_name: str,
    url: str,
    important_terms: set,
) -> Optional[SourceSummary]:
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 AutoCastAI/1.0 "
                    "(story research; contact: local development)"
                )
            },
            timeout=settings.RESEARCH_FETCH_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if content_type and "html" not in content_type and "text" not in content_type:
            logger.warning(f"Skipping non-text source content: {url}")
            return None
    except Exception as exc:
        logger.warning(f"Source research fetch failed for {url}: {exc}")
        return None

    html = response.text[: settings.RESEARCH_MAX_HTML_CHARS]
    title, description, published_at, paragraphs = _extract_article_parts(html)
    key_points = _rank_fact_sentences(paragraphs, important_terms)[:4]

    if not title and not description and not key_points:
        return None

    return SourceSummary(
        source_name=source_name or _host(url),
        url=url,
        title=title,
        description=description,
        published_at=published_at,
        key_points=key_points,
    )


def _extract_article_parts(html_text: str) -> tuple[str, str, Optional[str], List[str]]:
    if BeautifulSoup is None:
        clean = re.sub(r"<[^>]+>", " ", html_text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return "", "", None, _split_sentences(clean[:6000])

    soup = BeautifulSoup(html_text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside"]):
        tag.decompose()

    title = _meta_content(soup, ["og:title", "twitter:title"]) or _tag_text(soup.title)
    description = _meta_content(
        soup,
        ["description", "og:description", "twitter:description"],
    )
    published_at = _meta_content(
        soup,
        ["article:published_time", "datePublished", "pubdate", "publishdate"],
    )
    published_at = _normalize_date(published_at)

    paragraphs = []
    for tag in soup.find_all(["p", "li"]):
        text = _clean_text(tag.get_text(" ", strip=True))
        if _looks_like_article_text(text):
            paragraphs.append(text)
    return title, description, published_at, paragraphs[:30]


def _meta_content(soup, names: Iterable[str]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(tag["content"])
    return ""


def _tag_text(tag) -> str:
    return _clean_text(tag.get_text(" ", strip=True)) if tag else ""


def _collect_facts(
    trend: TrendItem,
    story_context: StoryContext,
    summaries: List[SourceSummary],
    important_terms: set,
) -> List[str]:
    candidates = [
        story_context.story_summary,
        *story_context.key_talking_points,
    ]
    for summary in summaries:
        candidates.extend([
            summary.title,
            summary.description,
            *summary.key_points,
        ])

    facts = []
    for candidate in candidates:
        for sentence in _split_sentences(candidate):
            cleaned = _clean_fact(sentence)
            if _is_good_fact(cleaned, important_terms):
                facts.append(cleaned)

    if not facts and trend.summary:
        facts.append(_clean_fact(trend.summary))
    if trend.topic and trend.topic not in facts:
        facts.insert(0, trend.topic)
    return _unique(facts)


def _rank_fact_sentences(paragraphs: List[str], important_terms: set) -> List[str]:
    scored = []
    for paragraph in paragraphs:
        for sentence in _split_sentences(paragraph):
            fact = _clean_fact(sentence)
            if not _is_good_fact(fact, important_terms):
                continue
            terms = _terms(fact)
            overlap = len(terms.intersection(important_terms))
            number_bonus = 2 if _extract_statistics(fact) else 0
            source_bonus = 1 if any(term in fact.lower() for term in ("reported", "announced", "said", "filed")) else 0
            scored.append((overlap + number_bonus + source_bonus, fact))
    scored.sort(key=lambda item: item[0], reverse=True)
    return _unique(fact for _, fact in scored)


def _important_terms(trend: TrendItem, story_context: StoryContext) -> set:
    values = [
        trend.topic,
        story_context.headline,
        story_context.main_story_angle,
        *story_context.entities,
        *story_context.companies,
        *story_context.products,
        *story_context.technologies,
        *story_context.people,
        *story_context.locations,
        *story_context.search_focus,
    ]
    return _terms(" ".join(values))


def _terms(text: str) -> set:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9&.-]{2,}", text or "")
        if token.lower() not in _STOPWORDS
    }


def _split_sentences(text: str) -> List[str]:
    text = _clean_text(text)
    if not text:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _clean_fact(text: str) -> str:
    text = _clean_text(text)
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwww\.\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\S+\.(?:com|org|net|io|ai|co|dev|html|xml|rss)\S*\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:Image Credits?|Photo Credits?|Advertisement)\s*:\s*", "", text, flags=re.IGNORECASE)
    return _clean_text(text).strip(" -")


def _clean_text(text: Optional[str]) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\xa0", " ")
    return text.strip()


def _is_good_fact(text: str, important_terms: set) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(term in lowered for term in _BAD_TEXT_MARKERS):
        return False
    words = text.split()
    if len(words) < 8 or len(words) > 42:
        return False
    if re.search(r"[{}<>]", text):
        return False
    terms = _terms(text)
    has_story_overlap = bool(terms.intersection(important_terms))
    has_number = bool(_extract_statistics(text))
    return has_story_overlap or has_number


def _looks_like_article_text(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if any(term in lowered for term in _BAD_TEXT_MARKERS):
        return False
    words = text.split()
    return 8 <= len(words) <= 90


def _extract_statistics(text: str) -> List[str]:
    pattern = (
        r"\$?\d+(?:\.\d+)?\s?"
        r"(?:%|percent|million|billion|trillion|users|people|years|months|days|hours|"
        r"x|times|share|shares|B|M|K|valuation|revenue)"
    )
    return _unique(re.findall(pattern, text or "", flags=re.IGNORECASE))


def _normalize_date(value: str) -> Optional[str]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.isoformat()
    except Exception:
        return value[:40]


def _is_fetchable_url(url: str) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        cleaned = _clean_text(str(value)).strip()
        key = re.sub(r"\W+", "", cleaned.lower())
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


_STOPWORDS = {
    "about", "after", "again", "also", "because", "before", "being", "could",
    "from", "have", "into", "more", "over", "said", "that", "their", "there",
    "they", "this", "through", "what", "when", "where", "which", "while",
    "with", "would", "your",
}

_BAD_TEXT_MARKERS = {
    "subscribe",
    "newsletter",
    "cookie",
    "privacy policy",
    "terms of service",
    "advertisement",
    "sign up",
    "log in",
    "click here",
    "all rights reserved",
    "share this",
    "follow us",
    "http://",
    "https://",
    "www.",
}
