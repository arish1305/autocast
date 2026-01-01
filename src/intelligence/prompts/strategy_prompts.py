def get_strategy_prompt(topic: str, summary: str, source_urls: list) -> str:
    return f"""
Analyze the following trending technology topic and define a content strategy for a YouTube video.

Topic: {topic}
Summary: {summary}
Sources: {', '.join(source_urls)}

Output a JSON object with the following fields:
- video_type: "short" or "long"
- duration_seconds: integer (max 60 for short, 300-600 for long)
- tone: string (e.g., "exciting", "educational", "critical", "futurist")
- narrative_beats: array of strings representing the key points of the story.

Rules:
1. If the topic is a quick update or single event, choose "short".
2. If the topic is complex or has deep implications, choose "long".
3. Ensure the tone matches the impact of the news.
"""
