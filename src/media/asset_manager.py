import os
import re
from typing import Dict, Iterable, List, Optional

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.llm_client import llm_client
from src.core.logger import logger
from src.intelligence.story_understanding import StoryContext
from src.media.pexels_client import pexels_client
from src.media.pixabay_client import pixabay_client


STOP_WORDS = {
    "about",
    "after",
    "against",
    "also",
    "because",
    "before",
    "being",
    "between",
    "could",
    "every",
    "first",
    "future",
    "follow",
    "important",
    "inside",
    "instead",
    "just",
    "like",
    "means",
    "might",
    "really",
    "should",
    "story",
    "subscribe",
    "that",
    "technology",
    "there",
    "these",
    "thing",
    "this",
    "those",
    "video",
    "where",
    "while",
    "with",
    "would",
}

ENTITY_STOP_WORDS = {
    "But",
    "Did",
    "Follow",
    "Here",
    "It",
    "That",
    "The",
    "This",
    "Watch",
}


class VisualScene(BaseModel):
    scene_id: int = 0
    segment_text: str
    duration: float = 8.0
    visual_requirement: str = ""
    keywords: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    asset_path: Optional[str] = None
    asset_type: str = "video"
    asset_source: Optional[str] = None
    selected_query: Optional[str] = None
    relevance_score: float = 0.0
    quality_score: float = 0.0
    final_score: float = 0.0
    caption_text: str = ""


def break_script_into_scenes(
    script_text: str,
    story_context: Optional[StoryContext] = None,
    target_duration: Optional[int] = None,
) -> List[VisualScene]:
    """Splits narration into visual scenes with concrete visual instructions."""
    logger.info("Breaking script into context-aware visual scenes...")

    scenes = _llm_scene_breakdown(script_text, story_context, target_duration)
    if len(scenes) < 3:
        scenes = _rule_based_scene_breakdown(script_text, story_context, target_duration)

    scenes = _normalize_scene_plan(scenes, story_context, target_duration)
    logger.info(f"Prepared {len(scenes)} visual scenes.")
    return scenes


def source_visual_assets(
    scenes: List[VisualScene],
    story_context: Optional[StoryContext] = None,
    min_score: float = 0.62,
) -> List[VisualScene]:
    """Sources, scores, and selects the best visual asset for every scene."""
    used_assets = set()

    for index, scene in enumerate(scenes):
        if not scene.search_queries:
            scene.search_queries = _build_search_queries(scene.segment_text, scene.keywords, scene.entities, story_context)

        logger.info(f"Sourcing visual for scene {scene.scene_id}: {scene.visual_requirement}")
        candidates = _collect_candidates(scene)
        candidates.sort(key=lambda item: item["final_score"], reverse=True)

        selected = None
        for candidate in candidates:
            asset_key = candidate.get("asset_key") or candidate.get("download_url")
            if asset_key in used_assets:
                continue
            if candidate["final_score"] < min_score:
                continue
            selected = candidate
            break

        if selected:
            filename = f"scene_{index}_{_slug(scene.keywords[0] if scene.keywords else 'asset')}.mp4"
            asset_path = pexels_client.download_asset(selected["download_url"], filename)
            if asset_path:
                used_assets.add(selected.get("asset_key") or selected["download_url"])
                scene.asset_path = asset_path
                scene.asset_type = "video"
                scene.asset_source = selected["source"]
                scene.selected_query = selected["query"]
                scene.relevance_score = selected["relevance_score"]
                scene.quality_score = selected["quality_score"]
                scene.final_score = selected["final_score"]
                logger.info(
                    f"Selected {scene.asset_source} asset for scene {scene.scene_id} "
                    f"(score={scene.final_score:.2f}, query='{scene.selected_query}')"
                )
                continue

        logger.warning(
            f"No sufficiently relevant stock asset for scene {scene.scene_id}; "
            "creating contextual visual fallback."
        )
        _create_contextual_scene_image(scene, story_context, index)

    return scenes


def _llm_scene_breakdown(
    script_text: str,
    story_context: Optional[StoryContext],
    target_duration: Optional[int],
) -> List[VisualScene]:
    context_block = story_context.compact_context() if story_context else "No story context available."
    prompt = f"""
Split this narration into short visual scenes for a vertical technology news video.

Story context:
{context_block}

Narration:
{_clean_script(script_text)}

Target runtime: {target_duration or "unknown"} seconds.

Return JSON with a top-level "scenes" array. Each scene must include:
- scene_id: integer
- segment_text: exact narration covered by this scene
- duration: 5-10 seconds
- visual_requirement: specific visual direction, not generic stock
- keywords: 4-6 precise terms
- entities: entity names from the narration/context
- search_queries: 3-5 specific stock-search queries
- caption_text: 2-6 punchy words for on-screen caption

Rules:
1. Every scene represents one idea.
2. Prefer company/product/technology-specific visuals.
3. Avoid broad searches like "technology innovation".
4. Do not invent facts.
"""

    result = llm_client.generate_json(prompt)
    raw_scenes = result.get("scenes") if isinstance(result, dict) else result
    if not isinstance(raw_scenes, list):
        return []

    scenes = []
    for index, item in enumerate(raw_scenes):
        if not isinstance(item, dict):
            continue
        segment = _clean_script(str(item.get("segment_text") or item.get("scene_text") or ""))
        if not segment:
            continue
        try:
            scenes.append(
                VisualScene(
                    scene_id=int(item.get("scene_id") or index + 1),
                    segment_text=segment,
                    duration=float(item.get("duration") or 8.0),
                    visual_requirement=str(item.get("visual_requirement") or ""),
                    keywords=_as_list(item.get("keywords")),
                    search_queries=_as_list(item.get("search_queries")),
                    entities=_as_list(item.get("entities")),
                    caption_text=str(item.get("caption_text") or ""),
                )
            )
        except Exception as exc:
            logger.error(f"Failed to parse LLM scene {index + 1}: {exc}")

    return scenes


def _rule_based_scene_breakdown(
    script_text: str,
    story_context: Optional[StoryContext],
    target_duration: Optional[int],
) -> List[VisualScene]:
    cleaned = _clean_script(script_text)
    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", cleaned) if sentence.strip()]
    if not sentences:
        return [VisualScene(segment_text=cleaned or "Technology news update")]

    target_scene_count = max(3, min(8, round((target_duration or _estimate_total_duration(cleaned)) / 8)))
    words_per_scene = max(14, round(len(cleaned.split()) / target_scene_count))

    segments = []
    current = []
    current_words = 0
    for sentence in sentences:
        sentence_words = len(sentence.split())
        if current and current_words + sentence_words > words_per_scene + 8:
            segments.append(" ".join(current))
            current = []
            current_words = 0
        current.append(sentence)
        current_words += sentence_words
    if current:
        segments.append(" ".join(current))

    if len(segments) < 3 and len(sentences) >= 3:
        segments = sentences

    scenes = []
    for index, segment in enumerate(segments[:8]):
        keywords = _extract_keywords(segment, story_context)
        entities = _entities_in_text(segment, story_context)
        scenes.append(
            VisualScene(
                scene_id=index + 1,
                segment_text=segment,
                duration=_estimate_scene_duration(segment),
                visual_requirement=_build_visual_requirement(segment, keywords, entities, story_context),
                keywords=keywords,
                entities=entities,
                search_queries=_build_search_queries(segment, keywords, entities, story_context),
                caption_text=_build_caption_text(segment, keywords, entities),
            )
        )
    return scenes


def _normalize_scene_plan(
    scenes: List[VisualScene],
    story_context: Optional[StoryContext],
    target_duration: Optional[int],
) -> List[VisualScene]:
    if not scenes:
        scenes = _rule_based_scene_breakdown("Technology news update.", story_context, target_duration)

    total_words = sum(len(scene.segment_text.split()) for scene in scenes) or 1
    target = float(target_duration or sum(_estimate_scene_duration(scene.segment_text) for scene in scenes))

    for index, scene in enumerate(scenes):
        scene.scene_id = index + 1
        if not scene.keywords:
            scene.keywords = _extract_keywords(scene.segment_text, story_context)
        if not scene.entities:
            scene.entities = _entities_in_text(scene.segment_text, story_context)
        if not scene.visual_requirement:
            scene.visual_requirement = _build_visual_requirement(
                scene.segment_text, scene.keywords, scene.entities, story_context
            )
        if not scene.search_queries:
            scene.search_queries = _build_search_queries(
                scene.segment_text, scene.keywords, scene.entities, story_context
            )
        if not scene.caption_text:
            scene.caption_text = _build_caption_text(scene.segment_text, scene.keywords, scene.entities)

        proportional_duration = target * (len(scene.segment_text.split()) / total_words)
        scene.duration = max(5.0, min(10.0, float(scene.duration or proportional_duration or 8.0)))
        scene.keywords = _unique(scene.keywords)[:6]
        scene.entities = _unique(scene.entities)[:6]
        scene.search_queries = _unique(scene.search_queries)[:5]

    return scenes


def _collect_candidates(scene: VisualScene) -> List[Dict]:
    candidates = []
    for query in scene.search_queries[:5]:
        pexels_videos = pexels_client.search_videos(query, limit=5)
        candidates.extend(_normalize_pexels_candidates(pexels_videos, query, scene))

        pixabay_videos = pixabay_client.search_videos(query, limit=5)
        candidates.extend(_normalize_pixabay_candidates(pixabay_videos, query, scene))

    deduped = {}
    for candidate in candidates:
        key = candidate.get("asset_key") or candidate["download_url"]
        if key not in deduped or candidate["final_score"] > deduped[key]["final_score"]:
            deduped[key] = candidate
    return list(deduped.values())


def _normalize_pexels_candidates(videos: List[Dict], query: str, scene: VisualScene) -> List[Dict]:
    candidates = []
    for video in videos:
        files = [file for file in video.get("video_files", []) if file.get("link")]
        if not files:
            continue
        best_file = max(files, key=lambda file: int(file.get("width") or 0) * int(file.get("height") or 0))
        width = int(best_file.get("width") or video.get("width") or 0)
        height = int(best_file.get("height") or video.get("height") or 0)
        duration = float(video.get("duration") or 0)
        relevance = _score_relevance(query, scene, video.get("url", ""))
        quality = _score_video_quality(width, height, duration)
        candidates.append(
            {
                "source": "pexels",
                "query": query,
                "download_url": best_file["link"],
                "asset_key": str(video.get("id") or best_file["link"]),
                "relevance_score": relevance,
                "quality_score": quality,
                "final_score": round((relevance * 0.68) + (quality * 0.32), 3),
            }
        )
    return candidates


def _normalize_pixabay_candidates(videos: List[Dict], query: str, scene: VisualScene) -> List[Dict]:
    candidates = []
    for video in videos:
        video_files = video.get("videos", {})
        selected = video_files.get("large") or video_files.get("medium") or video_files.get("small")
        if not selected or not selected.get("url"):
            continue
        width = int(selected.get("width") or 0)
        height = int(selected.get("height") or 0)
        duration = float(video.get("duration") or 0)
        tags = str(video.get("tags") or "")
        relevance = _score_relevance(query, scene, tags)
        quality = _score_video_quality(width, height, duration)
        candidates.append(
            {
                "source": "pixabay",
                "query": query,
                "download_url": selected["url"],
                "asset_key": str(video.get("id") or selected["url"]),
                "relevance_score": relevance,
                "quality_score": quality,
                "final_score": round((relevance * 0.68) + (quality * 0.32), 3),
            }
        )
    return candidates


def _score_relevance(query: str, scene: VisualScene, asset_text: str) -> float:
    query_text = query.lower()
    asset_text = asset_text.lower()
    visual_text = f"{query_text} {asset_text}"
    signal_terms = _unique([*scene.entities, *scene.keywords])
    if not signal_terms:
        return 0.5

    hits = 0
    for term in signal_terms:
        words = [word for word in re.findall(r"[a-z0-9]+", term.lower()) if len(word) > 2]
        if any(word in visual_text for word in words):
            hits += 1

    entity_bonus = 0.18 if any(entity.lower() in query_text for entity in scene.entities) else 0.0
    specificity_bonus = min(len(query.split()) / 8, 0.18)
    score = 0.42 + min(hits / max(len(signal_terms), 1), 1.0) * 0.4 + entity_bonus + specificity_bonus
    return round(min(score, 1.0), 3)


def _score_video_quality(width: int, height: int, duration: float) -> float:
    resolution_score = min((width * height) / (1280 * 720), 1.0) if width and height else 0.45
    if width and height:
        ratio = width / height
        aspect_score = 1.0 if ratio <= 1.0 else 0.82
    else:
        aspect_score = 0.65
    duration_score = 1.0 if 5 <= duration <= 25 else 0.78 if duration > 0 else 0.55
    return round((resolution_score * 0.45) + (aspect_score * 0.3) + (duration_score * 0.25), 3)


def _create_contextual_scene_image(
    scene: VisualScene,
    story_context: Optional[StoryContext],
    index: int,
) -> None:
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), color=(14, 18, 26))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        blue = int(24 + (y / height) * 34)
        green = int(18 + (y / height) * 24)
        red = int(14 + (y / height) * 16)
        draw.line([(0, y), (width, y)], fill=(red, green, blue))

    accents = [(0, 170, 170), (244, 182, 67), (226, 80, 92), (122, 201, 117)]
    accent = accents[index % len(accents)]
    draw.rectangle((0, 0, width, 26), fill=accent)
    draw.rectangle((70, 150, 980, 172), fill=accent)

    title_font = _font(74)
    body_font = _font(42)
    small_font = _font(30)
    label_font = _font(26)

    primary = scene.entities[0] if scene.entities else (story_context.search_focus[0] if story_context and story_context.search_focus else "Tech Update")
    caption = scene.caption_text or _build_caption_text(scene.segment_text, scene.keywords, scene.entities)

    draw.text((70, 220), _fit_text(primary.upper(), 18), font=label_font, fill=accent)
    _draw_wrapped_text(draw, caption.upper(), (70, 285), title_font, max_width=930, fill=(250, 252, 255), max_lines=3)

    body_text = scene.segment_text or scene.visual_requirement
    _draw_wrapped_text(draw, body_text, (70, 620), body_font, max_width=900, fill=(225, 232, 240), max_lines=5)

    key_terms = _unique([*scene.entities, *scene.keywords])[:5]
    y = 1120
    for term in key_terms:
        draw.rounded_rectangle((70, y, 980, y + 76), radius=18, fill=(28, 36, 48), outline=(70, 82, 98), width=2)
        draw.text((105, y + 18), _fit_text(term, 34), font=small_font, fill=(245, 247, 250))
        y += 96

    source_text = "AUTOCAST VISUAL INTELLIGENCE"
    if story_context and story_context.source_names:
        source_text = f"SOURCE: {story_context.source_names[0]}"
    draw.text((70, 1780), _fit_text(source_text.upper(), 42), font=label_font, fill=(160, 172, 188))

    output_dir = os.path.join(settings.DATA_DIR, "assets")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"scene_{index}_context.png")
    image.save(output_path)

    scene.asset_path = output_path
    scene.asset_type = "image"
    scene.asset_source = "generated-context"
    scene.selected_query = "contextual graphic"
    scene.relevance_score = 0.95
    scene.quality_score = 0.9
    scene.final_score = 0.93


def _build_visual_requirement(
    segment: str,
    keywords: List[str],
    entities: List[str],
    story_context: Optional[StoryContext],
) -> str:
    anchor = entities[0] if entities else (keywords[0] if keywords else "the story")
    action = _action_phrase(segment)
    if action == "audience follow-up":
        return "Closing news-channel visual with the story topic and a clean follow-up cue."
    if story_context and story_context.statistics and any(stat in segment for stat in story_context.statistics):
        return f"Data-led visual showing {anchor} and the key number discussed in the narration."
    if entities:
        return f"Entity-specific visual focused on {anchor}, showing {action}."
    if keywords:
        return f"Specific technology visual showing {', '.join(keywords[:3])} in the context of {action}."
    return f"Contextual news graphic matching this narration: {segment[:120]}"


def _build_search_queries(
    segment: str,
    keywords: List[str],
    entities: List[str],
    story_context: Optional[StoryContext],
) -> List[str]:
    action = _action_phrase(segment)
    technologies = story_context.technologies if story_context else []
    companies = story_context.companies if story_context else []

    anchors = _unique([*entities, *companies[:2], *keywords[:3], *technologies[:2]])
    queries = []
    for anchor in anchors[:3]:
        if anchor.lower() == action.lower():
            queries.append(f"{anchor} industry newsroom")
        elif action.lower().startswith(f"{anchor.lower()} "):
            queries.append(f"{action} technology news")
        else:
            queries.append(f"{anchor} {action} technology news")
    if keywords:
        queries.append(f"{' '.join(keywords[:3])} professional video")
    if technologies:
        queries.append(f"{technologies[0]} industry newsroom")
    queries.append(f"{action} technology business news")
    return _unique(_trim_query(query) for query in queries if query.strip())[:5]


def _extract_keywords(segment: str, story_context: Optional[StoryContext]) -> List[str]:
    lower_segment = segment.lower()
    priority_terms = []
    if story_context:
        for term in [*story_context.companies, *story_context.products, *story_context.technologies, *story_context.search_focus]:
            if term and term.lower() in lower_segment:
                priority_terms.append(term)

    tokens = [
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", segment)
        if token.lower() not in STOP_WORDS
    ]
    freq_terms = []
    for token in tokens:
        if token not in freq_terms:
            freq_terms.append(token)
    return _unique([*priority_terms, *freq_terms])[:6]


def _entities_in_text(segment: str, story_context: Optional[StoryContext]) -> List[str]:
    entities = []
    if story_context:
        for entity in [*story_context.companies, *story_context.products, *story_context.entities]:
            if entity and entity.lower() in segment.lower():
                entities.append(entity)
    pattern = r"\b[A-Z][A-Za-z0-9&.'-]+(?:\s+[A-Z][A-Za-z0-9&.'-]+){0,3}"
    entities.extend(re.findall(pattern, segment))
    return _unique(entity for entity in entities if entity not in ENTITY_STOP_WORDS)[:6]


def _build_caption_text(segment: str, keywords: List[str], entities: List[str]) -> str:
    if entities and keywords:
        keyword = next((item for item in keywords if item.lower() != entities[0].lower()), keywords[0])
        return _fit_text(f"{entities[0]}: {keyword}", 34)
    if entities:
        return _fit_text(entities[0], 34)
    if keywords:
        return _fit_text(" ".join(keywords[:3]), 34)
    words = [word.strip(".,!?") for word in segment.split()[:6]]
    return " ".join(words)


def _action_phrase(segment: str) -> str:
    lowered = segment.lower()
    if any(term in lowered for term in ("follow for", "subscribe", "hit like", "next update")):
        return "audience follow-up"
    action_terms = [
        "launch",
        "release",
        "funding",
        "data center",
        "robotics",
        "AI",
        "privacy",
        "cybersecurity",
        "chip",
        "startup",
        "market impact",
        "product demo",
        "business shift",
    ]
    for term in action_terms:
        if term.lower() in lowered:
            return term
    words = [word.lower().strip(".,!?") for word in segment.split() if len(word.strip(".,!?")) > 4]
    filtered = [word for word in words if word not in STOP_WORDS]
    return " ".join(filtered[:3]) or "technology update"


def _clean_script(script_text: str) -> str:
    text = re.sub(r"\[[A-Z\s_-]+\]", " ", script_text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _estimate_total_duration(text: str) -> int:
    return max(20, round(len(text.split()) / 2.35))


def _estimate_scene_duration(text: str) -> float:
    return max(5.0, min(10.0, len(text.split()) / 2.35))


def _as_list(value: object) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return _unique(str(item) for item in value if str(item).strip())
    if isinstance(value, str):
        if "\n" in value:
            return _unique(part.strip(" -") for part in value.splitlines() if part.strip(" -"))
        if "," in value:
            return _unique(part.strip() for part in value.split(",") if part.strip())
        return [value.strip()] if value.strip() else []
    return [str(value).strip()]


def _unique(values: Iterable[str]) -> List[str]:
    output = []
    seen = set()
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value)).strip(" -")
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _trim_query(query: str, max_words: int = 8) -> str:
    words = query.split()
    return " ".join(words[:max_words])


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:30] or "visual"


def _font(size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    position: tuple,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    fill: tuple,
    max_lines: int,
) -> None:
    lines = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    x, y = position
    line_height = font.size + 12
    for line in lines[:max_lines]:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height


def _fit_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "."
