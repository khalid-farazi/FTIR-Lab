"""FTIR Lab v3.1 launcher."""
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import messagebox

import splash_launcher as shared


shared.APP_NAME = "FTIR Lab"
shared.APP_VERSION = "3.1"


def main():
    root = tk.Tk(); root.withdraw()
    shared.load_bundled_fonts()
    verse = shared.select_ayat()
    splash = shared.build_splash(root, verse)
    started = time.monotonic()
    loading = {"ready": False, "error": None, "app_class": None}

    def import_application():
        try:
            from ftir_lab.ftir_app_v3 import FTIRLabApp
            loading["app_class"] = FTIRLabApp
        except BaseException as exc:
            loading["error"] = exc
        finally:
            loading["ready"] = True

    threading.Thread(target=import_application, daemon=True).start()

    def finish_when_ready():
        if not loading["ready"] or time.monotonic() - started < shared.MINIMUM_READING_SECONDS:
            root.after(100, finish_when_ready); return
        if loading["error"] is not None:
            splash.destroy()
            messagebox.showerror("Could not start application", str(loading["error"]))
            root.destroy(); return
        try:
            loading["app_class"](root)
        except BaseException as exc:
            splash.destroy()
            messagebox.showerror("Could not start application", str(exc))
            root.destroy(); return
        splash.destroy(); root.deiconify(); root.lift(); root.focus_force()

    root.after(100, finish_when_ready)
    root.mainloop()


if __name__ == "__main__":
    main()
