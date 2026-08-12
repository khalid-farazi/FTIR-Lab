"""Interactive FTIR plotting and peak-picking application.

Run with:  python ftir_app.py
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.colors import is_color_like
from matplotlib.figure import Figure
from scipy import sparse
from scipy.interpolate import PchipInterpolator
from scipy.signal import find_peaks, savgol_filter
from scipy.sparse.linalg import spsolve
from scipy.spatial import ConvexHull


LINESTYLES = {"Solid": "-", "Dashed": "--", "Dotted": ":", "Dash-dot": "-."}
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00",
           "#56B4E9", "#000000", "#F0E442", "#6A3D9A", "#A65628"]


def infer_group(filename):
    name = filename.lower()
    if "boric" in name:
        return "Boric acid"
    if "cal" in name or "cacl" in name:
        return "Calcium chloride"
    if "0%" in name or "control" in name:
        return "Control"
    return "Group 1"


@dataclass
class Spectrum:
    name: str
    x: np.ndarray
    y: np.ndarray
    source: str
    group: str = "Group 1"
    color: str = "#0072B2"
    linestyle: str = "-"
    visible: bool = True


def _numeric_pair(x, y):
    pair = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"),
                         "y": pd.to_numeric(y, errors="coerce")}).dropna()
    # Spectra are dense and their wavenumber column runs consistently in one
    # direction. This rejects exported peak tables and other sparse summaries.
    if len(pair) < 50:
        raise ValueError("fewer than 50 numeric x/y rows (likely a peak table, not a spectrum)")
    differences = np.diff(pair["x"].to_numpy(float))
    nonzero = differences[differences != 0]
    monotonic_fraction = max(np.mean(nonzero > 0), np.mean(nonzero < 0)) if len(nonzero) else 0
    if monotonic_fraction < .90:
        raise ValueError("wavenumber values are not consistently ordered")
    pair = pair.groupby("x", as_index=False)["y"].mean().sort_values("x")
    return pair.x.to_numpy(float), pair.y.to_numpy(float)


def read_spectra(path: str) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Read common FTIR layouts: two columns or one x plus many signal columns."""
    suffix = Path(path).suffix.lower()
    if suffix in {".csv", ".txt", ".tsv"}:
        frames = {"data": pd.read_csv(path, sep=None, engine="python", header=None)}
    else:
        frames = pd.read_excel(path, sheet_name=None, header=None)
    result = []
    for sheet, raw in frames.items():
        # Find the first row where the first two columns are numeric.
        best_row = 0
        for row in range(min(40, len(raw))):
            if (pd.notna(pd.to_numeric(pd.Series([raw.iloc[row, 0]]), errors="coerce").iloc[0])
                    and pd.notna(pd.to_numeric(pd.Series([raw.iloc[row, 1]]), errors="coerce").iloc[0])):
                best_row = row
                break
        data = raw.iloc[best_row:].copy()
        numeric = data.apply(pd.to_numeric, errors="coerce")
        usable = [c for c in numeric.columns if numeric[c].notna().sum() >= 5]
        if len(usable) < 2:
            continue
        xcol = usable[0]
        header_row = best_row - 1
        for j, ycol in enumerate(usable[1:]):
            try:
                x, y = _numeric_pair(numeric[xcol], numeric[ycol])
            except ValueError:
                continue
            label = ""
            if header_row >= 0 and pd.notna(raw.iloc[header_row, ycol]):
                label = str(raw.iloc[header_row, ycol]).strip()
            generic = {"%t", "t%", "transmittance", "%transmittance", "abs", "absorbance", "intensity"}
            if not label or label.lower().startswith("unnamed") or label.lower() in generic:
                label = Path(path).stem if len(usable) == 2 else f"{Path(path).stem} – {sheet} {j+1}"
            result.append((label, x, y))
    if not result:
        raise ValueError("No numeric wavenumber + signal columns were found")
    return result


def baseline_asls(y, lam=1e6, p=0.01, iterations=12):
    """Asymmetric least-squares baseline (Eilers/Boelens)."""
    y = np.asarray(y, float)
    d = sparse.diags([1, -2, 1], [0, 1, 2], shape=(len(y)-2, len(y)))
    penalty = lam * (d.T @ d)
    weights = np.ones(len(y))
    for _ in range(iterations):
        w = sparse.spdiags(weights, 0, len(y), len(y))
        z = spsolve(w + penalty, weights * y)
        weights = p * (y > z) + (1-p) * (y <= z)
    return np.asarray(z)


def baseline_rubberband(x, y):
    points = np.column_stack((x, y))
    hull = ConvexHull(points)
    vertices = hull.vertices  # cyclic order
    left, right = int(np.argmin(x[vertices])), int(np.argmax(x[vertices]))
    def cyclic_path(start, stop):
        ids = []
        i = start
        while True:
            ids.append(vertices[i])
            if i == stop:
                return np.asarray(ids, dtype=int)
            i = (i + 1) % len(vertices)
    a, b = cyclic_path(left, right), cyclic_path(right, left)
    chosen = a if np.mean(y[a]) < np.mean(y[b]) else b
    chosen = chosen[np.argsort(x[chosen])]
    return np.interp(x, x[chosen], y[chosen])


def process_signal(x, y, baseline, lam, asymmetry, smooth, normalize,
                   bands="Downward (%T)", artifact_range=None):
    out = np.asarray(y, float).copy()
    if baseline == "AsLS":
        if bands == "Downward (%T)":
            out -= -baseline_asls(-out, lam, asymmetry)
        else:
            out -= baseline_asls(out, lam, asymmetry)
    elif baseline == "Rubber band":
        if bands == "Downward (%T)":
            out -= -baseline_rubberband(x, -out)
        else:
            out -= baseline_rubberband(x, out)
    if smooth >= 5 and len(out) > 5:
        window = min(int(smooth) | 1, len(out) - (1 if len(out) % 2 == 0 else 2))
        if window >= 5:
            out = savgol_filter(out, window, min(3, window-2))
    # Replace only the selected atmospheric region, using a shape-preserving
    # interpolation between genuine measurements on either side.
    if artifact_range is not None:
        low, high = sorted(map(float, artifact_range))
        mask = (x >= low) & (x <= high)
        keep = ~mask
        if mask.any() and keep.sum() >= 4 and keep[0] and keep[-1]:
            out[mask] = PchipInterpolator(x[keep], out[keep])(x[mask])
    if normalize == "0-1":
        span = np.ptp(out)
        out = (out-out.min())/span if span else np.zeros_like(out)
    elif normalize == "Vector":
        norm = np.linalg.norm(out)
        out = out/norm if norm else out
    return out


def peaks_to_wide_dataframe(peaks, sample_order=None):
    """Return one row per sample with repeating wavenumber/intensity pairs."""
    grouped = {}
    for peak in peaks:
        grouped.setdefault(peak["sample"], []).append(peak)
    order = [name for name in (sample_order or []) if name in grouped]
    order += [name for name in grouped if name not in order]
    maximum = max((len(values) for values in grouped.values()), default=0)
    rows = []
    for sample in order:
        row = {"sample": sample}
        # FTIR tables conventionally run from high to low wavenumber.
        values = sorted(grouped[sample], key=lambda p: p["x"], reverse=True)
        for index, peak in enumerate(values, start=1):
            row[f"peak_{index}_wavenumber_cm-1"] = peak["x"]
            row[f"peak_{index}_processed_intensity"] = peak["y"]
        rows.append(row)
    columns = ["sample"]
    for index in range(1, maximum+1):
        columns += [f"peak_{index}_wavenumber_cm-1",
                    f"peak_{index}_processed_intensity"]
    return pd.DataFrame(rows, columns=columns)


class FTIRApp:
    def __init__(self, root):
        self.root, self.spectra, self.peaks = root, [], []
        self.lines, self.processed = {}, {}
        root.title("FTIR Lab")
        root.geometry("1280x900")
        root.minsize(950, 650)
        self._variables()
        self._layout()
        self.redraw()

    def _variables(self):
        self.baseline = tk.StringVar(value="AsLS")
        self.bands = tk.StringVar(value="Downward (%T)")
        self.lam = tk.DoubleVar(value=1e6)
        self.asym = tk.DoubleVar(value=.01)
        self.smooth = tk.IntVar(value=11)
        self.normalize = tk.StringVar(value="Auto")
        self.mode = tk.StringVar(value="Stacked")
        self.spacing = tk.DoubleVar(value=1.15)
        self.curve_height = tk.DoubleVar(value=1.15)
        self.xlabel = tk.StringVar(value="Wavenumber (cm⁻¹)")
        self.ylabel = tk.StringVar(value="Transmittance (%T)")
        self.auto_ylabel = tk.BooleanVar(value=True)
        self.label_style = tk.StringVar(value="Auto")
        self.label_position = tk.StringVar(value="Outside right")
        self.pick = tk.BooleanVar(value=False)
        self.show_grid = tk.BooleanVar(value=False)
        self.peak_scope = tk.StringVar(value="Visible spectra")
        self.peak_mode = tk.StringVar(value="Replace")
        self.peak_prominence = tk.DoubleVar(value=5.0)
        self.peak_distance = tk.DoubleVar(value=40.0)
        self.peak_maximum = tk.IntVar(value=10)
        self.peak_low = tk.DoubleVar(value=500.0)
        self.peak_high = tk.DoubleVar(value=4000.0)
        self.remove_air = tk.BooleanVar(value=False)
        self.air_low = tk.DoubleVar(value=2000)
        self.air_high = tk.DoubleVar(value=2500)

    def _layout(self):
        outer = ttk.Panedwindow(self.root, orient="horizontal"); outer.pack(fill="both", expand=True)
        side_shell = ttk.Frame(outer); plot = ttk.Frame(outer)
        outer.add(side_shell, weight=0); outer.add(plot, weight=1)
        self.side_scroller = tk.Canvas(side_shell, width=440, highlightthickness=0)
        side_scroll = ttk.Scrollbar(side_shell, orient="vertical", command=self.side_scroller.yview)
        self.side_scroller.configure(yscrollcommand=side_scroll.set)
        side_scroll.pack(side="right", fill="y")
        self.side_scroller.pack(side="left", fill="both", expand=True)
        side = ttk.Frame(self.side_scroller, padding=9)
        self.side_window = self.side_scroller.create_window((0,0), window=side, anchor="nw")
        side.bind("<Configure>", self._update_side_scroll_region)
        self.side_scroller.bind("<Configure>", self._resize_side_width)
        self.root.bind_all("<MouseWheel>", self._route_sidebar_wheel, add="+")
        bar = ttk.Frame(side); bar.pack(fill="x")
        ttk.Button(bar, text="Add files…", command=self.add_files).pack(side="left", expand=True, fill="x")
        ttk.Button(bar, text="Remove", command=self.remove).pack(side="left", padx=(5,0))
        orderbar = ttk.Frame(side); orderbar.pack(fill="x", pady=(4,0))
        ttk.Button(orderbar, text="Edit label…", command=self.edit_sample).pack(side="left", expand=True, fill="x")
        ttk.Button(orderbar, text="Move lower", command=self.move_lower).pack(side="left", padx=(4,0))
        ttk.Button(orderbar, text="Move higher", command=self.move_higher).pack(side="left", padx=(4,0))
        self.tree = ttk.Treeview(side, columns=("group", "style", "color"), show="tree headings", height=5, selectmode="extended")
        self.tree.heading("#0", text="Sample"); self.tree.heading("group", text="Group"); self.tree.heading("style", text="Style"); self.tree.heading("color", text="Color")
        self.tree.column("#0", width=145); self.tree.column("group", width=72); self.tree.column("style", width=55); self.tree.column("color", width=68)
        # Do not let the table consume the vertical space needed by controls.
        self.tree.pack(fill="x", expand=False, pady=7)
        self.tree.bind("<Double-1>", self.edit_sample)

        box = ttk.LabelFrame(side, text="Processing", padding=8); box.pack(fill="x")
        self._combo_row(box, "Baseline", self.baseline, ["None", "AsLS", "Rubber band"])
        self._combo_row(box, "Band direction", self.bands, ["Downward (%T)", "Upward (Abs)"])
        self._entry_row(box, "AsLS smoothness λ", self.lam)
        self._entry_row(box, "AsLS asymmetry p", self.asym)
        self._entry_row(box, "Savitzky–Golay window", self.smooth)
        self._combo_row(box, "Normalization", self.normalize, ["Auto", "None", "0-1", "Vector"])
        ttk.Separator(box).pack(fill="x", pady=4)
        ttk.Checkbutton(box, text="Interpolate air-artifact region",
                        variable=self.remove_air, command=self.redraw).pack(anchor="w")
        self._entry_row(box, "Artifact from (cm⁻¹)", self.air_low)
        self._entry_row(box, "Artifact to (cm⁻¹)", self.air_high)
        view = ttk.LabelFrame(side, text="Figure", padding=8); view.pack(fill="x", pady=7)
        self._combo_row(view, "Layout", self.mode, ["Separated (scrollable)", "Stacked", "Overlay"])
        self._entry_row(view, "Stack spacing", self.spacing)
        self._entry_row(view, "Height per curve (in)", self.curve_height)
        self._entry_row(view, "X-axis label", self.xlabel)
        self._entry_row(view, "Y-axis label", self.ylabel)
        ttk.Checkbutton(view, text="Automatic Y-axis label", variable=self.auto_ylabel,
                        command=self.redraw).pack(anchor="w")
        self._combo_row(view, "Curve labels", self.label_style,
                        ["Auto", "Direct", "Legend", "Both", "None"])
        self._combo_row(view, "Direct label position", self.label_position,
                        ["Outside right", "Inside right"])
        ttk.Checkbutton(view, text="Grid", variable=self.show_grid, command=self.redraw).pack(anchor="w")
        self.pick_check = ttk.Checkbutton(
            view, text="Pick peaks (left add, right remove)",
            variable=self.pick, command=self.toggle_peak_pick)
        self.pick_check.pack(anchor="w")
        peaks_box = ttk.LabelFrame(side, text="Automatic peak detection", padding=8)
        peaks_box.pack(fill="x", pady=(0,7))
        self._combo_row(peaks_box, "Apply to", self.peak_scope,
                        ["Visible spectra", "Selected samples"])
        self._combo_row(peaks_box, "Existing peaks", self.peak_mode,
                        ["Replace", "Append"])
        self._entry_row(peaks_box, "Min. prominence (%)", self.peak_prominence)
        self._entry_row(peaks_box, "Min. separation (cm⁻¹)", self.peak_distance)
        self._entry_row(peaks_box, "Maximum per sample", self.peak_maximum)
        self._entry_row(peaks_box, "Range from (cm⁻¹)", self.peak_low)
        self._entry_row(peaks_box, "Range to (cm⁻¹)", self.peak_high)
        ttk.Button(peaks_box, text="Auto-detect peaks", command=self.auto_detect_peaks).pack(fill="x", pady=(5,0))
        ttk.Button(side, text="Apply / redraw", command=self.redraw).pack(fill="x")
        out = ttk.Frame(side); out.pack(fill="x", pady=(7,0))
        ttk.Button(out, text="Export figure…", command=self.export).pack(side="left", expand=True, fill="x")
        ttk.Button(out, text="Save peaks…", command=self.save_peaks).pack(side="left", padx=(5,0))
        ttk.Button(side, text="Save project…", command=self.save_project).pack(fill="x", pady=(5,0))

        self.fig = Figure(figsize=(8,6), dpi=100); self.ax = self.fig.add_subplot(111)
        viewer = ttk.Frame(plot)
        self.plot_scroller = tk.Canvas(viewer, highlightthickness=0, background="white")
        scroll = ttk.Scrollbar(viewer, orient="vertical", command=self.plot_scroller.yview)
        self.plot_scroller.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y"); self.plot_scroller.pack(side="left", fill="both", expand=True)
        # Embed the Matplotlib widget directly; the previous intermediate frame
        # could collapse to zero height on Windows/Tk.
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_scroller); self.canvas.draw()
        self.figure_window = self.plot_scroller.create_window(
            (0,0), window=self.canvas.get_tk_widget(), anchor="nw")
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot, pack_toolbar=False)
        self.toolbar.update(); self.toolbar.pack(fill="x")
        viewer.pack(fill="both", expand=True)
        self.canvas.get_tk_widget().bind("<Configure>", self._update_scroll_region, add="+")
        self.plot_scroller.bind("<Configure>", self._resize_figure_width)
        self.canvas.get_tk_widget().bind("<MouseWheel>", self._scroll_plot, add="+")
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.status = ttk.Label(plot, text="Add Excel, CSV, TXT, or TSV files", anchor="w"); self.status.pack(fill="x")

    def _entry_row(self, parent, label, var):
        row=ttk.Frame(parent); row.pack(fill="x", pady=2); ttk.Label(row,text=label).pack(side="left")
        entry = ttk.Entry(row,textvariable=var,width=17)
        entry.pack(side="right")
        entry.bind("<Return>", self._apply_from_event)
        entry.bind("<FocusOut>", self._apply_from_event)

    def _combo_row(self, parent, label, var, values):
        row=ttk.Frame(parent); row.pack(fill="x", pady=2); ttk.Label(row,text=label).pack(side="left")
        combo = ttk.Combobox(row,textvariable=var,values=values,state="readonly",width=14)
        combo.pack(side="right")
        combo.bind("<<ComboboxSelected>>", self._apply_from_event)

    def _apply_from_event(self, _event=None):
        """Apply an edited setting without requiring the redraw button."""
        self.root.after_idle(self.redraw)

    def _update_scroll_region(self, _event=None):
        self.plot_scroller.configure(scrollregion=self.plot_scroller.bbox("all"))

    def _update_side_scroll_region(self, _event=None):
        self.side_scroller.configure(scrollregion=self.side_scroller.bbox("all"))

    def _resize_side_width(self, event):
        self.side_scroller.itemconfigure(self.side_window, width=event.width)

    def _route_sidebar_wheel(self, event):
        """Scroll controls only when the pointer is over the left sidebar."""
        x0, y0 = self.side_scroller.winfo_rootx(), self.side_scroller.winfo_rooty()
        x1, y1 = x0+self.side_scroller.winfo_width(), y0+self.side_scroller.winfo_height()
        if x0 <= event.x_root <= x1 and y0 <= event.y_root <= y1:
            self.side_scroller.yview_scroll(int(-event.delta/120), "units")
            return "break"

    def _resize_figure_width(self, event):
        self.plot_scroller.itemconfigure(self.figure_window, width=event.width)

    def _scroll_plot(self, event):
        if self.mode.get() == "Separated (scrollable)":
            self.plot_scroller.yview_scroll(int(-event.delta / 120), "units")
            return "break"

    def toggle_peak_pick(self):
        """Give plot clicks to the peak picker instead of the pan/zoom tools."""
        if self.pick.get():
            mode = str(self.toolbar.mode).lower()
            if "pan" in mode:
                self.toolbar.pan()
            elif "zoom" in mode:
                self.toolbar.zoom()
            self.status.config(text="PEAK PICKING ON — left-click a curve; right-click a label to remove")
        else:
            self.status.config(text=f"{len(self.spectra)} spectra • peak picking off")

    def auto_detect_peaks(self):
        """Detect local spectral bands using prominence and x-axis separation."""
        try:
            prominence_pct = float(self.peak_prominence.get())
            separation = float(self.peak_distance.get())
            maximum = int(self.peak_maximum.get())
            low, high = sorted((float(self.peak_low.get()), float(self.peak_high.get())))
            if prominence_pct < 0 or separation < 0 or maximum < 1:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid peak settings",
                                 "Prominence and separation must be non-negative; maximum peaks must be at least 1.")
            return

        if not self.processed:
            messagebox.showinfo("No spectra", "Add spectra before detecting peaks.")
            return
        if self.peak_scope.get() == "Selected samples":
            selected = {int(i) for i in self.tree.selection()}
            targets = [s for i, s in enumerate(self.spectra)
                       if i in selected and id(s) in self.processed]
            if not targets:
                messagebox.showinfo("No selected samples",
                                    "Select one or more visible samples in the table first.")
                return
        else:
            targets = [s for s in self.spectra if id(s) in self.processed]

        target_names = {s.name for s in targets}
        if self.peak_mode.get() == "Replace":
            self.peaks = [p for p in self.peaks if p["sample"] not in target_names]

        detected = 0
        downward = self.bands.get() == "Downward (%T)"
        for spectrum in targets:
            x, y = self.processed[id(spectrum)]
            region = (x >= low) & (x <= high)
            indices = np.flatnonzero(region)
            if len(indices) < 3:
                continue
            yr = y[indices]
            signal = -yr if downward else yr
            span = float(np.ptp(yr))
            prominence = span * prominence_pct / 100.0
            step = float(np.median(np.abs(np.diff(x[indices]))))
            distance_points = max(1, int(round(separation / step))) if step > 0 else 1
            local, properties = find_peaks(signal, prominence=prominence,
                                           distance=distance_points)
            if not len(local):
                continue
            # Keep the strongest bands, then display/export in descending
            # wavenumber order, conventional for FTIR.
            strengths = properties["prominences"]
            chosen = local[np.argsort(strengths)[-maximum:]]
            chosen = chosen[np.argsort(x[indices][chosen])[::-1]]
            for local_index in chosen:
                j = indices[local_index]
                self.peaks.append({"sample": spectrum.name,
                                   "x": float(x[j]), "y": float(y[j])})
                detected += 1
        self.redraw()
        self.status.config(text=f"Auto-detected {detected} peaks in {len(targets)} spectra — review before export")

    def add_files(self):
        paths=filedialog.askopenfilenames(filetypes=[("Spectra", "*.xlsx *.xls *.csv *.txt *.tsv"), ("All files", "*.*")])
        errors=[]
        for path in paths:
            try:
                for name,x,y in read_spectra(path):
                    s=Spectrum(name,x,y,path,group=infer_group(Path(path).stem),
                               color=PALETTE[len(self.spectra)%len(PALETTE)])
                    self.spectra.append(s)
            except Exception as exc: errors.append(f"{Path(path).name}: {exc}")
        self.refresh_tree(); self.redraw()
        if errors: messagebox.showwarning("Some files were skipped", "\n".join(errors))

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i,s in enumerate(self.spectra):
            mark="●" if s.visible else "○"
            self.tree.insert("", "end", iid=str(i), text=f"{mark} {s.name}", values=(s.group, next((k for k,v in LINESTYLES.items() if v==s.linestyle),s.linestyle), s.color))

    def remove(self):
        selected=sorted((int(i) for i in self.tree.selection()),reverse=True)
        for i in selected: self.spectra.pop(i)
        self.peaks=[]; self.refresh_tree(); self.redraw()

    def move_lower(self):
        """Move selected samples toward the bottom of a separated plot."""
        selected={int(i) for i in self.tree.selection()}
        if not selected: return
        for i in sorted(tuple(selected)):
            if i > 0 and i-1 not in selected:
                self.spectra[i-1],self.spectra[i]=self.spectra[i],self.spectra[i-1]
                selected.remove(i); selected.add(i-1)
        self.refresh_tree()
        for i in selected: self.tree.selection_add(str(i))
        self.redraw()

    def move_higher(self):
        """Move selected samples toward the top of a separated plot."""
        selected={int(i) for i in self.tree.selection()}
        if not selected: return
        for i in sorted(tuple(selected),reverse=True):
            if i < len(self.spectra)-1 and i+1 not in selected:
                self.spectra[i+1],self.spectra[i]=self.spectra[i],self.spectra[i+1]
                selected.remove(i); selected.add(i+1)
        self.refresh_tree()
        for i in selected: self.tree.selection_add(str(i))
        self.redraw()

    def edit_sample(self, _event=None):
        sel=self.tree.selection()
        if not sel: return
        s=self.spectra[int(sel[0])]
        win=tk.Toplevel(self.root); win.title("Sample appearance"); win.transient(self.root); win.grab_set()
        name=tk.StringVar(value=s.name); group=tk.StringVar(value=s.group)
        style=tk.StringVar(value=next((k for k,v in LINESTYLES.items() if v==s.linestyle),"Solid")); visible=tk.BooleanVar(value=s.visible)
        color_code=tk.StringVar(value=s.color)
        for label,var in [("Label",name),("Group",group)]:
            row=ttk.Frame(win,padding=6); row.pack(fill="x"); ttk.Label(row,text=label,width=10).pack(side="left"); ttk.Entry(row,textvariable=var,width=32).pack(side="left")
        row=ttk.Frame(win,padding=6); row.pack(fill="x"); ttk.Label(row,text="Line",width=10).pack(side="left"); ttk.Combobox(row,textvariable=style,values=list(LINESTYLES),state="readonly").pack(side="left")
        row=ttk.Frame(win,padding=6); row.pack(fill="x"); ttk.Label(row,text="Color code",width=10).pack(side="left"); ttk.Entry(row,textvariable=color_code,width=20).pack(side="left")
        ttk.Checkbutton(win,text="Visible",variable=visible).pack(anchor="w",padx=16)
        def choose():
            c=colorchooser.askcolor(s.color,parent=win)[1]
            if c: color_code.set(c)
        ttk.Button(win,text="Choose color…",command=choose).pack(fill="x",padx=8,pady=4)
        def done():
            code=color_code.get().strip()
            if not is_color_like(code):
                messagebox.showerror("Invalid color", "Enter a hex code such as #0072B2, or a valid Matplotlib color name.", parent=win); return
            old_name=s.name
            s.name=name.get().strip() or s.name
            for peak in self.peaks:
                if peak["sample"] == old_name: peak["sample"] = s.name
            s.group=group.get().strip() or "Group 1"; s.linestyle=LINESTYLES[style.get()]; s.color=code; s.visible=visible.get(); win.destroy(); self.refresh_tree(); self.redraw()
        ttk.Button(win,text="Apply",command=done).pack(fill="x",padx=8,pady=8)

    def redraw(self):
        old_xlim=self.ax.get_xlim() if self.lines else None
        self.ax.clear(); self.lines={}; self.processed={}
        try:
            spacing=float(self.spacing.get()); smooth=int(self.smooth.get())
            lam=float(self.lam.get()); asym=float(self.asym.get())
            curve_height=max(.5, float(self.curve_height.get()))
            artifact=(float(self.air_low.get()),float(self.air_high.get())) if self.remove_air.get() else None
        except (ValueError,tk.TclError): messagebox.showerror("Invalid setting","Processing settings must be numeric."); return
        visible=[s for s in self.spectra if s.visible]
        normalization=self.normalize.get()
        if normalization == "Auto":
            normalization = "None" if self.baseline.get() == "None" else "0-1"
        if self.auto_ylabel.get():
            if normalization == "None":
                auto_label = "Transmittance (%T)" if self.bands.get() == "Downward (%T)" else "Absorbance"
            else:
                signal = "transmittance" if self.bands.get() == "Downward (%T)" else "absorbance"
                auto_label = f"Normalized {signal} (a.u.)"
            self.ylabel.set(auto_label)
        label_anchors=[]
        for idx, s in enumerate(visible):
            separated=self.mode.get() in {"Stacked", "Separated (scrollable)"}
            offset=idx*spacing if separated else 0
            y=process_signal(s.x,s.y,self.baseline.get(),lam,asym,smooth,
                             normalization,self.bands.get(),artifact)+offset
            line,=self.ax.plot(s.x,y,label=s.name,color=s.color,linestyle=s.linestyle,linewidth=1.5,picker=5)
            self.lines[id(s)]=line; self.processed[id(s)]=(s.x,y)
            # A robust level near the low-wavenumber (right) edge. Using a
            # median avoids anchoring the label to a single edge spike.
            edge = s.x <= np.quantile(s.x, .06)
            label_anchors.append((s, float(np.median(y[edge]))))
        self.ax.set_xlabel(self.xlabel.get()); self.ax.set_ylabel(self.ylabel.get())
        if self.show_grid.get():
            self.ax.grid(True, linestyle=":", alpha=.35)
        else:
            self.ax.grid(False)
        if visible:
            lo=min(np.min(s.x) for s in visible); hi=max(np.max(s.x) for s in visible); self.ax.set_xlim(hi,lo)
            style=self.label_style.get()
            direct = style in {"Direct", "Both"} or (style=="Auto" and self.mode.get()!="Overlay")
            legend = style in {"Legend", "Both"} or (style=="Auto" and self.mode.get()=="Overlay")
            if direct:
                self._draw_direct_labels(label_anchors)
            if legend:
                self.ax.legend(frameon=False,ncol=max(1,min(4,len(visible))),loc="upper center",bbox_to_anchor=(.5,1.14))
        for p in self.peaks: self._annotate(p)
        target_height=max(6.0, len(visible)*curve_height+2.0) if self.mode.get()=="Separated (scrollable)" else 6.5
        self.fig.set_size_inches(max(8.0,self.fig.get_figwidth()),target_height,forward=False)
        self.canvas.get_tk_widget().configure(height=int(target_height*self.fig.dpi))
        style=self.label_style.get()
        direct = style in {"Direct", "Both"} or (style=="Auto" and self.mode.get()!="Overlay")
        right = .78 if direct and self.label_position.get()=="Outside right" else 1.0
        self.fig.tight_layout(rect=(0,0,right,.94)); self.canvas.draw_idle()
        self.root.after_idle(self._update_scroll_region)
        if self.pick.get():
            self.status.config(text=f"PEAK PICKING ON — {len(self.peaks)} selected • left add, right remove")
        else:
            self.status.config(text=f"{len(visible)} visible spectra • {len(self.peaks)} selected peaks")

    def _draw_direct_labels(self, anchors):
        """Place compact legend-like labels directly beside processed traces."""
        # x uses axes fraction while y remains in spectrum data coordinates.
        transform = self.ax.get_yaxis_transform()
        outside = self.label_position.get() == "Outside right"
        line_start, line_end, text_x = (1.02, 1.065, 1.075) if outside else (.805, .845, .855)
        for spectrum, y in anchors:
            self.ax.plot([line_start, line_end], [y, y], transform=transform,
                         color=spectrum.color, linestyle=spectrum.linestyle,
                         linewidth=2.0, clip_on=False, zorder=7)
            self.ax.text(text_x, y, spectrum.name, transform=transform,
                         ha="left", va="center", fontsize=9, color="#111111",
                         bbox=dict(boxstyle="square,pad=0.16", facecolor="white",
                                   edgecolor="none", alpha=.88),
                         clip_on=False, zorder=8)

    def on_click(self,event):
        if not self.pick.get() or event.inaxes!=self.ax or event.xdata is None: return
        # A toolbar mode can also be activated by a keyboard shortcut after the
        # checkbox was enabled. Turn it off and let the next click pick a peak.
        mode = str(self.toolbar.mode).lower()
        if "pan" in mode:
            self.toolbar.pan(); self.status.config(text="Pan turned off — click the peak again"); return
        if "zoom" in mode:
            self.toolbar.zoom(); self.status.config(text="Zoom turned off — click the peak again"); return
        if event.button==3:
            if self.peaks:
                click=np.array([event.x,event.y]); distances=[]
                for p in self.peaks:
                    display=self.ax.transData.transform((p["x"],p["y"])); distances.append(np.linalg.norm(display-click))
                j=int(np.argmin(distances))
                if distances[j]<35: self.peaks.pop(j); self.redraw()
            return
        if event.button!=1 or not self.processed: return
        click=np.array([event.x,event.y]); best=None
        for s in self.spectra:
            if id(s) not in self.processed: continue
            x,y=self.processed[id(s)]; pts=self.ax.transData.transform(np.column_stack((x,y)))
            j=int(np.argmin(np.sum((pts-click)**2,axis=1))); dist=np.linalg.norm(pts[j]-click)
            if best is None or dist<best[0]: best=(dist,s,j,x[j],y[j])
        if best and best[0]<50:
            _,s,j,x,y=best; self.peaks.append({"sample":s.name,"x":float(x),"y":float(y)}); self.redraw()
        else:
            self.status.config(text="No curve close enough — click directly on the peak line")

    def _annotate(self,p):
        self.ax.annotate(f'{p["x"]:.0f}',(p["x"],p["y"]),xytext=(0,15),textcoords="offset points",ha="center",fontsize=8,rotation=90,arrowprops={"arrowstyle":"-","lw":.7})

    def export(self):
        path=filedialog.asksaveasfilename(defaultextension=".tiff",filetypes=[("TIFF","*.tiff"),("PDF vector","*.pdf"),("SVG vector","*.svg"),("PNG","*.png")])
        if path:
            self.fig.savefig(path,dpi=600,bbox_inches="tight",facecolor="white")
            self.status.config(text=f"Saved {path}")

    def save_peaks(self):
        path=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
        if not path: return
        if not self.peaks:
            messagebox.showinfo("No selected peaks", "Select peaks on the graph before exporting.")
            return
        order=[s.name for s in self.spectra]
        peaks_to_wide_dataframe(self.peaks, order).to_csv(path,index=False)
        self.status.config(text=f"Saved wide peak table: {path}")

    def save_project(self):
        path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("FTIR project","*.json")])
        if not path: return
        data={"settings":{"baseline":self.baseline.get(),"band_direction":self.bands.get(),"lambda":self.lam.get(),"asymmetry":self.asym.get(),"smooth":self.smooth.get(),"normalization":self.normalize.get(),"air_artifact_correction":self.remove_air.get(),"air_range_cm-1":[self.air_low.get(),self.air_high.get()],"peak_detection":{"scope":self.peak_scope.get(),"mode":self.peak_mode.get(),"prominence_percent":self.peak_prominence.get(),"minimum_separation_cm-1":self.peak_distance.get(),"maximum_per_sample":self.peak_maximum.get(),"range_cm-1":[self.peak_low.get(),self.peak_high.get()]},"layout":self.mode.get(),"spacing":self.spacing.get(),"height_per_curve_in":self.curve_height.get(),"curve_labels":self.label_style.get(),"direct_label_position":self.label_position.get(),"xlabel":self.xlabel.get(),"automatic_ylabel":self.auto_ylabel.get(),"ylabel":self.ylabel.get()},
              "spectra":[{k:v for k,v in asdict(s).items() if k not in {"x","y"}} for s in self.spectra],"peaks":self.peaks}
        Path(path).write_text(json.dumps(data,indent=2),encoding="utf-8")


if __name__ == "__main__":
    root=tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name=="nt" else "clam")
    except tk.TclError: pass
    FTIRApp(root)
    root.mainloop()
