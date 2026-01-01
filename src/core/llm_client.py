import requests
import json
from src.core.config import settings
from src.core.logger import logger
from typing import Optional, Dict, Any

class LocalLLMClient:
    """Interfaces with a local Ollama instance for zero-cost LLM features."""
    
    def __init__(self):
        self.base_url = f"{settings.OLLAMA_BASE_URL}/api"
        self.model = settings.OLLAMA_MODEL

    def generate_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        """
        Sends a prompt to local Ollama and expects a JSON response.
        Note: We append JSON instructions to the prompt to help local models.
        """
        logger.info(f"Generating content with local LLM ({self.model})...")
        
        full_prompt = f"{prompt}\n\nStrictly output valid JSON only. No preamble."
        
        try:
            response = requests.post(
                f"{self.base_url}/generate",
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            response_text = result.get("response", "")
            
            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return None

# Global instance
llm_client = LocalLLMClient()
