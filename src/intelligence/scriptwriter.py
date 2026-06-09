import math
import re
from typing import Iterable, List, Optional

from pydantic import BaseModel, Field, field_validator

from src.core.config import settings
from src.core.llm_client import llm_client
from src.core.logger import logger
from src.intelligence.research import ResearchBrief
from src.intelligence.story_understanding import StoryContext

from .prompts.script_prompts import get_script_prompt


WORDS_PER_SECOND = 2.35
MIN_SHORT_WORDS = 70


class VideoScript(BaseModel):
    script_text: str
    estimated_runtime: int
    source_facts: List[str] = Field(default_factory=list)

    @field_validator('script_text', mode='before')
    def parse_script_text(cls, v):
        if isinstance(v, list):
            v = " ".join(v)
        return _clean_script_text(str(v or ""))

def generate_script(
    topic: str,
    video_type: str,
    tone: str,
    beats: List[str],
    story_context: Optional[StoryContext] = None,
    research_brief: Optional[ResearchBrief] = None,
    min_runtime_seconds: Optional[int] = None,
) -> Optional[VideoScript]:
    """Generates a video script based on the strategy beats using LLM."""
    logger.info(f"Generating {video_type} script for: {topic}")

    min_runtime = min_runtime_seconds or settings.SCRIPT_MIN_RUNTIME_SECONDS
    context_block = story_context.compact_context() if story_context else ""
    research_block = research_brief.compact_context() if research_brief else ""
    prompt = get_script_prompt(
        topic,
        video_type,
        tone,
        beats,
        context_block,
        research_block,
        min_runtime,
    )
    result = llm_client.generate_json(prompt)

    script = None
    if result:
        try:
            script = VideoScript(**result)
        except Exception as e:
            logger.error(f"Failed to parse script JSON: {e}")
            script = None

    if script and not _script_needs_rewrite(script, topic, story_context, research_brief, min_runtime, video_type):
        return _finalize_script(script, topic, story_context, research_brief, min_runtime)

    if script:
        logger.warning(
            "LLM script was too short or low-information; rebuilding a source-backed narration."
        )
    else:
        logger.warning("Using source-backed fallback script generation.")

    fallback = _build_data_rich_script(
        topic=topic,
        video_type=video_type,
        story_context=story_context,
        research_brief=research_brief,
        min_runtime_seconds=min_runtime,
    )
    return _finalize_script(fallback, topic, story_context, research_brief, min_runtime)


def _script_needs_rewrite(
    script: VideoScript,
    topic: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    min_runtime_seconds: int,
    video_type: str,
) -> bool:
    text = script.script_text or ""
    word_count = _word_count(text)
    minimum_words = _minimum_word_count(min_runtime_seconds, video_type)
    if word_count < minimum_words:
        logger.warning(
            f"Script too short: {word_count} words, need at least {minimum_words}."
        )
        return True
    if script.estimated_runtime < min_runtime_seconds and _estimated_runtime(text) < min_runtime_seconds:
        logger.warning(
            f"Script runtime too short: {script.estimated_runtime}s, "
            f"need at least {min_runtime_seconds}s."
        )
        return True
    if _is_generic_script(text):
        logger.warning("Script uses generic filler language.")
        return True
    if research_brief and research_brief.verified_facts:
        if _information_score(text, story_context, research_brief) < 2:
            logger.warning("Script does not include enough source-backed facts.")
            return True
    return False


def _build_data_rich_script(
    topic: str,
    video_type: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    min_runtime_seconds: int,
) -> VideoScript:
    facts = _fact_pool(topic, story_context, research_brief)
    stats = _unique([
        *(research_brief.statistics if research_brief else []),
        *(story_context.statistics if story_context else []),
    ])
    angle = _safe_fragment(story_context.main_story_angle if story_context else "")
    anchor = _best_anchor(topic, story_context)

    sentences = [
        _ensure_sentence(
            f"{topic} matters because it points to {angle or 'a real shift in the tech market'}"
        )
    ]

    if facts:
        sentences.append(_ensure_sentence(f"The core update is this: {facts[0]}"))

    for fact in facts[1:4]:
        sentences.append(_ensure_sentence(fact))

    if stats:
        sentences.append(
            _ensure_sentence(f"The key number to watch is {stats[0]}, because it shows the scale of the story")
        )

    if anchor:
        sentences.append(
            _ensure_sentence(
                f"For viewers, the important question is how {anchor} turns this update into a product, policy, or market move"
            )
        )
    else:
        sentences.append(
            "For viewers, the important question is whether this changes what people can actually use, buy, or build."
        )

    sentences.append(
        "Follow the next update, because the first reaction is usually loud, but the second wave shows the real impact."
    )

    target_words = _minimum_word_count(min_runtime_seconds, video_type)
    script_text = " ".join(sentences)
    remaining_facts = facts[4:]
    while _word_count(script_text) < target_words and remaining_facts:
        script_text += " " + _ensure_sentence(remaining_facts.pop(0))

    if _word_count(script_text) < target_words:
        script_text += " " + _ensure_sentence(
            f"The takeaway is simple: {topic} is worth tracking because the details affect users, builders, investors, and the companies trying to lead this market"
        )

    if video_type == "short" and _word_count(script_text) < MIN_SHORT_WORDS:
        script_text += " " + _ensure_sentence(
            "That is what makes this more than a headline: it connects the announcement to real decisions people will make next"
        )

    return VideoScript(
        script_text=script_text,
        estimated_runtime=_estimated_runtime(script_text),
        source_facts=facts[:6],
    )


def _finalize_script(
    script: VideoScript,
    topic: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    min_runtime_seconds: int,
) -> VideoScript:
    cleaned_text = _clean_script_text(script.script_text)
    facts = script.source_facts or _fact_pool(topic, story_context, research_brief)[:6]
    runtime = max(int(script.estimated_runtime or 0), _estimated_runtime(cleaned_text), min_runtime_seconds)
    finalized = VideoScript(
        script_text=cleaned_text,
        estimated_runtime=runtime,
        source_facts=facts,
    )
    logger.info(
        f"Script finalized: runtime={finalized.estimated_runtime}s, "
        f"words={_word_count(finalized.script_text)}, facts={len(finalized.source_facts)}"
    )
    return finalized


def _fact_pool(
    topic: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
) -> List[str]:
    facts = []
    if research_brief:
        facts.extend(research_brief.verified_facts)
    if story_context:
        facts.extend([
            story_context.story_summary,
            *story_context.key_talking_points,
            *story_context.events,
        ])
    facts.append(topic)
    return [
        _clean_fact(fact)
        for fact in _unique(facts)
        if _clean_fact(fact)
    ]


def _information_score(
    text: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
) -> int:
    lowered = text.lower()
    score = 0
    if story_context:
        anchors = _unique([
            *story_context.companies,
            *story_context.products,
            *story_context.technologies,
            *story_context.people,
            *story_context.locations,
        ])
        score += min(sum(1 for anchor in anchors if anchor.lower() in lowered), 3)
    if research_brief:
        score += min(sum(1 for stat in research_brief.statistics if stat.lower() in lowered), 2)
        for fact in research_brief.verified_facts[:6]:
            fact_terms = _terms(fact)
            text_terms = _terms(text)
            if len(fact_terms.intersection(text_terms)) >= 4:
                score += 1
    return score


def _is_generic_script(text: str) -> bool:
    lowered = text.lower()
    generic_markers = [
        "could change what happens next in tech",
        "companies, products, and people involved",
        "shape the next wave of adoption",
        "watch how this affects users, developers, and the wider market",
    ]
    return any(marker in lowered for marker in generic_markers)


def _minimum_word_count(min_runtime_seconds: int, video_type: str) -> int:
    base = math.ceil(min_runtime_seconds * 2.6)
    if video_type == "short":
        return max(base, MIN_SHORT_WORDS)
    return base


def _estimated_runtime(text: str) -> int:
    return max(1, math.ceil(_word_count(text) / WORDS_PER_SECOND))


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _clean_script_text(text: str) -> str:
    text = re.sub(r"\[[A-Z0-9\s_-]+\]", " ", text or "")
    text = re.sub(r"(?im)^\s*(?:hook|context|content|impact|cta|narrator|voiceover)\s*:\s*", "", text)
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwww\.\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\S+\.(?:com|org|net|io|ai|co|dev|html|xml|rss)\S*\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_fact(text: str) -> str:
    text = _clean_script_text(str(text or ""))
    text = re.sub(r"^(?:The core update is this:|Source coverage .*? says)\s*", "", text, flags=re.IGNORECASE)
    return text.strip(" -")


def _best_anchor(topic: str, story_context: Optional[StoryContext]) -> str:
    if not story_context:
        return ""
    for bucket in (
        story_context.companies,
        story_context.products,
        story_context.technologies,
        story_context.people,
    ):
        for value in bucket:
            if value and value.lower() in topic.lower():
                return value
    for bucket in (
        story_context.companies,
        story_context.products,
        story_context.technologies,
        story_context.people,
    ):
        if bucket:
            return bucket[0]
    return ""


def _safe_fragment(text: str) -> str:
    text = _clean_script_text(text)
    return text[0].lower() + text[1:] if text else ""


def _ensure_sentence(text: str) -> str:
    text = _clean_script_text(text).strip(" ,;")
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def _human_join(values: List[str]) -> str:
    values = [value for value in values if value]
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return f"{values[0]} and {values[1]}"


def _terms(text: str) -> set:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9&.-]{2,}", text or "")
        if token.lower() not in {"the", "and", "for", "that", "with", "this", "from"}
    }


def _unique(values: Iterable[str]) -> List[str]:
    seen = set()
    output = []
    for value in values:
        cleaned = _clean_script_text(str(value or "")).strip()
        key = re.sub(r"\W+", "", cleaned.lower())
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output
