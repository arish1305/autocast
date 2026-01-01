import os
import asyncio
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
    
    async def _generate():
        try:
            logger.info(f"Synthesizing voice with Edge-TTS (Voice: {settings.TTS_VOICE})...")
            communicate = edge_tts.Communicate(text, settings.TTS_VOICE)
            await communicate.save(output_path)
            logger.info(f"Audio saved to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Edge-TTS synthesis failed: {e}")
            return None

    # Edge-TTS is async, so we run it in a loop
    return asyncio.run(_generate())
