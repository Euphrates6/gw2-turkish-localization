"""Persistent local state, staging, backup, and transaction journal for GW2-TR Hub.

Always stores data under %LOCALAPPDATA%\\GW2_TR_Hub (never inside PyInstaller's _MEIPASS).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


def default_state_root() -> Path:
    local_app = os.environ.get("LOCALAPPDATA")
    if local_app:
        return Path(local_app) / "GW2_TR_Hub"
    return Path.home() / ".gw2_tr_hub"


class InstallState:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_state_root()).resolve()
        self.state_file = self.root / "install_state.json"
        self.journal_file = self.root / "journal.json"
        self.downloads_dir = self.root / "staging" / "downloads"
        self.extract_dir = self.root / "staging" / "extract"
        self.backups_dir = self.root / "backups"

    def ensure_dirs(self) -> None:
        for d in (self.root, self.downloads_dir, self.extract_dir, self.backups_dir):
            d.mkdir(parents=True, exist_ok=True)

    def load(self) -> dict:
        if not self.state_file.is_file():
            return {"version": "", "files": {}, "installed_at": ""}
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("version", "")
                data.setdefault("files", {})
                data.setdefault("installed_at", "")
                return data
        except Exception:
            pass
        return {"version": "", "files": {}, "installed_at": ""}

    def save(self, data: dict) -> None:
        self.ensure_dirs()
        payload = {
            "version": str(data.get("version") or ""),
            "files": {str(k).lower(): str(v).lower() for k, v in (data.get("files") or {}).items()},
            "installed_at": str(data.get("installed_at") or datetime.now(timezone.utc).isoformat()),
        }
        tmp = self.state_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def new_backup_dir(self) -> Path:
        self.ensure_dirs()
        stamp = time.strftime("%Y%m%d_%H%M%S")
        bdir = self.backups_dir / stamp
        bdir.mkdir(parents=True, exist_ok=True)
        return bdir

    def write_journal(self, entry: dict) -> Path:
        self.ensure_dirs()
        payload = dict(entry)
        payload.setdefault("status", "in_progress")
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        tmp = self.journal_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.journal_file)
        return self.journal_file

    def commit_journal(self) -> None:
        if self.journal_file.is_file():
            try:
                data = json.loads(self.journal_file.read_text(encoding="utf-8"))
                data["status"] = "committed"
                tmp = self.journal_file.with_suffix(".json.tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, self.journal_file)
            except Exception:
                pass

    def pending_journal(self) -> dict | None:
        if not self.journal_file.is_file():
            return None
        try:
            data = json.loads(self.journal_file.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("status") != "committed":
                return data
        except Exception:
            pass
        return None
