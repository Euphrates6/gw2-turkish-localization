"""Atomic cross-volume file applier with transaction journal and rollback for GW2-TR Hub."""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from downloader import extract_zip_safe
from manifest import UpdatePlan, sha256_file
from state import InstallState


class ApplyError(RuntimeError):
    """Raised when applying an update plan fails (after rollback)."""


def atomic_install_file(
    src: Path,
    dst: Path,
    *,
    backup_dir: Path | None = None,
    game_dir: Path | None = None,
    retries: int = 3,
) -> Path | None:
    """Cross-volume safe atomic install: copies src to dst.new on target volume, backs up dst, then os.replace."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if dst.is_file() and backup_dir is not None:
        if game_dir is not None:
            try:
                rel = dst.resolve().relative_to(game_dir.resolve())
            except ValueError:
                rel = Path(dst.name)
        else:
            rel = Path(dst.name)
        backup_path = backup_dir / rel
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(dst, backup_path)

    tmp_new = dst.with_name(dst.name + ".new")
    shutil.copy2(src, tmp_new)

    last_err: Exception | None = None
    for attempt in range(1, max(1, retries) + 1):
        try:
            os.replace(tmp_new, dst)
            return backup_path
        except PermissionError as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(0.2 * attempt)
    tmp_new.unlink(missing_ok=True)
    raise PermissionError(f"could not replace {dst}: {last_err}") from last_err


def _rollback(applied_records: list[tuple[Path, Path | None]]) -> None:
    for dst, bak in reversed(applied_records):
        try:
            if bak and bak.is_file():
                tmp = dst.with_name(dst.name + ".rb")
                shutil.copy2(bak, tmp)
                os.replace(tmp, dst)
            elif dst.is_file():
                dst.unlink(missing_ok=True)
        except OSError:
            pass


def apply_plan(
    plan: UpdatePlan,
    staged_assets: dict[str, Path],
    game_dir: Path,
    state: InstallState,
) -> dict:
    """Applies a verified UpdatePlan atomically with backup, journal, and automatic rollback on error."""
    game_resolved = game_dir.resolve()
    if plan.total_bytes > 0:
        free = shutil.disk_usage(game_resolved).free
        needed = plan.total_bytes * 2
        if free < needed:
            raise ApplyError(
                f"Yetersiz disk alanı: {needed // (1024*1024)} MB gerekli, {free // (1024*1024)} MB mevcut."
            )

    backup_dir = state.new_backup_dir()
    state.write_journal({
        "version": plan.version,
        "backup_dir": str(backup_dir),
        "items": [item.component.id for item in plan.download],
        "status": "in_progress",
    })

    applied_records: list[tuple[Path, Path | None]] = []
    current_state = state.load()
    new_files: dict[str, str] = dict(current_state.get("files") or {})

    try:
        for item in plan.download:
            staged = staged_assets.get(item.file.sha256)
            if not staged or not staged.is_file():
                raise ApplyError(f"staged asset missing for component {item.component.id!r}")

            if item.file.archive == "zip":
                ext_dir = state.extract_dir / item.component.id
                extracted = extract_zip_safe(staged, ext_dir, item.file.members)
                for src_file in extracted:
                    rel_member = src_file.resolve().relative_to(ext_dir.resolve())
                    dst_file = (item.dest / rel_member).resolve()
                    bak = atomic_install_file(src_file, dst_file, backup_dir=backup_dir, game_dir=game_resolved)
                    applied_records.append((dst_file, bak))
                    rel_key = dst_file.relative_to(game_resolved).as_posix().lower()
                    new_files[rel_key] = sha256_file(dst_file)
            else:
                bak = atomic_install_file(staged, item.dest, backup_dir=backup_dir, game_dir=game_resolved)
                applied_records.append((item.dest, bak))
                rel_key = item.dest.resolve().relative_to(game_resolved).as_posix().lower()
                new_files[rel_key] = item.file.sha256
    except Exception as exc:
        _rollback(applied_records)
        raise ApplyError(f"Güncelleme uygulanamadı ve geri alındı: {exc}") from exc

    state.save({"version": plan.version, "files": new_files})
    state.commit_journal()
    return {
        "ok": True,
        "version": plan.version,
        "applied_count": len(applied_records),
        "skipped_count": len(plan.skip),
        "backup_dir": str(backup_dir),
    }
