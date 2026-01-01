import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
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
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
                
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # This requires browser interaction, so it will fail in headless/background
                logger.error("OAuth2 token not found or invalid. Manual authentication required.")
                return
            
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        self.youtube = build("youtube", "v3", credentials=creds)

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
