"""Verified content-addressed downloader and safe zip extractor for GW2-TR Hub."""
from __future__ import annotations

import hashlib
import os
import shutil
import struct
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from manifest import ArchiveMember, sha256_file
from version import VERSION


class DownloadError(RuntimeError):
    """Raised when downloading, hashing, validating, or extracting a component fails."""


def validate_pe_file(path: Path, min_bytes: int = 16_384, max_bytes: int = 400 * 1024 * 1024) -> bool:
    """Validates that a file on disk is a reasonable-sized Windows PE binary (DLL/EXE)."""
    try:
        size = path.stat().st_size
        if not (min_bytes <= size <= max_bytes):
            return False
        with path.open("rb") as f:
            dos = f.read(0x40)
            if len(dos) < 0x40 or dos[:2] != b"MZ":
                return False
            pe_offset = struct.unpack_from("<I", dos, 0x3C)[0]
            if pe_offset + 4 > size:
                return False
            f.seek(pe_offset)
            return f.read(4) == b"PE\x00\x00"
    except OSError:
        return False


def download_verified(
    url: str,
    expected_sha256: str,
    expected_size: int,
    downloads_dir: Path,
    *,
    validate: str = "",
    retries: int = 3,
    timeout: float = 30.0,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Downloads url to a content-addressed file in downloads_dir with SHA-256 + optional PE verification."""
    expected_sha256 = expected_sha256.strip().lower()
    downloads_dir.mkdir(parents=True, exist_ok=True)
    final_path = downloads_dir / f"{expected_sha256}.bin"
    part_path = downloads_dir / f"{expected_sha256}.part"

    # Dedupe: reuse already-verified download if present
    if final_path.is_file():
        if final_path.stat().st_size == expected_size and sha256_file(final_path) == expected_sha256:
            if validate != "pe" or validate_pe_file(final_path):
                if on_progress:
                    on_progress(expected_size, expected_size)
                return final_path
        final_path.unlink(missing_ok=True)

    last_err: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            existing = part_path.stat().st_size if part_path.is_file() else 0
            if existing >= expected_size:
                part_path.unlink(missing_ok=True)
                existing = 0

            headers = {
                "User-Agent": f"GW2-TR-Hub/{VERSION}",
                "Cache-Control": "no-cache",
            }
            if existing > 0:
                headers["Range"] = f"bytes={existing}-"

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                mode = "ab" if (existing > 0 and status == 206) else "wb"
                downloaded = existing if mode == "ab" else 0
                with part_path.open(mode) as out:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out.write(chunk)
                        downloaded += len(chunk)
                        if on_progress:
                            on_progress(downloaded, expected_size)

            actual_size = part_path.stat().st_size
            if actual_size != expected_size:
                part_path.unlink(missing_ok=True)
                raise DownloadError(f"size mismatch: expected {expected_size}, got {actual_size}")

            actual_sha = sha256_file(part_path)
            if actual_sha != expected_sha256:
                part_path.unlink(missing_ok=True)
                raise DownloadError(f"sha256 mismatch: expected {expected_sha256}, got {actual_sha}")

            if validate == "pe" and not validate_pe_file(part_path):
                part_path.unlink(missing_ok=True)
                raise DownloadError("downloaded file failed Windows PE header validation")

            os.replace(part_path, final_path)
            return final_path
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(min(2.0 ** (attempt - 1), 4.0))

    raise DownloadError(f"failed to download {url} after {retries} attempts: {last_err}") from last_err


def _safe_zip_member_path(dest_dir: Path, member_name: str) -> Path:
    norm = member_name.replace("\\", "/")
    if not norm or norm.startswith("/") or (len(norm) >= 2 and norm[1] == ":"):
        raise DownloadError(f"unsafe zip member path: {member_name!r}")
    parts = [p for p in norm.split("/") if p]
    if any(p == ".." for p in parts):
        raise DownloadError(f"zip path traversal blocked: {member_name!r}")
    dest_resolved = dest_dir.resolve()
    target = (dest_resolved / norm).resolve()
    try:
        target.relative_to(dest_resolved)
    except ValueError as exc:
        raise DownloadError(f"zip member escapes extract dir: {member_name!r}") from exc
    return target


def extract_zip_safe(
    zip_path: Path,
    dest_dir: Path,
    expected_members: tuple[ArchiveMember, ...] = (),
) -> list[Path]:
    """Safely extracts a zip archive (blocking path traversal) and verifies expected member SHA-256s."""
    if dest_dir.exists():
        shutil.rmtree(dest_dir, ignore_errors=True)
    dest_dir.mkdir(parents=True, exist_ok=True)

    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            # Reject Unix symlinks stored in zip external attributes
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise DownloadError(f"symlink not allowed in archive: {info.filename!r}")
            target = _safe_zip_member_path(dest_dir, info.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst, length=65536)
            extracted.append(target)

    for member in expected_members:
        mpath = _safe_zip_member_path(dest_dir, member.name)
        if not mpath.is_file():
            raise DownloadError(f"expected archive member missing: {member.name!r}")
        if mpath.stat().st_size != member.size:
            raise DownloadError(f"archive member size mismatch for {member.name!r}")
        if sha256_file(mpath) != member.sha256:
            raise DownloadError(f"archive member sha256 mismatch for {member.name!r}")

    return extracted
