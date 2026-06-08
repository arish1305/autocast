import os
import pickle
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from src.core.config import settings
from src.core.logger import logger
from typing import Optional, List

class YouTubeClient:
    """Wrapper for YouTube Data API v3."""
    
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    
    def __init__(self):
        self.youtube = None
        self._authenticate()

    def _authenticate(self):
        """Authenticates the user and builds the YouTube service."""
        if not settings.YOUTUBE_CLIENT_ID or not settings.YOUTUBE_CLIENT_SECRET:
            logger.warning("YouTube API credentials missing. Publishing will be disabled.")
            return

        creds = None
        token_path = "token.pickle"
        
        if os.path.exists(token_path):
            try:
                with open(token_path, "rb") as token:
                    creds = pickle.load(token)
            except Exception as e:
                logger.error(
                    "Could not read token.pickle. YouTube publishing will be disabled "
                    f"until you re-authenticate. Error: {e}"
                )
                return
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    logger.error(
                        "YouTube OAuth token refresh failed. Publishing will be disabled. "
                        "Delete token.pickle and run setup_youtube_auth.py to re-authenticate. "
                        f"Error: {e}"
                    )
                    return
                except Exception as e:
                    logger.error(
                        "Unexpected YouTube OAuth refresh error. Publishing will be disabled. "
                        f"Error: {e}"
                    )
                    return
            else:
                # This requires browser interaction, so it will fail in headless/background
                logger.error("OAuth2 token not found or invalid. Manual authentication required.")
                return
            
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        try:
            self.youtube = build("youtube", "v3", credentials=creds)
        except Exception as e:
            logger.error(f"Failed to initialize YouTube service. Publishing will be disabled. Error: {e}")

    def upload_video(self, file_path: str, title: str, description: str, tags: List[str], category_id: str = "28") -> Optional[str]:
        """Uploads a video to YouTube."""
        if not self.youtube:
            logger.error("YouTube service not initialized.")
            return None

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": category_id
            },
            "status": {
                "privacyStatus": "private", # Default to private for safety
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        
        try:
            logger.info(f"Uploading video: {title}")
            request = self.youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )
            response = request.execute()
            video_id = response.get("id")
            logger.info(f"Video uploaded successfully. Video ID: {video_id}")
            return video_id
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return None

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """Sets the thumbnail for an uploaded video."""
        if not self.youtube:
            return False
            
        try:
            logger.info(f"Uploading thumbnail for video {video_id}...")
            self.youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            logger.info("Thumbnail updated successfully.")
            return True
        except Exception as e:
            logger.error(f"Thumbnail upload failed: {e}")
            return False

# Global instance
youtube_provider = YouTubeClient()
