def get_script_prompt(topic: str, video_type: str, tone: str, beats: list) -> str:
    format_instruction = "shoppable, fast-paced YouTube Short script (max 60 seconds)" if video_type == "short" else "engaging, well-paced YouTube Video script (5-10 minutes)"
    
    return f"""
Write a high-retention {format_instruction} about "{topic}".
The tone of the video should be {tone}.

Narrative Beats to follow:
{chr(10).join([f"- {beat}" for beat in beats])}

Rules for the script:
1. Start with a 5-second POWERFUL HOOK that immediately states why this matters.
2. Use simple, clear language. No jargon.
3. Keep sentences short for natural pacing.
4. No clickbait or exaggeration.
5. End with a natural call-to-action (CTA).

Output a JSON object with:
- script_text: The full script including speaker notes if necessary.
- estimated_runtime: integer seconds.
"""
