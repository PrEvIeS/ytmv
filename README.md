# ytmv

Интерактивный CLI-визард для скачивания видео и аудио с поддержкой кириллицы.

## Возможности

- 🎬 Скачивание видео (MP4) и аудио (M4A)
- 📋 Поддержка плейлистов
- 🔄 Транслитерация кириллицы в имена файлов
- 💫 Интерактивный визард
- 📊 Прогресс-бар для скачивания
- 🌍 Поддержка 1000+ видео-платформ

## Поддерживаемые платформы

Скрипт работает с любым сайтом, поддерживаемым [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md):

| Платформа | Видео | Плейлисты |
|-----------|:-----:|:---------:|
| YouTube   | ✅    | ✅        |
| Vimeo     | ✅    | ✅        |
| TikTok    | ✅    | ✅        |
| Instagram | ✅    | ✅        |
| Twitter/X | ✅    | —         |
| Facebook  | ✅    | ✅        |
| Reddit    | ✅    | —         |
| Twitch    | ✅    | ✅        |
| Rumble    | ✅    | ✅        |
| Odysee    | ✅    | ✅        |
| Bilibili  | ✅    | ✅        |
| Dailymotion | ✅  | ✅        |
| Rutube    | ✅    | ✅        |
| VK        | ✅    | ✅        |
| OK        | ✅    | ✅        |

... и многие другие (1000+ сайтов)

## Требования

- Python 3.10+
- yt-dlp
- ffmpeg

## Установка

### macOS

```bash
# Установка зависимостей
brew install yt-dlp ffmpeg

# Установка Python-библиотек
pip3 install --break-system-packages click rich questionary

# Скачивание скрипта
mkdir -p ~/Documents/scripts
curl -sL https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py -o ~/Documents/scripts/ytmv
chmod +x ~/Documents/scripts/ytmv

# Добавить в PATH (опционально)
sudo ln -sf ~/Documents/scripts/ytmv /usr/local/bin/ytmv
```

### Linux (Ubuntu/Debian)

```bash
# Установка зависимостей
sudo apt update
sudo apt install -y ffmpeg python3-pip
pip3 install yt-dlp

# Установка Python-библиотек
pip3 install click rich questionary

# Скачивание скрипта
mkdir -p ~/bin
curl -sL https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py -o ~/bin/ytmv
chmod +x ~/bin/ytmv

# Добавить в PATH (если нет)
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Linux (Arch)

```bash
# Установка зависимостей
sudo pacman -S ffmpeg python-pip
pip3 install yt-dlp

# Установка Python-библиотек
pip3 install click rich questionary

# Скачивание скрипта
mkdir -p ~/bin
curl -sL https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py -o ~/bin/ytmv
chmod +x ~/bin/ytmv
```

### Windows (PowerShell)

```powershell
# Установка зависимостей через winget
winget install ffmpeg
winget install yt-dlp

# Установка Python-библиотек
pip3 install click rich questionary

# Создание папки и скачивание
mkdir "$env:USERPROFILE\scripts"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py" -OutFile "$env:USERPROFILE\scripts\ytmv.py"

# Добавить в PATH (опционально)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$env:USERPROFILE\scripts", "User")
```

## Использование

Просто запустите скрипт и следуйте подсказкам:

```bash
ytmv
```

### Flow визарда

```
1. Ввод URL         → "Введите URL видео или плейлиста:"
2. Предпросмотр     → Показывает тип, название или количество треков
3. Выбор формата    → 🎥 Видео (MP4) / 🎵 Аудио (M4A)
4. Выбор папки      → По умолчанию или своя
5. Подтверждение    → "Начать скачивание? [Y/n]"
6. Результат        → Файл(ы) сохранены
```

### Папки по умолчанию

- **Видео**: `~/Movies/shorts`
- **Аудио**: `~/Movies/audios`

## Управление

- `Enter` — подтвердить выбор
- `↑/↓` — навигация в меню
- `Ctrl+C` — выход на любом шаге

## Транслитерация

Скрипт автоматически транслитерирует кириллицу в имена файлов:

| Кириллица | Latin |
|-----------|-------|
| Привет    | privet |
| Москва    | moskva |
| Щука      | shchuka |

## Лицензия

MIT
