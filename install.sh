#!/bin/bash
# Installation script for ytmv

set -e

echo "🎬 Installing ytmv..."

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
else
    echo "❌ Unsupported OS: $OSTYPE"
    exit 1
fi

# Install system dependencies
echo "📦 Installing system dependencies..."
if [[ "$OS" == "macos" ]]; then
    brew install yt-dlp ffmpeg
    PIP_FLAGS="--break-system-packages"
elif [[ "$OS" == "linux" ]]; then
    if command -v apt &> /dev/null; then
        sudo apt update
        sudo apt install -y ffmpeg python3-pip
    elif command -v pacman &> /dev/null; then
        sudo pacman -S --noconfirm ffmpeg python-pip
    fi
    PIP_FLAGS=""
fi

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip3 install $PIP_FLAGS click rich questionary

# Download script
echo "📥 Downloading ytmv..."
mkdir -p "$HOME/bin"
curl -sL https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py -o "$HOME/bin/ytmv"
chmod +x "$HOME/bin/ytmv"

# Add to PATH if needed
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
    echo "📝 Adding ~/bin to PATH..."
    echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
    echo "⚠️  Run 'source ~/.bashrc' or restart your terminal"
fi

echo "✅ ytmv installed successfully!"
echo "   Run: ytmv"
