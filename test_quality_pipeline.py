from src.core.models import SourceInfo, TrendItem
from src.intelligence.quality_audit import audit_video_plan
from src.intelligence.scriptwriter import VideoScript
from src.intelligence.story_understanding import build_story_context
from src.media import asset_manager
from src.media import thumbnail_generator as thumbnail_module


def run_quality_pipeline_smoke_test():
    """Offline smoke test for story understanding, scene planning, assets, and audit."""
    asset_manager.llm_client.generate_json = lambda prompt: None
    thumbnail_module.llm_client.generate_json = lambda prompt: None
    asset_manager.pexels_client.api_key = None
    asset_manager.pixabay_client.api_key = None

    trend = TrendItem(
        topic="OpenAI releases GPT-5 for developers",
        summary=(
            "OpenAI announced GPT-5 with stronger coding, lower latency, "
            "and new developer tools for AI applications."
        ),
        sources=[
            SourceInfo(
                name="TechCrunch",
                url="https://example.com/openai-gpt5",
                external_id="demo",
            )
        ],
    )

    script = VideoScript(
        script_text=(
            "[HOOK] OpenAI just released GPT-5, and developers are watching closely. "
            "The big change is stronger coding with lower latency. "
            "That means AI apps could feel faster and more useful. "
            "But the real question is how quickly companies adopt it. "
            "Follow for the next update as this story develops."
        ),
        estimated_runtime=18,
    )

    context = build_story_context(trend, use_llm=False)
    bad_entities = {"Have", "Imagine", "What", "In", "This", "That"}
    assert not bad_entities.intersection(context.entities), context.entities
    assert "OpenAI" in context.companies, context.companies
    assert "GPT-5" in context.products, context.products

    scenes = asset_manager.break_script_into_scenes(script.script_text, context, script.estimated_runtime)
    scenes = asset_manager.source_visual_assets(scenes, context)
    thumbnail_path = thumbnail_module.thumbnail_generator.generate_thumbnail(trend.topic, context.story_summary)
    report = audit_video_plan(context, script, scenes, thumbnail_path)
    assert report.approved, report

    print("Story entities:", context.entities[:5])
    print("Scene count:", len(scenes))
    print("Asset types:", [scene.asset_type for scene in scenes])
    print("Thumbnail:", thumbnail_path)
    print("Quality approved:", report.approved)
    print("Overall score:", report.overall_score)


if __name__ == "__main__":
    run_quality_pipeline_smoke_test()
