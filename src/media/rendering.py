from src.core.logger import logger
from .video_editor import create_video_project
from typing import List
from src.media.asset_manager import VisualScene

def render_final_video(audio_path: str, scenes: List[VisualScene], output_name: str = "final_output.mp4") -> str:
    """
    Entry point for the rendering phase.
    """
    logger.info("Starting final render process...")
    result_path = create_video_project(audio_path, scenes, output_name)
    
    if result_path:
        logger.info(f"Render successful! Video available at: {result_path}")
        return result_path
    else:
        logger.error("Render failed.")
        return ""
