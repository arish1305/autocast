from src.core.logger import logger
from src.core.config import settings
from src.intelligence.discovery import discover_trends
from src.intelligence.story_understanding import build_story_context
from src.intelligence.strategy import create_content_strategy
from src.intelligence.scriptwriter import generate_script
from src.intelligence.quality_audit import audit_video_plan
from src.media.tts_engine import text_to_speech
from src.media.audio_utils import normalize_audio
from src.media.asset_manager import break_script_into_scenes, source_visual_assets
from src.media.rendering import render_final_video
from src.media.thumbnail_generator import thumbnail_generator
from src.publishing.metadata_optimizer import optimize_metadata
from src.publishing.publisher import publish_to_youtube

def main():
    """Main orchestration entry point for TrendPilot AI."""
    try:
        logger.info("Starting AutoCast AI...")
        logger.info(f"Niche: {settings.NICHE}, Format: {settings.VIDEO_FORMAT}")
        
        # Phase 2 & 3: Discovery & Verification
        trends = discover_trends()
        
        if trends:
            logger.info(f"Found {len(trends)} verified trends.")
            
            # Phase 4-11: Full Pipeline (Free Edition)
            for i, trend in enumerate(trends[:1]):
                story_context = build_story_context(trend)
                logger.info(
                    f"Story context ready: entities={story_context.entities[:5]}, "
                    f"technologies={story_context.technologies[:5]}"
                )

                strategy = create_content_strategy(trend, story_context)
                if strategy:
                    logger.info(f"Strategy for '{trend.topic}': {strategy.video_type}, {strategy.tone}")
                    
                    script = generate_script(
                        trend.topic, 
                        strategy.video_type, 
                        strategy.tone, 
                        strategy.narrative_beats,
                        story_context
                    )
                    
                    if script:
                        logger.info(f"Script Generated (Runtime: {script.estimated_runtime}s)")
                        
                        # Phase 6: Voice Synthesis (Local/Free)
                        audio_filename = f"trend_audio_{i}.mp3"
                        audio_path = text_to_speech(script.script_text, audio_filename)
                        if audio_path:
                            normalize_audio(audio_path)
                        else:
                            logger.error("Skipping video render because narration audio was not generated.")
                            continue
                            
                        # Phase 7: Visual Asset Generation
                        scenes = break_script_into_scenes(
                            script.script_text,
                            story_context,
                            strategy.duration_seconds or script.estimated_runtime,
                        )
                        scenes = source_visual_assets(scenes, story_context)
                        
                        # Phase 9: Thumbnail & Quality Audit
                        thumb_path = thumbnail_generator.generate_thumbnail(
                            trend.topic,
                            story_context.story_summary,
                        )
                        quality_report = audit_video_plan(story_context, script, scenes, thumb_path)
                        if not quality_report.approved:
                            logger.warning(
                                "Quality report did not fully approve the plan. "
                                "Rendering will continue with generated contextual fallbacks where needed."
                            )

                        # Phase 8: Video Composition & Rendering
                        render_path = render_final_video(audio_path, scenes, f"trend_video_{i}.mp4")
                        
                        # Phase 10: Metadata
                        metadata = optimize_metadata(trend.topic, script.script_text)
                        
                        # Phase 11: Publishing
                        if render_path and thumb_path and metadata:
                            youtube_url = publish_to_youtube(render_path, thumb_path, metadata)
                            if youtube_url:
                                logger.info(f"!!! PUBLISHED: {youtube_url}")
                            else:
                                logger.info("Local assets ready, but YouTube publishing was skipped/failed.")
                        
        else:
            logger.warning("No verified trends found during this cycle.")
        
        logger.info("AutoCast AI execution cycle complete.")
    except Exception as e:
        logger.critical(f"Critical failure: {e}")

if __name__ == "__main__":
    main()
