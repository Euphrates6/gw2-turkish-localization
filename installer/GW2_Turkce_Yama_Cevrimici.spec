from pathlib import Path

# In PyInstaller spec files, SPECPATH is the directory containing the spec file
BASE_DIR = Path(SPECPATH).resolve().parent

datas = [
    (str(BASE_DIR / 'Local_Translator_Cevrimici_TR.zip'), '.'),
]

binaries = []
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
]

a = Analysis(
    ['gw2_control_panel.py'],
    pathex=[str(BASE_DIR / 'installer'), str(BASE_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch', 'torchvision', 'transformers', 'huggingface_hub',
        'ctranslate2', 'sentencepiece', 'numpy', 'scipy', 'matplotlib',
        'polars', 'pandas', 'cv2', 'playwright', 'PIL'
    ],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GW2_Turkce_Yama_Cevrimici',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
