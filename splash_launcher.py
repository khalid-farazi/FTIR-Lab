"""Quran-centered launcher for FTIR Lab.

The lightweight splash appears before Matplotlib, SciPy, and pandas load. The
scientific application imports on a worker thread so the splash remains
responsive and its progress indicator continues to animate.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import random
import math
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import ctypes
import webbrowser


APP_NAME = "FTIR Lab"
APP_VERSION = "3.1"
MINIMUM_READING_SECONDS = 10.0
SOUDA_BRANDING = os.environ.get("FTIR_SOUDA_BRANDING", "1") != "0"

INTRO_PASSAGES = [
    (10, 12, 12), (41, 52, 53), (41, 39, 39), (2, 21, 21),
    (2, 23, 24), (2, 170, 170), (12, 108, 108), (50, 16, 16),
    (50, 27, 27), (54, 32, 32), (36, 30, 30), (35, 37, 37),
    (47, 1, 1), (9, 31, 32), (4, 115, 117), (18, 103, 105),
    (16, 74, 75), (18, 4, 5), (28, 56, 56), (14, 35, 36),
    (53, 32, 32),
]

SURAH_NAMES = (
    "Al-Fatihah", "Al-Baqarah", "Ali 'Imran", "An-Nisa", "Al-Ma'idah",
    "Al-An'am", "Al-A'raf", "Al-Anfal", "At-Tawbah", "Yunus", "Hud",
    "Yusuf", "Ar-Ra'd", "Ibrahim", "Al-Hijr", "An-Nahl", "Al-Isra",
    "Al-Kahf", "Maryam", "Taha", "Al-Anbya", "Al-Hajj", "Al-Mu'minun",
    "An-Nur", "Al-Furqan", "Ash-Shu'ara", "An-Naml", "Al-Qasas",
    "Al-'Ankabut", "Ar-Rum", "Luqman", "As-Sajdah", "Al-Ahzab", "Saba",
    "Fatir", "Ya-Sin", "As-Saffat", "Sad", "Az-Zumar", "Ghafir",
    "Fussilat", "Ash-Shura", "Az-Zukhruf", "Ad-Dukhan", "Al-Jathiyah",
    "Al-Ahqaf", "Muhammad", "Al-Fath", "Al-Hujurat", "Qaf",
    "Adh-Dhariyat", "At-Tur", "An-Najm", "Al-Qamar", "Ar-Rahman",
    "Al-Waqi'ah", "Al-Hadid", "Al-Mujadilah", "Al-Hashr",
    "Al-Mumtahanah", "As-Saff", "Al-Jumu'ah", "Al-Munafiqun",
    "At-Taghabun", "At-Talaq", "At-Tahrim", "Al-Mulk", "Al-Qalam",
    "Al-Haqqah", "Al-Ma'arij", "Nuh", "Al-Jinn", "Al-Muzzammil",
    "Al-Muddaththir", "Al-Qiyamah", "Al-Insan", "Al-Mursalat", "An-Naba",
    "An-Nazi'at", "'Abasa", "At-Takwir", "Al-Infitar", "Al-Mutaffifin",
    "Al-Inshiqaq", "Al-Buruj", "At-Tariq", "Al-A'la", "Al-Ghashiyah",
    "Al-Fajr", "Al-Balad", "Ash-Shams", "Al-Layl", "Ad-Duha",
    "Ash-Sharh", "At-Tin", "Al-'Alaq", "Al-Qadr", "Al-Bayyinah",
    "Az-Zalzalah", "Al-'Adiyat", "Al-Qari'ah", "At-Takathur", "Al-'Asr",
    "Al-Humazah", "Al-Fil", "Quraysh", "Al-Ma'un", "Al-Kawthar",
    "Al-Kafirun", "An-Nasr", "Al-Masad", "Al-Ikhlas", "Al-Falaq", "An-Nas",
)


def verse_reference(verse: dict[str, str]) -> str:
    try:
        sura = int(verse["sura"])
        start = int(verse.get("aya_start", verse["aya"]))
        end = int(verse.get("aya_end", start))
        ayat = str(start) if start == end else f"{start}–{end}"
        return f"Surah {SURAH_NAMES[sura - 1]}  {sura}:{ayat}"
    except (KeyError, TypeError, ValueError, IndexError):
        return verse.get("reference", "Quran")


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def state_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    folder = appdata / "SOUDA" / APP_NAME
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "splash-state.json"


def verse_fits_splash(verse: dict[str, str]) -> bool:
    """Keep only verses that remain elegant without scrolling or clipping."""
    arabic = verse.get("arabic", "").strip()
    bengali = verse.get("bengali", "").strip()
    english = verse.get("english", "").strip()
    if not arabic or not bengali or not english:
        return False
    estimated_lines = (
        math.ceil(len(arabic) / 72)
        + math.ceil(len(bengali) / 68)
        + math.ceil(len(english) / 76)
    )
    return (
        len(arabic) <= 210
        and len(bengali) <= 300
        and len(english) <= 310
        and estimated_lines <= 11
    )


def _passage(records, sura, start, end):
    chosen = [v for v in records if int(v["sura"]) == sura
              and start <= int(v["aya"]) <= end]
    if len(chosen) != end - start + 1:
        raise ValueError(f"Missing Quran passage {sura}:{start}-{end}")
    return {
        "sura": sura, "aya": start, "aya_start": start, "aya_end": end,
        "arabic": " ﴿ ".join(v["arabic"] for v in chosen),
        "bengali": " ".join(v["bengali"] for v in chosen),
        "english": " ".join(v["english"] for v in chosen),
    }


def select_ayat() -> dict[str, str]:
    verses = json.loads(resource_path("assets/quran_ayat.json").read_text(encoding="utf-8"))
    state_file = state_path()
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        state = {}

    intro_index = int(state.get("intro_index", 0))
    if intro_index < len(INTRO_PASSAGES):
        passage = _passage(verses, *INTRO_PASSAGES[intro_index])
        state = {"intro_index": intro_index + 1}
    else:
        sura = int(state.get("random_sura", 0))
        aya = int(state.get("random_aya", 1))
        sura_records = [v for v in verses if int(v["sura"]) == sura]
        if not sura_records or aya > len(sura_records):
            sura = random.randint(1, 114)
            sura_records = [v for v in verses if int(v["sura"]) == sura]
            aya = 1
        end = aya
        # Combine consecutive short verses, but never create a crowded card.
        while end < len(sura_records) and end - aya < 2:
            candidate = _passage(verses, sura, aya, end + 1)
            if not verse_fits_splash(candidate):
                break
            end += 1
        passage = _passage(verses, sura, aya, end)
        state = {"intro_index": len(INTRO_PASSAGES), "random_sura": sura,
                 "random_aya": end + 1}
    try:
        state_file.write_text(
            json.dumps(state, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
    return passage


def load_bundled_fonts() -> None:
    """Register bundled OFL fonts privately for this Windows process."""
    if os.name != "nt":
        return
    FR_PRIVATE = 0x10
    for relative in ("assets/fonts/NotoSansBengali.ttf",
                     "assets/fonts/NotoNaskhArabic.ttf"):
        path = resource_path(relative)
        if path.exists():
            try:
                ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
            except (AttributeError, OSError):
                pass


def center_geometry(window: tk.Toplevel, width: int, height: int) -> None:
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = max(0, (screen_width - width) // 2)
    y = max(0, (screen_height - height) // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def build_splash(root: tk.Tk, verse: dict[str, str]) -> tk.Toplevel:
    navy = "#06132F"
    navy_soft = "#0C1D3D"
    cyan = "#78DDE0"
    pale = "#EAFBFB"
    muted = "#AFC7D8"

    splash = tk.Toplevel(root)
    splash.overrideredirect(True)
    splash.configure(background=navy)
    center_geometry(splash, 1050, 700)

    shell = tk.Frame(splash, bg=navy, highlightbackground=cyan,
                     highlightthickness=1)
    shell.pack(fill="both", expand=True)

    left = tk.Frame(shell, bg="#B9F0F0", width=230)
    left.pack(side="left", fill="y")
    left.pack_propagate(False)

    if SOUDA_BRANDING:
        logo = tk.PhotoImage(file=str(resource_path("assets/souda-logo.png")))
        scale = max(1, logo.width() // 235)
        if scale > 1:
            logo = logo.subsample(scale, scale)
        logo_label = tk.Label(left, image=logo, bg="#B9F0F0", bd=0)
        logo_label.image = logo
        logo_label.pack(pady=(94, 24))
        tk.Label(left, text="PRODUCED BY", bg="#B9F0F0", fg="#32465A",
                 font=("Segoe UI Semibold", 10)).pack()
        tk.Label(left, text="SOUDA", bg="#B9F0F0", fg=navy,
                 font=("Segoe UI Semibold", 24)).pack(pady=(2, 0))
    else:
        # Use the supplied FTIR Lab wordmark rather than reconstructing it
        # from fonts.  Integer zoom/subsample keeps Tkinter lightweight and
        # gives the same result in source and packaged applications.
        logo = tk.PhotoImage(file=str(resource_path("assets/ftir-lab-logo.png")))
        logo = logo.zoom(3, 3).subsample(5, 5)
        logo_label = tk.Label(left, image=logo, bg="#B9F0F0", bd=0)
        logo_label.image = logo
        logo_label.pack(pady=(205, 0))

    tk.Label(
        left,
        text="Open scientific plotting for every laboratory.",
        bg="#B9F0F0",
        fg="#29465B",
        font=("Segoe UI Semibold", 9),
        justify="center",
        wraplength=255,
    ).pack(side="bottom", padx=24, pady=(0, 66))

    right = tk.Frame(shell, bg=navy, padx=48, pady=38)
    right.pack(side="left", fill="both", expand=True)

    tk.Label(right, text=f"Scientific spectrum analysis  •  FTIR Lab {APP_VERSION}",
             bg=navy, fg=muted, font=("Segoe UI", 10), anchor="w").pack(
                 fill="x", pady=(0, 18))

    verse_card = tk.Frame(right, bg=navy_soft, padx=28, pady=25,
                          highlightbackground="#284568", highlightthickness=1)
    verse_card.pack(fill="both", expand=True)
    tk.Label(verse_card, text="A VERSE TO BEGIN", bg=navy_soft, fg=cyan,
             font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x")
    verse_text = tk.Text(verse_card, wrap="word", bg=navy_soft, fg="#FFFFFF",
                         relief="flat", bd=0, highlightthickness=0,
                         padx=3, pady=3, cursor="arrow", takefocus=False)
    verse_text.pack(fill="both", expand=True, pady=(14, 0))
    verse_text.tag_configure("arabic", font=("Noto Naskh Arabic", 12),
                             foreground="#FFFFFF", justify="right",
                             spacing1=4, spacing3=12)
    verse_text.tag_configure("bengali", font=("Noto Sans Bengali", 14),
                             foreground="#FFFFFF", justify="left",
                             spacing3=12)
    verse_text.tag_configure("english", font=("Segoe UI", 14),
                             foreground="#D7E7F1", justify="left",
                             spacing3=12)
    verse_text.tag_configure("reference", font=("Segoe UI Semibold", 10),
                             foreground=cyan, justify="right", spacing1=5)
    verse_text.insert("end", verse["arabic"] + "\n", "arabic")
    verse_text.insert("end", verse["bengali"] + "\n", "bengali")
    verse_text.insert("end", verse["english"] + "\n", "english")
    reference = verse_reference(verse)
    verse_text.insert("end", reference + "  ·  Read on Quran.com", "reference")
    verse_text.configure(state="disabled")
    verse_text.tag_bind("reference", "<Button-1>", lambda _event: webbrowser.open(
        f'https://quran.com/{verse["sura"]}?startingVerse={verse.get("aya_start", verse["aya"])}'))
    verse_text.tag_bind("reference", "<Enter>", lambda _event: verse_text.configure(cursor="hand2"))
    verse_text.tag_bind("reference", "<Leave>", lambda _event: verse_text.configure(cursor="arrow"))

    footer = tk.Frame(right, bg=navy, height=48)
    footer.pack(side="bottom", fill="x", pady=(18, 0))
    footer.pack_propagate(False)
    status_label = tk.Label(footer, text="FTIR Lab is starting  ● ○ ○",
                            bg=navy, fg=muted, font=("Segoe UI", 10),
                            anchor="w")
    status_label.pack(fill="x")

    def animate_status(step: int = 0) -> None:
        try:
            status_label.configure(
                text="FTIR Lab is starting  " + ("● ○ ○", "○ ● ○", "○ ○ ●")[step % 3]
            )
            splash.after(420, animate_status, step + 1)
        except tk.TclError:
            pass

    animate_status()
    tk.Label(footer, text="This window closes automatically.", bg=navy,
             fg="#718AA0", font=("Segoe UI", 8), anchor="w").pack(fill="x")
    return splash


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    load_bundled_fonts()
    verse = select_ayat()
    splash = build_splash(root, verse)
    started = time.monotonic()
    loading: dict[str, object] = {"ready": False, "error": None, "app_class": None}

    def import_application() -> None:
        try:
            from ftir_app_v2 import FTIRAppV2
            loading["app_class"] = FTIRAppV2
        except BaseException as exc:  # Report startup failures in the GUI.
            loading["error"] = exc
        finally:
            loading["ready"] = True

    threading.Thread(target=import_application, daemon=True).start()

    def finish_when_ready() -> None:
        elapsed = time.monotonic() - started
        if not loading["ready"] or elapsed < MINIMUM_READING_SECONDS:
            root.after(100, finish_when_ready)
            return
        if loading["error"] is not None:
            splash.destroy()
            messagebox.showerror("Could not start application", str(loading["error"]))
            root.destroy()
            return
        try:
            app_class = loading["app_class"]
            app_class(root)
        except BaseException as exc:
            splash.destroy()
            messagebox.showerror("Could not start application", str(exc))
            root.destroy()
            return
        splash.destroy()
        root.deiconify()
        root.lift()
        root.focus_force()

    root.after(100, finish_when_ready)
    root.mainloop()


if __name__ == "__main__":
    main()
