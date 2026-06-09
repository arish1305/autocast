import os
import re
from typing import Iterable, List, Optional

from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel

from src.core.config import settings
from src.core.llm_client import llm_client
from src.core.logger import logger


class ThumbnailConcept(BaseModel):
    hook_text: str
    emotional_angle: str
    visual_focus: str
    accent_color: str = "#00b8a9"


class ThumbnailGenerator:
    """Generates mobile-readable YouTube thumbnails with concept scoring."""
    
    def __init__(self):
        self.output_dir = os.path.join(settings.DATA_DIR, "thumbnails")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_thumbnail(self, topic: str, strategy_summary: str) -> Optional[str]:
        """
        Creates a thumbnail by selecting the strongest concept and rendering it locally.
        """
        logger.info(f"Generating local thumbnail for: {topic}")
        
        try:
            concepts = self.generate_thumbnail_concepts(topic, strategy_summary)
            concept = self._select_best_concept(concepts)
            path = self._render_thumbnail(topic, strategy_summary, concept)
            logger.info(f"Local thumbnail saved to: {path}")
            return path
        except Exception as e:
            logger.error(f"Local thumbnail generation failed: {e}")
            return None

    def generate_thumbnail_concepts(self, topic: str, strategy_summary: str) -> List[ThumbnailConcept]:
        prompt = f"""
You are a thumbnail strategist for AutoCast AI, a technology-news YouTube channel.
Generate 5 thumbnail concepts that are clear, factual, and readable on a phone.

VIDEO TOPIC
{topic}

STORY SUMMARY / ANGLE
{strategy_summary[:1000]}

THUMBNAIL GOAL
The thumbnail should instantly communicate the story's main tension or implication.
It should make viewers curious without lying or exaggerating.

CONCEPT REQUIREMENTS
Each concept needs:
- hook_text: 2-5 words, max 24 characters, high curiosity but factual
- emotional_angle: short phrase like "urgency", "risk", "delay", "market pressure", "breakthrough"
- visual_focus: concrete object/entity the thumbnail should show, such as company, product, person, region, chart, device
- accent_color: hex color that contrasts with dark background and white text

DESIGN RULES
1. No misleading clickbait or fake shock.
2. Text must be readable on a phone at small size.
3. Prefer specific company/product/entity wording over generic words like "Tech", "AI", or "Future".
4. Use simple visual ideas: device + region, company card + warning, chart + number, person + decision.
5. Avoid long sentences, URLs, dates unless the date is central to the story, and abstract phrases.
6. Avoid duplicate concepts; each should emphasize a different angle.
7. The thumbnail text must not promise something the video does not explain.

Return only valid JSON with this shape:
{{
  "concepts": [
    {{
      "hook_text": "Siri Delayed",
      "emotional_angle": "urgency",
      "visual_focus": "Apple Siri Europe",
      "accent_color": "#00b8a9"
    }}
  ]
}}
"""
        result = llm_client.generate_json(prompt)
        raw_concepts = result.get("concepts") if isinstance(result, dict) else result
        concepts = []
        if isinstance(raw_concepts, list):
            for item in raw_concepts:
                if not isinstance(item, dict):
                    continue
                try:
                    concepts.append(ThumbnailConcept(**item))
                except Exception:
                    continue
        return concepts or self._fallback_concepts(topic, strategy_summary)

    def _fallback_concepts(self, topic: str, strategy_summary: str) -> List[ThumbnailConcept]:
        entity = _main_entity(topic)
        hooks = [
            f"{entity} Shift",
            "Why It Matters",
            "Big Tech Move",
            "What Changed",
            "Watch This",
        ]
        angles = ["urgency", "impact", "market shift", "context", "curiosity"]
        colors = ["#00b8a9", "#f2b441", "#e8505b", "#7ac975", "#5b8def"]
        return [
            ThumbnailConcept(
                hook_text=_fit_text(hook, 24),
                emotional_angle=angles[index],
                visual_focus=entity or topic,
                accent_color=colors[index],
            )
            for index, hook in enumerate(hooks)
        ]

    def _select_best_concept(self, concepts: List[ThumbnailConcept]) -> ThumbnailConcept:
        def score(concept: ThumbnailConcept) -> int:
            hook = concept.hook_text.strip()
            return (
                (8 if 8 <= len(hook) <= 24 else 0)
                + (4 if len(hook.split()) <= 5 else 0)
                + (3 if concept.visual_focus else 0)
                + (2 if concept.emotional_angle else 0)
            )

        return sorted(concepts, key=score, reverse=True)[0]

    def _render_thumbnail(self, topic: str, summary: str, concept: ThumbnailConcept) -> str:
        width, height = 1280, 720
        img = Image.new("RGB", (width, height), color=(13, 17, 24))
        draw = ImageDraw.Draw(img)
        accent = _hex_to_rgb(concept.accent_color)

        for x in range(width):
            blend = x / width
            color = (
                int(13 + blend * 28),
                int(17 + blend * 20),
                int(24 + blend * 34),
            )
            draw.line([(x, 0), (x, height)], fill=color)

        draw.rectangle((0, 0, width, 18), fill=accent)
        draw.polygon([(840, 0), (1280, 0), (1280, 720), (980, 720)], fill=(24, 31, 42))
        draw.ellipse((870, 110, 1210, 450), outline=accent, width=12)
        draw.line((905, 500, 1210, 610), fill=(230, 236, 245), width=8)
        draw.rectangle((900, 500, 1170, 620), outline=accent, width=8)

        hook_font = _font(92)
        label_font = _font(34)
        detail_font = _font(30)

        draw.text((70, 70), _fit_text(concept.emotional_angle.upper(), 24), font=label_font, fill=accent)
        _draw_wrapped(draw, concept.hook_text.upper(), (70, 145), hook_font, 690, (255, 255, 255), 3)

        visual_focus = concept.visual_focus or _main_entity(topic)
        draw.rounded_rectangle((70, 555, 760, 640), radius=18, fill=(232, 238, 246))
        draw.text((105, 579), _fit_text(visual_focus.upper(), 30), font=detail_font, fill=(12, 16, 22))

        filename = f"thumb_{_slug(topic)[:36]}.png"
        path = os.path.join(self.output_dir, filename)
        img.save(path)
        return path


def _main_entity(topic: str) -> str:
    words = re.findall(r"[A-Z][A-Za-z0-9&.'-]+", topic)
    if words:
        return " ".join(words[:2])
    return " ".join(topic.split()[:2])


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


def _draw_wrapped(
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
    for line in lines[:max_lines]:
        draw.text((x + 4, y + 4), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + 4


def _hex_to_rgb(value: str) -> tuple:
    value = (value or "#00b8a9").strip().lstrip("#")
    if len(value) != 6:
        return (0, 184, 169)
    try:
        return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return (0, 184, 169)


def _fit_text(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "."


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "thumbnail"


# Global instance
thumbnail_generator = ThumbnailGenerator()
