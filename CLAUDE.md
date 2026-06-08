# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Audiobook video production system: PDF + audio + SRT subtitles → synchronized MP4 with burned-in subtitles and optional text highlighting. Chinese classical literature focus (红楼梦, 金瓶梅, 蘇東坡新傳).

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run web app
python app.py --port 5005

# CLI: PDF + audio + subtitles → video
python create_video.py --pdf in.pdf --audio in.m4a --subs in.srt --output out.mp4
python create_video.py --pdf in.pdf --audio in.m4a --subs in.srt --output out.mp4 --start-page 5 --end-page 15

# Run module tests
pytest test_pdf_text_extractor.py test_text_mapping_engine.py test_highlight_renderer.py -v

# Quick smoke test for all module imports
./test_all_modules.sh
```

## Architecture

### Core Pipeline (Phase 1)
`app.py` (Flask + SocketIO web server) → `create_video.py` (video engine)

`create_video.py` workflow:
1. `convert_pdf_to_images()` — PyMuPDF renders PDF pages to PNG (supports vertical 2-page spreads, configurable crop)
2. `get_audio_duration()` — ffprobe extracts audio length
3. Page timing: auto-calculated from audio duration or manual via `config.json`
4. `create_silent_video()` — ffmpeg encodes image sequence to silent H.264 video
5. `merge_audio_video()` — ffmpeg muxes audio stream
6. `burn_subtitles()` — ffmpeg burns SRT subtitles into video frames

### Highlight Pipeline (Phase 2)
Enabled when `HIGHLIGHT_AVAILABLE = True` in `create_video.py`. Five modules:

| Module | Role |
|---|---|
| `pdf_text_extractor.py` | Extracts text + character-level (x,y,w,h) coordinates from PDF via PyMuPDF |
| `subtitle_parser.py` | Parses SRT into `SubtitleSegment` list (index, start/end time, text) |
| `text_mapping_engine.py` | Maps subtitle text → PDF character ranges using `SequenceMatcher`, outputs `SubtitleMapping` with page + coordinate rectangles |
| `highlight_renderer.py` | PIL-based: draws semi-transparent highlight rectangles on page images per subtitle timing |
| `video_composition_coordinator.py` | Orchestrates the 4 modules above; `VideoConfig` controls quality, layout, transitions |

### Subtitle Tooling
- `subtitle_parser.py` — standard SRT parser
- `subtitle_validator.py` — detects/repairs malformed SRT timecodes (4+ digit milliseconds, etc.)
- `subtitle_format_validator.py` — pure format validation, no AI
- `strict_timecode_validation.py` — strict HH:MM:SS,mmm enforcement
- `pure_format_fixer.py` — format-only fixes

### AI Integration
- `deepseek_api.py` — `DeepSeekAPI` class: REST client for DeepSeek chat API, used for subtitle text correction
- `model_manager.py` — Whisper model detection (checks `~/.cache/whisper/models/`) and download management
- Both `faster-whisper` and `openai-whisper` supported; `faster-whisper` preferred

### Web Frontend
- `templates/index.html` — single-page app with drag-drop upload, page timing editor, progress via WebSocket
- `static/js/app.js` — file upload, WebSocket log streaming, job management
- Flask-SocketIO for real-time progress/log streaming to browser

## Data Layout

```
电子书/
  [书名]/
    原始文本/     # Source PDF/EPUB
    音频文件/     # .m4a/.mp3 audio
    字幕文件/     # .srt subtitles
    有声读物/     # Generated .mp4 + config.json
    配置信息/     # pageTimings, cropSettings per chapter
```

## Key Dependencies

- **PyMuPDF** (fitz) — PDF rendering and text extraction
- **FFmpeg/ffprobe** — must be in PATH; video encoding, audio muxing, subtitle burning
- **Pillow** — highlight rendering on images
- **faster-whisper** — speech-to-text for subtitle generation
- **Flask-SocketIO** — real-time WebSocket communication

## Configuration

- `config.py` — `DEFAULT_SETTINGS` (books root, default book, API keys), `WHISPER_MODELS` dict
- `config.json` — per-chapter settings: `pageTimings`, `startPage`, `endPage`, `verticalLayout`, `cropSettings`, `audioFilename`, `subtitleFilename`
- API key for DeepSeek in `config.py` or env var `DEEPSEEK_API_KEY`
