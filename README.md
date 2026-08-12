# FTIR Lab v3.1

FTIR Lab is a beginner-friendly desktop application for importing, processing,
annotating, and exporting publication-ready FTIR spectra. It does not use AI or
machine learning for scientific interpretation.

## Downloadable applications

This single repository supports Windows, macOS, and Linux. GitHub Actions runs
the permanent scientific tests and builds a separate application artifact for
each operating system. Users download the artifact matching their computer;
tests and developer tools are not included in those downloads.

To create release artifacts after uploading this folder:

1. Open **Actions → Build desktop packages → Run workflow**, or create a tag
   such as `v3.1.0`.
2. Download the three generated artifacts from the workflow run.
3. Attach them to a GitHub Release for ordinary users.

## Run from source

```text
python -m pip install -r requirements.txt
python -m ftir_lab.splash_launcher_standard_v3
```

## Scientific safeguards

- Functional-group results are literature-guided suggestions, not compound
  identification.
- Suggested assignments must be verified against sample chemistry, the full
  spectrum, controls, and cited literature.
- `tests/` contains permanent regression checks for processing, chemical
  typography, Quran sequencing, imports, projects, and exports.
- Portable `.hftir.json` projects embed spectral x/y data and provenance.

## Repository layout

```text
ftir_lab/           application package
assets/             fonts, Quran data, branding
tests/              repository/build-only scientific tests
.github/workflows/  tests and builds for all three operating systems
```
