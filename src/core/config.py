import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    """Application settings and environment variables."""
    
    # API Keys
    YOUTUBE_API_KEY: Optional[str] = None
    # Free/Local Service Settings
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_TIMEOUT_SECONDS: int = 600
    OLLAMA_RETRY_ATTEMPTS: int = 3
    TTS_VOICE: str = "en-US-GuyNeural" # Edge-TTS voice
    
    # Optional Free Tier Keys
    PEXELS_API_KEY: Optional[str] = None
    PIXABAY_API_KEY: Optional[str] = None
    YOUTUBE_CLIENT_ID: Optional[str] = None
    YOUTUBE_CLIENT_SECRET: Optional[str] = None
    
    # Project Settings
    NICHE: str = "technology"
    LANGUAGE: str = "en"
    REGION: str = "US"
    VIDEO_FORMAT: str = "short"  # short or long
    UPLOAD_SCHEDULE: str = "daily"
    TREND_MAX_AGE_DAYS: int = 14
    SCRIPT_MIN_RUNTIME_SECONDS: int = 20
    SHORT_TARGET_RUNTIME_SECONDS: int = 32
    CONTENT_CORRECTOR_USE_LLM: bool = True
    RESEARCH_MAX_SOURCES: int = 3
    RESEARCH_FETCH_TIMEOUT_SECONDS: int = 12
    RESEARCH_MAX_HTML_CHARS: int = 400000
    
    # Paths
    DATA_DIR: str = "data"
    LOGS_DIR: str = "logs"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

# Global settings instance
settings = Settings()
