# AutoCast AI (Free Edition) 🚀

AutoCast AI is a **zero-cost, fully autonomous** system designed to identify trending technology news, verify facts, generate high-retention scripts, and produce professional video content using only local and open-source tools.

## 🌟 Features (Free Edition)

- **Local Intelligence**: Uses **Ollama** (Mistral/Phi-3) for zero-cost content analysis and scriptwriting.
- **High-Quality Free Voice**: Integrates **Edge-TTS** for professional neural narration without API costs.
- **Smart Asset Sourcing**: Automated fetching from Pexels/Pixabay free tiers.
- **Local Thumbnails**: Programmatic thumbnail generation using PIL, optimized for mobile visibility.
- **Zero Dependencies on Paid APIs**: Built to run continuously on consumer hardware.

## 🛠️ Tech Stack

- **Core**: Python 3.10+
- **LLM**: OpenAI GPT-4o
- **Media**: MoviePy, ElevenLabs, gTTS, Pexels API, DALL-E 3
- **Publishing**: YouTube Data API v3
- **DevOps**: Pydantic Settings, Structured Logging

## 🚀 Getting Started

### 1. Prerequisites
- Python installed on your system.
- `ffmpeg` installed (required for MoviePy rendering).

### 2. Installation
```powershell
# Clone the repository (if applicable)
# cd autocast

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Rename `.env.example` to `.env` and configure your local/free services:
- `OLLAMA_BASE_URL`: Usually `http://localhost:11434`.
- `OLLAMA_MODEL`: Default `mistral` (ensure you've run `ollama pull mistral`).
- `TTS_VOICE`: The Edge-TTS voice to use (e.g., `en-US-GuyNeural`).
- `PEXELS_API_KEY` & `PIXABAY_API_KEY`: Optional but recommended for stock visuals.
- `YOUTUBE_CLIENT_ID` & `YOUTUBE_CLIENT_SECRET`: For automated publishing.

### 4. Running the System
```powershell
python main.py
```

## 📁 Project Structure

- `src/ingestion`: APIs and scrapers for trend discovery.
- `src/intelligence`: LLM agents for verification, strategy, and scripting.
- `src/media`: Engines for TTS, asset sourcing, and video rendering.
- `src/publishing`: SEO optimization and YouTube API integration.
- `data/`: Local storage for generated audio, assets, thumbnails, and renders.
- `logs/`: Application execution logs.

## 🛡️ License
MIT License - Created with love by Antigravity.
