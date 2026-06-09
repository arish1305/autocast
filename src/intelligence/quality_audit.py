import re
from statistics import mean
from typing import List, Optional

from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logger import logger
from src.intelligence.scriptwriter import VideoScript
from src.intelligence.story_understanding import StoryContext
from src.media.asset_manager import VisualScene


class QualityReport(BaseModel):
    scene_relevance_score: float
    visual_quality_score: float
    narration_quality_score: float
    retention_score: float
    thumbnail_score: float
    transition_quality_score: float
    story_coherence_score: float
    overall_score: float
    approved: bool
    issues: List[str] = Field(default_factory=list)


def audit_video_plan(
    story_context: StoryContext,
    script: VideoScript,
    scenes: List[VisualScene],
    thumbnail_path: Optional[str] = None,
) -> QualityReport:
    """Runs a pre-render quality audit on the generated video plan."""
    issues = []

    scene_relevance = _scene_relevance(story_context, scenes)
    visual_quality = _visual_quality(scenes)
    narration_quality = _narration_quality(script.script_text)
    retention = _retention_score(script.script_text, scenes)
    thumbnail = 88.0 if thumbnail_path else 60.0
    transition_quality = _transition_quality(scenes)
    story_coherence = _story_coherence(story_context, script.script_text, scenes)

    if scene_relevance < 90:
        issues.append("Some scenes do not strongly overlap with story entities or keywords.")
    if visual_quality < 85:
        issues.append("Some visuals are low-quality or only fallback graphics.")
    if narration_quality < 90:
        issues.append("Narration has long sentences or leftover script labels.")
    if retention < 80:
        issues.append("Hook/pacing could be stronger for short-form retention.")
    if script.estimated_runtime < settings.SCRIPT_MIN_RUNTIME_SECONDS:
        issues.append(
            f"Script is shorter than the minimum {settings.SCRIPT_MIN_RUNTIME_SECONDS}s runtime."
        )
    artifact_free = not _has_forbidden_narration_artifacts(script.script_text)
    if not artifact_free:
        issues.append("Narration contains URLs, domains, or source-reader language.")
    if thumbnail < 85:
        issues.append("Thumbnail was not generated before audit.")
    if transition_quality < 80:
        issues.append("Scene transitions need more visual variety.")
    if story_coherence < 90:
        issues.append("Script/scenes do not fully preserve the core story context.")

    overall = round(
        (scene_relevance * 0.25)
        + (visual_quality * 0.22)
        + (narration_quality * 0.18)
        + (retention * 0.12)
        + (thumbnail * 0.1)
        + (transition_quality * 0.05)
        + (story_coherence * 0.08),
        2,
    )

    report = QualityReport(
        scene_relevance_score=round(scene_relevance, 2),
        visual_quality_score=round(visual_quality, 2),
        narration_quality_score=round(narration_quality, 2),
        retention_score=round(retention, 2),
        thumbnail_score=round(thumbnail, 2),
        transition_quality_score=round(transition_quality, 2),
        story_coherence_score=round(story_coherence, 2),
        overall_score=overall,
        approved=(
            overall >= 85
            and scene_relevance >= 86
            and visual_quality >= 82
            and script.estimated_runtime >= settings.SCRIPT_MIN_RUNTIME_SECONDS
            and artifact_free
        ),
        issues=issues,
    )

    logger.info(
        "Quality audit: "
        f"overall={report.overall_score}, relevance={report.scene_relevance_score}, "
        f"visual={report.visual_quality_score}, narration={report.narration_quality_score}, "
        f"retention={report.retention_score}, transitions={report.transition_quality_score}, "
        f"coherence={report.story_coherence_score}, approved={report.approved}"
    )
    for issue in report.issues:
        logger.warning(f"Quality audit issue: {issue}")
    return report


def _scene_relevance(story_context: StoryContext, scenes: List[VisualScene]) -> float:
    if not scenes:
        return 0.0

    context_terms = _terms([
        *story_context.entities,
        *story_context.companies,
        *story_context.products,
        *story_context.technologies,
        *story_context.search_focus,
    ])

    scores = []
    for scene in scenes:
        scene_terms = _terms([scene.segment_text, *scene.keywords, *scene.entities, scene.visual_requirement])
        overlap = len(context_terms.intersection(scene_terms))
        base = 70.0 + min(overlap * 4.0, 20.0)
        if scene.final_score:
            base = max(base, scene.final_score * 100)
        scores.append(min(base, 98.0))
    return mean(scores)


def _visual_quality(scenes: List[VisualScene]) -> float:
    if not scenes:
        return 0.0
    scores = []
    for scene in scenes:
        quality = scene.quality_score * 100 if scene.quality_score else 70.0
        relevance = scene.relevance_score * 100 if scene.relevance_score else 70.0
        if not scene.asset_path:
            quality -= 25
        if scene.asset_source == "generated-context":
            quality = max(quality, 86.0)
            relevance = max(relevance, 92.0)
        scores.append((quality * 0.55) + (relevance * 0.45))
    return mean(scores)


def _narration_quality(script_text: str) -> float:
    cleaned = re.sub(r"\[[A-Z\s_-]+\]", " ", script_text or "")
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    if not sentences:
        return 50.0
    avg_words = mean(len(sentence.split()) for sentence in sentences)
    long_sentence_penalty = max(avg_words - 20, 0) * 1.2
    artifact_penalty = 28.0 if _has_forbidden_narration_artifacts(script_text) else 0.0
    return max(50.0, min(96.0, 96.0 - long_sentence_penalty - artifact_penalty))


def _retention_score(script_text: str, scenes: List[VisualScene]) -> float:
    cleaned = re.sub(r"\s+", " ", script_text or "").strip()
    first_words = cleaned.split()[:24]
    hook = " ".join(first_words).lower()
    hook_bonus = 10 if any(term in hook for term in ("why", "just", "new", "changed", "matters", "billion", "risk")) else 2
    scene_bonus = min(len(scenes) * 3, 18)
    pacing_bonus = 10 if 4 <= len(scenes) <= 8 else 4
    return min(96.0, 62.0 + hook_bonus + scene_bonus + pacing_bonus)


def _transition_quality(scenes: List[VisualScene]) -> float:
    if not scenes:
        return 0.0
    transitions = [scene.transition_type for scene in scenes if scene.transition_type]
    diversity = len(set(transitions)) / max(len(transitions), 1)
    has_motion = sum(1 for scene in scenes if scene.transition_type in {"crossfade", "push", "zoom", "headline"})
    return min(96.0, 76.0 + diversity * 10.0 + min(has_motion * 3.0, 10.0))


def _story_coherence(story_context: StoryContext, script_text: str, scenes: List[VisualScene]) -> float:
    important_terms = _terms([
        *story_context.companies,
        *story_context.products,
        *story_context.technologies,
        *story_context.people,
        *story_context.locations,
        story_context.main_story_angle,
    ])
    if not important_terms:
        return 88.0
    produced_terms = _terms([script_text, *[scene.segment_text for scene in scenes], *[scene.visual_requirement for scene in scenes]])
    coverage = len(important_terms.intersection(produced_terms)) / max(len(important_terms), 1)
    return min(96.0, 72.0 + coverage * 24.0)


def _has_forbidden_narration_artifacts(script_text: str) -> bool:
    text = script_text or ""
    if re.search(r"https?://|www\.|\b\S+\.(?:com|org|net|io|ai|co|dev|html|xml|rss)\b", text, flags=re.IGNORECASE):
        return True
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "source coverage from",
            "sources checked",
            "according to the url",
            "read this link",
            "visit the website",
        )
    )


def _terms(values: List[str]) -> set:
    text = " ".join(str(value) for value in values if value)
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", text)
        if len(token) > 3
    }
