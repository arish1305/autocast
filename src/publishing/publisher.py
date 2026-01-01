from src.core.logger import logger
from src.publishing.youtube_client import youtube_provider
from src.publishing.metadata_optimizer import VideoMetadata
from typing import Optional

def publish_to_youtube(video_path: str, thumb_path: str, metadata: VideoMetadata) -> Optional[str]:
    """
    Orchestrates the publishing process to YouTube.
    """
    logger.info(f"Initiating publishing for: {metadata.title}")
    
    # 1. Upload Video
    video_id = youtube_provider.upload_video(
        video_path,
        metadata.title,
        metadata.description,
        metadata.tags,
        metadata.category_id
    )
    
    if video_id:
        # 2. Upload Thumbnail
        youtube_provider.set_thumbnail(video_id, thumb_path)
        return f"https://www.youtube.com/watch?v={video_id}"
    
    logger.warning("Publishing skipped or failed.")
    return None
