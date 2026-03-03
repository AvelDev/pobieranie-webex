# CLAUDE.md — Developer Notes

Dokumentacja techniczna dla przyszłych modyfikacji aplikacji **Webex Downloader**.

## Architektura

### Stack

- **GUI**: CustomTkinter 5.2+ (ciemny motyw natywnie)
- **Pobieranie**: yt-dlp 2024+ (jako biblioteka Python, nie CLI)
- **Threading**: threading (pobieranie w osobnym wątku, GUI updates przez `root.after()`)
- **Powiadomienia**: plyer 2.1+ (cross-platform)
- **Tooltips**: CTkToolTip 0.8+
- **Pakowanie**: PyInstaller 6.0+

### Struktura pliku `app.py`

```
app.py (361 linii)
├── Imports + konfiguracja ścieżek
├── resolve_webex_redirect() — Workaround dla ldr.php/lsr.php redirects
├── notify() — Desktop notifications (try/except wrapper)
├── Klasa App(ctk.CTk)
│   ├── __init__() — Setup okna, zmienne
│   ├── _build_ui() — Layout całego GUI (wiersze 0-6)
│   ├── _on_text_change() — Podświetlanie średników
│   ├── _parse_lines() — Parse "URL;hasło" format
│   ├── _on_download_click() — UI button handler
│   ├── _on_cancel() — Anulowanie pobierania
│   ├── _download_worker() — Worker w osobnym wątku (główna logika)
│   ├── _progress_hook() — yt-dlp progress callback
│   ├── _ui() — Thread-safe GUI updates (self.after)
│   ├── _log() — Dopisz do verbose textbox
│   ├── _log_from_thread() — _log z wątku
│   └── _finish_ui() — Reset UI po zakończeniu
├── Klasa _YDLLogger — Custom logger dla yt-dlp
└── if __name__ == "__main__" — Entry point
```

## Kluczowe komponenty

### 1. Workaround Webex Redirect

**Problem**: yt-dlp ekstraktor `ciscowebex` ma buga — przy URL-ach `ldr.php?RCID=...` szuka URL-a w HTML zamiast używać finalnego URL-a po redirect.

**Rozwiązanie** (`resolve_webex_redirect()`):

- Detektuje `ldr.php`/`lsr.php`
- Wykonuje HTTP request z follow redirect
- Zwraca finalny URL `recordingservice/sites/.../recording/playback/...`
- yt-dlp dostaje bezpośredni URL

**Miejsce użycia**: `_download_worker()` przed przesłaniem do `YoutubeDL`

### 2. Thread-safe GUI updates

Pobieranie w osobnym wątku, ale GUI updates muszą być w głównym wątku.

```python
def _ui(self, func, *args, **kwargs):
    self.after(0, lambda: func(*args, **kwargs))

# Użycie z wątku:
self._ui(self._log, "Tekst")
self._ui(self.lbl_status.configure, text="Status")
self._ui(self.progress.set, 0.5)
```

### 3. Podświetlanie średników

W CTkTextbox tagsize działają normalnie (mimo że documentation jest limitowana):

```python
tb.tag_config("sc", background=SEMICOLON_BG)
tb.tag_add("sc", start_pos, end_pos)
```

Bindowanie na `<KeyRelease>` z ponawianiem wyszukiwania średników.

### 4. yt-dlp integration

Kluczowe opcje:

```python
ydl_opts = {
    "outtmpl": "folder/%(title)s.%(ext)s",
    "progress_hooks": [callback],       # Aktualizacja paska
    "logger": _YDLLogger(...),          # Custom logi
    "videopassword": "hasło",           # Dla nagr. zabezpieczonych
    "noplaylist": True,                 # Nie pobieraj playlisty
}
with YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])
```

## Jak dodać nową funkcjonalność

### Nowy przycisk / akcja w GUI

1. Dodaj widget w `_build_ui()`
2. Binduj event do nowej metody `_on_xxx_click()`
3. Jeśli asynchroniczne — uruchom w wątku z `threading.Thread(target=..., daemon=True)`
4. Thread-safe updates przez `self._ui()`

### Nowe opcje pobierania

Opcje yt-dlp idą do `ydl_opts` dict:

```python
# Przykład: audio-only format
ydl_opts["format"] = "bestaudio"[webm]/bestaudio[m4a]/.."
```

[Pełna lista opcji](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L177)

### Nowy format wejścia

Metoda `_parse_lines()` — zmień format parsingowania:

```python
@staticmethod
def _parse_lines(raw: str):
    # Zmień logikę tutaj
    # Zwróć listę (url, password|None, **kwargs)
```

### Dodanie ustawień UI

CustomTkinter obsługuje preferencje poprzez pliki JSON / pickle:

```python
import json
config_file = os.path.join(BASE_DIR, "config.json")
```

## Znane problemy / TODO

1. **ffmpeg bundling** — Rozmiar .exe ~180MB (ffmpeg ~80MB). Alternatywy:
   - Separate installer dla ffmpeg
   - Lazy-download ffmpeg przy pierwszym uruchomieniu
   - Użycie bezpośredniego MP4 URL (jeśli dostępny w API)

2. **macOS .app** — Wymaga budowania NA macOS (cross-compile nie działa z PyInstaller)

3. **Error recovery** — Brak retry mechniki. TODO: retry-loop z exponential backoff

4. **License info** — Webex recordings mogą mieć ograniczenia prawne. TODO: disclaimer w UI

5. **Proxy support** — yt-dlp obsługuje proxy, ale nie exposowaliśmy w GUI. TODO: opcjonalny proxy field

## Dependencje — pinning versions

requirements.txt:

```
customtkinter>=5.2.0  # Nie 6.0+ (breaking changes potencjalne)
yt-dlp>=2024.0.0     # Stale updated, buga ciscowebex mogą być naprawiane
plyer>=2.1.0
CTkToolTip>=0.8
pyinstaller>=6.0.0
```

Monitor za zmianami yt-dlp ekstraktora `ciscowebex` — główne źródło bugów.

## Test checklist

Przed releaseą:

- [ ] GUI uruchamia się bez crashes
- [ ] Średniki podświetlają się
- [ ] Tooltip pokazuje się na "?"
- [ ] Pobieranie działa (test z publicznym Webex URL)
- [ ] Pasek postępu i log aktualizują się
- [ ] Anulowanie działa
- [ ] Powiadomienie wyświetla się
- [ ] .exe jest pojedynczym plikiem w dist/
- [ ] .exe działa na czystym Windowsie (bez Pythona)
- [ ] ffmpeg/ffprobe są w bundlu

## Build instructions (reference)

### Windows

```bash
# Pobierz ffmpeg.exe, ffprobe.exe z gyan.dev
# Umieść w folderze projektu
./build_win.bat
```

### macOS

```bash
brew install ffmpeg
cp $(which ffmpeg) . && cp $(which ffprobe) .
chmod +x build_mac.sh && ./build_mac.sh
```

## Useful yt-dlp commands (CLI reference)

```bash
# Debug ekstraktor ciscowebex
yt-dlp --dump-json "https://firma.webex.com/recordingservice/.../playback/..."

# Z hasłem
yt-dlp --video-password "hasło" "https://..."

# Only audio
yt-dlp -f bestaudio "https://..."

# List dostępnych formatów
yt-dlp -F "https://..."
```

## References

- yt-dlp docs: https://github.com/yt-dlp/yt-dlp#usage-and-examples
- CustomTkinter docs: https://github.com/TomSchimansky/CustomTkinter
- PyInstaller docs: https://pyinstaller.org/
