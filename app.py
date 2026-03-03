"""
Webex Downloader — Prosta aplikacja do masowego pobierania nagrań z Webex.
Obsługuje nagrania zabezpieczone hasłem (link;hasło) i bez hasła (sam link).
"""

import os
import sys
import re
import threading
import logging
import urllib.request
from datetime import datetime

import customtkinter as ctk
from CTkToolTip import CTkToolTip

# ── Ścieżka bazowa (kompatybilna z PyInstaller --onefile) ──────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
    # Dodaj folder bundla do PATH żeby yt-dlp znalazł ffmpeg
    os.environ["PATH"] = BUNDLE_DIR + os.pathsep + os.environ.get("PATH", "")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = BASE_DIR

# ── Import yt-dlp ──────────────────────────────────────────────────────────
from yt_dlp import YoutubeDL


# ── Resolve Webex redirect (ldr.php / lsr.php → recordingservice URL) ──────
def resolve_webex_redirect(url: str) -> str:
    """Jeśli URL to ldr.php/lsr.php z RCID, podąża za redirectem i zwraca finalny URL.
    yt-dlp ma bug w ekstraktorze ciscowebex — szuka URL-a w HTML zamiast
    użyć finalnego URL-a po HTTP redirect."""
    if re.search(r'/l[ds]r\.php\?.*RCID=', url):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36',
            })
            resp = urllib.request.urlopen(req, timeout=20)
            final = resp.url
            resp.close()
            if final and final != url:
                return final
        except Exception:
            pass
    return url

# ── Powiadomienia ──────────────────────────────────────────────────────────
try:
    from plyer import notification as _notifier

    def notify(title: str, message: str):
        try:
            _notifier.notify(
                title=title,
                message=message,
                app_name="Webex Downloader",
                timeout=10,
            )
        except Exception:
            pass  # powiadomienia nie są krytyczne
except ImportError:
    def notify(title: str, message: str):
        pass


# ── Stałe GUI ──────────────────────────────────────────────────────────────
WINDOW_W, WINDOW_H = 750, 620
SEMICOLON_BG = "#1a5c2a"
FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "SF Pro Text"


# ══════════════════════════════════════════════════════════════════════════════
#  Klasa aplikacji
# ══════════════════════════════════════════════════════════════════════════════
class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── Konfiguracja okna ──────────────────────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        self.title("Webex Downloader")
        self.geometry(f"{WINDOW_W}x{WINDOW_H}")
        self.minsize(600, 500)
        self.resizable(True, True)

        self._downloading = False
        self._cancel_flag = False

        self._build_ui()

    # ── Budowa interfejsu ──────────────────────────────────────────────────
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)   # pole linków
        self.grid_rowconfigure(5, weight=1)   # verbose log

        pad = {"padx": 14, "pady": (6, 0)}

        # ── 0: Nagłówek ───────────────────────────────────────────────────
        header = ctk.CTkLabel(
            self, text="Webex Downloader",
            font=ctk.CTkFont(family=FONT_FAMILY, size=22, weight="bold"),
        )
        header.grid(row=0, column=0, pady=(14, 4))

        # ── 1: Label + ? ──────────────────────────────────────────────────
        label_frame = ctk.CTkFrame(self, fg_color="transparent")
        label_frame.grid(row=1, column=0, sticky="w", **pad)

        lbl = ctk.CTkLabel(
            label_frame, text="Linki do nagrań",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14),
        )
        lbl.pack(side="left")

        help_btn = ctk.CTkLabel(
            label_frame, text=" ? ",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=24, height=24,
            corner_radius=12,
            fg_color=("gray70", "gray30"),
            text_color=("gray20", "gray90"),
        )
        help_btn.pack(side="left", padx=(6, 0))

        CTkToolTip(
            help_btn,
            message=(
                "Wklej linki — jeden na linię.\n"
                "Format: link;hasło  lub sam  link\n\n"
                "Przykład:\n"
                "https://firma.webex.com/rec/abc123;MojeHaslo\n"
                "https://firma.webex.com/rec/def456"
            ),
            delay=0.15,
            alpha=0.95,
        )

        # ── 2: Pole tekstowe (linki) ──────────────────────────────────────
        self.txt_links = ctk.CTkTextbox(
            self, height=140,
            font=ctk.CTkFont(family="Consolas", size=13),
            wrap="none",
        )
        self.txt_links.grid(row=2, column=0, sticky="nsew", padx=14, pady=(4, 6))
        self.txt_links.bind("<KeyRelease>", self._on_text_change)

        # ── 3: Przycisk pobierania ────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=3, column=0, pady=6)

        self.btn_download = ctk.CTkButton(
            btn_frame, text="⬇  Pobierz nagrania",
            font=ctk.CTkFont(family=FONT_FAMILY, size=14, weight="bold"),
            width=220, height=38,
            command=self._on_download_click,
        )
        self.btn_download.pack(side="left", padx=(0, 8))

        self.btn_cancel = ctk.CTkButton(
            btn_frame, text="Anuluj",
            font=ctk.CTkFont(family=FONT_FAMILY, size=13),
            width=90, height=38,
            fg_color="gray30", hover_color="gray40",
            command=self._on_cancel,
            state="disabled",
        )
        self.btn_cancel.pack(side="left")

        # ── 4: Label verbose ──────────────────────────────────────────────
        lbl_log = ctk.CTkLabel(
            self, text="Log",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            anchor="w",
        )
        lbl_log.grid(row=4, column=0, sticky="w", padx=14, pady=(4, 0))

        # ── 5: Verbose textbox ────────────────────────────────────────────
        self.txt_log = ctk.CTkTextbox(
            self, height=120, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
        )
        self.txt_log.grid(row=5, column=0, sticky="nsew", padx=14, pady=(2, 6))

        # ── 6: Pasek postępu + status ─────────────────────────────────────
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=6, column=0, sticky="ew", padx=14, pady=(0, 10))
        bottom.grid_columnconfigure(0, weight=1)

        self.progress = ctk.CTkProgressBar(bottom, height=14)
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(
            bottom, text="Gotowy",
            font=ctk.CTkFont(family=FONT_FAMILY, size=12),
            anchor="w",
        )
        self.lbl_status.grid(row=1, column=0, sticky="w")

    # ── Podświetlanie średników ────────────────────────────────────────────
    def _on_text_change(self, event=None):
        """Podświetla każdy średnik na ciemnozielonym tle."""
        tb = self.txt_links
        tb.tag_delete("sc")
        tb.tag_config("sc", background=SEMICOLON_BG)
        start = "1.0"
        while True:
            pos = tb.search(";", start, stopindex="end")
            if not pos:
                break
            end = f"{pos}+1c"
            tb.tag_add("sc", pos, end)
            start = end

    # ── Parsowanie linii ───────────────────────────────────────────────────
    @staticmethod
    def _parse_lines(raw: str):
        """Zwraca listę krotek (url, password|None)."""
        entries = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if ";" in line:
                url, pwd = line.split(";", 1)
                url, pwd = url.strip(), pwd.strip()
                entries.append((url, pwd if pwd else None))
            else:
                entries.append((line, None))
        return entries

    # ── Klik przycisku ─────────────────────────────────────────────────────
    def _on_download_click(self):
        if self._downloading:
            return
        raw = self.txt_links.get("1.0", "end")
        entries = self._parse_lines(raw)
        if not entries:
            self._log("⚠ Brak linków do pobrania.\n")
            return

        self._downloading = True
        self._cancel_flag = False
        self.btn_download.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress.set(0)
        self.lbl_status.configure(text="Rozpoczynam pobieranie…")

        thread = threading.Thread(
            target=self._download_worker, args=(entries,), daemon=True
        )
        thread.start()

    def _on_cancel(self):
        self._cancel_flag = True
        self._log("⛔ Anulowanie po bieżącym pobieraniu…\n")

    # ── Worker (osobny wątek) ──────────────────────────────────────────────
    def _download_worker(self, entries):
        total = len(entries)
        success = 0
        failed = 0
        download_dir = BASE_DIR

        for i, (url, pwd) in enumerate(entries, 1):
            if self._cancel_flag:
                self._ui(self._log, f"⛔ Anulowano. Pobrano {success}/{total}.\n")
                break

            # Resolve Webex ldr.php/lsr.php redirects (workaround yt-dlp bug)
            resolved_url = resolve_webex_redirect(url)
            if resolved_url != url:
                self._ui(self._log, f"↳ Redirect: {url[:60]}… → {resolved_url[:60]}…\n")
                url = resolved_url

            short_url = url[:80] + ("…" if len(url) > 80 else "")
            self._ui(self.lbl_status.configure, text=f"({i}/{total}) {short_url}")
            self._ui(self._log, f"\n── ({i}/{total}) {short_url}\n")

            ydl_opts = {
                "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
                "progress_hooks": [lambda d, _i=i, _t=total: self._progress_hook(d, _i, _t)],
                "logger": _YDLLogger(self._log_from_thread),
                "noplaylist": True,
                "quiet": False,
                "no_warnings": False,
            }

            if pwd:
                ydl_opts["videopassword"] = pwd

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                success += 1
                self._ui(self._log, f"✔ Pobrano pomyślnie.\n")
            except Exception as e:
                failed += 1
                self._ui(self._log, f"✖ Błąd: {e}\n")

        # ── Koniec ─────────────────────────────────────────────────────────
        summary = f"Zakończono: {success} OK, {failed} błędów (z {total})"
        self._ui(self.lbl_status.configure, text=summary)
        self._ui(self.progress.set, 1.0 if not self._cancel_flag else self.progress.get())
        self._ui(self._finish_ui)
        notify("Webex Downloader", summary)

    # ── Progress hook yt-dlp ───────────────────────────────────────────────
    def _progress_hook(self, d: dict, idx: int, total: int):
        if d["status"] == "downloading":
            pct_str = d.get("_percent_str", "").strip()
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            filename = os.path.basename(d.get("filename", ""))

            # Oblicz lokalny procent (0-1)
            downloaded = d.get("downloaded_bytes", 0)
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            local_pct = downloaded / total_bytes

            # Globalny postęp
            global_pct = ((idx - 1) + local_pct) / total

            status_text = f"({idx}/{total}) {filename}  {pct_str}  {speed}  ETA {eta}"
            self._ui(self.lbl_status.configure, text=status_text)
            self._ui(self.progress.set, min(global_pct, 1.0))

        elif d["status"] == "finished":
            filename = os.path.basename(d.get("filename", ""))
            self._ui(self._log, f"  ↳ Zakończono pobieranie: {filename}\n")

    # ── Helpers GUI (thread‑safe) ──────────────────────────────────────────
    def _ui(self, func, *args, **kwargs):
        """Wykonaj func w głównym wątku GUI."""
        self.after(0, lambda: func(*args, **kwargs))

    def _log(self, text: str):
        """Dopisz tekst do verbose logu (wywoływać z głównego wątku)."""
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", text)
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _log_from_thread(self, text: str):
        """Dopisz tekst do logu — bezpiecznie z wątku."""
        self._ui(self._log, text)

    def _finish_ui(self):
        self._downloading = False
        self.btn_download.configure(state="normal")
        self.btn_cancel.configure(state="disabled")


# ── Logger adapter dla yt-dlp ──────────────────────────────────────────────
class _YDLLogger:
    """Przekierowuje logi yt-dlp do callbacka."""
    def __init__(self, callback):
        self._cb = callback

    def debug(self, msg):
        # yt-dlp progress lines zaczynają się od [download]
        if msg.startswith("[download]"):
            return  # pomijamy — mamy progress_hook
        self._cb(msg + "\n")

    def info(self, msg):
        self._cb(msg + "\n")

    def warning(self, msg):
        self._cb(f"⚠ {msg}\n")

    def error(self, msg):
        self._cb(f"✖ {msg}\n")


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = App()
    app.mainloop()
