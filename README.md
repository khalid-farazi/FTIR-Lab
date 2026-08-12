<div align="center">

<img width="375" height="98" alt="FTIR Lab logo" src="assets/ftir-lab-logo.png" />

### Open-Source Software for Publication-Quality FTIR Analysis

**Spectrum Processing • Peak Assignment Assistance • Scientific Visualization**

<br>

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21766542-800000)](https://doi.org/10.5281/zenodo.21766542)
[![GPL](https://img.shields.io/badge/License-GPLv3-2EA44F)](https://github.com/khalid-farazi/FTIR-Lab/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D4)](https://github.com/khalid-farazi/FTIR-Lab/releases)

<br>

[![Download](https://img.shields.io/badge/Download-Latest%20Release-blue?style=for-the-badge&logo=github)](https://github.com/khalid-farazi/FTIR-Lab/releases/latest)

<br><br>

> **سَنُرِيهِمْ آيَاتِنَا فِي الْآفَاقِ وَفِي أَنفُسِهِمْ حَتَّىٰ يَتَبَيَّنَ لَهُمْ أَنَّهُ الْحَقُّ**
>
> *"আমরা অতিশীঘ্রই তাদেরকে আমাদের নিদর্শনসমূহ দেখাবো দূর-দিগন্তে এবং তাদের নিজেদের মধ্যে, যতক্ষণ না তাদের কাছে স্পষ্টভাবে ফুটে ওঠে যে এটিই সত্য।"*
>
> *"We will show them Our signs in the horizons and within themselves until it becomes clear to them that it is the truth."*
>
> — **Surah Fussilat (41:53)**

</div>

---

## Why FTIR Lab?

FTIR Lab is an open-source desktop application for FTIR spectrum processing,
analysis, annotation, and publication-quality visualization. It is designed to
be approachable for a new researcher while retaining the controls needed for
reproducible scientific work.

Unlike general-purpose plotting software, FTIR Lab brings preprocessing, peak
detection, literature-guided assignment assistance, and journal-oriented export
into one workflow. It does not use AI or machine learning for scientific
interpretation.

<p align="center">
  <img src="https://github.com/user-attachments/assets/0eb6a3dc-35ef-4456-8470-e7e7b10cf5d0" alt="FTIR Lab interface" width="100%" />
</p>

---

## Key Features

### Preprocessing

- Asymmetric Least Squares (AsLS) and rubber-band baseline correction
- Savitzky–Golay smoothing with guided and custom window sizes
- Optional interpolation of atmospheric artifact regions
- Automatic or user-controlled normalization and band direction

### Peak analysis

- Automatic peak detection with adjustable prominence, separation, range, and limit
- Manual peak selection directly on the spectrum
- Individually editable peak labels and custom text annotations
- Editable functional-group reference library with citations and DOI fields
- Literature-guided assignment suggestions with user confirmation

### Visualization and export

- Stacked, overlaid, and vertically separated multi-spectrum layouts
- Reorderable spectra, editable curve names, colors, and line styles
- Direct labels beside curves or conventional legends
- Automatic chemical subscripts such as CaCl₂, SiO₂, and B₂O₃
- Live export preview and responsive typography
- Single-column, double-column, and custom-size publication presets
- PNG, SVG, TIFF, and PDF output

### Reproducibility

- Peak tables exportable to Excel or CSV
- Portable `.hftir.json` project files containing spectra and settings
- Analysis-summary export containing processing parameters and provenance
- Permanent automated tests for core scientific and data-handling functions

---

## Installation

### Windows

1. Download the Windows ZIP from [Releases](https://github.com/khalid-farazi/FTIR-Lab/releases).
2. Extract the ZIP completely.
3. Open the extracted folder.
4. Double-click **FTIR Lab v3.1.exe**. Python is not required.

### macOS and Linux

Download and extract the package for your operating system from the Releases
page. Because the application is not yet code-signed, the operating system may
ask you to confirm that you trust the downloaded application.

### Run from source

```bash
python -m pip install -r requirements.txt
python -m ftir_lab.splash_launcher_standard_v3
```

---

## Supported File Formats

**Input:** `.csv`, `.xlsx`, `.xls`

**Plot export:** `.png`, `.svg`, `.tiff`, `.pdf`

**Data export:** `.xlsx`, `.csv`, `.json`

---

## Essential Workflow

1. **Add spectra** — import one or more FTIR data files.
2. **Smooth** — apply the smallest suitable Savitzky–Golay window.
3. **Detect peaks** — use automatic detection, then refine peaks manually.
4. **Suggest groups** — review literature-guided functional-group suggestions.
5. **Export plot** — select the layout and publication dimensions.
6. **Export to Excel** — save peak positions, intensities, assignments, and references.

---

## Scientific Safeguard

Functional-group results are **suggested assignments**, not definitive compound
identification. Verify every suggestion against sample chemistry, the complete
spectrum, appropriate controls, expected band shapes and shifts, and the cited
literature. Automated peak detection and baseline correction must also be
visually reviewed before publication.

---

## Cross-Platform Builds and Tests

The workflows in `.github/workflows/` run the permanent regression tests and
build separate artifacts for Windows, macOS, and Linux. The tests remain in the
repository but are not something ordinary users need to install or run.

Maintainers can open **Actions → Build desktop packages → Run workflow** to
produce the three downloadable packages.

---

## License

FTIR Lab is released under the [GNU GPLv3 License](https://github.com/khalid-farazi/FTIR-Lab/blob/main/LICENSE).

---

## Citation

If you use **FTIR Lab** in research or a publication, please cite the archived
software record. Update the displayed version number on Zenodo when depositing
the v3.1 release.

> Farazi, K. A. (2026). FTIR-Lab (Version 3.1) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21766542

```bibtex
@software{farazi_2026_ftirlab,
  author    = {Farazi, K. A.},
  title     = {FTIR-Lab},
  version   = {3.1},
  year      = {2026},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.21766542},
  url       = {https://doi.org/10.5281/zenodo.21766542}
}
```

---

## Author's Note

<div align="center">

FTIR Lab is built on the belief that scientific inquiry, empirical
investigation, and research tools should be transparent, accessible, and shared
openly for the advancement of knowledge.

<br>

**قُلْ أَرَأَيْتُمْ إِن كَانَ مِنْ عِندِ اللَّهِ ثُمَّ كَفَرْتُم بِهِ مَنْ أَضَلُّ مِمَّنْ هُوَ فِي شِقَاقٍ بَعِيدٍ**

<br>

*"বলুন, 'তোমরা ভেবে দেখেছ কি, যদি এ কুরআন আল্লাহর কাছ থেকে নাযিল হয়ে থাকে আর তোমরা এটা প্রত্যাখ্যান কর, তবে যে ব্যক্তি ঘোর বিরোধিতায় লিপ্ত আছে, তার চেয়ে বেশী বিভ্রান্ত আর কে?'"*

<br>

*"Say, 'Have you considered: if the Qur'an is from Allah and you disbelieved in it, who is more astray than one who is in extreme dissension?'"*

<br>

— **Surah Fussilat (41:52)**

</div>
