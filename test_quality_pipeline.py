from src.core.models import SourceInfo, TrendItem
from src.intelligence.content_corrector import correct_script_content
from src.intelligence.quality_audit import audit_video_plan
from src.intelligence.research import ResearchBrief, SourceSummary
from src.intelligence.scriptwriter import generate_script
from src.intelligence.story_understanding import build_story_context
from src.media import asset_manager
from src.media import thumbnail_generator as thumbnail_module


def run_quality_pipeline_smoke_test():
    """Offline smoke test for story understanding, scene planning, assets, and audit."""
    asset_manager.llm_client.generate_json = lambda prompt: {
        "script_text": "Read https://example.com/openai-gpt5 because OpenAI released GPT-5.",
        "estimated_runtime": 5,
    }
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

    context = build_story_context(trend, use_llm=False)
    bad_entities = {"Have", "Imagine", "What", "In", "This", "That"}
    assert not bad_entities.intersection(context.entities), context.entities
    assert "OpenAI" in context.companies, context.companies
    assert "GPT-5" in context.products, context.products

    research = ResearchBrief(
        topic=trend.topic,
        source_count=1,
        source_names=["TechCrunch"],
        source_urls=["https://example.com/openai-gpt5"],
        source_summaries=[
            SourceSummary(
                source_name="TechCrunch",
                url="https://example.com/openai-gpt5",
                title="OpenAI releases GPT-5 for developers",
                description="OpenAI announced GPT-5 with stronger coding, lower latency, and new developer tools.",
                key_points=[
                    "OpenAI announced GPT-5 with stronger coding, lower latency, and new developer tools for AI applications.",
                    "The release is aimed at developers building faster AI products and coding workflows.",
                ],
            )
        ],
        verified_facts=[
            "OpenAI announced GPT-5 with stronger coding, lower latency, and new developer tools for AI applications.",
            "The release is aimed at developers building faster AI products and coding workflows.",
            "Developers are watching adoption because latency and coding quality affect real AI app performance.",
        ],
        statistics=[],
    )
    script = generate_script(
        trend.topic,
        "short",
        "informative",
        ["Hook", "What changed", "Why it matters", "Impact", "CTA"],
        context,
        research,
        20,
    )
    script = correct_script_content(
        trend.topic,
        script,
        context,
        research,
        "short",
        "informative",
        20,
    )
    assert script.estimated_runtime >= 20, script
    assert len(script.script_text.split()) >= 70, script.script_text
    assert "[" not in script.script_text, script.script_text
    assert "http" not in script.script_text.lower(), script.script_text
    assert ".com" not in script.script_text.lower(), script.script_text
    assert "source coverage" not in script.script_text.lower(), script.script_text
    assert "message" in script.script_text.lower() or "takeaway" in script.script_text.lower(), script.script_text

    asset_manager.llm_client.generate_json = lambda prompt: None
    thumbnail_module.llm_client.generate_json = lambda prompt: None

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
