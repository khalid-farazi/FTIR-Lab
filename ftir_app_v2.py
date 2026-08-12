"""FTIR Lab legacy v2 engine.

This file intentionally leaves ftir_app.py unchanged.  It subclasses the stable
application and adds project loading, peak review, publication export presets,
and clearer stacked-axis handling.

Run with:  python ftir_app_v2.py
"""
from __future__ import annotations

import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.text import Annotation

from ftir_app import FTIRApp, Spectrum, read_spectra


class FTIRAppV2(FTIRApp):
    VERSION = "2.2"

    def _variables(self):
        super()._variables()
        self.hide_offset_ticks = tk.BooleanVar(value=True)
        self.publication_width = tk.DoubleVar(value=7.20)
        self.publication_aspect = tk.DoubleVar(value=0.75)
        self.base_font_size = tk.DoubleVar(value=9.0)
        self.legend_font_ratio = tk.DoubleVar(value=1.0)
        self.peak_legend_ratio = tk.DoubleVar(value=0.78)
        self.peak_label_direction = tk.StringVar(value="Vertical")
        self.stagger_peak_labels = tk.BooleanVar(value=True)

    def __init__(self, root):
        super().__init__(root)
        root.title(f"FTIR Lab v{self.VERSION}")
        self._build_v2_menu()
        self._build_v2_sidebar()

    def _build_v2_menu(self):
        menu = tk.Menu(self.root)
        project = tk.Menu(menu, tearoff=False)
        project.add_command(label="Load project…", command=self.load_project)
        project.add_command(label="Save project…", command=self.save_project)
        menu.add_cascade(label="Project", menu=project)

        review = tk.Menu(menu, tearoff=False)
        review.add_command(label="Review selected peaks…", command=self.review_peaks)
        review.add_checkbutton(label="Hide offset Y ticks",
                               variable=self.hide_offset_ticks,
                               command=self.redraw)
        menu.add_cascade(label="Review", menu=review)

        publish = tk.Menu(menu, tearoff=False)
        publish.add_command(label="Export single-column figure…",
                            command=lambda: self.export_publication(3.54))
        publish.add_command(label="Export double-column figure…",
                            command=lambda: self.export_publication(7.20))
        menu.add_cascade(label="Publication", menu=publish)
        self.root.configure(menu=menu)

    def _build_v2_sidebar(self):
        """Put publication controls where they remain visible in the sidebar."""
        side = next((w for w in self.side_scroller.winfo_children()
                     if isinstance(w, ttk.Frame)), None)
        if side is None:
            return
        box = ttk.LabelFrame(side, text="V2 publication export", padding=8)
        apply_button = next((w for w in side.winfo_children()
                             if isinstance(w, ttk.Button)
                             and w.cget("text") == "Apply / redraw"), None)
        if apply_button is not None:
            box.pack(fill="x", pady=(0, 7), before=apply_button)
        else:
            box.pack(fill="x", pady=(0, 7))
        self._entry_row(box, "Export width (in)", self.publication_width)
        self._entry_row(box, "Width / height ratio", self.publication_aspect)
        ttk.Separator(box).pack(fill="x", pady=4)
        self._entry_row(box, "Base font size (pt)", self.base_font_size)
        self._entry_row(box, "Legend / base ratio", self.legend_font_ratio)
        self._entry_row(box, "Peak / legend ratio", self.peak_legend_ratio)
        self._combo_row(box, "Peak label direction", self.peak_label_direction,
                        ["Horizontal", "Vertical"])
        ttk.Checkbutton(box, text="Stagger nearby peak labels",
                        variable=self.stagger_peak_labels,
                        command=self.redraw).pack(anchor="w")
        ttk.Button(box, text="Apply typography", command=self.redraw).pack(fill="x", pady=(5, 3))
        ttk.Button(box, text="Preview export layout",
                   command=self.preview_export_layout).pack(fill="x", pady=(0, 3))
        row = ttk.Frame(box); row.pack(fill="x")
        ttk.Button(row, text="Single column", command=lambda: self.export_publication(3.54)).pack(side="left", expand=True, fill="x")
        ttk.Button(row, text="Double column", command=lambda: self.export_publication(7.20)).pack(side="left", expand=True, fill="x", padx=(4,0))
        ttk.Button(box, text="Custom-size export…", command=lambda: self.export_publication(None)).pack(fill="x", pady=(4,0))
        self.root.after_idle(self._update_side_scroll_region)

    def _font_sizes(self):
        try:
            base = max(5.0, float(self.base_font_size.get()))
            legend = max(5.0, base * float(self.legend_font_ratio.get()))
            peak = max(4.0, legend * float(self.peak_legend_ratio.get()))
            return base, legend, peak
        except (ValueError, tk.TclError):
            return 9.0, 9.0, 7.0

    def _publication_dimensions(self, width=None):
        width = float(self.publication_width.get()) if width is None else float(width)
        aspect = float(self.publication_aspect.get())
        if width <= 0 or aspect <= 0:
            raise ValueError("Width and width/height ratio must be positive numbers.")
        return width, width/aspect

    def _apply_publication_layout(self, width, height, resize_widget=False):
        """One layout path shared by preview and file export."""
        self.fig.set_size_inches(width, height, forward=False)
        if resize_widget:
            display_width = max(500, self.plot_scroller.winfo_width(),
                                self.canvas.get_tk_widget().winfo_width())
            self.canvas.get_tk_widget().configure(
                height=max(320, int(display_width * height/width)))
        base, legend_size, peak_size = self._font_sizes()
        self.ax.xaxis.label.set_fontsize(base + 1)
        self.ax.yaxis.label.set_fontsize(base + 1)
        self.ax.tick_params(labelsize=base)
        legend = self.ax.get_legend()
        if legend:
            for text in legend.get_texts(): text.set_fontsize(legend_size)
        for text in self.ax.texts:
            text.set_fontsize(peak_size if isinstance(text, Annotation) else legend_size)
        style = self.label_style.get()
        direct = style in {"Direct", "Both"} or (style == "Auto" and self.mode.get() != "Overlay")
        right = .78 if direct and self.label_position.get() == "Outside right" else 1.0
        self.fig.tight_layout(rect=(0, 0, right, .96))
        self.fig.canvas.draw()
        self.root.after_idle(self._update_scroll_region)

    def preview_export_layout(self, width=None):
        try:
            if width is not None:
                self.publication_width.set(width)
            width, height = self._publication_dimensions(width)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid export size", str(exc)); return False
        self.redraw()
        self._apply_publication_layout(width, height, resize_widget=True)
        self.status.config(text=(f"Publication preview: {width:.2f} × {height:.2f} in — "
                                 "this layout will be exported"))
        return True

    def redraw(self):
        super().redraw()
        base, legend_size, peak_size = self._font_sizes()
        self.ax.xaxis.label.set_fontsize(base + 1)
        self.ax.yaxis.label.set_fontsize(base + 1)
        self.ax.tick_params(labelsize=base)
        legend = self.ax.get_legend()
        if legend:
            for text in legend.get_texts(): text.set_fontsize(legend_size)
        for text in self.ax.texts:
            text.set_fontsize(peak_size if isinstance(text, Annotation) else legend_size)
        if self.hide_offset_ticks.get() and self.mode.get() != "Overlay":
            self.ax.set_yticks([])
            normalization = self.normalize.get()
            if normalization == "Auto":
                normalization = "None" if self.baseline.get() == "None" else "0-1"
            if self.auto_ylabel.get():
                if normalization == "None":
                    label = ("Transmittance (%T), offset for clarity"
                             if self.bands.get() == "Downward (%T)"
                             else "Absorbance, offset for clarity")
                else:
                    signal = ("transmittance" if self.bands.get() == "Downward (%T)"
                              else "absorbance")
                    label = f"Normalized {signal} (a.u.; offset for clarity)"
                self.ax.set_ylabel(label)
            self.canvas.draw_idle()

    def _annotate(self, peak):
        if not peak.get("show", True):
            return
        text = f'{peak["x"]:.0f}'
        if peak.get("assignment"):
            text += f'  {peak["assignment"]}'
        _, _, peak_size = self._font_sizes()
        tier = self._peak_label_tier(peak) if self.stagger_peak_labels.get() else 0
        vertical = self.peak_label_direction.get() == "Vertical"
        if vertical:
            # Separate nearby narrow vertical labels sideways. The leader line
            # remains anchored at the exact detected peak coordinate.
            step = peak_size + 6
            visible_x = [s.x for s in self.spectra if id(s) in self.processed]
            if visible_x:
                x_low = min(float(x.min()) for x in visible_x)
                x_high = max(float(x.max()) for x in visible_x)
                edge_fraction = ((peak["x"]-x_low)/(x_high-x_low)
                                 if x_high > x_low else .5)
            else:
                edge_fraction = .5
            # The FTIR axis is reversed: low wavenumbers are at the right.
            # Near either frame edge, shift text inward only.
            if edge_fraction < .16:
                shifts = (0, -step, -2*step, -3*step)
            elif edge_fraction > .84:
                shifts = (0, step, 2*step, 3*step)
            else:
                shifts = (0, step, -step, 2*step)
            text_offset = (shifts[min(tier, len(shifts)-1)], -10)
        else:
            # Horizontal labels are separated into rows below the peak.
            text_offset = (0, -(10 + tier * (peak_size + 5)))
        self.ax.annotate(text, (peak["x"], peak["y"]), xytext=text_offset,
                         textcoords="offset points", ha="center", va="top",
                         fontsize=peak_size, rotation=90 if vertical else 0,
                         bbox=dict(boxstyle="square,pad=0.08", facecolor="white",
                                   edgecolor="none", alpha=.78),
                         arrowprops={"arrowstyle": "-", "lw": .7})

    def _peak_label_tier(self, peak):
        """Assign nearby labels to separate rows within the same spectrum."""
        _, _, peak_size = self._font_sizes()
        # Four-digit vertical labels need more horizontal breathing room than
        # their narrow appearance in a tall on-screen preview suggests.
        minimum_gap = max(160.0, peak_size * 24.0)
        same = sorted((p for p in self.peaks
                       if p.get("show", True) and p["sample"] == peak["sample"]),
                      key=lambda p: p["x"], reverse=True)
        last_x = [None, None, None, None]
        tiers = {}
        for candidate in same:
            assigned = len(last_x)-1
            for tier, previous in enumerate(last_x):
                if previous is None or abs(previous-candidate["x"]) >= minimum_gap:
                    assigned = tier
                    break
            tiers[id(candidate)] = assigned
            last_x[assigned] = candidate["x"]
        return tiers.get(id(peak), 0)

    def review_peaks(self):
        win = tk.Toplevel(self.root)
        win.title("Peak Review Manager")
        win.geometry("850x480")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=8); frame.pack(fill="both", expand=True)
        columns = ("sample", "wavenumber", "intensity", "assignment", "shown")
        tree = ttk.Treeview(frame, columns=columns, show="headings",
                            selectmode="extended")
        widths = (180, 115, 130, 280, 70)
        labels = ("Sample", "Wavenumber (cm⁻¹)", "Processed intensity",
                  "Assignment", "Shown")
        for column, label, width in zip(columns, labels, widths):
            tree.heading(column, text=label); tree.column(column, width=width)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True); scroll.pack(side="right", fill="y")

        def refresh():
            tree.delete(*tree.get_children())
            for i, peak in enumerate(self.peaks):
                tree.insert("", "end", iid=str(i), values=(
                    peak["sample"], f'{peak["x"]:.2f}', f'{peak["y"]:.6g}',
                    peak.get("assignment", ""), "Yes" if peak.get("show", True) else "No"))

        def remove():
            for i in sorted((int(i) for i in tree.selection()), reverse=True):
                self.peaks.pop(i)
            refresh(); self.redraw()

        def assignment():
            selected = tree.selection()
            if not selected: return
            value = simpledialog.askstring("Peak assignment",
                                           "Assignment for selected peak(s):",
                                           parent=win)
            if value is None: return
            for i in selected: self.peaks[int(i)]["assignment"] = value.strip()
            refresh(); self.redraw()

        def toggle():
            for i in tree.selection():
                peak = self.peaks[int(i)]
                peak["show"] = not peak.get("show", True)
            refresh(); self.redraw()

        tree.bind("<Double-1>", lambda _e: assignment())
        controls = ttk.Frame(win, padding=(8, 0, 8, 8)); controls.pack(fill="x")
        ttk.Button(controls, text="Edit assignment…", command=assignment).pack(side="left")
        ttk.Button(controls, text="Show / hide annotation", command=toggle).pack(side="left", padx=5)
        ttk.Button(controls, text="Remove selected", command=remove).pack(side="left")
        ttk.Button(controls, text="Close", command=win.destroy).pack(side="right")
        refresh()

    def load_project(self):
        path = filedialog.askopenfilename(filetypes=[("FTIR project", "*.json")])
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            metadata = data.get("spectra", [])
            cache, used, loaded = {}, {}, []
            for item in metadata:
                source = item["source"]
                if source not in cache:
                    cache[source] = read_spectra(source)
                    used[source] = 0
                position = min(used[source], len(cache[source])-1)
                _, x, y = cache[source][position]
                used[source] += 1
                loaded.append(Spectrum(
                    item.get("name", Path(source).stem), x, y, source,
                    group=item.get("group", "Group 1"),
                    color=item.get("color", "#0072B2"),
                    linestyle=item.get("linestyle", "-"),
                    visible=item.get("visible", True)))
            self.spectra = loaded
            self.peaks = data.get("peaks", [])
            self._restore_settings(data.get("settings", {}))
            self.refresh_tree(); self.redraw()
            self.status.config(text=f"Loaded project: {path}")
        except Exception as exc:
            messagebox.showerror("Could not load project", str(exc))

    def _restore_settings(self, settings):
        mapping = {
            "baseline": self.baseline, "band_direction": self.bands,
            "lambda": self.lam, "asymmetry": self.asym,
            "smooth": self.smooth, "normalization": self.normalize,
            "layout": self.mode, "spacing": self.spacing,
            "height_per_curve_in": self.curve_height,
            "curve_labels": self.label_style,
            "direct_label_position": self.label_position,
            "xlabel": self.xlabel, "ylabel": self.ylabel,
            "automatic_ylabel": self.auto_ylabel,
            "air_artifact_correction": self.remove_air,
        }
        for key, variable in mapping.items():
            if key in settings: variable.set(settings[key])
        air = settings.get("air_range_cm-1", [])
        if len(air) == 2: self.air_low.set(air[0]); self.air_high.set(air[1])
        detection = settings.get("peak_detection", {})
        detection_map = {
            "scope": self.peak_scope, "mode": self.peak_mode,
            "prominence_percent": self.peak_prominence,
            "minimum_separation_cm-1": self.peak_distance,
            "maximum_per_sample": self.peak_maximum,
        }
        for key, variable in detection_map.items():
            if key in detection: variable.set(detection[key])
        region = detection.get("range_cm-1", [])
        if len(region) == 2: self.peak_low.set(region[0]); self.peak_high.set(region[1])

    def export_publication(self, width_inches=None):
        try:
            if width_inches is not None: self.publication_width.set(width_inches)
            width_inches, height = self._publication_dimensions(width_inches)
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror("Invalid export size", str(exc))
            return
        if not self.preview_export_layout(width_inches): return
        self.root.update_idletasks()
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF vector", "*.pdf"), ("SVG vector", "*.svg"),
                       ("TIFF", "*.tiff"), ("PNG", "*.png")])
        if not path: return
        old_size = self.fig.get_size_inches().copy()
        old_fonts = []
        old_widths = [(line, line.get_linewidth()) for line in self.ax.lines]
        current_legend = self.ax.get_legend()
        artists = ([self.ax.xaxis.label, self.ax.yaxis.label] +
                   list(self.ax.get_xticklabels()) + list(self.ax.get_yticklabels()) +
                   list(self.ax.texts) +
                   (list(current_legend.get_texts()) if current_legend else []))
        for artist in artists:
            old_fonts.append((artist, artist.get_fontsize()))
        try:
            self._apply_publication_layout(width_inches, height, resize_widget=False)
            for line in self.ax.lines: line.set_linewidth(max(.75, min(1.25, line.get_linewidth())))
            self.fig.savefig(path, dpi=1000 if Path(path).suffix.lower() in {".tif", ".tiff"} else 600,
                             bbox_inches="tight", facecolor="white")
            self.status.config(text=f"Saved publication figure: {path}")
        finally:
            self.fig.set_size_inches(old_size, forward=False)
            for artist, size in old_fonts: artist.set_fontsize(size)
            for line, width in old_widths: line.set_linewidth(width)
            self.preview_export_layout(width_inches)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    FTIRAppV2(root)
    root.mainloop()
