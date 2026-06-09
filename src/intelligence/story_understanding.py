import html
import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from src.core.llm_client import llm_client
from src.core.logger import logger
from src.core.models import TrendItem


TECH_COMPANIES = [
    "OpenAI", "Microsoft", "Google", "Alphabet", "Apple", "Meta", "Amazon",
    "AWS", "Nvidia", "AMD", "Intel", "Tesla", "SpaceX", "Anthropic",
    "Perplexity", "xAI", "Samsung", "Sony", "IBM", "Oracle", "Salesforce",
    "Adobe", "Qualcomm", "TSMC", "Arm", "ByteDance", "TikTok", "Reddit",
    "GitHub", "Hugging Face", "LinkedIn", "Box", "YouTube", "Nintendo",
]

TECH_TERMS = [
    "AI", "artificial intelligence", "machine learning", "large language model",
    "LLM", "AI agents", "robotics", "semiconductor", "chip", "GPU",
    "data center", "cloud", "cybersecurity", "ransomware", "electric vehicle",
    "robotaxi", "startup", "IPO", "funding", "search", "social media",
    "privacy", "open source", "developer tools", "quantum", "blockchain",
    "medical AI", "healthcare technology", "spatial computing",
]

PRODUCT_PREFIXES = (
    "GPT", "iPhone", "Galaxy", "Pixel", "Windows", "Xbox", "PlayStation",
    "Switch", "Claude", "Gemini", "Llama", "Mistral", "Sora", "Optimus",
    "Ryzen", "GeForce", "RTX", "H100", "B200", "Minecraft", "Halo",
)

INVALID_ENTITY_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "could",
    "did", "do", "does", "for", "from", "had", "has", "have", "he", "her",
    "here", "him", "his", "how", "i", "if", "imagine", "in", "inside", "is",
    "it", "its", "like", "new", "not", "of", "on", "or", "our", "she",
    "should", "that", "the", "their", "there", "these", "they", "this",
    "those", "to", "top", "video", "was", "watch", "we", "what", "when",
    "where", "who", "why", "will", "with", "would", "you", "your",
}

GENERIC_ENTITY_WORDS = {
    "technology", "innovation", "future", "news", "update", "story", "market",
    "business", "company", "companies", "product", "products", "users",
    "people", "system", "systems", "platform", "platforms", "tools",
}

SPACY_LABELS = {
    "ORG": "organizations",
    "PERSON": "people",
    "GPE": "locations",
    "LOC": "locations",
    "FAC": "locations",
    "PRODUCT": "products",
    "EVENT": "events",
}


class StoryContext(BaseModel):
    """Semantic context used by script, visual, and quality stages."""

    headline: str = ""
    story_summary: str
    main_story_angle: str = ""
    entities: List[str] = Field(default_factory=list)
    companies: List[str] = Field(default_factory=list)
    products: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    people: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
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
            f"Headline: {self.headline}",
            f"Summary: {self.story_summary}",
            f"Angle: {self.main_story_angle or 'none'}",
            f"Companies: {', '.join(self.companies[:6]) or 'none'}",
            f"Products: {', '.join(self.products[:6]) or 'none'}",
            f"Technologies: {', '.join(self.technologies[:6]) or 'none'}",
            f"People: {', '.join(self.people[:4]) or 'none'}",
            f"Locations: {', '.join(self.locations[:4]) or 'none'}",
            f"Statistics: {', '.join(self.statistics[:5]) or 'none'}",
            f"Key points: {'; '.join(self.key_talking_points[:5]) or 'none'}",
        ]
        return "\n".join(parts)


def build_story_context(item: TrendItem, use_llm: bool = True) -> StoryContext:
    """Builds semantic story context with deterministic fallback enrichment."""
    fallback = _build_rule_based_context(item)

    if not use_llm:
        return fallback

    prompt = f"""
You are the story-understanding analyst for AutoCast AI.
Before any script or visuals are generated, extract the real story structure from this technology news item.

INPUT
Headline:
{item.topic}

Summary:
{_clean_text(item.summary)}

Known source URLs:
{", ".join(fallback.source_urls[:5]) or "No source URLs available."}

TASK
Return a compact but useful semantic brief for video production. This is not a script.
The goal is to identify concrete entities, the central angle, and search terms that can guide scriptwriting,
visual planning, thumbnail design, and quality checks.

WHAT TO EXTRACT
- headline: cleaned headline, preserving the actual subject.
- summary: one accurate sentence summarizing the story.
- main_story_angle: one phrase explaining the practical meaning or tension.
- companies: real company names only.
- products: real product/model/service names only.
- organizations: agencies, standards bodies, universities, publishers, or institutions.
- technologies: technology categories explicitly present, such as AI, chips, cloud, cybersecurity.
- people: named people only.
- locations: real places or regions only.
- statistics: numbers with units exactly as present in the input.
- timelines: dates, years, "this week", launch windows, or schedule references exactly as present.
- key_points: 3-6 factual points that a viewer should understand.
- search_focus: 5-10 concrete visual/search anchors, such as company + product + region + technology.

STRICT RULES
1. Extract only meaningful named entities. Do not include sentence starters, pronouns, filler words, or generic words.
2. Do not invent facts, numbers, dates, people, or organizations that are not in the headline or summary.
3. Do not include full URLs in any field.
4. Prefer concrete visual subjects over abstract wording.
5. Keep each list item short. Avoid paragraph-length entities.
6. If a field has no evidence, return an empty array for that field.
7. The main_story_angle should be useful for a video, for example "AI feature delay in Europe" or "IPO market pressure".

Return only valid JSON with this exact shape:
{{
  "headline": "clean headline",
  "summary": "one accurate sentence",
  "main_story_angle": "practical story angle",
  "companies": [],
  "products": [],
  "organizations": [],
  "technologies": [],
  "people": [],
  "locations": [],
  "statistics": [],
  "timelines": [],
  "key_points": [],
  "search_focus": []
}}
"""

    result = llm_client.generate_json(prompt)
    if not isinstance(result, dict):
        logger.warning("Story understanding LLM failed; using rule-based context.")
        return fallback

    try:
        llm_context = StoryContext(
            headline=_as_string(result.get("headline")) or fallback.headline,
            story_summary=_as_string(result.get("summary")) or fallback.story_summary,
            main_story_angle=_as_string(result.get("main_story_angle")) or fallback.main_story_angle,
            companies=_sanitize_entities(_as_list(result.get("companies"))),
            products=_sanitize_entities(_as_list(result.get("products")), allow_products=True),
            organizations=_sanitize_entities(_as_list(result.get("organizations"))),
            technologies=_sanitize_entities(_as_list(result.get("technologies")), allow_tech=True),
            people=_sanitize_entities(_as_list(result.get("people"))),
            locations=_sanitize_entities(_as_list(result.get("locations"))),
            events=_sanitize_entities(_as_list(result.get("events"))),
            timeline=_as_list(result.get("timelines") or result.get("timeline")),
            statistics=_as_list(result.get("statistics")),
            key_talking_points=_as_list(result.get("key_points") or result.get("key_talking_points")),
            source_urls=fallback.source_urls,
            source_names=fallback.source_names,
            search_focus=_sanitize_entities(_as_list(result.get("search_focus")), allow_tech=True),
        )
        return _merge_contexts(llm_context, fallback)
    except Exception as exc:
        logger.error(f"Failed to parse story context JSON: {exc}")
        return fallback


def _build_rule_based_context(item: TrendItem) -> StoryContext:
    text = _clean_text(f"{item.topic}. {item.summary}")
    sentences = _split_sentences(text)
    spacy_entities = _extract_spacy_entities(text)

    companies = _unique([
        *_known_matches(text, TECH_COMPANIES),
        *[entity for entity in spacy_entities["organizations"] if _looks_like_company(entity)],
    ])
    products = _unique([
        product for product in [*_extract_products(text), *spacy_entities["products"]]
        if product not in companies
    ])
    technologies = _unique(_known_matches(text, TECH_TERMS))
    organizations = _unique([*companies, *spacy_entities["organizations"]])
    people = spacy_entities["people"]
    locations = spacy_entities["locations"]
    statistics = _extract_statistics(text)
    timeline = _extract_timeline(text)
    events = _unique([*spacy_entities["events"], *_extract_events(sentences)])
    regex_entities = _extract_named_entities(text)

    entities = _unique([
        *companies,
        *products,
        *organizations,
        *technologies,
        *people,
        *locations,
        *regex_entities,
    ])
    talking_points = _unique([item.topic, *sentences[:4]])
    source_urls = [source.url for source in item.sources if source.url]
    source_names = [source.name for source in item.sources if source.name]
    summary = _clean_text(item.summary if item.summary else item.topic)
    main_angle = _infer_main_angle(item.topic, summary, companies, products, technologies, statistics)

    search_focus = _unique([
        *companies,
        *products,
        *technologies,
        *people[:2],
        *locations[:2],
        main_angle,
    ])[:12]

    return StoryContext(
        headline=item.topic,
        story_summary=summary,
        main_story_angle=main_angle,
        entities=entities[:14],
        companies=companies[:8],
        products=products[:8],
        organizations=organizations[:8],
        technologies=technologies[:8],
        people=people[:6],
        locations=locations[:6],
        events=events[:6],
        timeline=timeline[:6],
        statistics=statistics[:8],
        key_talking_points=talking_points[:6],
        source_urls=source_urls,
        source_names=source_names,
        search_focus=search_focus,
    )


def _merge_contexts(primary: StoryContext, fallback: StoryContext) -> StoryContext:
    companies = _unique([*primary.companies, *fallback.companies])[:8]
    products = _unique([*primary.products, *fallback.products])[:8]
    organizations = _unique([*primary.organizations, *fallback.organizations, *companies])[:8]
    technologies = _unique([*primary.technologies, *fallback.technologies])[:8]
    people = _unique([*primary.people, *fallback.people])[:6]
    locations = _unique([*primary.locations, *fallback.locations])[:6]
    events = _unique([*primary.events, *fallback.events])[:8]

    return StoryContext(
        headline=primary.headline or fallback.headline,
        story_summary=primary.story_summary or fallback.story_summary,
        main_story_angle=primary.main_story_angle or fallback.main_story_angle,
        entities=_unique([
            *companies, *products, *organizations, *technologies,
            *people, *locations, *primary.entities, *fallback.entities,
        ])[:14],
        companies=companies,
        products=products,
        organizations=organizations,
        technologies=technologies,
        people=people,
        locations=locations,
        events=events,
        timeline=_unique([*primary.timeline, *fallback.timeline])[:8],
        statistics=_unique([*primary.statistics, *fallback.statistics])[:10],
        key_talking_points=_unique([*primary.key_talking_points, *fallback.key_talking_points])[:8],
        source_urls=fallback.source_urls,
        source_names=fallback.source_names,
        search_focus=_unique([*primary.search_focus, *fallback.search_focus])[:12],
    )


def _extract_spacy_entities(text: str) -> Dict[str, List[str]]:
    buckets = {name: [] for name in ["organizations", "people", "locations", "products", "events"]}
    nlp = _load_spacy_model()
    if not nlp:
        return buckets

    doc = nlp(text)
    for ent in doc.ents:
        bucket = SPACY_LABELS.get(ent.label_)
        if not bucket:
            continue
        value = _clean_entity(ent.text)
        if bucket == "locations" and value.lower() in {term.lower() for term in TECH_TERMS}:
            continue
        if bucket == "products" and value in TECH_COMPANIES:
            continue
        if _is_valid_entity(value, allow_products=bucket == "products"):
            buckets[bucket].append(value)
    return {key: _unique(values) for key, values in buckets.items()}


@lru_cache(maxsize=1)
def _load_spacy_model():
    try:
        import spacy

        return spacy.load("en_core_web_sm")
    except Exception as exc:
        logger.warning(
            "spaCy model en_core_web_sm is not available; using rule-based entity extraction. "
            "Install with: python -m spacy download en_core_web_sm. "
            f"Error: {exc}"
        )
        return None


def _extract_named_entities(text: str) -> List[str]:
    pattern = r"\b(?:[A-Z][A-Za-z0-9&.'-]+)(?:\s+(?:[A-Z][A-Za-z0-9&.'-]+|of|and|the|for|in|on)){0,3}"
    candidates = re.findall(pattern, text)
    return _sanitize_entities(candidates, allow_products=True, allow_tech=True)


def _extract_products(text: str) -> List[str]:
    patterns = [
        r"\bGPT[- ]?\d(?:\.\d)?\b",
        r"\b[A-Z][A-Za-z]+ ?\d{1,3}(?:\s?(?:Pro|Ultra|Max|Mini|Plus))?\b",
        r"\b[A-Z][A-Za-z]+(?:AI|GPT|OS|Cloud|Studio|Drive|Search)\b",
    ]
    products = []
    for pattern in patterns:
        products.extend(re.findall(pattern, text))
    return _sanitize_entities(products, allow_products=True)


def _sanitize_entities(values: Iterable[str], allow_products: bool = False, allow_tech: bool = False) -> List[str]:
    return _unique(
        value for value in (_clean_entity(item) for item in values)
        if _is_valid_entity(value, allow_products=allow_products, allow_tech=allow_tech)
    )


def _is_valid_entity(value: str, allow_products: bool = False, allow_tech: bool = False) -> bool:
    if not value:
        return False
    lowered = value.lower().strip()
    if re.search(r"[.!?]$", value):
        return False
    if lowered in INVALID_ENTITY_WORDS or lowered in GENERIC_ENTITY_WORDS:
        return False
    if lowered in {term.lower() for term in TECH_TERMS} and not allow_tech:
        return False
    if allow_products and value in TECH_COMPANIES:
        return False
    if re.fullmatch(r"\d{1,3}", value):
        return False
    if len(value) < 2:
        return False
    words = re.findall(r"[A-Za-z0-9]+", value)
    if not words:
        return False
    if len(words) > 4:
        return False
    if any(word.lower() in INVALID_ENTITY_WORDS for word in words):
        return False
    if any(word.lower() in {"announced", "released", "launches", "releases", "developers"} for word in words):
        return False
    if any(word.lower() in GENERIC_ENTITY_WORDS for word in words) and len(words) == 1:
        return False
    if allow_products and any(value.startswith(prefix) for prefix in PRODUCT_PREFIXES):
        return True
    if allow_tech and lowered in {term.lower() for term in TECH_TERMS}:
        return True
    if value in TECH_COMPANIES:
        return True
    if value.isupper() and len(value) >= 2:
        return True
    return bool(re.search(r"[A-Z]", value)) and len(value) >= 3


def _clean_entity(value: str) -> str:
    cleaned = _clean_text(value).strip(" .,:;!?\"'")
    cleaned = re.sub(r"\s+(?:of|and|the|for|in|on|with|to)$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _looks_like_company(value: str) -> bool:
    if value in TECH_COMPANIES:
        return True
    return bool(re.search(r"\b(?:Inc|Corp|Corporation|Labs|AI|Technologies|Systems|Group)\b", value))


def _infer_main_angle(
    headline: str,
    summary: str,
    companies: List[str],
    products: List[str],
    technologies: List[str],
    statistics: List[str],
) -> str:
    anchor = companies[0] if companies else products[0] if products else technologies[0] if technologies else ""
    text = f"{headline} {summary}".lower()
    if "ipo" in text:
        action = "market debut and investor impact"
    elif any(term in text for term in ("launch", "release", "unveil", "arrives")):
        action = "new product launch"
    elif any(term in text for term in ("sue", "lawsuit", "ban", "regulation", "order")):
        action = "regulatory or legal pressure"
    elif statistics:
        action = f"the key number {statistics[0]}"
    else:
        action = "why this technology story matters"
    return f"{anchor} {action}".strip() if anchor else action


def _clean_text(value: Optional[str]) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> List[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _known_matches(text: str, terms: Iterable[str]) -> List[str]:
    matches = []
    for term in terms:
        if re.search(r"\b" + re.escape(term) + r"\b", text, flags=re.IGNORECASE):
            matches.append(term)
    return _unique(matches)


def _extract_statistics(text: str) -> List[str]:
    pattern = r"\$?\d+(?:\.\d+)?\s?(?:%|percent|million|billion|trillion|users|people|years|months|days|hours|x|times|share|shares|B|M|K)"
    return _unique(re.findall(pattern, text, flags=re.IGNORECASE))


def _extract_timeline(text: str) -> List[str]:
    patterns = [
        r"\b20\d{2}\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}\b",
        r"\b(?:today|yesterday|tomorrow|this week|next week|last week)\b",
    ]
    values = []
    for pattern in patterns:
        values.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return _unique(values)


def _extract_events(sentences: List[str]) -> List[str]:
    event_terms = (
        "launch", "release", "unveil", "raise", "fund", "acquire", "merge",
        "announce", "ban", "sue", "investigate", "build", "expand", "ship",
        "test", "plead", "ipo", "files", "signs",
    )
    events = [sentence for sentence in sentences if any(term in sentence.lower() for term in event_terms)]
    return events[:4] or sentences[:2]


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
