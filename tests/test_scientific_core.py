import unittest
import numpy as np
import tempfile
from pathlib import Path
from scipy.signal import find_peaks

from ftir_app import baseline_asls, baseline_rubberband, process_signal, read_spectra
from ftir_lab.ftir_app_v3 import format_chemical_formula


class ScientificCoreTests(unittest.TestCase):
    def test_asls_returns_finite_same_length_baseline(self):
        x = np.linspace(0, 1, 401)
        y = 2*x + np.exp(-((x-.55)/.035)**2)
        baseline = baseline_asls(y, lam=1e5, p=.01)
        self.assertEqual(len(baseline), len(y))
        self.assertTrue(np.isfinite(baseline).all())

    def test_rubberband_returns_finite_same_length_baseline(self):
        x = np.linspace(400, 4000, 301)
        y = .2*x/4000 + np.sin(x/400)**2
        baseline = baseline_rubberband(x, y)
        self.assertEqual(len(baseline), len(y))
        self.assertTrue(np.isfinite(baseline).all())

    def test_savgol_preserves_length_and_finiteness(self):
        x = np.linspace(400, 4000, 501)
        y = np.sin(x/140) + .03*np.cos(x)
        out = process_signal(x, y, "None", 1e6, .01, 11, "None",
                             "Upward (Abs)")
        self.assertEqual(len(out), len(y))
        self.assertTrue(np.isfinite(out).all())

    def test_chemical_formula_formatting_is_safe(self):
        self.assertEqual(format_chemical_formula("1 wt% CaCl2"), "1 wt% CaCl₂")
        self.assertEqual(format_chemical_formula("B2O3 and SiO2"), "B₂O₃ and SiO₂")
        self.assertEqual(format_chemical_formula("Sample 2, Day 14"), "Sample 2, Day 14")

    def test_known_synthetic_peaks_are_detected(self):
        x = np.linspace(400, 4000, 3601)
        y = sum(np.exp(-((x-center)/12)**2) for center in (1000, 1700, 3400))
        indices, _ = find_peaks(y, prominence=.5, distance=100)
        detected = x[indices]
        for expected in (1000, 1700, 3400):
            self.assertLess(np.min(np.abs(detected-expected)), 2)

    def test_csv_import_preserves_numeric_spectrum(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "spectrum.csv"
            x = np.linspace(4000, 400, 101)
            lines = ["wavenumber,intensity"] + [
                f"{a:.1f},{70 + 10*np.sin(a/350):.6f}" for a in x]
            path.write_text("\n".join(lines), encoding="utf-8")
            spectra = read_spectra(str(path))
            self.assertEqual(len(spectra), 1)
            self.assertEqual(len(spectra[0][1]), 101)


if __name__ == "__main__":
    unittest.main()
