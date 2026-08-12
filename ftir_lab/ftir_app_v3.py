"""FTIR Lab v3.1.

V3 is an isolated extension of the stable v2.2 engine. It adds a conservative,
editable functional-group suggestion library and portable project files.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import uuid
import webbrowser

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ftir_app import Spectrum, read_spectra  # noqa: E402
from ftir_app_v2 import FTIRAppV2  # noqa: E402


VERSION = "3.1"
CONTEXTS = ["All suitable contexts", "General", "Silicate", "Borate",
            "Hydroxyl / water"]


def bundled_library_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    packaged = base / "ftir_lab" / "functional_groups.default.json"
    return packaged if packaged.exists() else Path(__file__).with_name(
        "functional_groups.default.json")


def user_library_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home()))
    folder = appdata / "FTIR Lab" / "v3.1"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "functional_groups.json"


def doi_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.lower().startswith(("http://", "https://")):
        return value
    value = re.sub(r"^(doi:\s*)", "", value, flags=re.I)
    return f"https://doi.org/{value}"


SUBSCRIPT_TABLE = str.maketrans("0123456789+-()", "₀₁₂₃₄₅₆₇₈₉₊₋₍₎")
FORMULA_PATTERN = re.compile(r"(?<![A-Za-z])(?:[A-Z][a-z]?\d*){2,}(?![A-Za-z])")


def format_chemical_formula(text: str) -> str:
    """Format digits only inside likely multi-element chemical formulae."""
    def convert(match):
        return match.group(0).translate(SUBSCRIPT_TABLE)
    return FORMULA_PATTERN.sub(convert, str(text))


class FTIRLabApp(FTIRAppV2):
    VERSION = VERSION

    def _variables(self):
        super()._variables()
        # Requested v3 default: nearby labels are not staggered unless enabled.
        self.stagger_peak_labels.set(False)
        self.assignment_context = tk.StringVar(value="All suitable contexts")
        self.assign_unassigned_only = tk.BooleanVar(value=True)
        self.peak_assignment_labels = tk.StringVar(
            value="Wavenumber + chemical symbol")
        self.auto_typography = tk.BooleanVar(value=True)
        self._live_preview_job = None
        self.custom_annotations = []

    def __init__(self, root):
        self.functional_library: list[dict] = []
        super().__init__(root)
        root.title(f"FTIR Lab v{self.VERSION}")
        self._load_functional_library()
        self._build_v3_menu()
        self._finish_v31_publication_ui()
        self._build_quick_workflow()
        self._build_assignment_sidebar()
        self._highlight_essential_controls()
        self._enable_live_preview()
        self.canvas.mpl_connect("pick_event", self._on_pick)
        self.root.after_idle(self._update_side_scroll_region)

    def _finish_v31_publication_ui(self):
        side = self._sidebar_frame()
        if side:
            for widget in side.winfo_children():
                if isinstance(widget, ttk.LabelFrame) and "publication export" in widget.cget("text"):
                    widget.configure(text="Publication export")
                    for child in list(widget.winfo_children()):
                        if isinstance(child, ttk.Button) and child.cget("text") in {
                                "Preview export layout", "Apply typography"}:
                            child.destroy()
                    ttk.Checkbutton(widget, text="Automatic typography",
                                    variable=self.auto_typography,
                                    command=self._schedule_live_preview).pack(
                                        anchor="w", pady=(4, 2))

    def _enable_live_preview(self):
        variables = (self.publication_width, self.publication_aspect,
                     self.base_font_size, self.legend_font_ratio,
                     self.peak_legend_ratio, self.peak_label_direction,
                     self.stagger_peak_labels, self.mode, self.spacing,
                     self.curve_height, self.label_style, self.label_position)
        for variable in variables:
            variable.trace_add("write", self._schedule_live_preview)

    def _schedule_live_preview(self, *_args):
        if self._live_preview_job:
            self.root.after_cancel(self._live_preview_job)
        self._live_preview_job = self.root.after(180, self._run_live_preview)

    def _run_live_preview(self):
        self._live_preview_job = None
        try:
            width, height = self._publication_dimensions()
            self.redraw()
            self._apply_publication_layout(width, height, resize_widget=True)
        except (ValueError, tk.TclError):
            pass

    def _font_sizes(self):
        if not getattr(self, "auto_typography", None) or not self.auto_typography.get():
            return super()._font_sizes()
        try:
            width, height = self._publication_dimensions()
        except Exception:
            width, height = 7.2, 5.0
        spectra = max(1, len([s for s in self.spectra if s.visible]))
        density = min(2.0, len(self.peaks) / max(1, spectra * 8))
        base = max(7.0, min(10.5, 7.3 + .35 * width + .08 * min(height, 8)))
        legend = max(6.5, base - .25 - .12 * max(0, spectra - 6))
        peak = max(5.3, min(base - 1.0, legend * (.82 - .08 * density)))
        return base, legend, peak

    def redraw(self):
        super().redraw()
        for text in self.ax.texts:
            text.set_text(format_chemical_formula(text.get_text()))
        legend = self.ax.get_legend()
        if legend:
            for text in legend.get_texts():
                text.set_text(format_chemical_formula(text.get_text()))
            legend.set_handlelength(1.25)
            legend.set_handletextpad(.45)
            legend.set_columnspacing(1.0)
        for index, item in enumerate(self.custom_annotations):
            artist = self.ax.text(item["x"], item["y"],
                                  format_chemical_formula(item["text"]),
                                  transform=self.ax.transAxes, ha="center", va="center",
                                  fontsize=self._font_sizes()[0], color="#263640",
                                  bbox=dict(boxstyle="round,pad=.25", facecolor="white",
                                            edgecolor="#8AA2AE", alpha=.9), picker=True)
            artist.set_gid(f"text:{index}")
        self.canvas.draw_idle()

    # ---------- beginner workflow and visual emphasis ----------
    def _sidebar_frame(self):
        return next((w for w in self.side_scroller.winfo_children()
                     if isinstance(w, ttk.Frame)), None)

    def _build_quick_workflow(self):
        side = self._sidebar_frame()
        if side is None:
            return
        first = side.winfo_children()[0] if side.winfo_children() else None
        card = tk.Frame(side, bg="#E8F2F6", highlightbackground="#7FA9BA",
                        highlightthickness=1, padx=9, pady=8)
        card.pack(fill="x", pady=(0, 8), before=first)
        tk.Label(card, text="ESSENTIAL WORKFLOW", bg="#E8F2F6", fg="#173B4D",
                 font=("Segoe UI Semibold", 9), anchor="w").pack(fill="x")
        tk.Label(card,
                 text="ADD  ·  PREPARE  ·  ANALYZE  ·  EXPORT",
                 bg="#E8F2F6", fg="#34596A", font=("Segoe UI", 8),
                 anchor="w").pack(fill="x", pady=(1, 6))
        primary = tk.Frame(card, bg="#E8F2F6"); primary.pack(fill="x")
        primary_actions = [
            ("1  Add files", self.add_files),
            ("2  Smooth", self.guided_smoothing),
            ("3  Detect", self.auto_detect_peaks),
        ]
        for index, (text, command) in enumerate(primary_actions):
            primary.grid_columnconfigure(index, weight=1, uniform="workflow")
            tk.Button(primary, text=text, command=command, bg="#D4E8EF",
                      fg="#102F3E", activebackground="#BFDCE6", relief="flat",
                      font=("Segoe UI Semibold", 8), padx=5, pady=3).grid(
                          row=0, column=index, sticky="ew",
                          padx=2)
        secondary = tk.Frame(card, bg="#E8F2F6"); secondary.pack(fill="x", pady=(4, 0))
        secondary_actions = [
            ("4  Assign", self.guided_assignment),
            ("5  Export plot", lambda: self.export_publication(None)),
            ("6  Export to Excel", self.save_peaks),
        ]
        for index, (text, command) in enumerate(secondary_actions):
            secondary.grid_columnconfigure(index, weight=1, uniform="workflow")
            tk.Button(secondary, text=text, command=command, bg="#D4E8EF",
                      fg="#102F3E", activebackground="#BFDCE6", relief="flat",
                      font=("Segoe UI Semibold", 8), padx=5, pady=3).grid(
                          row=0, column=index, sticky="ew",
                          padx=2)

    def guided_smoothing(self):
        """Beginner presets that favor preservation over cosmetic flattening."""
        win = tk.Toplevel(self.root)
        win.title("Guided spectral smoothing")
        win.geometry("430x335")
        win.transient(self.root); win.grab_set()
        body = ttk.Frame(win, padding=18); body.pack(fill="both", expand=True)
        ttk.Label(body, text="Smoothing",
                  font=("Segoe UI Semibold", 14), foreground="#164E63").pack(anchor="w")
        ttk.Label(body, text="Start with a small window.",
                  foreground="#6A4B1C").pack(anchor="w", pady=(2, 11))
        choice = tk.StringVar(value="Light · 11 points")
        presets = {
            "Raw · no smoothing": 0,
            "Light · 11 points": 11,
            "Moderate · 21 points": 21,
            "Strong · 41 points": 41,
            "Custom": None,
        }
        for label in list(presets)[:-1]:
            ttk.Radiobutton(body, text=label, value=label,
                            variable=choice).pack(anchor="w", pady=2)
        custom_row = ttk.Frame(body); custom_row.pack(fill="x", pady=2)
        ttk.Radiobutton(custom_row, text="Custom:", value="Custom",
                        variable=choice).pack(side="left")
        custom = tk.StringVar(value=str(self.smooth.get()))
        custom_entry = ttk.Entry(custom_row, textvariable=custom, width=8)
        custom_entry.pack(side="left", padx=5)
        ttk.Label(custom_row, text="points").pack(side="left")
        custom_entry.bind("<FocusIn>", lambda _event: choice.set("Custom"))

        def apply_smoothing():
            try:
                value = presets[choice.get()]
                if value is None:
                    value = max(0, int(custom.get()))
                    if value and value % 2 == 0:
                        value += 1
                self.smooth.set(value)
            except (ValueError, tk.TclError):
                messagebox.showerror("Invalid smoothing window",
                                     "Enter zero or a positive whole number.", parent=win)
                return
            win.destroy(); self.redraw()
            self.status.config(text=(
                "Smoothing disabled — raw signal shown" if value == 0 else
                f"Applied Savitzky–Golay smoothing: {value}-point window — inspect peak preservation"))

        buttons = ttk.Frame(body); buttons.pack(fill="x", pady=(13, 0))
        ttk.Button(buttons, text="Apply", command=apply_smoothing,
                   style="Essential.TButton").pack(anchor="center", ipadx=24)
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(
            anchor="center", pady=(5, 0), ipadx=17)

    def _highlight_essential_controls(self):
        style = ttk.Style(self.root)
        style.configure("Essential.TLabel", foreground="#0B4960",
                        background="#E5F1F5", padding=(3, 2),
                        font=("Segoe UI Semibold", 9))
        style.configure("Essential.TButton", foreground="#0E4A60",
                        font=("Segoe UI Semibold", 9))
        important_labels = {"Baseline", "Savitzky–Golay window", "Layout",
                            "Min. prominence (%)"}

        def walk(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Label) and child.cget("text") in important_labels:
                    child.configure(style="Essential.TLabel")
                    # A narrow marker highlights the workflow row while the
                    # native Windows entry/combobox appearance (and arrow) stays intact.
                    marker = tk.Frame(child.master, bg="#2B718A", width=4)
                    marker.pack(side="left", fill="y", padx=(0, 4), before=child)
                if isinstance(child, ttk.Button) and child.cget("text") in {
                    "Add files…", "Auto-detect peaks", "Export figure…",
                    "Save peaks…", "Single column", "Double column"}:
                    child.configure(style="Essential.TButton")
                walk(child)

        walk(self.root)

    # ---------- functional-group library ----------
    def _load_functional_library(self):
        path = user_library_path()
        source = path if path.exists() else bundled_library_path()
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
            entries = payload.get("entries", payload)
            if not isinstance(entries, list):
                raise ValueError("The library must contain an entries list.")
            self.functional_library = [self._normalize_library_entry(e) for e in entries]
        except Exception as exc:
            self.functional_library = []
            messagebox.showerror("Functional-group library",
                                 f"Could not load the assignment library:\n{exc}")

    @staticmethod
    def _normalize_library_entry(entry):
        result = dict(entry)
        result.setdefault("id", uuid.uuid4().hex)
        result.setdefault("enabled", True)
        result.setdefault("context", "General")
        result.setdefault("group", "Unspecified band")
        result.setdefault("symbol", FTIRLabApp._default_symbol(result["group"]))
        result.setdefault("note", "")
        result.setdefault("citation", "")
        result.setdefault("doi", "")
        result["min_cm-1"] = float(result["min_cm-1"])
        result["max_cm-1"] = float(result["max_cm-1"])
        if result["min_cm-1"] > result["max_cm-1"]:
            result["min_cm-1"], result["max_cm-1"] = (
                result["max_cm-1"], result["min_cm-1"])
        return result

    @staticmethod
    def _default_symbol(group):
        text = group.lower()
        mappings = (
            ("si–oh", "Si–OH"), ("si-oh", "Si–OH"),
            ("silicate network", "Si–O–Si"), ("ring vibration", "Si–O–Si"),
            ("non-bridging", "Si–O(NBO)"), ("o–si–o", "O–Si–O"),
            ("si–o", "Si–O–Si"), ("si-o", "Si–O–Si"),
            ("bo3", "BO₃"), ("bo4", "BO₄"), ("b–o–b", "B–O–B"),
            ("h–o–h", "H–O–H"), ("o–h", "O–H"), ("n–h", "N–H"),
            ("c=o", "C=O"), ("c=c", "C=C"), ("c–o", "C–O"),
            ("c–h", "C–H"),
        )
        for needle, symbol in mappings:
            if needle in text:
                return symbol
        return group.split(" stretching")[0].split(" bending")[0][:18]

    def _compact_peak_symbol(self, peak):
        symbol = str(peak.get("assignment_symbol", "")).strip()
        verbose = (len(symbol) > 14 or any(word in symbol.lower() for word in
                   ("stretching", "bending", "vibration", "network", "/")))
        if not symbol or verbose:
            symbol = self._default_symbol(peak.get("assignment", ""))
        return symbol[:14]

    def _save_functional_library(self):
        payload = {
            "schema_version": 1,
            "notice": ("Assignments are literature-guided suggestions. Confirm using "
                       "sample chemistry, band shape, controls, and complementary evidence."),
            "entries": self.functional_library,
        }
        user_library_path().write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                       encoding="utf-8")

    def _build_v3_menu(self):
        menu = self.root.nametowidget(self.root.cget("menu"))
        library = tk.Menu(menu, tearoff=False)
        library.add_command(label="Guided assignment…",
                            command=self.guided_assignment)
        library.add_command(label="Suggest groups for current peaks",
                            command=self.auto_assign_functional_groups)
        library.add_command(label="Review assignments…",
                            command=self.review_assignments)
        library.add_separator()
        library.add_command(label="Edit functional-group library…",
                            command=self.edit_functional_library)
        library.add_command(label="Open user library folder",
                            command=self.open_library_folder)
        menu.add_cascade(label="Assignments", menu=library)
        annotations = tk.Menu(menu, tearoff=False)
        annotations.add_command(label="Add text box…", command=self.add_text_box)
        annotations.add_command(label="Edit peak labels…", command=self.review_assignments)
        menu.add_cascade(label="Annotations", menu=annotations)
        analysis = tk.Menu(menu, tearoff=False)
        analysis.add_command(label="Analysis summary…", command=self.show_analysis_summary)
        menu.add_cascade(label="Analysis", menu=analysis)

    def analysis_summary(self):
        return {
            "application": f"FTIR Lab {self.VERSION}",
            "samples": [s.name for s in self.spectra],
            "sources": [s.source for s in self.spectra],
            "processing": {
                "baseline": self.baseline.get(), "asls_lambda": self.lam.get(),
                "asls_asymmetry": self.asym.get(),
                "savgol_window": self.smooth.get(),
                "normalization": self.normalize.get(),
                "band_direction": self.bands.get(),
                "air_artifact_interpolation": self.remove_air.get(),
            },
            "peak_detection": {
                "prominence_percent": self.peak_prominence.get(),
                "minimum_separation_cm-1": self.peak_distance.get(),
                "maximum_per_sample": self.peak_maximum.get(),
            },
            "peaks": len(self.peaks),
            "confirmed_assignments": sum(bool(p.get("assignment_confirmed")) for p in self.peaks),
            "notice": "Suggested assignments require verification against the spectrum and literature.",
        }

    def show_analysis_summary(self):
        summary = self.analysis_summary()
        win = tk.Toplevel(self.root); win.title("Analysis summary")
        win.geometry("680x560"); win.transient(self.root)
        text = tk.Text(win, wrap="word", padx=12, pady=12, font=("Consolas", 10))
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(summary, indent=2, ensure_ascii=False))
        text.configure(state="disabled")
        row = ttk.Frame(win, padding=8); row.pack(fill="x")
        def export_summary():
            path = filedialog.asksaveasfilename(defaultextension=".json",
                filetypes=[("JSON provenance", "*.json")])
            if path:
                Path(path).write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
        ttk.Button(row, text="Export summary…", command=export_summary).pack(side="left")
        ttk.Button(row, text="Close", command=win.destroy).pack(side="right")

    def add_text_box(self):
        text = simpledialog.askstring("Add text box", "Text:", parent=self.root)
        if not text:
            return
        self.custom_annotations.append({"text": text, "x": .5, "y": .92})
        self.redraw()
        self.status.config(text="Text box added — double-click it to edit")

    def _edit_artist(self, artist):
        gid = artist.get_gid() or ""
        if gid.startswith("peak:"):
            peak_id = gid.split(":", 1)[1]
            peak = next((p for p in self.peaks if str(id(p)) == peak_id), None)
            if peak is None:
                return
            value = simpledialog.askstring(
                "Edit peak label", "Label or chemical formula:",
                initialvalue=peak.get("manual_label", peak.get("assignment_symbol", "")),
                parent=self.root)
            if value is not None:
                peak["manual_label"] = value.strip()
                self.redraw()
        elif gid.startswith("text:"):
            index = int(gid.split(":", 1)[1])
            value = simpledialog.askstring("Edit text box", "Text:",
                                           initialvalue=self.custom_annotations[index]["text"],
                                           parent=self.root)
            if value is not None:
                self.custom_annotations[index]["text"] = value
                self.redraw()

    def _on_pick(self, event):
        mouse = getattr(event, "mouseevent", None)
        if mouse and getattr(mouse, "dblclick", False):
            self._edit_artist(event.artist)

    def _build_assignment_sidebar(self):
        side = self._sidebar_frame()
        if side is None:
            return
        apply_button = next((w for w in side.winfo_children()
                             if isinstance(w, ttk.Button)
                             and w.cget("text") == "Apply / redraw"), None)
        box = ttk.LabelFrame(side, text="V3 functional-group suggestions", padding=8)
        if apply_button:
            box.pack(fill="x", pady=(0, 7), before=apply_button)
        else:
            box.pack(fill="x", pady=(0, 7))
        self._combo_row(box, "Material context", self.assignment_context, CONTEXTS)
        self._combo_row(box, "Plot peak labels", self.peak_assignment_labels,
                        ["Wavenumber only", "Wavenumber + chemical symbol",
                         "Chemical symbol only"])
        ttk.Checkbutton(box, text="Keep existing manual assignments",
                        variable=self.assign_unassigned_only).pack(anchor="w", pady=(3, 0))
        ttk.Button(box, text="Guided assignment…",
                   command=self.guided_assignment,
                   style="Essential.TButton").pack(fill="x", pady=(6, 3))
        row = ttk.Frame(box); row.pack(fill="x")
        ttk.Button(row, text="Review suggestions…",
                   command=self.review_assignments).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Edit library…",
                   command=self.edit_functional_library).pack(side="left", expand=True,
                                                               fill="x", padx=(4, 0))
        ttk.Label(box, text="Suggestions require researcher confirmation.",
                  foreground="#6A4B1C", wraplength=390).pack(anchor="w", pady=(5, 0))

    def guided_assignment(self):
        win = tk.Toplevel(self.root)
        win.title("Guided functional-group assignment")
        win.geometry("570x390")
        win.transient(self.root); win.grab_set()
        body = ttk.Frame(win, padding=18); body.pack(fill="both", expand=True)
        ttk.Label(body, text="Assign FTIR bands in three simple steps",
                  font=("Segoe UI Semibold", 14), foreground="#164E63").pack(anchor="w")
        ttk.Label(body, text=("The software will suggest literature ranges. It will not claim "
                              "that a compound is proven from one peak."),
                  wraplength=520, foreground="#6A4B1C").pack(anchor="w", pady=(4, 16))
        ttk.Label(body, text="1. What best describes your material?",
                  font=("Segoe UI Semibold", 10)).pack(anchor="w")
        friendly = {
            "General organic / unknown": "General",
            "Silicate, silica, cement, clay, or glass": "Silicate",
            "Borate or borosilicate material": "Borate",
            "Water, hydration, or hydroxyl study": "Hydroxyl / water",
            "Search every enabled library entry": "All suitable contexts",
        }
        selected = tk.StringVar(value=next(
            (label for label, value in friendly.items()
             if value == self.assignment_context.get()),
            "General organic / unknown"))
        combo = ttk.Combobox(body, textvariable=selected, values=list(friendly),
                             state="readonly", width=52)
        combo.pack(fill="x", pady=(5, 14))
        ttk.Label(body, text="2. Peak source",
                  font=("Segoe UI Semibold", 10)).pack(anchor="w")
        peak_source = tk.StringVar(value=(
            "Use current detected/selected peaks" if self.peaks
            else "Detect peaks automatically, then suggest"))
        for label in ("Detect peaks automatically, then suggest",
                      "Use current detected/selected peaks"):
            ttk.Radiobutton(body, text=label, value=label,
                            variable=peak_source).pack(anchor="w", pady=1)
        ttk.Label(body, text=("3. A review table will rank matching ranges. Double-click the "
                              "chemically reasonable suggestion to confirm it."),
                  wraplength=520).pack(anchor="w", pady=(14, 8))

        def continue_assignment():
            self.assignment_context.set(friendly[selected.get()])
            win.destroy()
            if peak_source.get().startswith("Detect"):
                self.auto_detect_peaks()
            if self.peaks:
                self.auto_assign_functional_groups()

        buttons = ttk.Frame(body); buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Continue to suggestions",
                   command=continue_assignment,
                   style="Essential.TButton").pack(side="right")
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=6)

    def _eligible_library_entries(self):
        context = self.assignment_context.get()
        if context == "All suitable contexts":
            return [e for e in self.functional_library if e.get("enabled", True)]
        return [e for e in self.functional_library if e.get("enabled", True)
                and e.get("context") in {"General", context}]

    def suggestions_for_wavenumber(self, wavenumber):
        matches = [e for e in self._eligible_library_entries()
                   if e["min_cm-1"] <= wavenumber <= e["max_cm-1"]]
        matches.sort(key=lambda e: (
            0 if e.get("context") == self.assignment_context.get() else 1,
            e["max_cm-1"] - e["min_cm-1"],
            abs(wavenumber - (e["min_cm-1"] + e["max_cm-1"]) / 2),
        ))
        return matches

    def auto_assign_functional_groups(self):
        if not self.peaks:
            messagebox.showinfo("No peaks",
                                "Detect or select peaks before suggesting functional groups.")
            return
        assigned = ambiguous = unmatched = skipped = 0
        for peak in self.peaks:
            if self.assign_unassigned_only.get() and peak.get("assignment"):
                skipped += 1
                continue
            matches = self.suggestions_for_wavenumber(float(peak["x"]))
            peak["assignment_candidates"] = [dict(match) for match in matches]
            if not matches:
                peak.pop("assignment", None)
                peak.pop("assignment_citation", None)
                unmatched += 1
                continue
            choice = matches[0]
            peak["assignment"] = choice["group"]
            peak["assignment_symbol"] = choice.get("symbol") or self._default_symbol(
                choice["group"])
            peak["assignment_citation"] = choice.get("citation", "")
            peak["assignment_doi"] = choice.get("doi", "")
            peak["assignment_library_id"] = choice.get("id", "")
            assigned += 1
            ambiguous += int(len(matches) > 1)
        self.redraw()
        self.status.config(text=(f"Suggested assignments for {assigned} peaks; "
                                 f"{ambiguous} have alternatives, {unmatched} unmatched, "
                                 f"{skipped} manual assignments kept — review before publication"))
        self.review_assignments()

    def review_assignments(self):
        win = tk.Toplevel(self.root)
        win.title("Review functional-group suggestions")
        win.geometry("1120x560")
        win.transient(self.root)
        top = ttk.Frame(win, padding=9); top.pack(fill="both", expand=True)
        ttk.Label(top, text=("Suggested matches are hypotheses, not identification. Select a "
                            "candidate and confirm it only when chemically reasonable."),
                  foreground="#6A4B1C", wraplength=1040).pack(anchor="w", pady=(0, 7))
        columns = ("sample", "peak", "group", "range", "context", "source")
        tree = ttk.Treeview(top, columns=columns, show="headings", selectmode="browse")
        labels = ("Sample", "Peak (cm⁻¹)", "Suggested assignment", "Library range",
                  "Context", "Citation / DOI")
        widths = (145, 90, 245, 115, 105, 330)
        for col, label, width in zip(columns, labels, widths):
            tree.heading(col, text=label); tree.column(col, width=width)
        scroll = ttk.Scrollbar(top, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        row_map = {}
        for peak_index, peak in enumerate(self.peaks):
            matches = peak.get("assignment_candidates") or self.suggestions_for_wavenumber(
                float(peak["x"]))
            if not matches:
                iid = f"{peak_index}:none"
                tree.insert("", "end", iid=iid, values=(peak["sample"], f'{peak["x"]:.1f}',
                            "No library match", "—", "—", "—"))
                row_map[iid] = (peak_index, None)
            for candidate_index, entry in enumerate(matches):
                iid = f"{peak_index}:{candidate_index}"
                source = entry.get("doi") or entry.get("citation", "")
                tree.insert("", "end", iid=iid, values=(
                    peak["sample"], f'{peak["x"]:.1f}', entry["group"],
                    f'{entry["min_cm-1"]:.0f}–{entry["max_cm-1"]:.0f}',
                    entry.get("context", "General"), source))
                row_map[iid] = (peak_index, entry)

        controls = ttk.Frame(win, padding=(9, 0, 9, 9)); controls.pack(fill="x")

        def selected():
            selection = tree.selection()
            return row_map.get(selection[0]) if selection else None

        def confirm():
            item = selected()
            if not item or item[1] is None:
                return
            peak, entry = self.peaks[item[0]], item[1]
            peak["assignment"] = entry["group"]
            peak["assignment_symbol"] = entry.get("symbol") or self._default_symbol(
                entry["group"])
            peak["assignment_citation"] = entry.get("citation", "")
            peak["assignment_doi"] = entry.get("doi", "")
            peak["assignment_library_id"] = entry.get("id", "")
            peak["assignment_confirmed"] = True
            self.redraw()
            self.status.config(text=f"Confirmed {entry['group']} at {peak['x']:.1f} cm⁻¹")

        def clear():
            item = selected()
            if not item:
                return
            peak = self.peaks[item[0]]
            for key in ("assignment", "assignment_symbol", "assignment_citation", "assignment_doi",
                        "assignment_library_id", "assignment_confirmed"):
                peak.pop(key, None)
            self.redraw()

        def source():
            item = selected()
            if not item or item[1] is None:
                return
            url = doi_url(item[1].get("doi", ""))
            if url:
                webbrowser.open(url)
            else:
                self.root.clipboard_clear()
                self.root.clipboard_append(item[1].get("citation", ""))
                messagebox.showinfo("Citation copied", "The citation was copied to the clipboard.",
                                    parent=win)

        ttk.Button(controls, text="Use selected suggestion", command=confirm,
                   style="Essential.TButton").pack(side="left")
        ttk.Button(controls, text="Open DOI / copy citation", command=source).pack(
            side="left", padx=5)
        ttk.Button(controls, text="Clear assignment", command=clear).pack(side="left")
        ttk.Button(controls, text="Close", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", lambda _event: confirm())

    def edit_functional_library(self):
        win = tk.Toplevel(self.root)
        win.title("Editable functional-group library")
        win.geometry("1120x570")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=9); frame.pack(fill="both", expand=True)
        columns = ("on", "context", "group", "range", "citation")
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        for col, label, width in zip(columns,
                ("Use", "Context", "Assignment", "Range (cm⁻¹)", "Citation / DOI"),
                (48, 120, 260, 125, 420)):
            tree.heading(col, text=label); tree.column(col, width=width)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")

        def refresh():
            tree.delete(*tree.get_children())
            for index, entry in enumerate(self.functional_library):
                tree.insert("", "end", iid=str(index), values=(
                    "Yes" if entry.get("enabled", True) else "No", entry.get("context"),
                    entry.get("group"),
                    f'{entry["min_cm-1"]:.0f}–{entry["max_cm-1"]:.0f}',
                    entry.get("doi") or entry.get("citation", "")))

        def edit(existing=None, index=None):
            self._library_entry_dialog(win, existing, lambda value: save_entry(value, index))

        def save_entry(value, index):
            if index is None:
                self.functional_library.append(value)
            else:
                self.functional_library[index] = value
            self._save_functional_library(); refresh()

        def selected_index():
            selection = tree.selection()
            return int(selection[0]) if selection else None

        def edit_selected():
            index = selected_index()
            if index is not None:
                edit(dict(self.functional_library[index]), index)

        def toggle():
            index = selected_index()
            if index is not None:
                self.functional_library[index]["enabled"] = not self.functional_library[index].get(
                    "enabled", True)
                self._save_functional_library(); refresh()

        def delete():
            index = selected_index()
            if index is not None and messagebox.askyesno(
                    "Delete library entry", "Delete the selected entry?", parent=win):
                self.functional_library.pop(index); self._save_functional_library(); refresh()

        controls = ttk.Frame(win, padding=(9, 0, 9, 9)); controls.pack(fill="x")
        ttk.Button(controls, text="Add entry…", command=lambda: edit()).pack(side="left")
        ttk.Button(controls, text="Edit selected…", command=edit_selected).pack(side="left", padx=5)
        ttk.Button(controls, text="Enable / disable", command=toggle).pack(side="left")
        ttk.Button(controls, text="Delete", command=delete).pack(side="left", padx=5)
        ttk.Button(controls, text="Close", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", lambda _event: edit_selected())
        refresh()

    def _library_entry_dialog(self, parent, existing, on_save):
        data = existing or {"enabled": True, "context": "General", "group": "",
                            "min_cm-1": 0, "max_cm-1": 0, "note": "",
                            "citation": "", "doi": ""}
        win = tk.Toplevel(parent); win.title("Functional-group entry")
        win.geometry("650x430"); win.transient(parent); win.grab_set()
        body = ttk.Frame(win, padding=12); body.pack(fill="both", expand=True)
        variables = {
            "enabled": tk.BooleanVar(value=data.get("enabled", True)),
            "context": tk.StringVar(value=data.get("context", "General")),
            "group": tk.StringVar(value=data.get("group", "")),
            "symbol": tk.StringVar(value=data.get("symbol", self._default_symbol(
                data.get("group", "")))),
            "min_cm-1": tk.StringVar(value=str(data.get("min_cm-1", ""))),
            "max_cm-1": tk.StringVar(value=str(data.get("max_cm-1", ""))),
            "note": tk.StringVar(value=data.get("note", "")),
            "citation": tk.StringVar(value=data.get("citation", "")),
            "doi": tk.StringVar(value=data.get("doi", "")),
        }
        ttk.Checkbutton(body, text="Use this entry for suggestions",
                        variable=variables["enabled"]).pack(anchor="w", pady=(0, 5))
        fields = [
            ("Context", "context"), ("Assignment / group", "group"),
            ("Short plot symbol", "symbol"),
            ("Minimum wavenumber (cm⁻¹)", "min_cm-1"),
            ("Maximum wavenumber (cm⁻¹)", "max_cm-1"),
            ("Interpretation note", "note"), ("Full citation", "citation"),
            ("DOI or URL", "doi"),
        ]
        for label, key in fields:
            row = ttk.Frame(body); row.pack(fill="x", pady=3)
            ttk.Label(row, text=label, width=28).pack(side="left")
            if key == "context":
                ttk.Combobox(row, textvariable=variables[key],
                             values=CONTEXTS[1:], state="normal").pack(
                                 side="left", fill="x", expand=True)
            else:
                ttk.Entry(row, textvariable=variables[key]).pack(
                    side="left", fill="x", expand=True)

        def save():
            try:
                value = {
                    "id": data.get("id", uuid.uuid4().hex),
                    "enabled": variables["enabled"].get(),
                    "context": variables["context"].get().strip() or "General",
                    "group": variables["group"].get().strip(),
                    "symbol": variables["symbol"].get().strip(),
                    "min_cm-1": float(variables["min_cm-1"].get()),
                    "max_cm-1": float(variables["max_cm-1"].get()),
                    "note": variables["note"].get().strip(),
                    "citation": variables["citation"].get().strip(),
                    "doi": variables["doi"].get().strip(),
                }
                if not value["group"]:
                    raise ValueError("Enter an assignment name.")
                value = self._normalize_library_entry(value)
            except ValueError as exc:
                messagebox.showerror("Invalid entry", str(exc), parent=win); return
            on_save(value); win.destroy()

        buttons = ttk.Frame(body); buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="Save entry", command=save,
                   style="Essential.TButton").pack(side="right")
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right", padx=5)

    def open_library_folder(self):
        path = user_library_path().parent
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())

    # ---------- portable projects and assignment-aware peak export ----------
    def _v3_settings(self):
        return {
            "baseline": self.baseline.get(), "band_direction": self.bands.get(),
            "lambda": self.lam.get(), "asymmetry": self.asym.get(),
            "smooth": self.smooth.get(), "normalization": self.normalize.get(),
            "air_artifact_correction": self.remove_air.get(),
            "air_range_cm-1": [self.air_low.get(), self.air_high.get()],
            "peak_detection": {
                "scope": self.peak_scope.get(), "mode": self.peak_mode.get(),
                "prominence_percent": self.peak_prominence.get(),
                "minimum_separation_cm-1": self.peak_distance.get(),
                "maximum_per_sample": self.peak_maximum.get(),
                "range_cm-1": [self.peak_low.get(), self.peak_high.get()]},
            "layout": self.mode.get(), "spacing": self.spacing.get(),
            "height_per_curve_in": self.curve_height.get(),
            "curve_labels": self.label_style.get(),
            "direct_label_position": self.label_position.get(),
            "xlabel": self.xlabel.get(), "ylabel": self.ylabel.get(),
            "automatic_ylabel": self.auto_ylabel.get(),
            "assignment_context": self.assignment_context.get(),
            "peak_assignment_labels": self.peak_assignment_labels.get(),
            "stagger_peak_labels": self.stagger_peak_labels.get(),
            "publication_width": self.publication_width.get(),
            "publication_aspect": self.publication_aspect.get(),
            "base_font_size": self.base_font_size.get(),
        }

    def save_project(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".hftir.json",
            filetypes=[("FTIR Lab portable project", "*.hftir.json"),
                       ("JSON", "*.json")])
        if not path:
            return
        payload = {
            "format": "FTIR Lab portable project", "format_version": 3,
            "application_version": self.VERSION,
            "settings": self._v3_settings(),
            "spectra": [], "peaks": self.peaks,
            "annotations": self.custom_annotations,
        }
        for spectrum in self.spectra:
            item = {k: v for k, v in asdict(spectrum).items() if k not in {"x", "y"}}
            item["x"] = np.asarray(spectrum.x, dtype=float).tolist()
            item["y"] = np.asarray(spectrum.y, dtype=float).tolist()
            payload["spectra"].append(item)
        Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                              encoding="utf-8")
        self.status.config(text=f"Saved portable project with embedded spectra: {path}")

    def load_project(self):
        path = filedialog.askopenfilename(
            filetypes=[("FTIR Lab projects", "*.hftir.json *.json"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            metadata = data.get("spectra", [])
            if metadata and all("x" in item and "y" in item for item in metadata):
                loaded = [Spectrum(
                    item.get("name", "Spectrum"),
                    np.asarray(item["x"], dtype=float),
                    np.asarray(item["y"], dtype=float),
                    item.get("source", "embedded project data"),
                    group=item.get("group", "Group 1"),
                    color=item.get("color", "#0072B2"),
                    linestyle=item.get("linestyle", "-"),
                    visible=item.get("visible", True)) for item in metadata]
            else:
                loaded = self._load_legacy_project_spectra(metadata)
            self.spectra = loaded
            self.peaks = data.get("peaks", [])
            self.custom_annotations = data.get("annotations", [])
            self._restore_settings(data.get("settings", {}))
            settings = data.get("settings", {})
            for key, variable in {
                "assignment_context": self.assignment_context,
                "peak_assignment_labels": self.peak_assignment_labels,
                "stagger_peak_labels": self.stagger_peak_labels,
                "publication_width": self.publication_width,
                "publication_aspect": self.publication_aspect,
                "base_font_size": self.base_font_size,
            }.items():
                if key in settings:
                    variable.set(settings[key])
            self.refresh_tree(); self.redraw()
            kind = "portable" if metadata and "x" in metadata[0] else "recovered legacy"
            self.status.config(text=f"Loaded {kind} project: {path}")
        except Exception as exc:
            messagebox.showerror("Could not load project", str(exc))

    def _load_legacy_project_spectra(self, metadata):
        replacements, cache, used, loaded = {}, {}, {}, []
        for item in metadata:
            original = item.get("source", "")
            source = replacements.get(original, original)
            if not source or not Path(source).exists():
                messagebox.showwarning(
                    "Locate original spectrum",
                    f"The v2 project refers to a missing source file:\n{original}\n\n"
                    "Select its current location to recover the project.")
                source = filedialog.askopenfilename(
                    title=f"Locate {Path(original).name or 'source spectrum'}",
                    filetypes=[("Spectra", "*.xlsx *.xls *.csv *.txt *.tsv"),
                               ("All files", "*.*")])
                if not source:
                    raise FileNotFoundError(
                        f"Cannot recover the project without: {original}")
                replacements[original] = source
            if source not in cache:
                cache[source] = read_spectra(source); used[source] = 0
            position = min(used[source], len(cache[source]) - 1)
            _, x, y = cache[source][position]; used[source] += 1
            loaded.append(Spectrum(
                item.get("name", Path(source).stem), x, y, source,
                group=item.get("group", "Group 1"),
                color=item.get("color", "#0072B2"),
                linestyle=item.get("linestyle", "-"),
                visible=item.get("visible", True)))
        return loaded

    def save_peaks(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx"),
                       ("Excel-compatible UTF-8 CSV", "*.csv")])
        if not path:
            return
        if not self.peaks:
            messagebox.showinfo("No selected peaks",
                                "Select or detect peaks before exporting.")
            return
        by_sample = {s.name: [] for s in self.spectra}
        for peak in self.peaks:
            by_sample.setdefault(peak["sample"], []).append(peak)
        maximum = max((len(values) for values in by_sample.values()), default=0)
        rows = []
        for sample, values in by_sample.items():
            values = sorted(values, key=lambda p: p["x"], reverse=True)
            row = {"sample": sample}
            for index, peak in enumerate(values, 1):
                row[f"peak_{index}_wavenumber_cm-1"] = peak["x"]
                row[f"peak_{index}_processed_intensity"] = peak["y"]
                row[f"peak_{index}_suggested_assignment"] = peak.get("assignment", "")
                row[f"peak_{index}_chemical_symbol"] = self._compact_peak_symbol(peak)
                row[f"peak_{index}_citation"] = peak.get("assignment_citation", "")
                row[f"peak_{index}_doi"] = peak.get("assignment_doi", "")
                row[f"peak_{index}_researcher_confirmed"] = peak.get(
                    "assignment_confirmed", False)
            rows.append(row)
        columns = ["sample"]
        for index in range(1, maximum + 1):
            columns.extend([
                f"peak_{index}_wavenumber_cm-1",
                f"peak_{index}_processed_intensity",
                f"peak_{index}_suggested_assignment",
                f"peak_{index}_chemical_symbol",
                f"peak_{index}_citation", f"peak_{index}_doi",
                f"peak_{index}_researcher_confirmed",
            ])
        table = pd.DataFrame(rows).reindex(columns=columns)
        if Path(path).suffix.lower() == ".xlsx":
            table.to_excel(path, index=False, sheet_name="Assigned peaks")
        else:
            # UTF-8 with BOM is required for correct O–H, Si–O–Si, and BO₃
            # display when a CSV is opened directly in Microsoft Excel.
            table.to_csv(path, index=False, encoding="utf-8-sig")
        self.status.config(text=f"Saved assignment-aware peak table: {path}")

    def _annotate(self, peak):
        """Compact commercial-style labels with distinct semantic colors."""
        had_assignment = "assignment" in peak
        original = peak.get("assignment")
        mode = self.peak_assignment_labels.get()
        symbol = peak.get("manual_label") or self._compact_peak_symbol(peak)
        before = len(self.ax.texts)
        try:
            # The v2 annotation engine supplies exact anchoring, collision
            # tiers, edge handling, and the leader line. Keep its base label
            # numeric, then add or substitute only the compact chemical symbol.
            peak.pop("assignment", None)
            super()._annotate(peak)
            if len(self.ax.texts) == before:
                return
            number = self.ax.texts[-1]
            number.set_picker(True)
            number.set_gid(f"peak:{id(peak)}")
            number.set_color("#303840")
            if mode == "Chemical symbol only":
                number.set_text(symbol or f'{peak["x"]:.0f}')
                if symbol:
                    number.set_color("#08788A")
            elif mode == "Wavenumber + chemical symbol" and symbol:
                x_offset, y_offset = number.get_position()
                vertical = self.peak_label_direction.get() == "Vertical"
                _, _, peak_size = self._font_sizes()
                if vertical:
                    visible_x = [s.x for s in self.spectra if id(s) in self.processed]
                    if visible_x:
                        low = min(float(x.min()) for x in visible_x)
                        high = max(float(x.max()) for x in visible_x)
                        fraction = ((peak["x"] - low) / (high - low)
                                    if high > low else .5)
                    else:
                        fraction = .5
                    # Low wavenumbers are displayed at the right edge of an
                    # FTIR axis; shift their symbols left, into the plot.
                    direction = -1 if fraction < .5 else 1
                    symbol_offset = (x_offset + direction * (peak_size + 3), y_offset)
                else:
                    symbol_offset = (x_offset, y_offset - peak_size - 5)
                self.ax.annotate(
                    symbol, (peak["x"], peak["y"]), xytext=symbol_offset,
                    textcoords="offset points", ha="center", va="top",
                    fontsize=peak_size, rotation=90 if vertical else 0,
                    color="#08788A",
                    bbox=dict(boxstyle="square,pad=0.08", facecolor="white",
                              edgecolor="none", alpha=.78))
                self.ax.texts[-1].set_picker(True)
                self.ax.texts[-1].set_gid(f"peak:{id(peak)}")
        finally:
            if had_assignment:
                peak["assignment"] = original
            else:
                peak.pop("assignment", None)


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except tk.TclError:
        pass
    FTIRLabApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
