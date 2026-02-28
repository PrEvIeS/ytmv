# ytmv - Interactive Video/Audio Downloader

CLI wizard for downloading videos and audio from YouTube and 1000+ other sites.

## Project Overview

**Language**: Python 3.11+
**Package Manager**: pip / Homebrew
**Main file**: `ytmv.py` (single-file application)

## Commands

```bash
# Run the wizard
ytmv

# Show download history
ytmv --history

# Show config file location
ytmv --config

# Run tests
pytest tests/ -v

# Lint
flake8 ytmv.py tests/ --max-line-length=120 --ignore=E501,W503,E203

# Format
black ytmv.py tests/
isort --profile black ytmv.py tests/

# Pre-commit (all hooks)
pre-commit run --all-files
```

## Dependencies

### Runtime
- `click` - CLI framework
- `rich` - Console output
- `questionary` - Interactive prompts

### System (required)
- `yt-dlp` - Video downloader
- `ffmpeg` - Audio/video conversion

### Dev
- `pytest` - Testing
- `black` - Code formatter
- `isort` - Import sorter
- `flake8` - Linter
- `pre-commit` - Git hooks

## Architecture

```
ytmv.py
├── Configuration (DEFAULTS, CONFIG_FILE, HISTORY_FILE)
├── Data Classes (DownloadMode, DownloadOptions, VideoInfo)
├── Utility Functions
│   ├── transliterate() - Cyrillic to Latin
│   ├── sanitize_filename() - Clean filenames
│   └── run_with_retry() - Retry logic
├── History Functions
│   ├── add_to_history()
│   └── show_history()
├── URL/Info Functions
│   ├── is_playlist()
│   ├── get_video_info()
│   └── get_playlist_info()
├── Download Functions
│   ├── download_single()
│   ├── download_playlist()
│   ├── download_playlist_item() - parallel execution
│   ├── convert_file()
│   └── embed_metadata()
├── Wizard Steps
│   ├── prompt_url()
│   ├── show_preview()
│   ├── prompt_format()
│   ├── prompt_options()
│   ├── prompt_output_dir()
│   └── confirm_download()
└── main() - Entry point
```

## Key Patterns

### Parallel Downloads
Uses `ThreadPoolExecutor` with configurable workers (default: 3):
```python
parallel = int(get_config_value("parallel_downloads"))
with ThreadPoolExecutor(max_workers=parallel) as executor:
    futures = {executor.submit(download_playlist_item, ...): ...}
```

### Config System
- Config file: `~/.ytmvrc` (INI format)
- History file: `~/.ytmv_history` (JSON)
- Fallback to `DEFAULTS` dict

### Filename Sanitization
1. Transliterate Cyrillic to Latin
2. Remove special characters
3. Replace spaces with underscores
4. Limit to 200 chars

## Configuration

User config stored in `~/.ytmvrc`:
```ini
[settings]
output_dir_video = ~/Movies/shorts
output_dir_audio = ~/Movies/audios
video_quality = 1080
audio_quality = 192k
audio_format = m4a
download_thumbnails = false
download_subtitles = false
subtitle_lang = ru
parallel_downloads = 3
max_retries = 3
```

## CI/CD

- **Tests**: `.github/workflows/tests.yml` - pytest + flake8
- **Pre-commit**: `.github/workflows/pre-commit.yml` - black, isort, flake8
- **Dependabot**: `.github/dependabot.yml` - weekly updates for actions and pip

## Release Process

1. Update version in `ytmv.py` docstring
2. Push to main
3. Calculate new SHA256:
   ```bash
   curl -sL https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py | shasum -a 256
   ```
4. Update Homebrew formula in `homebrew-tap` repo
5. Reinstall: `brew reinstall previes/tap/ytmv`

## Notes

- Single-file application for easy distribution
- Tool paths hardcoded for macOS (`/opt/homebrew/bin/`)
- Supports back navigation in wizard (← Назад option)
- Handles file collisions with timestamp suffix
