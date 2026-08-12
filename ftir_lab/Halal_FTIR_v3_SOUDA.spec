# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for FTIR Lab v3.1 — SOUDA edition."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Let PyInstaller's maintained SciPy hook collect the required compiled
# modules; recursively bundling all of SciPy is unnecessary and very slow.
hiddenimports = collect_submodules("openpyxl")
datas = collect_data_files("matplotlib") + [
    ("../assets/ftir-lab-logo.png", "assets"),
    ("../assets/souda-logo.png", "assets"),
    ("../assets/quran_ayat.json", "assets"),
    ("../assets/QURAN_SOURCES.md", "assets"),
    ("../assets/fonts", "assets/fonts"),
    ("functional_groups.default.json", "ftir_lab"),
]
anaconda_bin = Path("C:/ProgramData/anaconda3/Library/bin")
dlls = ["ffi.dll", "libbz2.dll", "libcrypto-3-x64.dll", "libexpat.dll",
        "liblzma.dll", "libssl-3-x64.dll", "sqlite3.dll", "tcl86t.dll",
        "tk86t.dll", "zlib.dll"]
binaries = [(str(anaconda_bin / name), ".") for name in dlls
            if (anaconda_bin / name).exists()]

a = Analysis(["splash_launcher_v3.py"], pathex=[".."],
             binaries=binaries, datas=datas, hiddenimports=hiddenimports,
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=["pytest", "IPython", "notebook", "jupyter"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="FTIR Lab v3.1 - SOUDA",
          debug=False, bootloader_ignore_signals=False, strip=False, upx=True,
          console=False, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, upx_exclude=[],
               name="FTIR Lab v3.1 - SOUDA")
