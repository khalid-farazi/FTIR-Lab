<div align="center">

<img width="375" height="98" alt="FTIR-Lab Logo" src="https://github.com/user-attachments/assets/511f6386-01ed-429d-ad41-fb7f3980527c" />

### Open-Source Software for Publication-Quality FTIR Analysis

**Spectrum Processing • Peak Assignment • Scientific Visualization**

<br>

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21766542-800000)](https://doi.org/10.5281/zenodo.21766542)
[![GPL](https://img.shields.io/badge/License-GPLv3-2EA44F)](https://github.com/khalid-farazi/FTIR-Lab/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.x-3776AB)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4)](https://github.com/khalid-farazi/FTIR-Lab/releases)

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

## Why FTIR-Lab?

FTIR-Lab is an open-source desktop application for FTIR spectrum processing, analysis, and publication-quality visualization. It's built to be usable by beginners while remaining powerful enough for research work.

Unlike general-purpose plotting software, FTIR-Lab integrates spectrum preprocessing, peak detection, functional-group assignment, and publication-quality visualization into a single, streamlined workflow.

<p align="center">
  <img src="https://github.com/user-attachments/assets/0eb6a3dc-35ef-4456-8470-e7e7b10cf5d0" alt="FTIR-Lab Interface" width="100%" />
</p>

---

## Key Features

**Preprocessing**
- Asymmetric Least Squares (AsLS) baseline correction
- Savitzky-Golay smoothing with custom window sizes
- Air-artifact removal via region interpolation (2000–2500 cm⁻¹) to mask atmospheric CO₂ and water vapor noise

**Analysis**
- Automatic and manual peak detection with adjustable prominence/separation sensitivity
- Context-aware functional group library with material-specific suggestions and guided confirmation

**Visualization & Export**
- Stacked or overlaid multi-curve layouts with adjustable spacing and curve height
- One-click single/double-column journal presets with smart label staggering
- Vector and raster export: `.png`, `.svg`, `.tiff`, `.pdf`

**Data Export**
- Fitted peak tables, intensities, and reference assignments exportable to `.xlsx` or `.csv`

---

## Installation

### Portable Executable (Windows)
1. Download the latest release from [Releases](https://github.com/khalid-farazi/FTIR-Lab/releases).
2. Extract the `.zip` archive to your preferred location.
3. Launch `FTIR-Lab.exe` — no installation required.

---

## Supported File Formats

**Input:** `.csv`, `.xlsx`

**Export:** `.png`, `.svg`, `.tiff`, `.pdf` (plots) · `.xlsx`, `.csv` (peak data)

---

## User Guide (6-Step Essential Workflow)

### Step 1: Load Files
Import raw spectra files (`.csv` or `.xlsx`) directly into the project panel.

### Step 2: Smooth & Baseline Correction
Apply AsLS baseline correction, adjust Savitzky-Golay window sizes, and toggle air-artifact region interpolation (2000–2500 cm⁻¹) to clean raw spectra.

### Step 3: Auto-Detect Peaks
Detect peak positions automatically using customizable prominence and separation thresholds, or click directly on the curve to manually refine peak markers.

### Step 4: Assign Functional Groups
Match detected peaks against the built-in library with context-aware material suggestions, or customize and expand the library for specific samples.

### Step 5: Export Plot & Adjust Layout
Choose between Stacked or Overlaid layouts, configure single/double-column journal widths, apply smart label staggering to avoid overlap, and export to `.pdf`, `.svg`, `.tiff`, or `.png`.

### Step 6: Export Peak Data
Save compiled peak locations, intensities, and functional group assignments to Excel or CSV for tabular reporting.

---

## License

FTIR-Lab is released under the [GPLv3 License](https://github.com/khalid-farazi/FTIR-Lab/blob/main/LICENSE).

---

## Citation

If you use **FTIR-Lab** in your research or publications, please cite it as:

> Farazi, K. A. (2026). FTIR-Lab (Version 3.0.1) [Software]. Zenodo. https://doi.org/10.5281/zenodo.21766542

### BibTeX
```bibtex
@software{farazi_2026_ftirlab,
  author       = {Farazi, K. A.},
  title        = {FTIR-Lab},
  version      = {3.0.1},
  year         = {2026},
  publisher    = {Zenodo},
  doi          = {10.5281/zenodo.21766542},
  url          = {https://doi.org/10.5281/zenodo.21766542}
}
```

---

## Author's Note

<div align="center">

FTIR-Lab is built on the belief that scientific inquiry, empirical investigation, and research tools should be transparent, accessible, and shared openly for the advancement of knowledge.

<br>

**قُلْ أَرَأَيْتُمْ إِن كَانَ مِنْ عِندِ اللَّهِ ثُمَّ كَفَرْتُم بِهِ مَنْ أَضَلُّ مِمَّنْ هُوَ فِي شِقَاقٍ بَعِيدٍ**

<br>

*"বলুন, 'তোমরা ভেবে দেখেছ কি, যদি এ কুরআন আল্লাহর কাছ থেকে নাযিল হয়ে থাকে আর তোমরা এটা প্রত্যাখ্যান কর, তবে যে ব্যক্তি ঘোর বিরোধিতায় লিপ্ত আছে, তার চেয়ে বেশী বিভ্রান্ত আর কে?'"*

<br>

*"Say, 'Have you considered: if the Qur'an is from Allah and you disbelieved in it, who is more astray than one who is in extreme dissension?'"*

<br>

— **Surah Fussilat (41:52)**

</div>
