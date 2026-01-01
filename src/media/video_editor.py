from moviepy import VideoFileClip, AudioFileClip, TextClip, CompositeVideoClip, concatenate_videoclips
import moviepy.video.fx as vfx
from typing import List, Optional
import os
from src.core.logger import logger
from src.media.asset_manager import VisualScene
from src.core.config import settings

def create_video_project(audio_path: str, scenes: List[VisualScene], output_name: str) -> Optional[str]:
    """
    Assembles the final video from audio and visual assets.
    """
    logger.info(f"Assembling video project: {output_name}")
    
    try:
        # Load Main Audio
        audio = AudioFileClip(audio_path)
        total_duration = audio.duration
        
        clips = []
        current_time = 0.0
        
        if not scenes:
             logger.error("No valid video clips to assemble.")
             return None

        for i, scene in enumerate(scenes):
            if not scene.asset_path or not os.path.exists(scene.asset_path):
                logger.warning(f"No asset found for scene {i}. Skipping segment.")
                continue
                
            try:
                # Calculate Duration for this clip
                if len(scenes) == 1:
                    clip_duration = total_duration
                else:
                    clip_duration = total_duration / len(scenes)

                video_clip = VideoFileClip(scene.asset_path)
                
                # Resize/Crop to 9:16 (Vertical) - Simple Center Crop
                w, h = video_clip.size
                target_ratio = 9/16
                
                # Logic to crop to vertical
                if w/h > target_ratio:
                    # Too wide, crop width
                    new_w = h * target_ratio
                    video_clip = video_clip.cropped(x1=(w/2 - new_w/2), width=new_w, height=h)
                else:
                    # Too tall or perfect
                    pass
                
                # MoviePy 2.x: resize -> resized
                video_clip = video_clip.resized(height=1920) 
                
                # KEY FIX: Loop video if shorter than required duration
                if video_clip.duration < clip_duration:
                    logger.info(f"Asset too short ({video_clip.duration}s < {clip_duration}s). Looping.")
                    # Calculate how many times to loop
                    loop_count = int(clip_duration // video_clip.duration) + 1
                    # Note: verify if concatenate_videoclips supports looping list correctly, it should.
                    video_clip = concatenate_videoclips([video_clip] * loop_count)
                
                # Trim to exact duration
                # MoviePy 2.x: subclip -> subclipped
                video_clip = video_clip.subclipped(0, clip_duration)
                
                # MoviePy 2.x: set_duration -> with_duration
                video_clip = video_clip.with_duration(clip_duration)
                
                clips.append(video_clip)
                
            except Exception as e:
                logger.error(f"Failed to process clip {scene.asset_path}: {e}")
                
        if not clips:
            logger.error("No clips were successfully processed.")
            return None
            
        final_video = concatenate_videoclips(clips)
        # MoviePy 2.x: set_audio -> with_audio
        final_video = final_video.with_audio(audio)
        
        output_path = os.path.join(settings.DATA_DIR, "renders", output_name)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        
        return output_path
        
    except Exception as e:
        logger.error(f"Video composition failed: {e}")
        return None
