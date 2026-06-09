import os
import shutil
import subprocess
import tempfile
from src.core.logger import logger

def normalize_audio(file_path: str) -> bool:
    """
    Applies loudness normalization using ffmpeg when available.
    """
    if not os.path.exists(file_path):
        logger.error(f"Cannot normalize missing file: {file_path}")
        return False
        
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        logger.warning("ffmpeg not found. Audio normalization skipped.")
        return True

    temp_dir = tempfile.mkdtemp(prefix="autocast_audio_")
    temp_output = os.path.join(temp_dir, os.path.basename(file_path))
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        file_path,
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        temp_output,
    ]

    try:
        logger.info(f"Normalizing audio: {file_path}")
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.warning(f"Audio normalization failed; keeping original. ffmpeg: {result.stderr[-300:]}")
            return True
        shutil.move(temp_output, file_path)
        return True
    except Exception as exc:
        logger.warning(f"Audio normalization skipped after error: {exc}")
        return True
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _find_ffmpeg() -> str:
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return get_ffmpeg_exe()
    except Exception:
        return ""
