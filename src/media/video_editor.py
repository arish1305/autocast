from moviepy import VideoFileClip, AudioFileClip, ImageClip, CompositeVideoClip, concatenate_videoclips
from typing import List, Optional
import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from src.core.logger import logger
from src.media.asset_manager import VisualScene
from src.core.config import settings

TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def create_video_project(audio_path: str, scenes: List[VisualScene], output_name: str) -> Optional[str]:
    """
    Assembles the final video from audio and visual assets.
    """
    logger.info(f"Assembling video project: {output_name}")
    
    try:
        # Load Main Audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        
        clips = []
        valid_scenes = [
            scene for scene in scenes
            if scene.asset_path and os.path.exists(scene.asset_path)
        ]

        if not valid_scenes:
             logger.error("No valid video clips to assemble.")
             return None

        planned_duration = sum(max(scene.duration, 0.1) for scene in valid_scenes)
        duration_scale = total_duration / planned_duration if planned_duration else 1.0

        for i, scene in enumerate(valid_scenes):
            try:
                clip_duration = max(1.0, scene.duration * duration_scale)
                visual_clip = _load_scene_clip(scene, clip_duration)
                if not visual_clip:
                    continue

                visual_clip = _fit_to_vertical(visual_clip).with_duration(clip_duration)
                visual_clip = _add_caption_overlay(visual_clip, scene, clip_duration)
                clips.append(visual_clip)
                
            except Exception as e:
                logger.error(f"Failed to process clip {scene.asset_path}: {e}")
                
        if not clips:
            logger.error("No clips were successfully processed.")
            return None
            
        final_video = concatenate_videoclips(clips, method="compose")
        # MoviePy 2.x: set_audio -> with_audio
        final_video = final_video.with_audio(audio)
        
        output_path = os.path.join(settings.DATA_DIR, "renders", output_name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Video composition failed: {e}")
        return None


def _load_scene_clip(scene: VisualScene, clip_duration: float):
    extension = os.path.splitext(scene.asset_path or "")[1].lower()
    if scene.asset_type == "image" or extension in IMAGE_EXTENSIONS:
        return ImageClip(scene.asset_path).with_duration(clip_duration)

    video_clip = VideoFileClip(scene.asset_path)
    if video_clip.duration < clip_duration:
        logger.info(f"Asset too short ({video_clip.duration}s < {clip_duration:.2f}s). Looping.")
        loop_count = int(clip_duration // max(video_clip.duration, 0.1)) + 1
        video_clip = concatenate_videoclips([video_clip] * loop_count)
    return video_clip.subclipped(0, clip_duration).with_duration(clip_duration)


def _fit_to_vertical(clip):
    clip = _center_crop_to_ratio(clip, TARGET_WIDTH / TARGET_HEIGHT)
    clip = clip.resized(height=TARGET_HEIGHT)
    width, height = clip.size
    if width < TARGET_WIDTH:
        clip = clip.resized(width=TARGET_WIDTH)
        width, height = clip.size
    return clip.cropped(
        x_center=int(width / 2),
        y_center=int(height / 2),
        width=TARGET_WIDTH,
        height=TARGET_HEIGHT,
    )


def _center_crop_to_ratio(clip, target_ratio: float):
    width, height = clip.size
    current_ratio = width / height
    if current_ratio > target_ratio:
        new_width = int(height * target_ratio)
        return clip.cropped(x_center=int(width / 2), width=new_width, height=height)
    if current_ratio < target_ratio:
        new_height = int(width / target_ratio)
        if new_height <= height:
            return clip.cropped(y_center=int(height / 2), width=width, height=new_height)
    return clip


def _add_caption_overlay(clip, scene: VisualScene, duration: float):
    try:
        caption = scene.caption_text or _caption_from_segment(scene.segment_text)
        if not caption:
            return clip
        caption_image = _make_caption_image(caption)
        caption_clip = (
            ImageClip(np.array(caption_image))
            .with_duration(duration)
            .with_position(("center", int(TARGET_HEIGHT * 0.72)))
        )
        return CompositeVideoClip([clip, caption_clip], size=(TARGET_WIDTH, TARGET_HEIGHT)).with_duration(duration)
    except Exception as exc:
        logger.warning(f"Caption overlay skipped: {exc}")
        return clip


def _make_caption_image(text: str) -> Image.Image:
    width, height = 940, 220
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, width, height), radius=36, fill=(8, 12, 18, 212))
    draw.rounded_rectangle((0, 0, 18, height), radius=8, fill=(0, 186, 174, 255))

    font = _font(58)
    lines = _wrap_text(draw, text.upper(), font, width - 110, max_lines=2)
    y = 48 if len(lines) == 2 else 76
    for line in lines:
        draw.text((56, y), line, font=font, fill=(255, 255, 255, 255))
        y += 70
    return image


def _caption_from_segment(segment: str) -> str:
    words = [word.strip(".,!?") for word in re.split(r"\s+", segment) if word.strip(".,!?")]
    return " ".join(words[:6])


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int, max_lines: int) -> List[str]:
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
    return lines[:max_lines]


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
