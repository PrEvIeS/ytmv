#!/usr/bin/env python3
"""
Universal video/audio downloader with Russian transliteration support.
Interactive CLI wizard for downloading videos and playlists from 1000+ sites.
"""

from __future__ import annotations

import configparser
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

import click
import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn, TaskProgressColumn
from rich.table import Table
from rich.traceback import install

install(show_locals=True)

console = Console()

# ============== Configuration ==============

CONFIG_FILE = Path.home() / ".ytmvrc"
HISTORY_FILE = Path.home() / ".ytmv_history"

# Default config values
DEFAULTS = {
    'output_dir_video': '~/Movies/shorts',
    'output_dir_audio': '~/Movies/audios',
    'video_quality': '1080',
    'audio_quality': '192k',
    'audio_format': 'm4a',
    'download_thumbnails': 'false',
    'download_subtitles': 'false',
    'subtitle_lang': 'ru',
    'parallel_downloads': '3',
    'max_retries': '3',
}

# Custom style for questionary
CUSTOM_STYLE = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:green bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('instruction', 'fg:yellow'),
])

# Quality options
VIDEO_QUALITIES = {
    '4K (2160p)': '2160',
    '1080p': '1080',
    '720p': '720',
    '480p': '480',
    '360p': '360',
    'Лучшее доступное': 'best',
}

AUDIO_QUALITIES = {
    '320 kbps': '320k',
    '256 kbps': '256k',
    '192 kbps': '192k',
    '128 kbps': '128k',
}

AUDIO_FORMATS = {
    'M4A (AAC)': 'm4a',
    'MP3': 'mp3',
    'FLAC': 'flac',
    'OPUS': 'opus',
}

SUBTITLE_LANGS = {
    'Русский': 'ru',
    'English': 'en',
    'Auto': 'auto',
}

# Russian to Latin transliteration table
TRANSLIT_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ї': 'yi', 'і': 'i', 'ґ': 'g', 'є': 'ye',
}

# Full paths for tools
TOOL_PATHS = {
    'yt-dlp': '/opt/homebrew/bin/yt-dlp',
    'ffmpeg': '/opt/homebrew/bin/ffmpeg',
}


# ============== Data Classes ==============

class DownloadMode(Enum):
    VIDEO = 'video'
    AUDIO = 'audio'


@dataclass
class DownloadOptions:
    mode: DownloadMode = DownloadMode.VIDEO
    video_quality: str = '1080'
    audio_quality: str = '192k'
    audio_format: str = 'm4a'
    output_dir: Path = field(default_factory=lambda: Path('~/Movies/shorts').expanduser())
    download_thumbnail: bool = False
    download_subtitles: bool = False
    subtitle_lang: str = 'ru'
    playlist_start: int = 1
    playlist_end: Optional[int] = None
    cookies_file: Optional[Path] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class VideoInfo:
    url: str
    title: str
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    description: Optional[str] = None


# ============== Utility Functions ==============

def load_config() -> configparser.ConfigParser:
    """Load configuration from file."""
    config = configparser.ConfigParser()
    if CONFIG_FILE.exists():
        config.read(CONFIG_FILE)
    if 'settings' not in config:
        config['settings'] = {}
    return config


def save_config(config: configparser.ConfigParser):
    """Save configuration to file."""
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)


def get_config_value(key: str) -> str:
    """Get config value with fallback to default."""
    config = load_config()
    return config['settings'].get(key, DEFAULTS.get(key, ''))


def set_config_value(key: str, value: str):
    """Set config value."""
    config = load_config()
    config['settings'][key] = value
    save_config(config)


def transliterate(text: str) -> str:
    """Transliterate Cyrillic text to Latin."""
    result = []
    for char in text.lower():
        if char in TRANSLIT_TABLE:
            result.append(TRANSLIT_TABLE[char])
        elif char.isalnum() or char in ' _-':
            result.append(char)
    return ''.join(result)


def sanitize_filename(name: str) -> str:
    """Sanitize filename: transliterate, replace spaces, remove unsafe chars."""
    name = transliterate(name)
    name = name.encode('ascii', 'ignore').decode('ascii')
    name = re.sub(r'[_\s]+', '_', name)
    name = re.sub(r'[^A-Za-z0-9_-]', '', name)
    name = name.strip('_-')
    if len(name) > 200:
        name = name[:200]
    return name or 'video'


def check_dependencies():
    """Check if required tools are installed."""
    for tool, path in TOOL_PATHS.items():
        try:
            flag = '-version' if tool == 'ffmpeg' else '--version'
            subprocess.run([path, flag], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print(f"[bold red]Error:[/bold red] {tool} not found at {path}. Install with: brew install {tool}")
            raise SystemExit(1)


def cleanup_temp_files(output_dir: Path, pattern: str = "*.tmp*"):
    """Remove orphaned temp files."""
    for tmp in output_dir.glob(pattern):
        try:
            tmp.unlink()
        except OSError:
            pass


def handle_collision(output_file: Path) -> Path:
    """Add timestamp suffix if file exists."""
    if output_file.exists():
        stem = output_file.stem
        suffix = output_file.suffix
        new_name = f"{stem}_{int(time.time())}{suffix}"
        return output_file.parent / new_name
    return output_file


def run_with_retry(cmd: list, max_retries: int = 3, **kwargs) -> subprocess.CompletedProcess:
    """Run command with retry on failure."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return subprocess.run(cmd, check=True, **kwargs)
        except subprocess.CalledProcessError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                console.print(f"[yellow]Retry {attempt + 1}/{max_retries} in {wait_time}s...[/yellow]")
                time.sleep(wait_time)
    raise last_error


# ============== History Functions ==============

def add_to_history(url: str, title: str, output_path: str, mode: str):
    """Add download to history."""
    entry = {
        'timestamp': datetime.now().isoformat(),
        'url': url,
        'title': title,
        'output': output_path,
        'mode': mode,
    }

    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass

    history.insert(0, entry)
    history = history[:100]  # Keep last 100 entries

    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def show_history():
    """Show download history."""
    if not HISTORY_FILE.exists():
        console.print("[yellow]История пуста[/yellow]")
        return

    try:
        with open(HISTORY_FILE, 'r') as f:
            history = json.load(f)
    except (json.JSONDecodeError, IOError):
        console.print("[yellow]История пуста[/yellow]")
        return

    if not history:
        console.print("[yellow]История пуста[/yellow]")
        return

    table = Table(title="История скачиваний")
    table.add_column("Дата", style="cyan")
    table.add_column("Название", style="green")
    table.add_column("Режим", style="yellow")

    for entry in history[:20]:
        dt = datetime.fromisoformat(entry['timestamp']).strftime('%d.%m %H:%M')
        title = entry['title'][:40] + '...' if len(entry['title']) > 40 else entry['title']
        table.add_row(dt, title, entry['mode'])

    console.print(table)


# ============== URL/Info Functions ==============

def is_playlist(url: str) -> bool:
    """Check if URL is a playlist."""
    return 'list=' in url or 'playlist?' in url


def get_video_info(url: str) -> VideoInfo:
    """Get detailed video information."""
    try:
        result = subprocess.run(
            [TOOL_PATHS['yt-dlp'], '--dump-json', '--no-warnings', url],
            capture_output=True, text=True, check=True
        )
        data = json.loads(result.stdout)
        return VideoInfo(
            url=url,
            title=data.get('title', 'Unknown'),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            uploader=data.get('uploader'),
            description=data.get('description'),
        )
    except subprocess.CalledProcessError:
        # Fallback to just title
        title = get_video_title(url)
        return VideoInfo(url=url, title=title)


def get_video_title(url: str) -> str:
    """Get single video title."""
    try:
        result = subprocess.run(
            [TOOL_PATHS['yt-dlp'], '--get-title', '--no-warnings', url],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error fetching video info:[/bold red] {e.stderr or str(e)}")
        raise SystemExit(1)


def get_playlist_info(url: str) -> dict:
    """Get playlist information."""
    try:
        result = subprocess.run(
            [TOOL_PATHS['yt-dlp'], '--dump-json', '--flat-playlist', '--no-warnings', url],
            capture_output=True, text=True, check=True
        )
        entries = [json.loads(line) for line in result.stdout.strip().split('\n') if line]
        return {
            'count': len(entries),
            'entries': entries
        }
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Error getting playlist info:[/bold red] {e.stderr or str(e)}")
        raise SystemExit(1)


# ============== Download Functions ==============

def download_thumbnail(url: str, output_path: Path) -> Optional[Path]:
    """Download video thumbnail."""
    try:
        thumb_path = output_path.with_suffix('.jpg')
        subprocess.run([
            TOOL_PATHS['yt-dlp'],
            '--write-thumbnail',
            '--skip-download',
            '-o', str(output_path.with_suffix('')),
            url
        ], check=True, capture_output=True)

        # Find and rename thumbnail
        for f in output_path.parent.glob(f"{output_path.stem}.*"):
            if f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']:
                if f != thumb_path:
                    f.rename(thumb_path)
                return thumb_path
    except Exception:
        pass
    return None


def download_subtitles(url: str, output_path: Path, lang: str = 'ru') -> Optional[Path]:
    """Download video subtitles."""
    try:
        sub_lang = '' if lang == 'auto' else lang
        subprocess.run([
            TOOL_PATHS['yt-dlp'],
            '--write-subs', '--write-auto-subs' if lang == 'auto' else '--write-subs',
            '--sub-lang', sub_lang if sub_lang else 'all',
            '--skip-download',
            '-o', str(output_path.with_suffix('')),
            url
        ], check=True, capture_output=True)

        # Find subtitle file
        for f in output_path.parent.glob(f"{output_path.stem}.*.vtt"):
            return f
        for f in output_path.parent.glob(f"{output_path.stem}.*.srt"):
            return f
    except Exception:
        pass
    return None


def embed_metadata(input_file: Path, output_file: Path, info: VideoInfo, thumbnail_path: Optional[Path] = None):
    """Embed metadata into audio file."""
    cmd = [TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file)]

    # Add metadata
    metadata = []
    if info.title:
        metadata.append(f'title={info.title}')
    if info.uploader:
        metadata.append(f'artist={info.uploader}')

    for m in metadata:
        cmd.extend(['-metadata', m])

    # Add thumbnail if available
    if thumbnail_path and thumbnail_path.exists():
        cmd.extend(['-i', str(thumbnail_path), '-map', '0', '-map', '1', '-c:v', 'mjpeg', '-disposition:v:0', 'attached_pic'])

    cmd.append(str(output_file))

    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError:
        # Fallback without thumbnail
        subprocess.run([
            TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file),
            '-c', 'copy'
        ] + [arg for m in metadata for arg in ['-metadata', m]] + [str(output_file)],
            check=True, capture_output=True)


def convert_file(input_file: Path, output_file: Path, options: DownloadOptions,
                 info: Optional[VideoInfo] = None, quiet: bool = False):
    """Convert downloaded file to final format."""
    if options.mode == DownloadMode.AUDIO:
        fmt = options.audio_format
        codec_map = {
            'm4a': ('aac', options.audio_quality),
            'mp3': ('libmp3lame', options.audio_quality),
            'flac': ('flac', '8'),
            'opus': ('libopus', '192k'),
        }
        codec, quality = codec_map.get(fmt, ('aac', '192k'))

        status = console.status(f"[bold yellow]Converting to {fmt.upper()}...") if not quiet else None
        if status:
            status.__enter__()

        try:
            cmd = [
                TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file),
                '-c:a', codec, '-b:a', quality,
            ]

            # Add metadata if we have info
            if info:
                if info.title:
                    cmd.extend(['-metadata', f'title={info.title}'])
                if info.uploader:
                    cmd.extend(['-metadata', f'artist={info.uploader}'])

            cmd.append(str(output_file))
            subprocess.run(cmd, check=True, capture_output=True)

            # Try to embed thumbnail for m4a/mp3
            if info and fmt in ('m4a', 'mp3') and options.download_thumbnail:
                # Download thumbnail for embedding
                thumb_temp = input_file.parent / f"{input_file.stem}_thumb"
                thumb_path = download_thumbnail(info.url, thumb_temp)
                if thumb_path:
                    temp_output = output_file.with_suffix(f'.tmp{output_file.suffix}')
                    embed_metadata(output_file, temp_output, info, thumb_path)
                    if temp_output.exists():
                        output_file.unlink()
                        temp_output.rename(output_file)
                    thumb_path.unlink()

        except subprocess.CalledProcessError as e:
            if not quiet:
                console.print(f"[bold red]Conversion failed:[/bold red] {e.stderr.decode() if e.stderr else str(e)}")
            raise SystemExit(1)
        finally:
            if status:
                status.__exit__(None, None, None)

    else:  # VIDEO mode
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            console=console,
            disable=quiet
        ) as progress:
            task = progress.add_task("[bold yellow]Converting to MP4...", total=100)

            try:
                cmd = [
                    TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file),
                    '-c:v', 'libx264', '-preset', 'fast',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-movflags', '+faststart',
                ]

                # Add scale filter for quality
                if options.video_quality != 'best':
                    cmd.extend(['-vf', f"scale=-2:{options.video_quality}"])

                cmd.append(str(output_file))
                subprocess.run(cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                if not quiet:
                    console.print(f"[bold red]Conversion failed:[/bold red] {e.stderr.decode() if e.stderr else str(e)}")
                raise SystemExit(1)

            progress.update(task, completed=100)


def download_single(url: str, options: DownloadOptions) -> Path:
    """Download a single video/audio."""
    info = get_video_info(url)
    safe_name = sanitize_filename(info.title)

    if options.mode == DownloadMode.AUDIO:
        ext = options.audio_format
    else:
        ext = 'mp4'

    output_file = options.output_dir / f"{safe_name}.{ext}"
    output_file = handle_collision(output_file)

    console.print(f"[bold cyan]Название:[/bold cyan] {info.title}")
    console.print(f"[bold cyan]Файл:[/bold cyan] {output_file}")

    temp_base = options.output_dir / f"{safe_name}.tmp"

    # Build yt-dlp format string
    if options.mode == DownloadMode.AUDIO:
        fmt = 'bestaudio/best'
    else:
        if options.video_quality == 'best':
            fmt = 'bestvideo+bestaudio/best'
        else:
            fmt = f'bestvideo[height<={options.video_quality}]+bestaudio/best[height<={options.video_quality}]'

    # Build download command
    cmd = [
        TOOL_PATHS['yt-dlp'],
        '-f', fmt,
        '-o', str(temp_base) + '.%(ext)s',
        '--newline',
        '--no-playlist',
    ]

    # Add cookies if provided
    if options.cookies_file:
        cmd.extend(['--cookies', str(options.cookies_file)])

    cmd.append(url)

    console.print("[bold yellow]Скачивание...[/bold yellow]")

    try:
        run_with_retry(cmd, max_retries=int(get_config_value('max_retries')))
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Ошибка скачивания:[/bold red] {e.stderr or str(e)}")
        for tmp in options.output_dir.glob(f"{safe_name}.tmp.*"):
            tmp.unlink()
        raise SystemExit(1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Скачивание отменено[/bold yellow]")
        for tmp in options.output_dir.glob(f"{safe_name}.tmp.*"):
            tmp.unlink()
        raise SystemExit(130)

    # Find downloaded file
    temp_files = list(options.output_dir.glob(f"{safe_name}.tmp.*"))
    if not temp_files:
        console.print("[bold red]Ошибка:[/bold red] Скачанный файл не найден")
        raise SystemExit(1)
    temp_file = temp_files[0]

    # Download thumbnail
    if options.download_thumbnail:
        console.print("[dim]Скачивание превью...[/dim]")
        download_thumbnail(url, output_file.with_suffix(''))

    # Download subtitles
    if options.download_subtitles:
        console.print("[dim]Скачивание субтитров...[/dim]")
        download_subtitles(url, output_file, options.subtitle_lang)

    # Convert
    convert_file(temp_file, output_file, options, info)

    # Cleanup
    if temp_file.exists():
        temp_file.unlink()

    # Add to history
    add_to_history(url, info.title, str(output_file), options.mode.value)

    return output_file


def download_playlist_item(entry: dict, idx: int, options: DownloadOptions, total: int) -> tuple[bool, str, Optional[Path]]:
    """Download single playlist item (for parallel execution)."""
    video_url = entry.get('url') or entry.get('id')
    if video_url and not video_url.startswith('http'):
        video_url = f"https://www.youtube.com/watch?v={video_url}"

    title = entry.get('title', f'Video {idx}')
    safe_name = sanitize_filename(title)
    indexed_name = f"{idx:02d}_{safe_name}"

    if options.mode == DownloadMode.AUDIO:
        ext = options.audio_format
    else:
        ext = 'mp4'

    output_file = options.output_dir / f"{indexed_name}.{ext}"
    output_file = handle_collision(output_file)

    temp_base = options.output_dir / f"{indexed_name}.tmp"

    # Build format string
    if options.mode == DownloadMode.AUDIO:
        fmt = 'bestaudio/best'
    else:
        if options.video_quality == 'best':
            fmt = 'bestvideo+bestaudio/best'
        else:
            fmt = f'bestvideo[height<={options.video_quality}]+bestaudio/best[height<={options.video_quality}]'

    cmd = [
        TOOL_PATHS['yt-dlp'],
        '-f', fmt,
        '-o', str(temp_base) + '.%(ext)s',
        '--newline',
        '--no-playlist',
    ]

    if options.cookies_file:
        cmd.extend(['--cookies', str(options.cookies_file)])

    cmd.append(video_url)

    try:
        run_with_retry(cmd, max_retries=int(get_config_value('max_retries')), capture_output=True)

        temp_files = list(options.output_dir.glob(f"{indexed_name}.tmp.*"))
        if temp_files:
            temp_file = temp_files[0]

            # Get video info for metadata
            try:
                info = get_video_info(video_url)
            except Exception:
                info = VideoInfo(url=video_url, title=title)

            # Download thumbnail
            if options.download_thumbnail:
                download_thumbnail(video_url, output_file.with_suffix(''))

            # Download subtitles
            if options.download_subtitles:
                download_subtitles(video_url, output_file, options.subtitle_lang)

            convert_file(temp_file, output_file, options, info, quiet=True)

            if temp_file.exists():
                temp_file.unlink()

            return True, title, output_file
        else:
            return False, title, None

    except Exception:
        return False, title, None


def download_playlist(url: str, options: DownloadOptions) -> list[Path]:
    """Download playlist with parallel support."""
    playlist_info = get_playlist_info(url)
    total = playlist_info['count']

    # Apply range filter
    start = max(1, options.playlist_start)
    end = min(total, options.playlist_end) if options.playlist_end else total
    entries = playlist_info['entries'][start - 1:end]
    actual_total = len(entries)

    console.print(Panel.fit(
        f"[bold cyan]Плейлист:[/bold cyan] {total} треков\n"
        f"[bold cyan]Скачиваем:[/bold cyan] {start}-{end} ({actual_total} треков)\n"
        f"[bold cyan]Режим:[/bold cyan] {options.mode.value}\n"
        f"[bold cyan]Папка:[/bold cyan] {options.output_dir}",
        title="[bold green]YouTube Playlist Downloader[/bold green]"
    ))

    downloaded_files = []
    failed = []
    parallel = int(get_config_value('parallel_downloads'))

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        main_task = progress.add_task("[yellow]Скачивание плейлиста...", total=actual_total)

        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(download_playlist_item, entry, start + idx, options, actual_total): entry
                for idx, entry in enumerate(entries)
            }

            for future in as_completed(futures):
                success, title, output_file = future.result()

                if success and output_file:
                    downloaded_files.append(output_file)
                    console.print(f"  [green]✓[/green] {title[:50]}")
                else:
                    failed.append(title)
                    console.print(f"  [red]✗[/red] {title[:50]}")

                progress.advance(main_task)

    # Add to history
    add_to_history(url, f"Playlist ({actual_total} items)", str(options.output_dir), f"playlist_{options.mode.value}")

    if failed:
        console.print(f"\n[yellow]Не удалось скачать {len(failed)} треков[/yellow]")

    return downloaded_files


# ============== Wizard Steps ==============

class WizardState:
    """Track wizard state for back navigation."""
    def __init__(self):
        self.step = 0
        self.url = ''
        self.info = {}
        self.options = DownloadOptions()

    def go_back(self):
        """Go to previous step."""
        if self.step > 0:
            self.step -= 1
            return True
        return False


def prompt_url(state: WizardState) -> bool:
    """Step 1: Enter URL."""
    url = questionary.text(
        "Введите URL видео или плейлиста:",
        style=CUSTOM_STYLE,
        default=state.url,
        validate=lambda x: len(x) > 0 or "Введите URL"
    ).ask()

    if url is None:
        return False

    state.url = url.strip()
    return True


def show_preview(state: WizardState) -> bool:
    """Step 2: Show preview."""
    console.print("\n[dim]Получение информации...[/dim]")

    if is_playlist(state.url):
        playlist_info = get_playlist_info(state.url)
        count = playlist_info['count']
        console.print(Panel.fit(
            f"[bold cyan]Тип:[/bold cyan] Плейлист\n"
            f"[bold cyan]Количество треков:[/bold cyan] {count}",
            title="[bold green]Предпросмотр[/bold green]"
        ))
        state.info = {'type': 'playlist', 'count': count, 'info': playlist_info}
    else:
        info = get_video_info(state.url)
        title_extra = f"\n[bold cyan]Автор:[/bold cyan] {info.uploader}" if info.uploader else ""
        console.print(Panel.fit(
            f"[bold cyan]Тип:[/bold cyan] Видео\n"
            f"[bold cyan]Название:[/bold cyan] {info.title}{title_extra}",
            title="[bold green]Предпросмотр[/bold green]"
        ))
        state.info = {'type': 'video', 'title': info.title, 'video_info': info}

    return True


def prompt_format(state: WizardState) -> bool:
    """Step 3: Select format and quality."""
    # Mode selection
    mode = questionary.select(
        "Выберите формат:",
        choices=[
            questionary.Choice("🎥 Видео", value="video"),
            questionary.Choice("🎵 Аудио", value="audio"),
            questionary.Choice("← Назад", value="back"),
        ],
        style=CUSTOM_STYLE
    ).ask()

    if mode is None:
        return False
    if mode == 'back':
        return state.go_back()

    state.options.mode = DownloadMode(mode)

    # Quality selection
    if state.options.mode == DownloadMode.VIDEO:
        quality = questionary.select(
            "Выберите качество видео:",
            choices=[
                questionary.Choice(k, value=v) for k, v in VIDEO_QUALITIES.items()
            ] + [questionary.Choice("← Назад", value="back")],
            style=CUSTOM_STYLE,
            default=get_config_value('video_quality')
        ).ask()

        if quality == 'back':
            return state.go_back()
        state.options.video_quality = quality

    else:  # AUDIO
        # Audio format
        audio_fmt = questionary.select(
            "Выберите формат аудио:",
            choices=[
                questionary.Choice(k, value=v) for k, v in AUDIO_FORMATS.items()
            ] + [questionary.Choice("← Назад", value="back")],
            style=CUSTOM_STYLE,
            default=get_config_value('audio_format')
        ).ask()

        if audio_fmt == 'back':
            return state.go_back()
        state.options.audio_format = audio_fmt

        # Audio quality
        quality = questionary.select(
            "Выберите качество аудио:",
            choices=[
                questionary.Choice(k, value=v) for k, v in AUDIO_QUALITIES.items()
            ] + [questionary.Choice("← Назад", value="back")],
            style=CUSTOM_STYLE,
            default=get_config_value('audio_quality')
        ).ask()

        if quality == 'back':
            return state.go_back()
        state.options.audio_quality = quality

    return True


def prompt_options(state: WizardState) -> bool:
    """Step 4: Additional options."""
    # Thumbnail
    thumbnail = questionary.confirm(
        "Скачать превью (thumbnail)?",
        default=get_config_value('download_thumbnails').lower() == 'true',
        style=CUSTOM_STYLE
    ).ask()

    if thumbnail is None:
        return False
    state.options.download_thumbnail = thumbnail

    # Subtitles (only for video)
    if state.options.mode == DownloadMode.VIDEO:
        subtitles = questionary.confirm(
            "Скачать субтитры?",
            default=get_config_value('download_subtitles').lower() == 'true',
            style=CUSTOM_STYLE
        ).ask()

        if subtitles is None:
            return False
        state.options.download_subtitles = subtitles

        if subtitles:
            lang = questionary.select(
                "Язык субтитров:",
                choices=[
                    questionary.Choice(k, value=v) for k, v in SUBTITLE_LANGS.items()
                ],
                style=CUSTOM_STYLE,
                default=get_config_value('subtitle_lang')
            ).ask()

            if lang is None:
                return False
            state.options.subtitle_lang = lang

    # Playlist range
    if state.info.get('type') == 'playlist':
        use_range = questionary.confirm(
            "Скачать часть плейлиста (диапазон)?",
            default=False,
            style=CUSTOM_STYLE
        ).ask()

        if use_range is None:
            return False

        if use_range:
            total = state.info['count']
            start = questionary.text(
                f"С какого трека начать? [1-{total}]",
                default="1",
                style=CUSTOM_STYLE,
                validate=lambda x: x.isdigit() and 1 <= int(x) <= total or "Неверный номер"
            ).ask()

            if start is None:
                return False

            end = questionary.text(
                f"Каким треком закончить? [1-{total}]",
                default=str(total),
                style=CUSTOM_STYLE,
                validate=lambda x: x.isdigit() and 1 <= int(x) <= total or "Неверный номер"
            ).ask()

            if end is None:
                return False

            state.options.playlist_start = int(start)
            state.options.playlist_end = int(end)

    return True


def prompt_output_dir(state: WizardState) -> bool:
    """Step 5: Select output folder."""
    if state.options.mode == DownloadMode.AUDIO:
        default_dir = get_config_value('output_dir_audio')
    else:
        default_dir = get_config_value('output_dir_video')

    default_path = Path(default_dir).expanduser()

    use_default = questionary.confirm(
        f"Сохранить в папку по умолчанию? [{default_dir}]",
        default=True,
        style=CUSTOM_STYLE
    ).ask()

    if use_default is None:
        return False

    if use_default:
        state.options.output_dir = default_path
    else:
        custom_path = questionary.text(
            "Введите путь к папке:",
            default=str(default_path),
            style=CUSTOM_STYLE
        ).ask()

        if custom_path is None:
            return False

        state.options.output_dir = Path(custom_path).expanduser()

    # Ask to save as default
    if not use_default:
        save = questionary.confirm(
            "Сохранить эту папку как папку по умолчанию?",
            default=False,
            style=CUSTOM_STYLE
        ).ask()

        if save:
            key = 'output_dir_audio' if state.options.mode == DownloadMode.AUDIO else 'output_dir_video'
            set_config_value(key, str(state.options.output_dir))

    return True


def confirm_download(state: WizardState) -> bool:
    """Step 6: Confirmation."""
    type_label = "Плейлист" if state.info['type'] == 'playlist' else "Видео"

    if state.options.mode == DownloadMode.AUDIO:
        mode_label = f"Аудио ({state.options.audio_format.upper()})"
    else:
        mode_label = f"Видео ({state.options.video_quality}p)"

    details = f"[bold cyan]Тип:[/bold cyan] {type_label}\n"

    if state.info['type'] == 'playlist':
        start = state.options.playlist_start
        end = state.options.playlist_end or state.info['count']
        if start > 1 or end < state.info['count']:
            details += f"[bold cyan]Треки:[/bold cyan] {start}-{end} из {state.info['count']}\n"
        else:
            details += f"[bold cyan]Треков:[/bold cyan] {state.info['count']}\n"
    else:
        details += f"[bold cyan]Название:[/bold cyan] {state.info['title']}\n"

    details += f"[bold cyan]Формат:[/bold cyan] {mode_label}\n"
    details += f"[bold cyan]Папка:[/bold cyan] {state.options.output_dir}\n"

    extras = []
    if state.options.download_thumbnail:
        extras.append("превью")
    if state.options.download_subtitles:
        extras.append("субтитры")
    if extras:
        details += f"[bold cyan]Дополнительно:[/bold cyan] {', '.join(extras)}"

    console.print(Panel.fit(details, title="[bold green]Готово к скачиванию[/bold green]"))

    confirm = questionary.confirm(
        "Начать скачивание?",
        default=True,
        style=CUSTOM_STYLE
    ).ask()

    return confirm if confirm is not None else False


# ============== Main ==============

@click.command()
@click.option('--history', '-h', 'show_hist', is_flag=True, help='Show download history')
@click.option('--config', '-c', 'edit_config', is_flag=True, help='Edit configuration')
def main(show_hist: bool, edit_config: bool):
    """Interactive video/audio downloader wizard.

    Run 'ytmv' and follow the prompts to download videos or audio
    from YouTube and 1000+ other sites.
    """
    check_dependencies()

    # Handle --history flag
    if show_hist:
        show_history()
        return

    # Handle --config flag
    if edit_config:
        console.print(f"\n[cyan]Конфигурационный файл:[/cyan] {CONFIG_FILE}")
        console.print(f"[cyan]Файл истории:[/cyan] {HISTORY_FILE}\n")

        if CONFIG_FILE.exists():
            console.print("[green]Текущие настройки:[/green]")
            with open(CONFIG_FILE) as f:
                console.print(f.read())
        else:
            console.print("[yellow]Конфигурационный файл не существует. Будет создан при первом запуске.[/yellow]")
        return

    # Initialize wizard state
    state = WizardState()

    # Step 1: URL
    if not prompt_url(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Step 2: Preview
    if not show_preview(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Step 3: Format & Quality
    if not prompt_format(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Step 4: Additional options
    if not prompt_options(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Step 5: Output directory
    if not prompt_output_dir(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Step 6: Confirmation
    if not confirm_download(state):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Create directory and cleanup
    state.options.output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_temp_files(state.options.output_dir)

    # Download
    console.print()
    if state.info['type'] == 'playlist':
        files = download_playlist(state.url, state.options)
        console.print(f"\n[bold green]Готово![/bold green] Скачано {len(files)} файлов в {state.options.output_dir}")
    else:
        output_file = download_single(state.url, state.options)
        console.print(f"\n[bold green]Готово![/bold green] Сохранено в {output_file}")


if __name__ == '__main__':
    main()
