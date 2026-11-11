"""Migrates the clean unified v0.12.0 codebase from Gw2-TR to gw2-turkish-localization.
Preserves the .git directory while cleanly updating all tracked files.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

SRC_DIR = Path(r"E:\Gw2 TR Translate\Gw2-TR")
DST_DIR = Path(r"E:\Gw2 TR Translate\gw2-turkish-localization")

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


def main() -> None:
    assert SRC_DIR.is_dir(), f"Source not found: {SRC_DIR}"
    assert DST_DIR.is_dir(), f"Destination not found: {DST_DIR}"
    assert (DST_DIR / ".git").is_dir(), f"Destination is not a git repo: {DST_DIR}"

    # 1. Clean destination working directory (except .git)
    print(">> Cleaning legacy files in destination repo (preserving .git)...")
    for item in DST_DIR.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)

    # 2. Copy all files and folders from SRC_DIR to DST_DIR
    print(f">> Copying clean v0.12.0 files from {SRC_DIR} to {DST_DIR}...")
    for item in SRC_DIR.iterdir():
        if item.name in EXCLUDE:
            continue
        dst_item = DST_DIR / item.name
        if item.is_dir():
            shutil.copytree(item, dst_item, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.log"))
            print(f"  [+] Copied folder: {item.name}")
        elif item.is_file():
            shutil.copy2(item, dst_item)
            print(f"  [+] Copied file  : {item.name}")

    print("[+] Migration completed successfully!")


if __name__ == "__main__":
    main()
