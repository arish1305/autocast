import os
import requests
from src.core.config import settings
from src.core.logger import logger
from src.core.llm_client import llm_client
from typing import Optional

class ThumbnailGenerator:
    """Generates thumbnails using local PIL composition for zero cost."""
    
    def __init__(self):
        self.output_dir = os.path.join(settings.DATA_DIR, "thumbnails")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_thumbnail(self, topic: str, strategy_summary: str) -> Optional[str]:
        """
        Creates a thumbnail by combining a background image with text overlays.
        """
        logger.info(f"Generating local thumbnail for: {topic}")
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            # 1. Create a dark gradient or solid background
            width, height = 1280, 720
            img = Image.new('RGB', (width, height), color=(20, 20, 30))
            draw = ImageDraw.Draw(img)
            
            # 2. Add some techy elements (simple lines)
            for i in range(0, width, 50):
                draw.line([(i, 0), (i, height)], fill=(40, 40, 60), width=1)
            
            # 3. Add Title Text
            # We'll try to find a system font
            font_path = "C:\\Windows\\Fonts\\arialbd.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                font = ImageFont.load_default()
            else:
                font = ImageFont.truetype(font_path, 80)
            
            # Split topic into lines if too long
            title = topic.upper()
            draw.text((60, 300), title, font=font, fill=(255, 255, 255))
            
            filename = f"thumb_{topic.replace(' ', '_').lower()[:20]}.png"
            path = os.path.join(self.output_dir, filename)
            img.save(path)
                
            logger.info(f"Local thumbnail saved to: {path}")
            return path
            
        except Exception as e:
            logger.error(f"Local thumbnail generation failed: {e}")
            return None

# Global instance
thumbnail_generator = ThumbnailGenerator()
