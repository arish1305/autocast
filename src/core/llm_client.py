import requests
import json
import re
from src.core.config import settings
from src.core.logger import logger
from typing import Optional, Any


def _extract_json_payload(text: str) -> Optional[Any]:
    """Parses JSON even when a local model adds markdown fences or short prose."""
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    for candidate in (cleaned,):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    starts = [idx for idx in (cleaned.find("{"), cleaned.find("[")) if idx != -1]
    if not starts:
        return None

    start = min(starts)
    opening = cleaned[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escape = False

    for idx in range(start, len(cleaned)):
        char = cleaned[idx]
        if escape:
            escape = False
            continue
        if char == "\\":
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cleaned[start : idx + 1])
                except json.JSONDecodeError:
                    return None

    return None

class LocalLLMClient:
    """Interfaces with a local Ollama instance for zero-cost LLM features."""
    
    def __init__(self):
        self.base_url = f"{settings.OLLAMA_BASE_URL}/api"
        self.model = settings.OLLAMA_MODEL

    def generate_json(self, prompt: str) -> Optional[Any]:
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
            
            parsed = _extract_json_payload(response_text)
            if parsed is None:
                logger.error("Local LLM returned text that could not be parsed as JSON.")
            return parsed
        except Exception as e:
            logger.error(f"Ollama generation failed: {e}")
            return None

# Global instance
llm_client = LocalLLMClient()
