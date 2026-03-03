@echo off
REM ============================================================
REM  Webex Downloader — Budowanie .exe (Windows)
REM ============================================================
REM  Wymagania:
REM   1. Python 3.10+ z pip
REM   2. pip install -r requirements.txt
REM   3. ffmpeg.exe i ffprobe.exe w tym folderze
REM      (pobierz z https://www.gyan.dev/ffmpeg/builds/
REM       -> ffmpeg-release-essentials.zip -> bin/)
REM ============================================================

echo.
echo === Webex Downloader — Build Windows .exe ===
echo.

REM Sprawdź ffmpeg
if not exist "ffmpeg.exe" (
    echo [BLAD] Brakuje ffmpeg.exe w biezacym folderze!
    echo Pobierz z https://www.gyan.dev/ffmpeg/builds/
    echo Rozpakuj i skopiuj ffmpeg.exe + ffprobe.exe tutaj.
    pause
    exit /b 1
)

if not exist "ffprobe.exe" (
    echo [BLAD] Brakuje ffprobe.exe w biezacym folderze!
    pause
    exit /b 1
)

echo [1/2] Instalowanie zaleznosci...
pip install -r requirements.txt

echo [2/2] Budowanie .exe...
pyinstaller --onefile --windowed ^
    --name "WebexDownloader" ^
    --add-binary "ffmpeg.exe;." ^
    --add-binary "ffprobe.exe;." ^
    --collect-all yt_dlp ^
    --collect-all customtkinter ^
    --hidden-import plyer.platforms.win.notification ^
    --hidden-import CTkToolTip ^
    app.py

echo.
if exist "dist\WebexDownloader.exe" (
    echo === SUKCES! ===
    echo Plik: dist\WebexDownloader.exe
) else (
    echo === BLAD BUDOWANIA ===
)
echo.
pause
