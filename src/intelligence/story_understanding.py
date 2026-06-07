import html
import re
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field

from src.core.llm_client import llm_client
from src.core.logger import logger
from src.core.models import TrendItem


TECH_COMPANIES = [
    "OpenAI",
    "Microsoft",
    "Google",
    "Alphabet",
    "Apple",
    "Meta",
    "Amazon",
    "AWS",
    "Nvidia",
    "AMD",
    "Intel",
    "Tesla",
    "SpaceX",
    "Anthropic",
    "Perplexity",
    "xAI",
    "Samsung",
    "Sony",
    "IBM",
    "Oracle",
    "Salesforce",
    "Adobe",
    "Qualcomm",
    "TSMC",
    "Arm",
    "ByteDance",
    "TikTok",
    "Reddit",
    "GitHub",
    "Hugging Face",
]

TECH_TERMS = [
    "AI",
    "artificial intelligence",
    "machine learning",
    "large language model",
    "LLM",
    "robotics",
    "semiconductor",
    "chip",
    "GPU",
    "data center",
    "cloud",
    "cybersecurity",
    "ransomware",
    "electric vehicle",
    "robotaxi",
    "startup",
    "funding",
    "search",
    "social media",
    "privacy",
    "open source",
    "developer tools",
    "quantum",
    "blockchain",
]

STOP_ENTITIES = {
    "The",
    "A",
    "An",
    "This",
    "That",
    "These",
    "Those",
    "YouTube",
    "Video",
    "Short",
    "Technology",
    "Did",
    "Here",
    "Follow",
    "Watch",
    "But",
    "It",
    "Like",
    "Will",
    "Why",
    "Your",
}

NOISY_HEADLINE_WORDS = {"affect", "like", "not", "will", "why", "your"}
PRODUCT_PREFIXES = (
    "GPT",
    "iPhone",
    "Galaxy",
    "Pixel",
    "Windows",
    "Xbox",
    "PlayStation",
    "Switch",
    "Claude",
    "Gemini",
    "Llama",
    "Mistral",
    "Sora",
    "Optimus",
    "Ryzen",
    "GeForce",
    "RTX",
    "H100",
    "B200",
)


class StoryContext(BaseModel):
    """Semantic context used by script, visual, and quality stages."""

    story_summary: str
    entities: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    events: List[str] = Field(default_factory=list)
    timeline: List[str] = Field(default_factory=list)
    statistics: List[str] = Field(default_factory=list)
    key_talking_points: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)
    source_names: List[str] = Field(default_factory=list)
    search_focus: List[str] = Field(default_factory=list)

    def compact_context(self) -> str:
        """Returns a short, prompt-friendly context block."""
        parts = [
            f"Summary: {self.story_summary}",
            f"Entities: {', '.join(self.entities[:8]) or 'none'}",
            f"Companies: {', '.join(self.companies[:6]) or 'none'}",
            f"Products: {', '.join(self.products[:6]) or 'none'}",
            f"Technologies: {', '.join(self.technologies[:6]) or 'none'}",
            f"Key points: {'; '.join(self.key_talking_points[:5]) or 'none'}",
        ]
        return "\n".join(parts)


def build_story_context(item: TrendItem, use_llm: bool = True) -> StoryContext:
    """Builds semantic story context with deterministic fallback enrichment."""
    fallback = _build_rule_based_context(item)

    if not use_llm:
        return fallback

    prompt = f"""
Analyze this technology news item before video production.

Topic: {item.topic}
Summary: {_clean_text(item.summary)}
Sources: {", ".join(fallback.source_urls[:5])}

Return JSON with these keys:
- story_summary: concise factual summary
- entities: named people, organizations, countries, and concepts
- companies: company or organization names
- products: product, model, app, or service names
- technologies: relevant technologies
- events: concrete actions or developments
- timeline: dates, years, or sequence markers if present
- statistics: numbers, money, percentages, quantities if present
- key_talking_points: 4-6 points the video should cover
- search_focus: specific terms that should guide visual search

Rules:
1. Prefer concrete names over broad categories.
2. Do not invent facts that are not in the topic or summary.
3. Keep each list item short.
"""

    result = llm_client.generate_json(prompt)
    if not isinstance(result, dict):
        logger.warning("Story understanding LLM failed; using rule-based context.")
        return fallback

    try:
        llm_context = StoryContext(
            story_summary=_as_string(result.get("story_summary")) or fallback.story_summary,
            entities=_as_list(result.get("entities")),
            companies=_as_list(result.get("companies")),
            products=_as_list(result.get("products")),
            technologies=_as_list(result.get("technologies")),
            events=_as_list(result.get("events")),
            timeline=_as_list(result.get("timeline")),
            statistics=_as_list(result.get("statistics")),
            key_talking_points=_as_list(result.get("key_talking_points")),
            source_urls=fallback.source_urls,
            source_names=fallback.source_names,
            search_focus=_as_list(result.get("search_focus")),
        )
        return _merge_contexts(llm_context, fallback)
    except Exception as exc:
        logger.error(f"Failed to parse story context JSON: {exc}")
        return fallback


def _build_rule_based_context(item: TrendItem) -> StoryContext:
    text = _clean_text(f"{item.topic}. {item.summary}")
    sentences = _split_sentences(text)
    companies = _known_matches(text, TECH_COMPANIES)
    technologies = _known_matches(text, TECH_TERMS)
    products = _extract_products(text)
    named_entities = _extract_named_entities(text)
    statistics = _extract_statistics(text)
    timeline = _extract_timeline(text)
    events = _extract_events(sentences)

    entities = _unique([*companies, *products, *named_entities, *technologies])
    talking_points = _unique([item.topic, *sentences[:4]])
    summary = item.summary if item.summary else item.topic

    source_urls = [source.url for source in item.sources if source.url]
    source_names = [source.name for source in item.sources if source.name]

    search_focus = _unique([
        *companies,
        *products,
        *technologies,
        *entities[:4],
        item.topic,
    ])[:10]

    return StoryContext(
        story_summary=_clean_text(summary),
        entities=entities[:12],
        companies=companies[:8],
        products=products[:8],
        technologies=technologies[:8],
        events=events[:6],
        timeline=timeline[:6],
        statistics=statistics[:8],
        key_talking_points=talking_points[:6],
        source_urls=source_urls,
        source_names=source_names,
        search_focus=search_focus,
    )


def _merge_contexts(primary: StoryContext, fallback: StoryContext) -> StoryContext:
    return StoryContext(
        story_summary=primary.story_summary or fallback.story_summary,
        entities=_unique([*primary.entities, *fallback.entities])[:12],
        companies=_unique([*primary.companies, *fallback.companies])[:8],
        products=_unique([*primary.products, *fallback.products])[:8],
        technologies=_unique([*primary.technologies, *fallback.technologies])[:8],
        events=_unique([*primary.events, *fallback.events])[:8],
        timeline=_unique([*primary.timeline, *fallback.timeline])[:8],
        statistics=_unique([*primary.statistics, *fallback.statistics])[:10],
        key_talking_points=_unique([*primary.key_talking_points, *fallback.key_talking_points])[:8],
        source_urls=fallback.source_urls,
        source_names=fallback.source_names,
        search_focus=_unique([*primary.search_focus, *fallback.search_focus])[:12],
    )


def _clean_text(value: Optional[str]) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence.strip()
    ]


def _known_matches(text: str, terms: Iterable[str]) -> List[str]:
    matches = []
    for term in terms:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            matches.append(term)
    return _unique(matches)


def _extract_named_entities(text: str) -> List[str]:
    pattern = r"\b(?:[A-Z][A-Za-z0-9&.'-]+)(?:\s+(?:[A-Z][A-Za-z0-9&.'-]+|of|and|the|for|in|on)){0,4}"
    candidates = re.findall(pattern, text)
    cleaned = []
    for candidate in candidates:
        normalized = candidate.strip(" .,:;!?")
        normalized = re.sub(r"\s+(?:of|and|the|for|in|on)$", "", normalized, flags=re.IGNORECASE)
        if not normalized or normalized in STOP_ENTITIES:
            continue
        words = {word.lower() for word in re.findall(r"[A-Za-z]+", normalized)}
        if words.intersection(NOISY_HEADLINE_WORDS):
            continue
        if len(normalized) < 3:
            continue
        if normalized.lower() in {"did", "new", "top", "best"}:
            continue
        cleaned.append(normalized)
    return _unique(cleaned)


def _extract_products(text: str) -> List[str]:
    patterns = [
        r"\bGPT[- ]?\d(?:\.\d)?\b",
        r"\b[A-Z][A-Za-z]+ ?\d{1,3}(?:\s?(?:Pro|Ultra|Max|Mini|Plus))?\b",
        r"\b[A-Z][A-Za-z]+(?:AI|GPT|OS|Cloud|Studio|Drive|Search)\b",
    ]
    products = []
    for pattern in patterns:
        products.extend(re.findall(pattern, text))
    filtered = []
    for product in products:
        if any(product.startswith(prefix) for prefix in PRODUCT_PREFIXES):
            filtered.append(product)
    return _unique(filtered)


def _extract_statistics(text: str) -> List[str]:
    pattern = r"(?:\$?\d+(?:\.\d+)?\s?(?:%|percent|million|billion|trillion|users|people|years|months|days|hours|x|times|B|M|K)?)"
    values = []
    for match in re.findall(pattern, text, flags=re.IGNORECASE):
        cleaned = match.strip()
        if cleaned.isdigit() and len(cleaned) < 4:
            continue
        values.append(cleaned)
    return _unique(values)


def _extract_timeline(text: str) -> List[str]:
    date_patterns = [
        r"\b20\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b",
        r"\b(?:today|yesterday|tomorrow|this week|next week|last week)\b",
    ]
    values = []
    for pattern in date_patterns:
        values.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return _unique(values)


def _extract_events(sentences: List[str]) -> List[str]:
    event_terms = (
        "launch",
        "release",
        "unveil",
        "raise",
        "fund",
        "acquire",
        "merge",
        "announce",
        "ban",
        "sue",
        "investigate",
        "build",
        "expand",
        "ship",
        "test",
        "plead",
    )
    events = [
        sentence
        for sentence in sentences
        if any(term in sentence.lower() for term in event_terms)
    ]
    return events or sentences[:2]


def _as_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value).strip()


def _as_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _unique(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, str):
        if "\n" in value:
            return _unique(part.strip(" -") for part in value.splitlines() if part.strip(" -"))
        if "," in value:
            return _unique(part.strip() for part in value.split(",") if part.strip())
        return [value.strip()] if value.strip() else []
    return [str(value).strip()]


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        cleaned = _clean_text(str(value)).strip(" -")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output
