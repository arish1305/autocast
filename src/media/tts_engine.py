import os
import asyncio
import re
import edge_tts
from src.core.config import settings
from src.core.logger import logger
from typing import Optional

def text_to_speech(text: str, filename: str) -> Optional[str]:
    """
    Converts text to speech using Edge-TTS (Free, High Quality).
    """
    output_path = os.path.join(settings.DATA_DIR, "audio", filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    narration_text = prepare_narration_text(text)
    
    async def _generate():
        try:
            logger.info(f"Synthesizing voice with Edge-TTS (Voice: {settings.TTS_VOICE})...")
            communicate = edge_tts.Communicate(
                narration_text,
                settings.TTS_VOICE,
                rate="+2%",
                volume="+0%",
                pitch="+0Hz",
            )
            await communicate.save(output_path)
            logger.info(f"Audio saved to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Edge-TTS synthesis failed: {e}")
            return None

    # Edge-TTS is async, so we run it in a loop
    return asyncio.run(_generate())


def prepare_narration_text(text: str) -> str:
    """Cleans script labels and improves pacing before TTS synthesis."""
    cleaned = re.sub(r"\[[A-Z\s_-]+\]", " ", text or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"([.!?])\s+", r"\1 ", cleaned)
    cleaned = re.sub(r"\b(AI|GPU|LLM|API|CEO)\b", lambda match: match.group(1).replace("", " ").strip(), cleaned)
    cleaned = cleaned.replace(" .", ".").replace(" ,", ",")
    return cleaned
