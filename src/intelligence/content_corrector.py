import math
import re
from typing import Iterable, List, Optional

from src.core.config import settings
from src.core.llm_client import llm_client
from src.core.logger import logger
from src.intelligence.research import ResearchBrief
from src.intelligence.scriptwriter import VideoScript
from src.intelligence.story_understanding import StoryContext


WORDS_PER_SECOND = 2.35
MIN_SHORT_WORDS = 70


def correct_script_content(
    topic: str,
    script: VideoScript,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    video_type: str = "short",
    tone: str = "informative",
    min_runtime_seconds: Optional[int] = None,
) -> VideoScript:
    """
    Polishes narration before TTS so the final audio has a clear message and no URLs.

    The local LLM does not browse by itself. The app fetches internet sources in
    ResearchBrief, then gives those facts to the local model for correction.
    """
    min_runtime = min_runtime_seconds or settings.SCRIPT_MIN_RUNTIME_SECONDS
    cleaned = _sanitize_narration(script.script_text)
    needs_rewrite = _needs_rewrite(cleaned, min_runtime, video_type)

    if settings.CONTENT_CORRECTOR_USE_LLM:
        llm_script = _rewrite_with_local_llm(
            topic=topic,
            current_script=cleaned,
            story_context=story_context,
            research_brief=research_brief,
            video_type=video_type,
            tone=tone,
            min_runtime_seconds=min_runtime,
        )
        if llm_script and not _needs_rewrite(llm_script, min_runtime, video_type):
            cleaned = llm_script
            needs_rewrite = False
        elif llm_script:
            logger.warning("Content corrector LLM output still failed checks; using deterministic correction.")

    if needs_rewrite:
        cleaned = _build_message_first_script(topic, story_context, research_brief, video_type, min_runtime)

    cleaned = _sanitize_narration(cleaned)
    if _needs_rewrite(cleaned, min_runtime, video_type, allow_message_repair=False):
        cleaned = _build_message_first_script(topic, story_context, research_brief, video_type, min_runtime)
        cleaned = _sanitize_narration(cleaned)

    corrected = VideoScript(
        script_text=cleaned,
        estimated_runtime=max(script.estimated_runtime, _estimated_runtime(cleaned), min_runtime),
        source_facts=_clean_facts(script.source_facts or _fact_pool(topic, story_context, research_brief))[:6],
    )
    logger.info(
        f"Content corrected: runtime={corrected.estimated_runtime}s, "
        f"words={_word_count(corrected.script_text)}, "
        f"message_score={_message_score(corrected.script_text)}, "
        f"url_free={not _contains_url(corrected.script_text)}"
    )
    return corrected


def _rewrite_with_local_llm(
    topic: str,
    current_script: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    video_type: str,
    tone: str,
    min_runtime_seconds: int,
) -> Optional[str]:
    facts = "\n".join(f"- {fact}" for fact in _fact_pool(topic, story_context, research_brief)[:8])
    context = story_context.compact_context() if story_context else "No story context available."
    prompt = f"""
You are the final content corrector for a vertical technology news video.

Topic:
{topic}

Story context:
{context}

Internet research facts already fetched by the app:
{facts or '- No facts available.'}

Current narration:
{current_script}

Rewrite the narration for a {video_type} video in a {tone} tone.

Hard rules:
1. Return clean narration only in JSON. No markdown.
2. Do not include or read URLs, domains, source links, "https", "www", or file names.
3. Do not say "source coverage", "sources checked", "according to the URL", or "read this link".
4. Give the video a real message: hook, what happened, why it matters, who is affected, what to watch next.
5. Use only the provided facts and story context. Do not invent numbers, names, dates, or claims.
6. Keep it at least {min_runtime_seconds} seconds and usually 70-105 words for a short.
7. Make every sentence sound natural when spoken by TTS.

Output JSON:
{{
  "corrected_script_text": "clean narration only",
  "estimated_runtime": 30,
  "core_message": "one sentence takeaway"
}}
"""
    result = llm_client.generate_json(prompt)
    if not isinstance(result, dict):
        return None
    text = (
        result.get("corrected_script_text")
        or result.get("script_text")
        or result.get("narration")
        or ""
    )
    return _sanitize_narration(str(text))


def _build_message_first_script(
    topic: str,
    story_context: Optional[StoryContext],
    research_brief: Optional[ResearchBrief],
    video_type: str,
    min_runtime_seconds: int,
) -> str:
    facts = _fact_pool(topic, story_context, research_brief)
    stats = _clean_facts([
        *(research_brief.statistics if research_brief else []),
        *(story_context.statistics if story_context else []),
    ])
    message = _derive_core_message(topic, story_context, facts)
    anchor = _best_anchor(topic, story_context)

    sentences = [
        _sentence(f"Here is the real story: {topic} is not just another tech headline"),
        _sentence(f"The message is {message}"),
    ]

    for fact in facts[:2]:
        if fact.lower() not in " ".join(sentences).lower():
            sentences.append(_sentence(fact))

    if stats:
        sentences.append(_sentence(f"The number to watch is {stats[0]}, because scale changes how this story plays out"))

    if anchor:
        sentences.append(
            _sentence(
                f"For {anchor}, the pressure is to turn the announcement into something people can actually trust"
            )
        )

    sentences.extend([
        _sentence("That is why this matters: the real test is usefulness, availability, and trust"),
        _sentence("Watch what happens next, because the follow-up decisions will show whether this becomes a real shift or just another headline cycle"),
    ])

    script = " ".join(sentences)
    target_words = _minimum_word_count(min_runtime_seconds, video_type)
    while _word_count(script) < target_words:
        script += " " + _sentence(
            "The takeaway is simple: pay attention to the practical impact, not only the announcement"
        )
        if _word_count(script) >= target_words or _word_count(script) > 115:
            break
    return script


def _needs_rewrite(
    text: str,
    min_runtime_seconds: int,
    video_type: str,
    allow_message_repair: bool = True,
) -> bool:
    if not text:
        logger.warning("Content corrector found empty narration.")
        return True
    if _contains_url(text):
        logger.warning("Content corrector found URL/domain text in narration.")
        return True
    if _has_source_reader_language(text):
        logger.warning("Content corrector found source-reader language in narration.")
        return True
    if _word_count(text) < _minimum_word_count(min_runtime_seconds, video_type):
        logger.warning("Content corrector found narration below minimum word count.")
        return True
    if _estimated_runtime(text) < min_runtime_seconds:
        logger.warning("Content corrector found narration below minimum runtime.")
        return True
    if allow_message_repair and not _has_explicit_takeaway(text):
        logger.warning("Content corrector found narration without an explicit takeaway/message.")
        return True
    if allow_message_repair and _message_score(text) < 2:
        logger.warning("Content corrector found narration without a clear message.")
        return True
    return False


def _sanitize_narration(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"\[[A-Z0-9\s_-]+\]", " ", text)
    text = re.sub(r"(?im)^\s*(?:hook|context|content|impact|cta|narrator|voiceover|source)\s*:\s*", "", text)
    text = re.sub(r"https?://\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwww\.\S+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\S+\.(?:com|org|net|io|ai|co|dev|html|xml|rss)\S*\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:Source coverage from|Sources checked|according to the URL|read this link)\b[: ]*", " ", text, flags=re.IGNORECASE)
    text = text.replace("�", "'")
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _contains_url(text: str) -> bool:
    return bool(
        re.search(
            r"https?://|www\.|\b\S+\.(?:com|org|net|io|ai|co|dev|html|xml|rss)\b",
            text or "",
            flags=re.IGNORECASE,
        )
    )


def _has_source_reader_language(text: str) -> bool:
    lowered = (text or "").lower()
    markers = [
        "source coverage from",
        "sources checked",
        "according to the url",
        "read this link",
        "open the link",
        "visit the website",
    ]
    return any(marker in lowered for marker in markers)


def _message_score(text: str) -> int:
    lowered = (text or "").lower()
    score = 0
    if any(term in lowered for term in ("why this matters", "why it matters", "the message is", "the takeaway")):
        score += 1
    if any(term in lowered for term in ("users", "developers", "regulators", "investors", "customers", "companies")):
        score += 1
    if any(term in lowered for term in ("watch", "next", "pressure", "risk", "impact", "trust", "available")):
        score += 1
    return score


def _has_explicit_takeaway(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        phrase in lowered
        for phrase in (
            "the message is",
            "the takeaway is",
            "why this matters",
            "why it matters",
        )
    )


def _derive_core_message(
    topic: str,
    story_context: Optional[StoryContext],
    facts: List[str],
) -> str:
    text = " ".join([topic, *(facts[:4]), story_context.story_summary if story_context else ""]).lower()
    if any(term in text for term in ("europe", "eu", "regulation", "regulator", "available")):
        return "AI product launches are becoming policy stories, because regulation can decide who gets new features first"
    if any(term in text for term in ("ipo", "stock", "share", "investor", "valuation")):
        return "the market story matters only if the business behind it can prove durable demand"
    if any(term in text for term in ("privacy", "data", "personalize", "tracking")):
        return "the trade-off is convenience versus control over personal data"
    if any(term in text for term in ("cybersecurity", "hack", "ransomware", "breach")):
        return "the real issue is whether defenses can move as fast as attackers"
    if any(term in text for term in ("ai", "agent", "model", "siri", "gpt", "claude", "gemini")):
        return "AI is moving from demos into products, and the hard part is making it reliable in real life"
    if any(term in text for term in ("launch", "release", "unveil", "upgrade")):
        return "a launch only matters if it changes what people can actually do"
    return "the headline matters because it can change decisions for users, builders, and the market"


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
    return _clean_facts(facts)


def _clean_facts(values: Iterable[str]) -> List[str]:
    output = []
    seen = set()
    for value in values:
        cleaned = _sanitize_narration(str(value or "")).strip(" -")
        if not cleaned:
            continue
        key = re.sub(r"\W+", "", cleaned.lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _best_anchor(topic: str, story_context: Optional[StoryContext]) -> str:
    if not story_context:
        return ""
    lowered_topic = topic.lower()
    for bucket in (
        story_context.companies,
        story_context.products,
        story_context.technologies,
        story_context.people,
    ):
        for value in bucket:
            if value and value.lower() in lowered_topic:
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


def _sentence(text: str) -> str:
    text = _sanitize_narration(text).strip(" ,;")
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def _minimum_word_count(min_runtime_seconds: int, video_type: str) -> int:
    base = math.ceil(min_runtime_seconds * 2.6)
    if video_type == "short":
        return max(base, MIN_SHORT_WORDS)
    return base


def _estimated_runtime(text: str) -> int:
    return max(1, math.ceil(_word_count(text) / WORDS_PER_SECOND))


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text or ""))
