"""Single source of truth for GW2-TR version."""
from __future__ import annotations

import sys
from pathlib import Path

_FALLBACK_VERSION = "0.13.3"


def _read_version() -> str:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "VERSION")
        candidates.append(Path(sys.executable).resolve().parent / "VERSION")
    here = Path(__file__).resolve().parent
    candidates.extend([here.parent / "VERSION", here / "VERSION"])
    for p in candidates:
        if p.is_file():
            try:
                val = p.read_text(encoding="utf-8").strip()
                if val:
                    return val
            except OSError:
                pass
    return _FALLBACK_VERSION


VERSION: str = _read_version()
