def get_script_prompt(
    topic: str,
    video_type: str,
    tone: str,
    beats: list,
    story_context: str = "",
    research_context: str = "",
    min_runtime_seconds: int = 20,
) -> str:
    format_instruction = (
        f"data-rich, fast-paced YouTube Short script ({min_runtime_seconds}-45 seconds)"
        if video_type == "short"
        else "engaging, well-paced YouTube Video script (5-10 minutes)"
    )
    
    return f"""
Write a high-retention {format_instruction} about "{topic}".
The tone of the video should be {tone}.

Story context to stay accurate:
{story_context or 'No additional story context available.'}

Research brief:
{research_context or 'No source-backed research brief available.'}

Narrative Beats to follow:
{chr(10).join([f"- {beat}" for beat in beats])}

Rules for the script:
1. Start with a 5-second POWERFUL HOOK that immediately states why this matters.
2. Use simple, clear language. No jargon.
3. Keep sentences short for natural pacing.
4. No clickbait or exaggeration.
5. End with a natural call-to-action (CTA).
6. Use concrete entities, products, and numbers from the story context where available.
7. Make each sentence visually representable.
8. For Shorts, the narration must be at least {min_runtime_seconds} seconds and usually 70-100 words.
9. Include 2-4 source-backed facts from the research brief. Do not invent numbers, dates, products, people, or claims.
10. Do not include bracket labels like [HOOK], timestamps, markdown, scene notes, or speaker notes in script_text.

Output a JSON object with:
- script_text: The clean narration text only.
- estimated_runtime: integer seconds.
"""
