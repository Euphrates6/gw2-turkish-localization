"""Reproducible build pipeline for GW2-TR:
- Verifies pinned SHA-256 of canonical `font-injector/turkish_atlases.bin`
- Compiles C++ Raidcore Nexus addon (`turkish_font.dll`)
- Optionally compiles deprecated Rust proxy (`--legacy-proxy`)
- Builds `Local_Translator_TR.exe` and lightweight `--onedir` `GW2_TR_Hub.zip`
- With `--release`, assembles `release_v{VERSION}/` and generates `manifest.json` + `.sha256`
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from version import VERSION  # noqa: E402

CANONICAL_ATLAS = ROOT / "font-injector" / "turkish_atlases.bin"
PINNED_ATLAS_SHA256 = "3ec02b7751a9243a3c1981d6cac0a1dda0bd7915222de4b3a079ab6ce76bc0a0"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print(f">> Running: {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, cwd=str(cwd), check=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def verify_and_stage_atlas(*, copy_loader: bool = False) -> Path:
    """Verifies canonical turkish_atlases.bin SHA-256 and copies it into build subdirs."""
    if not CANONICAL_ATLAS.is_file():
        raise SystemExit(f"ERROR: Canonical atlas blob missing: {CANONICAL_ATLAS}")
    actual = sha256_file(CANONICAL_ATLAS)
    if actual != PINNED_ATLAS_SHA256:
        raise SystemExit(
            f"ERROR: turkish_atlases.bin SHA-256 mismatch!\n"
            f"  Expected: {PINNED_ATLAS_SHA256}\n"
            f"  Actual  : {actual}"
        )
    addon_dst = ROOT / "font-injector" / "addon" / "turkish_atlases.bin"
    shutil.copy2(CANONICAL_ATLAS, addon_dst)
    if copy_loader:
        loader_dst = ROOT / "font-injector" / "loader" / "turkish_atlases.bin"
        shutil.copy2(CANONICAL_ATLAS, loader_dst)
    print(f"[+] Verified canonical atlas ({CANONICAL_ATLAS.stat().st_size:,} bytes, sha256={actual[:12]}...)")
    return CANONICAL_ATLAS


def build_font_injector_dll() -> Path:
    """Compiles font-injector/addon/turkish_font.dll using MinGW windres + g++."""
    windres = shutil.which("windres")
    gxx = shutil.which("g++")
    if not windres or not gxx:
        missing = [n for n, p in (("windres", windres), ("g++", gxx)) if not p]
        raise SystemExit(
            f"ERROR: Missing C++ build tools on PATH: {', '.join(missing)}. "
            "Install MinGW-w64 (ucrt64) and ensure g++/windres are on PATH."
        )
    verify_and_stage_atlas(copy_loader=False)
    addon_dir = ROOT / "font-injector" / "addon"
    run([windres, "resource.rc", "-O", "coff", "-o", "resource.res"], cwd=addon_dir)
    run([
        gxx, "-shared", "-O2", "-std=c++20",
        "-static-libgcc", "-static-libstdc++", "-static",
        "-o", "turkish_font.dll", "main.cpp", "resource.res",
    ], cwd=addon_dir)
    dll_out = addon_dir / "turkish_font.dll"
    print(f"[+] Built: {dll_out} ({dll_out.stat().st_size / (1024*1024):.2f} MB)")
    return dll_out


def build_legacy_proxy_dll() -> Path:
    """Opt-in (--legacy-proxy): compiles deprecated Rust version.dll proxy."""
    cargo = shutil.which("cargo")
    if not cargo:
        raise SystemExit("ERROR: 'cargo' not found on PATH for --legacy-proxy build.")
    verify_and_stage_atlas(copy_loader=True)
    run([cargo, "build", "--release", "--locked", "--manifest-path", str(ROOT / "font-injector" / "loader" / "Cargo.toml")])
    dll_out = ROOT / "font-injector" / "loader" / "target" / "release" / "version.dll"
    print(f"[+] Built (deprecated legacy proxy): {dll_out} ({dll_out.stat().st_size / (1024*1024):.2f} MB)")
    return dll_out


def build_local_translator_exe() -> Path:
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
    return exe_out


def build_hub_exe(*, bundle_assets: bool = False) -> Path:
    """Builds GW2_TR_Hub (--onedir to avoid PyInstaller --onefile AV false positives)
    and packages dist/GW2_TR_Hub.zip (~13.7 MB lightweight manifest-driven Hub)."""
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
    return hub_zip


def assemble_release() -> Path:
    """Assembles release_v{VERSION}/ with all 5 manifest assets + Hub ZIP + manifest.json."""
    rel_dir = ROOT / f"release_v{VERSION}"
    rel_dir.mkdir(parents=True, exist_ok=True)
    copies = [
        (ROOT / "dist" / "GW2_TR_Hub.zip", rel_dir / "GW2_TR_Hub.zip"),
        (ROOT / "dist" / "Local_Translator_TR.exe", rel_dir / "Local_Translator_TR.exe"),
        (ROOT / "font-injector" / "addon" / "turkish_font.dll", rel_dir / "turkish_font.dll"),
        (ROOT / "assets" / "d3d11.dll", rel_dir / "d3d11.dll"),
        (ROOT / "assets" / "addons" / "text_translator.dll", rel_dir / "text_translator.dll"),
    ]
    for src, dst in copies:
        if not src.is_file():
            raise SystemExit(f"ERROR: Release asset missing: {src}")
        shutil.copy2(src, dst)

    model_zip = rel_dir / "opus-mt-en-tr-ct2.zip"
    model_dir = ROOT / "TR" / "model"
    if model_dir.is_dir() and any(model_dir.iterdir()):
        with zipfile.ZipFile(model_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(model_dir.iterdir()):
                if p.is_file():
                    zf.write(p, p.name)
    elif not model_zip.is_file():
        raise SystemExit(f"ERROR: Neither {model_dir} nor {model_zip} exists for release packaging.")

    run([sys.executable, str(ROOT / "tools" / "build_manifest.py"), "--assets-dir", str(rel_dir), "--version", VERSION])
    print(f"[+] Release directory ready: {rel_dir}")
    return rel_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Build GW2-TR native DLLs, EXEs, and release package.")
    parser.add_argument("--hub-only", action="store_true", help="Only build GW2_TR_Hub.zip")
    parser.add_argument("--dll-only", action="store_true", help="Only build turkish_font.dll")
    parser.add_argument("--bundled", action="store_true", help="Embed TR/model and DLLs into Hub (legacy)")
    parser.add_argument("--legacy-proxy", action="store_true", help="Also build deprecated Rust version.dll proxy")
    parser.add_argument("--release", action="store_true", help="Assemble release_v{VERSION}/ and generate manifest.json")
    args = parser.parse_args()

    if args.dll_only:
        build_font_injector_dll()
        if args.legacy_proxy:
            build_legacy_proxy_dll()
        return 0

    if not args.hub_only:
        build_font_injector_dll()
        if args.legacy_proxy:
            build_legacy_proxy_dll()
        build_local_translator_exe()

    build_hub_exe(bundle_assets=args.bundled)

    if args.release:
        assemble_release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
