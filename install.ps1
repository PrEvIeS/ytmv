# Installation script for ytmv (Windows)

Write-Host "🎬 Installing ytmv..." -ForegroundColor Cyan

# Check for winget
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "❌ winget not found. Please install winget first." -ForegroundColor Red
    exit 1
}

# Install system dependencies
Write-Host "📦 Installing system dependencies..." -ForegroundColor Yellow
winget install ffmpeg
winget install yt-dlp

# Install Python dependencies
Write-Host "📦 Installing Python dependencies..." -ForegroundColor Yellow
pip3 install click rich questionary

# Create scripts directory
$scriptsDir = "$env:USERPROFILE\scripts"
if (-not (Test-Path $scriptsDir)) {
    New-Item -ItemType Directory -Path $scriptsDir | Out-Null
}

# Download script
Write-Host "📥 Downloading ytmv..." -ForegroundColor Yellow
$scriptPath = "$scriptsDir\ytmv.py"
Invoke-WebRequest -Uri "https://raw.githubusercontent.com/PrEvIeS/ytmv/main/ytmv.py" -OutFile $scriptPath

# Create wrapper batch file
$batPath = "$scriptsDir\ytmv.bat"
"@echo off`npython3 `"$scriptPath`" %*" | Out-File -FilePath $batPath -Encoding ASCII

# Add to PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$scriptsDir*") {
    Write-Host "📝 Adding to PATH..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$scriptsDir", "User")
}

Write-Host "✅ ytmv installed successfully!" -ForegroundColor Green
Write-Host "   Run: ytmv" -ForegroundColor Cyan
Write-Host "   Note: Restart your terminal if ytmv is not found"
