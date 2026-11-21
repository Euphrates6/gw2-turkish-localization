"""Migrates the clean unified v0.12.0 codebase from a source directory to the target repo.
Preserves the .git directory while cleanly updating all tracked files.
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

DEFAULT_DST = Path(__file__).resolve().parent.parent

# Folders and files to exclude from git root copy
EXCLUDE = {
    ".git",
    "build",
    "dist",
    "_manual_pkg_tmp",
    ".pytest_cache",
    "__pycache__",
    ".coverage",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync GW2-TR source directory into git repository.")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path(os.environ["GW2_TR_SRC"]) if os.environ.get("GW2_TR_SRC") else None,
        help="Source directory (or set GW2_TR_SRC env var)",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        default=Path(os.environ.get("GW2_TR_DST", str(DEFAULT_DST))),
        help="Destination git repo directory (default: current repo root or GW2_TR_DST)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.src is None:
        raise SystemExit("Hata: --src parametresi veya GW2_TR_SRC ortam değişkeni belirtilmelidir.")
    src_dir = args.src.resolve()
    dst_dir = args.dst.resolve()

    assert src_dir.is_dir(), f"Source not found: {src_dir}"
    assert dst_dir.is_dir(), f"Destination not found: {dst_dir}"
    assert (dst_dir / ".git").is_dir(), f"Destination is not a git repo: {dst_dir}"

    # 1. Clean destination working directory (except .git)
    print(">> Cleaning legacy files in destination repo (preserving .git)...")
    for item in dst_dir.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)

    # 2. Copy all files and folders from src_dir to dst_dir
    print(f">> Copying clean v0.12.0 files from {src_dir} to {dst_dir}...")
    for item in src_dir.iterdir():
        if item.name in EXCLUDE:
            continue
        dst_item = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dst_item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
            print(f"  [+] Copied folder: {item.name}")
        elif item.is_file():
            shutil.copy2(item, dst_item)
            print(f"  [+] Copied file  : {item.name}")

    print("[+] Migration completed successfully!")


if __name__ == "__main__":
    main()
