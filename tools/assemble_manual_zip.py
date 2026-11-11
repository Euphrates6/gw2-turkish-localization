"""Assembles the official standalone manual zip package: GW2_TR_v0.12.0_Manuel_Paket.zip
Gamers can extract this zip directly into their Guild Wars 2 root folder.
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
DIST_DIR.mkdir(parents=True, exist_ok=True)
ZIP_OUT = DIST_DIR / "GW2_TR_v0.12.0_Manuel_Paket.zip"


def main() -> None:
    temp_dir = DIST_DIR / "_manual_pkg_tmp"
    if temp_dir.is_dir():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # 1. Root DLLs
    assets = ROOT / "assets"
    shutil.copy2(assets / "d3d11.dll", temp_dir / "d3d11.dll")
    shutil.copy2(assets / "version.dll", temp_dir / "version.dll")

    # 2. Addons folder
    addons_dir = temp_dir / "addons"
    addons_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(assets / "addons" / "text_translator.dll", addons_dir / "text_translator.dll")
    shutil.copy2(assets / "addons" / "turkish_font.dll", addons_dir / "turkish_font.dll")

    # 3. Text Translator modules
    mod_dir = addons_dir / "text_translator" / "modules" / "local_translator_tr"
    mod_dir.mkdir(parents=True, exist_ok=True)

    # Binary and config
    local_tr_exe = DIST_DIR / "Local_Translator_TR.exe"
    if not local_tr_exe.is_file():
        local_tr_exe = assets / "Local_Translator_TR.exe"
    shutil.copy2(local_tr_exe, mod_dir / "Local_Translator_TR.exe")

    module_toml = (
        'name = "Local Translator TR"\n'
        'path = "Local_Translator_TR.exe"\n'
        'args = ["--lang", "tr"]\n'
    )
    (mod_dir / "module.toml").write_text(module_toml, encoding="utf-8")

    # Also copy Python source files as alternative/fallback
    for py_file in ("lt_module.py", "lt_server.py", "patch_db.py", "editor.py", "map_upload.py", "glossary_tr.default.json"):
        shutil.copy2(ROOT / "src" / py_file, mod_dir / py_file)

    # 4. TR directory (model, glossary, config, contributor)
    tr_dir = mod_dir / "TR"
    tr_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "TR" / "glossary_tr.json", tr_dir / "glossary_tr.json")
    shutil.copy2(ROOT / "TR" / "config.json", tr_dir / "config.json")
    shutil.copy2(ROOT / "TR" / "contributor.json", tr_dir / "contributor.json")

    model_src = ROOT / "TR" / "model"
    model_dst = tr_dir / "model"
    model_dst.mkdir(parents=True, exist_ok=True)
    for mf in model_src.iterdir():
        if mf.is_file():
            shutil.copy2(mf, model_dst / mf.name)

    # 5. Create zip
    if ZIP_OUT.is_file():
        ZIP_OUT.unlink()

    print(f">> Creating {ZIP_OUT}...")
    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for p in temp_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(temp_dir)
                zf.write(p, rel)

    shutil.rmtree(temp_dir, ignore_errors=True)
    size_mb = ZIP_OUT.stat().st_size / (1024 * 1024)
    print(f"[+] Created: {ZIP_OUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
