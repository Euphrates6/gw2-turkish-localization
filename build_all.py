"""Build script for GW2-TR: Compiles C++/Rust Font Injector DLLs and builds standalone EXEs
(`Local_Translator_TR.exe` and `GW2_TR_Hub.exe`) into `dist/`."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print(f">> Running: {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def build_local_translator_exe() -> None:
    """Builds Local_Translator_TR.exe (the background module started by Text Translator)."""
    icon_path = ROOT / "assets" / "app_icon.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--noconsole",
        "--name", "Local_Translator_TR",
        "--paths", str(ROOT / "src"),
        *(["--icon", str(icon_path)] if icon_path.is_file() else []),
        "--add-data", f"{ROOT / 'src' / 'glossary_tr.default.json'};.",
        "--add-data", f"{ROOT / 'VERSION'};.",
        "--collect-all", "ctranslate2",
        "--collect-all", "sentencepiece",
        str(ROOT / "src" / "lt_module.py"),
    ]
    run(cmd)
    exe_out = ROOT / "dist" / "Local_Translator_TR.exe"
    if exe_out.is_file():
        shutil.copy2(exe_out, ROOT / "assets" / "Local_Translator_TR.exe")
        print(f"[+] Built: {exe_out} ({exe_out.stat().st_size / (1024*1024):.1f} MB)")


def build_hub_exe(*, bundle_assets: bool = False) -> None:
    """Builds GW2_TR_Hub (--onedir to avoid PyInstaller --onefile AV false positives)
    and packages dist/GW2_TR_Hub.zip (~15 MB lightweight manifest-driven Hub)."""
    import zipfile

    icon_path = ROOT / "assets" / "app_icon.ico"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--noconsole",
        "--name", "GW2_TR_Hub",
        "--paths", str(ROOT / "src"),
        "--paths", str(ROOT / "hub"),
        *(["--icon", str(icon_path)] if icon_path.is_file() else []),
        "--collect-all", "webview",
        "--exclude-module", "ctranslate2",
        "--exclude-module", "sentencepiece",
        "--exclude-module", "numpy",
        "--add-data", f"{ROOT / 'hub' / 'ui'};hub/ui",
        "--add-data", f"{ROOT / 'VERSION'};.",
        "--add-data", f"{ROOT / 'src'};src",
        "--add-data", f"{ROOT / 'TR' / 'glossary_tr.json'};TR",
        "--add-data", f"{ROOT / 'TR' / 'config.json'};TR",
        "--add-data", f"{ROOT / 'TR' / 'contributor.json'};TR",
    ]
    if icon_path.is_file():
        cmd.extend(["--add-data", f"{icon_path};assets"])
    if bundle_assets:
        cmd.extend([
            "--add-data", f"{ROOT / 'assets'};assets",
            "--add-data", f"{ROOT / 'TR' / 'model'};TR/model",
        ])
    cmd.append(str(ROOT / "hub" / "app.py"))
    run(cmd)
    hub_dir = ROOT / "dist" / "GW2_TR_Hub"
    hub_zip = ROOT / "dist" / "GW2_TR_Hub.zip"
    if hub_dir.is_dir():
        with zipfile.ZipFile(hub_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(hub_dir.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(hub_dir.parent).as_posix())
        mode = "bundled-offline" if bundle_assets else "lightweight-manifest-onedir"
        print(f"[+] Built ({mode}): {hub_zip} ({hub_zip.stat().st_size / (1024*1024):.1f} MB)")


if __name__ == "__main__":
    bundled = "--bundled" in sys.argv
    if "--hub-only" not in sys.argv:
        build_local_translator_exe()
    build_hub_exe(bundle_assets=bundled)

