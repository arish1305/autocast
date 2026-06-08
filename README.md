# AutoCast AI

AutoCast AI is an autonomous technology-news video generation pipeline. It discovers trending stories, verifies and ranks them, builds a semantic story context, writes a short-form script, creates narration, finds or generates scene-matched visuals, renders a vertical video, creates a thumbnail and metadata, and can publish privately to YouTube.

The main goal of this version is video quality: every scene should be tied to the narration instead of using random generic stock footage.

## What It Does

- Discovers technology trends from Hacker News and RSS feeds.
- Scores and verifies stories by freshness, engagement, source mentions, and authority.
- Filters stale content older than the configured freshness window.
- Builds story understanding: companies, products, organizations, technologies, people, locations, events, statistics, timelines, main story angle, and key talking points.
- Uses optional spaCy NER plus LLM-assisted extraction and strict entity filters.
- Generates strategy and script using local Ollama when available.
- Falls back to deterministic rule-based logic if Ollama is not running.
- Splits narration into scene-level visual plans with visual type, subjects, action, emotion, location, transition, and graphic type.
- Creates semantic stock-search queries for each scene instead of raw script fragments.
- Scores visual candidates by relevance and quality.
- Generates contextual fallback scene graphics when no good stock asset is found.
- Creates Edge-TTS narration and normalizes audio with ffmpeg.
- Renders vertical 9:16 video with MoviePy, captions, light motion, and transitions.
- Generates mobile-readable thumbnails with Pillow.
- Runs a quality audit before final rendering.
- Uploads privately to YouTube only when valid YouTube OAuth credentials/token are available.

## Tech Stack

- Python 3.10+
- Pydantic / Pydantic Settings
- Ollama for local LLM generation
- spaCy for optional local named-entity recognition
- Edge-TTS for narration
- MoviePy for video rendering
- Pillow and NumPy for graphics/captions
- Pexels and Pixabay APIs for free stock visuals
- YouTube Data API v3 for publishing

## Project Structure

```text
main.py                         Main orchestration entry point
test_quality_pipeline.py         Offline quality-pipeline smoke test
test_discovery.py                Trend discovery smoke test

src/core                         Settings, logger, LLM client, shared models
src/ingestion                    Hacker News, RSS, Reddit ingestion
src/intelligence                 Discovery, scoring, story understanding, script, audit
src/media                        TTS, audio normalization, assets, thumbnails, rendering
src/publishing                   Metadata and YouTube upload

data/audio                       Generated narration
data/assets                      Downloaded or generated scene visuals
data/thumbnails                  Generated thumbnails
data/renders                     Final videos
logs/app.log                     Runtime logs
```

## Requirements

Install these before running:

- Python 3.10 or newer
- ffmpeg
- Optional: Ollama, for better LLM-generated story/script/scene planning
- Optional: spaCy English model, for stronger local entity extraction
- Optional: Pexels API key, for stock video sourcing
- Optional: YouTube OAuth credentials, for upload

On Windows, verify Python:

```powershell
python --version
```

Verify ffmpeg:

```powershell
ffmpeg -version
```

If system ffmpeg is unavailable, MoviePy/imageio-ffmpeg can still help rendering, but installing ffmpeg globally is recommended.

## Setup

From the project folder:

```powershell
cd D:\autocast
```

Create a virtual environment if you do not already have one:

```powershell
python -m venv venv
```

Activate it:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the optional spaCy English model:

```powershell
python -m spacy download en_core_web_sm
```

If this model is not installed, AutoCast still runs with dictionary and rule-based entity extraction.

## Environment Configuration

Create `.env` from `.env.example` and fill in the values you want to use.

Minimum local configuration:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT_SECONDS=600
OLLAMA_RETRY_ATTEMPTS=3
TTS_VOICE=en-US-GuyNeural
NICHE=technology
LANGUAGE=en
REGION=US
VIDEO_FORMAT=short
UPLOAD_SCHEDULE=daily
TREND_MAX_AGE_DAYS=14
```

Optional stock-asset keys:

```env
PEXELS_API_KEY=your_pexels_api_key_here
PIXABAY_API_KEY=your_pixabay_api_key_here
```

Optional YouTube publishing:

```env
YOUTUBE_CLIENT_ID=your_youtube_client_id_here
YOUTUBE_CLIENT_SECRET=your_youtube_client_secret_here
```

Important: if YouTube credentials and a valid `token.pickle` are present, `main.py` can upload the rendered video as a private YouTube video. For local rendering only, leave YouTube credentials blank or run with blank YouTube environment variables.

## Optional Ollama Setup

Install Ollama, then pull a model:

```powershell
ollama pull mistral
```

Start Ollama:

```powershell
ollama serve
```

The system still runs without Ollama. In that case, it uses fallback strategy/script/scene logic.

You can verify Ollama is reachable:

```powershell
Invoke-RestMethod http://localhost:11434/api/tags
```

## How To Run

Use the virtual environment Python:

```powershell
.\venv\Scripts\python.exe main.py
```

The pipeline will:

1. Fetch trends.
2. Verify and rank them.
3. Select the top trend.
4. Build story context.
5. Generate strategy and script.
6. Create narration audio.
7. Source or generate visuals per scene.
8. Generate thumbnail.
9. Run quality audit.
10. Render the final video.
11. Generate metadata.
12. Publish only if YouTube is configured.

Outputs are written to:

```text
data/audio
data/assets
data/thumbnails
data/renders
```

The final video is usually:

```text
data/renders/trend_video_0.mp4
```

## Run Without Uploading To YouTube

PowerShell one-time local-render run:

```powershell
$env:YOUTUBE_CLIENT_ID=''
$env:YOUTUBE_CLIENT_SECRET=''
.\venv\Scripts\python.exe main.py
```

This still generates the video locally, but YouTube publishing is disabled for that process.

## Smoke Tests

Run the offline quality pipeline test:

```powershell
.\venv\Scripts\python.exe test_quality_pipeline.py
```

This does not require Ollama, Pexels, Pixabay, or YouTube. It verifies:

- story context generation
- entity filtering
- scene planning
- fallback visual generation
- thumbnail generation
- quality audit

Run discovery test:

```powershell
.\venv\Scripts\python.exe test_discovery.py
```

This verifies Hacker News/RSS trend ingestion and ranking.

Compile-check the project:

```powershell
.\venv\Scripts\python.exe -m compileall main.py test_quality_pipeline.py src
```

## YouTube Authentication

To publish to YouTube:

1. Add `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` to `.env`.
2. Run:

```powershell
.\venv\Scripts\python.exe setup_youtube_auth.py
```

3. Complete the browser OAuth flow.
4. A `token.pickle` file will be created.
5. Run:

```powershell
.\venv\Scripts\python.exe main.py
```

Videos are uploaded as private by default.

## Interview Explanation

A good summary:

> AutoCast AI is a Python pipeline that automates short-form tech-news video creation. It ingests trending stories, verifies them, understands the story semantically, writes a script, plans scene-level visuals, sources or generates matching assets, creates narration, renders a vertical video, generates thumbnail/metadata, audits quality, and can publish to YouTube.

Key architecture:

- `src/ingestion`: collects candidate news stories.
- `src/intelligence`: decides what story matters and how to tell it.
- `src/media`: turns the script into audio, visuals, thumbnails, captions, and video.
- `src/publishing`: prepares metadata and uploads to YouTube.

Most important improvement:

> The earlier issue was generic visuals. The upgrade adds story understanding, scene-level visual requirements, entity-aware search queries, asset relevance scoring, contextual fallback graphics, and a final quality audit.

V2 upgrade:

> The second upgrade adds stricter entity extraction with optional spaCy NER, stale-content filtering, semantic visual direction, parallel asset search, stronger asset thresholds for data/company scenes, scene transitions, Ken Burns-style motion for graphics, and stricter quality scoring.

Why it is robust:

> The system degrades gracefully. If Ollama fails, rule-based logic still works. If stock APIs fail, contextual visuals are generated locally. If YouTube credentials are missing, the final video is still rendered locally.

## Common Issues

Ollama connection refused:

```text
HTTPConnectionPool(host='localhost', port=11434)
```

Fix: start Ollama with `ollama serve`, or ignore it and use fallback mode.

spaCy model missing:

```text
spaCy model en_core_web_sm is not available
```

Fix:

```powershell
.\venv\Scripts\python.exe -m spacy download en_core_web_sm
```

This is optional. The app still runs with fallback entity extraction.

No Pixabay assets:

```text
PIXABAY_API_KEY not found
```

This is okay. Pexels or generated fallback visuals can still be used.

YouTube service not initialized:

```text
YouTube API credentials missing
```

This is okay for local rendering. Add credentials and run OAuth only if you want uploads.

YouTube OAuth `invalid_grant`:

```text
google.auth.exceptions.RefreshError: invalid_grant
```

This means `token.pickle` is expired, revoked, or does not match the current OAuth app credentials. Local rendering still works, but YouTube publishing is disabled until you re-authenticate.

Fix:

```powershell
Remove-Item .\token.pickle
.\venv\Scripts\python.exe setup_youtube_auth.py
```

Rendering is slow:

MoviePy rendering can be CPU-heavy, especially with 1080x1920 vertical clips. Let the command finish; output appears in `data/renders`.
