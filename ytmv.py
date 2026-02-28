#!/usr/bin/env python3
"""
YouTube downloader with Russian transliteration support.
Interactive CLI wizard for downloading videos and playlists.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import click
import questionary
from questionary import Style
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeRemainingColumn, TaskProgressColumn
from rich.traceback import install

install(show_locals=True)

console = Console()

# Custom style for questionary
CUSTOM_STYLE = Style([
    ('qmark', 'fg:cyan bold'),
    ('question', 'fg:white bold'),
    ('answer', 'fg:green bold'),
    ('pointer', 'fg:cyan bold'),
    ('highlighted', 'fg:cyan bold'),
    ('instruction', 'fg:yellow'),
])

# Russian to Latin transliteration table (ISO 9 / BGN variant)
TRANSLIT_TABLE = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    # Ukrainian letters
    'ї': 'yi', 'і': 'i', 'ґ': 'g', 'є': 'ye',
}


def transliterate(text: str) -> str:
    """Transliterate Cyrillic text to Latin."""
    result = []
    for char in text.lower():
        if char in TRANSLIT_TABLE:
            result.append(TRANSLIT_TABLE[char])
        elif char.isalnum() or char in ' _-':
            result.append(char)
        # Remove emojis and other special characters
    return ''.join(result)


def sanitize_filename(name: str) -> str:
    """Sanitize filename: transliterate, replace spaces with underscores, remove unsafe chars."""
    # Transliterate
    name = transliterate(name)
    # Remove remaining non-ASCII
    name = name.encode('ascii', 'ignore').decode('ascii')
    # Replace spaces and multiple underscores with single underscore
    name = re.sub(r'[_\s]+', '_', name)
    # Remove unsafe characters
    name = re.sub(r'[^A-Za-z0-9_-]', '', name)
    # Trim and clean
    name = name.strip('_-')
    # Limit length
    if len(name) > 200:
        name = name[:200]
    return name or 'video'


# Full paths for tools (fixes PATH issues in non-interactive shells)
TOOL_PATHS = {
    'yt-dlp': '/opt/homebrew/bin/yt-dlp',
    'ffmpeg': '/opt/homebrew/bin/ffmpeg',
}


def check_dependencies():
    """Check if required tools are installed."""
    for tool, path in TOOL_PATHS.items():
        try:
            # ffmpeg uses -version, yt-dlp uses --version
            flag = '-version' if tool == 'ffmpeg' else '--version'
            subprocess.run([path, flag], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            console.print(f"[bold red]Error:[/bold red] {tool} not found at {path}. Install with: brew install {tool}")
            raise SystemExit(1)


def cleanup_temp_files(output_dir: Path, pattern: str = "*.tmp*"):
    """Remove orphaned temp files from previous runs."""
    for tmp in output_dir.glob(pattern):
        try:
            tmp.unlink()
            console.print(f"[dim]Cleaned up: {tmp.name}[/dim]")
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


def is_playlist(url: str) -> bool:
    """Check if URL is a playlist."""
    return 'list=' in url or 'playlist?' in url


def get_playlist_info(url: str) -> dict:
    """Get playlist information using yt-dlp --dump-json."""
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


# ============== Wizard Steps ==============

def prompt_url() -> str:
    """Step 1: Enter URL"""
    url = questionary.text(
        "Введите URL видео или плейлиста:",
        style=CUSTOM_STYLE,
        validate=lambda x: len(x) > 0 and ('youtube.com' in x or 'youtu.be' in x) or "Введите корректный YouTube URL"
    ).ask()

    if url is None:
        raise SystemExit(0)

    return url.strip()


def show_preview(url: str) -> dict:
    """Step 2: Show preview of video/playlist"""
    console.print("\n[dim]Получение информации...[/dim]")

    if is_playlist(url):
        playlist_info = get_playlist_info(url)
        count = playlist_info['count']
        console.print(Panel.fit(
            f"[bold cyan]Тип:[/bold cyan] Плейлист\n"
            f"[bold cyan]Количество треков:[/bold cyan] {count}",
            title="[bold green]Предпросмотр[/bold green]"
        ))
        return {'type': 'playlist', 'count': count, 'info': playlist_info}
    else:
        title = get_video_title(url)
        console.print(Panel.fit(
            f"[bold cyan]Тип:[/bold cyan] Видео\n"
            f"[bold cyan]Название:[/bold cyan] {title}",
            title="[bold green]Предпросмотр[/bold green]"
        ))
        return {'type': 'video', 'title': title}


def prompt_format() -> str:
    """Step 3: Select format (video/audio)"""
    mode = questionary.select(
        "Выберите формат:",
        choices=[
            questionary.Choice("🎥 Видео (MP4)", value="video"),
            questionary.Choice("🎵 Аудио (M4A)", value="audio"),
        ],
        style=CUSTOM_STYLE
    ).ask()

    if mode is None:
        raise SystemExit(0)

    return mode


def prompt_output_dir(mode: str) -> Path:
    """Step 4: Select output folder"""
    default_dir = "~/Movies/audios" if mode == "audio" else "~/Movies/shorts"
    default_path = Path(default_dir).expanduser()

    use_default = questionary.confirm(
        f"Сохранить в папку по умолчанию? [{default_dir}]",
        default=True,
        style=CUSTOM_STYLE
    ).ask()

    if use_default is None:
        raise SystemExit(0)

    if use_default:
        return default_path

    custom_path = questionary.text(
        "Введите путь к папке:",
        default=str(default_path),
        style=CUSTOM_STYLE
    ).ask()

    if custom_path is None:
        raise SystemExit(0)

    return Path(custom_path).expanduser()


def confirm_download(info: dict, mode: str, output_dir: Path) -> bool:
    """Step 5: Confirmation"""
    type_label = "Плейлист" if info['type'] == 'playlist' else "Видео"
    mode_label = "Видео (MP4)" if mode == "video" else "Аудио (M4A)"

    details = f"[bold cyan]Тип:[/bold cyan] {type_label}\n"
    if info['type'] == 'playlist':
        details += f"[bold cyan]Треков:[/bold cyan] {info['count']}\n"
    else:
        details += f"[bold cyan]Название:[/bold cyan] {info['title']}\n"
    details += f"[bold cyan]Формат:[/bold cyan] {mode_label}\n"
    details += f"[bold cyan]Папка:[/bold cyan] {output_dir}"

    console.print(Panel.fit(details, title="[bold green]Готово к скачиванию[/bold green]"))

    confirm = questionary.confirm(
        "Начать скачивание?",
        default=True,
        style=CUSTOM_STYLE
    ).ask()

    return confirm if confirm is not None else False


# ============== Download Functions ==============

def download_single(url: str, mode: str, output_dir: Path) -> Path:
    """Download a single video/audio."""
    title = get_video_title(url)
    safe_name = sanitize_filename(title)
    ext = 'm4a' if mode == 'audio' else 'mp4'
    output_file = output_dir / f"{safe_name}.{ext}"
    output_file = handle_collision(output_file)

    console.print(f"[bold cyan]Title:[/bold cyan] {title}")
    console.print(f"[bold cyan]Output:[/bold cyan] {output_file}")

    temp_base = output_dir / f"{safe_name}.tmp"

    # Download
    console.print("[bold yellow]Downloading...[/bold yellow]")
    try:
        subprocess.run([
            TOOL_PATHS['yt-dlp'],
            '-f', 'bestaudio/best' if mode == 'audio' else 'bestvideo+bestaudio',
            '-o', str(temp_base) + '.%(ext)s',
            '--newline',
            '--no-playlist',  # Ensure single video only
            url
        ], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]Download failed:[/bold red] {e.stderr or str(e)}")
        for tmp in output_dir.glob(f"{safe_name}.tmp.*"):
            tmp.unlink()
        raise SystemExit(1)
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Download cancelled[/bold yellow]")
        for tmp in output_dir.glob(f"{safe_name}.tmp.*"):
            tmp.unlink()
        raise SystemExit(130)

    # Find downloaded file
    temp_files = list(output_dir.glob(f"{safe_name}.tmp.*"))
    if not temp_files:
        console.print("[bold red]Error:[/bold red] Downloaded file not found")
        raise SystemExit(1)
    temp_file = temp_files[0]

    # Convert
    convert_file(temp_file, output_file, mode)

    # Cleanup
    if temp_file.exists():
        temp_file.unlink()

    return output_file


def download_playlist(url: str, mode: str, output_dir: Path) -> list[Path]:
    """Download all videos in a playlist."""
    playlist_info = get_playlist_info(url)
    total = playlist_info['count']

    console.print(Panel.fit(
        f"[bold cyan]Playlist:[/bold cyan] {total} items\n"
        f"[bold cyan]Mode:[/bold cyan] {mode}\n"
        f"[bold cyan]Output:[/bold cyan] {output_dir}",
        title="[bold green]YouTube Playlist Downloader[/bold green]"
    ))

    downloaded_files = []
    ext = 'm4a' if mode == 'audio' else 'mp4'

    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        main_task = progress.add_task("[yellow]Downloading playlist...", total=total)

        for idx, entry in enumerate(playlist_info['entries'], 1):
            video_url = entry.get('url') or entry.get('id')
            if video_url and not video_url.startswith('http'):
                video_url = f"https://www.youtube.com/watch?v={video_url}"

            title = entry.get('title', f'Video {idx}')
            safe_name = sanitize_filename(title)

            # Add index prefix for playlist ordering
            indexed_name = f"{idx:02d}_{safe_name}"
            output_file = output_dir / f"{indexed_name}.{ext}"
            output_file = handle_collision(output_file)

            progress.update(main_task, description=f"[yellow]({idx}/{total}) {title[:40]}...")

            temp_base = output_dir / f"{indexed_name}.tmp"

            try:
                # Download single video from playlist
                subprocess.run([
                    TOOL_PATHS['yt-dlp'],
                    '-f', 'bestaudio/best' if mode == 'audio' else 'bestvideo+bestaudio',
                    '-o', str(temp_base) + '.%(ext)s',
                    '--newline',
                    '--no-playlist',
                    video_url
                ], check=True, capture_output=True)

                # Find downloaded file
                temp_files = list(output_dir.glob(f"{indexed_name}.tmp.*"))
                if temp_files:
                    temp_file = temp_files[0]
                    convert_file(temp_file, output_file, mode, quiet=True)
                    if temp_file.exists():
                        temp_file.unlink()
                    downloaded_files.append(output_file)
                    console.print(f"  [green]✓[/green] {title[:50]}")
                else:
                    console.print(f"  [red]✗[/red] {title[:50]} - file not found")

            except subprocess.CalledProcessError:
                console.print(f"  [red]✗[/red] {title[:50]} - download failed")
            except KeyboardInterrupt:
                console.print("\n[bold yellow]Download cancelled[/bold yellow]")
                cleanup_temp_files(output_dir, "*.tmp*")
                raise SystemExit(130)

            progress.advance(main_task)

    return downloaded_files


def convert_file(input_file: Path, output_file: Path, mode: str, quiet: bool = False):
    """Convert downloaded file to final format."""
    if mode == 'audio':
        status = console.status("[bold yellow]Converting to M4A...") if not quiet else None
        if status:
            status.__enter__()
        try:
            subprocess.run([
                TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file),
                '-c:a', 'aac', '-b:a', '192k',
                str(output_file)
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            if not quiet:
                console.print(f"[bold red]Conversion failed:[/bold red] {e.stderr.decode() if e.stderr else str(e)}")
            raise SystemExit(1)
        finally:
            if status:
                status.__exit__(None, None, None)
    else:
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
                subprocess.run([
                    TOOL_PATHS['ffmpeg'], '-y', '-i', str(input_file),
                    '-c:v', 'libx264',
                    '-c:a', 'aac',
                    '-movflags', '+faststart',
                    str(output_file)
                ], check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                if not quiet:
                    console.print(f"[bold red]Conversion failed:[/bold red] {e.stderr.decode() if e.stderr else str(e)}")
                raise SystemExit(1)

            progress.update(task, completed=100)


# ============== Main Wizard ==============

@click.command()
def main():
    """Interactive YouTube downloader wizard.

    Just run 'ytmv' and follow the prompts.
    """
    check_dependencies()

    # Step 1: URL
    url = prompt_url()

    # Step 2: Preview
    info = show_preview(url)

    # Step 3: Format
    mode = prompt_format()

    # Step 4: Output directory
    output_dir = prompt_output_dir(mode)

    # Step 5: Confirmation
    if not confirm_download(info, mode, output_dir):
        console.print("\n[yellow]Отменено[/yellow]")
        return

    # Create directory and cleanup old temp files
    output_dir.mkdir(parents=True, exist_ok=True)
    cleanup_temp_files(output_dir)

    # Step 6: Download
    console.print()
    if info['type'] == 'playlist':
        files = download_playlist(url, mode, output_dir)
        console.print(f"\n[bold green]Готово![/bold green] Скачано {len(files)} файлов в {output_dir}")
    else:
        output_file = download_single(url, mode, output_dir)
        console.print(f"\n[bold green]Готово![/bold green] Сохранено в {output_file}")


if __name__ == '__main__':
    main()
