"""Manifest schema, validation, and incremental update planner for GW2-TR Hub."""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from version import VERSION

SCHEMA_VERSION = 1
GITHUB_REPO = "Euphrates6/gw2-turkish-localization"
MANIFEST_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/manifest.json"
HUB_DOWNLOAD_URL = f"https://github.com/{GITHUB_REPO}/releases/latest/download/GW2_TR_Hub.exe"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


@dataclass(frozen=True)
class ArchiveMember:
    name: str
    sha256: str
    size: int


@dataclass(frozen=True)
class FileSpec:
    path: str
    asset: str
    sha256: str
    size: int
    validate: str = ""
    archive: str = ""
    members: tuple[ArchiveMember, ...] = ()


@dataclass(frozen=True)
class Component:
    id: str
    label: str
    target: str
    order: int
    required: bool
    files: tuple[FileSpec, ...]
    toggle: str = ""
    if_missing: bool = False


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    version: str
    channel: str
    published_at: str
    notes_url: str
    base_url: str
    block_if_running: tuple[str, ...]
    targets: dict[str, str]
    preserve: tuple[str, ...]
    components: tuple[Component, ...]


@dataclass(frozen=True)
class PlannedItem:
    component: Component
    file: FileSpec
    dest: Path
    url: str
    reason: str


@dataclass(frozen=True)
class UpdatePlan:
    version: str
    download: list[PlannedItem]
    skip: list[tuple[Component, FileSpec, str]]
    total_bytes: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def _validate_rel_path(rel: str, label: str) -> str:
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError(f"{label}: path cannot be empty")
    norm = rel.replace("\\", "/")
    if norm.startswith("/") or re.match(r"^[A-Za-z]:", norm):
        raise ValueError(f"{label}: absolute path not allowed ({rel!r})")
    parts = [p for p in norm.split("/") if p]
    if any(p == ".." for p in parts):
        raise ValueError(f"{label}: path traversal not allowed ({rel!r})")
    return norm


def _validate_sha256(val: str, label: str) -> str:
    if not isinstance(val, str) or not _SHA256_RE.match(val.strip()):
        raise ValueError(f"{label}: invalid sha256 ({val!r})")
    return val.strip().lower()


def validate_schema(data: dict) -> Manifest:
    """Validates raw manifest JSON dict and returns a typed Manifest object."""
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a JSON object")

    schema_ver = data.get("schema_version")
    if schema_ver != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {schema_ver!r} (expected {SCHEMA_VERSION})")

    version = str(data.get("version") or "").strip()
    if not version:
        raise ValueError("manifest missing 'version'")

    base_url = str(data.get("base_url") or "").strip()
    if not base_url.startswith("https://"):
        raise ValueError(f"manifest base_url must use https:// (got {base_url!r})")
    if not base_url.endswith("/"):
        base_url += "/"

    install = data.get("install") or {}
    if not isinstance(install, dict):
        raise ValueError("manifest 'install' must be an object")
    block_list = tuple(str(x).lower() for x in (install.get("block_if_running") or ()))
    raw_targets = install.get("targets") or {"game": "{game_dir}"}
    if not isinstance(raw_targets, dict) or "game" not in raw_targets:
        raise ValueError("manifest 'install.targets' must include 'game'")
    targets = {str(k): str(v) for k, v in raw_targets.items()}

    preserve = tuple(str(p) for p in (data.get("preserve") or ()))

    raw_comps = data.get("components")
    if not isinstance(raw_comps, dict) or not raw_comps:
        raise ValueError("manifest must contain a non-empty 'components' object")

    components: list[Component] = []
    for comp_id, cdata in raw_comps.items():
        if not isinstance(cdata, dict):
            raise ValueError(f"component {comp_id!r} must be an object")
        target = str(cdata.get("target") or "game")
        if target not in targets:
            raise ValueError(f"component {comp_id!r} references unknown target {target!r}")
        raw_files = cdata.get("files")
        if not isinstance(raw_files, list) or not raw_files:
            raise ValueError(f"component {comp_id!r} must define non-empty 'files' list")

        files: list[FileSpec] = []
        for idx, fdata in enumerate(raw_files):
            flabel = f"{comp_id}.files[{idx}]"
            if not isinstance(fdata, dict):
                raise ValueError(f"{flabel} must be an object")
            fpath = _validate_rel_path(str(fdata.get("path") or ""), flabel)
            asset = _validate_rel_path(str(fdata.get("asset") or ""), f"{flabel}.asset")
            sha = _validate_sha256(str(fdata.get("sha256") or ""), flabel)
            size = int(fdata.get("size") or 0)
            if size <= 0:
                raise ValueError(f"{flabel}: size must be positive")
            validate = str(fdata.get("validate") or "").strip().lower()
            archive = str(fdata.get("archive") or "").strip().lower()
            if archive and archive != "zip":
                raise ValueError(f"{flabel}: unsupported archive type {archive!r}")

            members: list[ArchiveMember] = []
            for midx, mdata in enumerate(fdata.get("members") or ()):
                mlabel = f"{flabel}.members[{midx}]"
                mname = _validate_rel_path(str(mdata.get("name") or ""), mlabel)
                msha = _validate_sha256(str(mdata.get("sha256") or ""), mlabel)
                msize = int(mdata.get("size") or 0)
                if msize <= 0:
                    raise ValueError(f"{mlabel}: size must be positive")
                members.append(ArchiveMember(name=mname, sha256=msha, size=msize))

            files.append(FileSpec(
                path=fpath,
                asset=asset,
                sha256=sha,
                size=size,
                validate=validate,
                archive=archive,
                members=tuple(members),
            ))

        components.append(Component(
            id=str(comp_id),
            label=str(cdata.get("label") or comp_id).strip(),
            target=target,
            order=int(cdata.get("order") or 100),
            required=bool(cdata.get("required", True)),
            files=tuple(files),
            toggle=str(cdata.get("toggle") or "").strip(),
            if_missing=bool(cdata.get("if_missing", False)),
        ))

    components.sort(key=lambda c: (c.order, c.id))
    return Manifest(
        schema_version=schema_ver,
        version=version,
        channel=str(data.get("channel") or "stable"),
        published_at=str(data.get("published_at") or ""),
        notes_url=str(data.get("notes_url") or RELEASES_URL),
        base_url=base_url,
        block_if_running=block_list,
        targets=targets,
        preserve=preserve,
        components=tuple(components),
    )


def parse_manifest_bytes(raw: bytes) -> Manifest:
    return validate_schema(json.loads(raw.decode("utf-8")))


def load_manifest_file(path: Path) -> Manifest:
    return parse_manifest_bytes(path.read_bytes())


def fetch_manifest(url: str = MANIFEST_URL, timeout: float = 8.0) -> Manifest:
    """Downloads and validates manifest.json using direct release URL (no GitHub API rate limit)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"GW2-TR-Hub/{VERSION}",
            "Cache-Control": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return parse_manifest_bytes(resp.read())


def resolve_target_path(manifest: Manifest, target_key: str, rel_path: str, game_dir: Path) -> Path:
    """Resolves a manifest target + relative path safely inside game_dir."""
    game_resolved = game_dir.resolve()
    tmpl = manifest.targets[target_key]
    base = Path(tmpl.format(game_dir=str(game_resolved))).resolve()
    dest = (base / rel_path).resolve()
    try:
        dest.relative_to(game_resolved)
    except ValueError as exc:
        raise ValueError(f"resolved path escapes game_dir: {dest}") from exc
    return dest


def _state_key(dest: Path, game_dir: Path) -> str:
    return dest.resolve().relative_to(game_dir.resolve()).as_posix().lower()


def plan_update(
    manifest: Manifest,
    game_dir: Path,
    local_state: dict | None = None,
    toggles: dict[str, bool] | None = None,
    verify_disk_hash: bool = False,
) -> UpdatePlan:
    """Computes an incremental update plan: downloads only missing or hash-changed components."""
    state_files: dict[str, str] = {}
    if isinstance(local_state, dict) and isinstance(local_state.get("files"), dict):
        state_files = {str(k).lower(): str(v).lower() for k, v in local_state["files"].items()}
    toggles = toggles or {}

    download: list[PlannedItem] = []
    skip: list[tuple[Component, FileSpec, str]] = []
    total_bytes = 0

    for comp in manifest.components:
        if comp.toggle and not toggles.get(comp.toggle, True):
            for fspec in comp.files:
                skip.append((comp, fspec, "disabled"))
            continue

        for fspec in comp.files:
            dest = resolve_target_path(manifest, comp.target, fspec.path, game_dir)
            url = manifest.base_url + fspec.asset

            if comp.if_missing and dest.is_file():
                skip.append((comp, fspec, "already_present"))
                continue

            if fspec.archive == "zip" and fspec.members:
                needs_dl = False
                reason = "up_to_date"
                for member in fspec.members:
                    m_dest = (dest / member.name).resolve()
                    if not m_dest.is_file():
                        needs_dl = True
                        reason = "missing"
                        break
                    skey = _state_key(m_dest, game_dir)
                    recorded = state_files.get(skey)
                    if verify_disk_hash or not recorded:
                        actual = sha256_file(m_dest)
                        if actual != member.sha256:
                            needs_dl = True
                            reason = "hash_mismatch"
                            break
                    elif recorded != member.sha256:
                        needs_dl = True
                        reason = "outdated"
                        break
                if needs_dl:
                    download.append(PlannedItem(comp, fspec, dest, url, reason))
                    total_bytes += fspec.size
                else:
                    skip.append((comp, fspec, "up_to_date"))
            else:
                if not dest.is_file():
                    download.append(PlannedItem(comp, fspec, dest, url, "missing"))
                    total_bytes += fspec.size
                    continue
                skey = _state_key(dest, game_dir)
                recorded = state_files.get(skey)
                if verify_disk_hash or not recorded:
                    actual = sha256_file(dest)
                    if actual != fspec.sha256:
                        download.append(PlannedItem(comp, fspec, dest, url, "hash_mismatch"))
                        total_bytes += fspec.size
                    else:
                        skip.append((comp, fspec, "up_to_date"))
                elif recorded != fspec.sha256:
                    download.append(PlannedItem(comp, fspec, dest, url, "outdated"))
                    total_bytes += fspec.size
                else:
                    skip.append((comp, fspec, "up_to_date"))

    return UpdatePlan(
        version=manifest.version,
        download=download,
        skip=skip,
        total_bytes=total_bytes,
    )
