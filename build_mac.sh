#!/bin/bash
# ============================================================
#  Webex Downloader — Budowanie .app (macOS)
# ============================================================
#  Wymagania:
#   1. Python 3.10+ z pip
#   2. pip install -r requirements.txt
#   3. ffmpeg i ffprobe w tym folderze
#      (brew install ffmpeg, potem: cp $(which ffmpeg) . ; cp $(which ffprobe) .)
# ============================================================

set -e

echo ""
echo "=== Webex Downloader — Build macOS .app ==="
echo ""

# Sprawdź ffmpeg
if [ ! -f "ffmpeg" ]; then
    echo "[BŁĄD] Brakuje ffmpeg w bieżącym folderze!"
    echo "Zainstaluj: brew install ffmpeg"
    echo "Potem: cp \$(which ffmpeg) . && cp \$(which ffprobe) ."
    exit 1
fi

if [ ! -f "ffprobe" ]; then
    echo "[BŁĄD] Brakuje ffprobe w bieżącym folderze!"
    exit 1
fi

echo "[1/2] Instalowanie zależności..."
pip install -r requirements.txt

echo "[2/2] Budowanie .app..."
pyinstaller --windowed \
    --name "WebexDownloader" \
    --add-binary "ffmpeg:." \
    --add-binary "ffprobe:." \
    --collect-all yt_dlp \
    --collect-all customtkinter \
    --hidden-import plyer.platforms.macosx.notification \
    --hidden-import CTkToolTip \
    --osx-bundle-identifier com.webex.downloader \
    app.py

echo ""
if [ -d "dist/WebexDownloader.app" ]; then
    echo "=== SUKCES! ==="
    echo "Aplikacja: dist/WebexDownloader.app"
else
    echo "=== BŁĄD BUDOWANIA ==="
fi
echo ""
