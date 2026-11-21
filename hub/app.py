"""GW2 TR — Mod Installation Hub (pywebview + WebView2 Desktop App).

Provides the backend API for the IDE-themed Mod Installation Hub UI (`hub/ui/index.html`):
- Auto-detects Guild Wars 2 directory
- Checks & installs Raidcore Nexus (`d3d11.dll`) with website fallback
- Toggles GW2 Turkish Font Injector (`turkish_font.dll` / `version.dll`) ON/OFF and synchronizes
  `cache.db` between authentic Turkish glyphs (`off`) and 6-character fallback (`ascii_6`:
  ş->s, Ş->S, ğ->g, Ğ->G, İ->I, ı->i while keeping ç, Ç, ö, Ö, ü, Ü)
- Configures in-game translation toggle keybind (`ALT+T`) in `addons/Nexus/InputBinds.json`
- Configures "Keep Item & Location Names in English" and Offline OPUS-MT vs Optional Cloud backends
- Integrates Live & Offline Translation Editor (`editor.py` on `127.0.0.1:8770` or direct SQLite)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
HUB_DIR = Path(__file__).resolve().parent
for _p in (str(SRC_DIR), str(HUB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lt_server as lt  # noqa: E402
from patch_db import CachePatch, sync_key_tags  # noqa: E402
import editor as editor_mod  # noqa: E402
from version import VERSION  # noqa: E402
import process_guard  # noqa: E402
import manifest as manifest_mod  # noqa: E402
import state as state_mod  # noqa: E402
import downloader as downloader_mod  # noqa: E402
import applier as applier_mod  # noqa: E402

SCANCODE_TO_KEY = {
    1: "ESC", 2: "1", 3: "2", 4: "3", 5: "4", 6: "5", 7: "6", 8: "7", 9: "8", 10: "9", 11: "0",
    16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U", 23: "I", 24: "O", 25: "P",
    30: "A", 31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J", 37: "K", 38: "L",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M",
    59: "F1", 60: "F2", 61: "F3", 62: "F4", 63: "F5", 64: "F6",
    65: "F7", 66: "F8", 67: "F9", 68: "F10", 87: "F11", 88: "F12",
}

NEXUS_SIG_TEXT_TRANSLATOR = -541596960
NEXUS_SIG_TURKISH_FONT = 1414877771  # 'TURK' (0x5455524B)
KEYBIND_ID = "TEXTTRANSLATOR_TOGGLE_SHOW_TRANSLATED"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{lt.GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{lt.GITHUB_REPO}/releases/latest"


def _parse_semver(tag: str) -> tuple[int, ...]:
    """Parses a version string like 'v0.12.0-TR' into a comparable integer tuple (0, 12, 0)."""
    nums = [int(x) for x in re.findall(r"\d+", str(tag or ""))[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums)


def resource_root() -> Path:
    """Returns bundle root when frozen with PyInstaller, otherwise repository root."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return ROOT_DIR


def _mask_secret(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "••••"
    return f"{s[:4]}••••{s[-4:]}"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _validate_pe_dll(data: bytes, min_bytes: int = 65_536, max_bytes: int = 50 * 1024 * 1024) -> bool:
    """Validates that downloaded bytes are a reasonable-sized Windows PE binary."""
    if not (min_bytes <= len(data) <= max_bytes):
        return False
    if len(data) < 0x40 or data[:2] != b"MZ":
        return False
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_offset + 4 > len(data):
        return False
    return data[pe_offset:pe_offset + 4] == b"PE\x00\x00"


def _safe_copy_with_backup(src: Path, dst: Path) -> bool:
    """Copies src to dst only if missing or content differs; backs up existing dst to .bak."""
    if dst.is_file():
        try:
            if _sha256_file(src) == _sha256_file(dst):
                return False
        except OSError:
            pass
        try:
            shutil.copy2(dst, dst.with_name(dst.name + ".bak"))
        except OSError:
            pass
    shutil.copy2(src, dst)
    return True


def _merge_settings_toml(settings_path: Path, folder_bytes: list[int]) -> None:
    """Updates active_module in settings.toml while preserving existing user settings."""
    active_line = f"active_module = {{ Windows = {folder_bytes} }}"
    if settings_path.is_file():
        try:
            existing = settings_path.read_text(encoding="utf-8")
            try:
                shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".bak"))
            except OSError:
                pass
            if re.search(r"^\s*active_module\s*=", existing, flags=re.MULTILINE):
                merged = re.sub(
                    r"^\s*active_module\s*=.*$",
                    active_line,
                    existing,
                    count=1,
                    flags=re.MULTILINE,
                )
            else:
                merged = active_line + "\n" + existing
            settings_path.write_text(merged, encoding="utf-8")
            return
        except OSError:
            pass
    settings_toml = (
        f"{active_line}\n"
        "show_translated = true\n"
        "pause_refreshes = false\n"
        "pause_translations = false\n\n"
        "[refresh_debounce]\n"
        "secs = 0\n"
        "nanos = 500000000\n"
    )
    settings_path.write_text(settings_toml, encoding="utf-8")


def _detect_gw2_from_registry() -> list[Path]:
    found: list[Path] = []
    if os.name != "nt":
        return found
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ArenaNet\Guild Wars 2"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\ArenaNet\Guild Wars 2"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\ArenaNet\Guild Wars 2"),
        ]
        for root, subkey in reg_paths:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for val_name in ("Path", "SrcDir", "InstallLocation"):
                        try:
                            val, _ = winreg.QueryValueEx(key, val_name)
                            if isinstance(val, str) and val.strip():
                                p = Path(val.strip())
                                found.append(p.parent if p.suffix.lower() == ".exe" else p)
                        except OSError:
                            pass
            except OSError:
                pass
    except Exception:
        pass
    return found


def _detect_steam_gw2_dirs() -> list[Path]:
    found: list[Path] = []
    steam_roots: list[Path] = [
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Program Files\Steam"),
    ]
    if os.name == "nt":
        try:
            import winreg
            for root, subkey in (
                (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
            ):
                try:
                    with winreg.OpenKey(root, subkey) as key:
                        val, _ = winreg.QueryValueEx(key, "SteamPath")
                        if isinstance(val, str) and val.strip():
                            steam_roots.insert(0, Path(val.strip()))
                except OSError:
                    pass
        except Exception:
            pass

    seen_libs: set[Path] = set()
    for sroot in steam_roots:
        if not sroot.is_dir():
            continue
        libs = [sroot]
        vdf = sroot / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            try:
                content = vdf.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'"path"\s+"([^"]+)"', content):
                    libs.append(Path(m.group(1).replace("\\\\", "\\")))
            except OSError:
                pass
        for lib in libs:
            if lib not in seen_libs:
                seen_libs.add(lib)
                found.append(lib / "steamapps" / "common" / "Guild Wars 2")
    return found


def detect_gw2_dir() -> Path | None:
    """Finds Guild Wars 2 installation directory automatically via Registry, Steam libraries, and common paths."""
    candidates: list[Path] = []
    candidates.extend(_detect_gw2_from_registry())
    candidates.extend(_detect_steam_gw2_dirs())
    for drive in ("C", "D", "E", "F"):
        root = Path(f"{drive}:\\")
        if not root.is_dir():
            continue
        candidates.extend([
            root / "Program Files" / "Guild Wars 2",
            root / "Program Files (x86)" / "Guild Wars 2",
            root / "Guild Wars 2",
            root / "GuildWars2",
            root / "Games" / "Guild Wars 2",
            root / "SteamLibrary" / "steamapps" / "common" / "Guild Wars 2",
        ])
    for p in candidates:
        if (p / "Gw2-64.exe").is_file():
            return p
    return None


class HubAPI:
    def __init__(self) -> None:
        self._window = None
        self._res_dir = resource_root()
        self._state_file = Path.home() / ".gw2_tr_hub.json"
        self._game_dir: Path | None = self._load_saved_dir() or detect_gw2_dir()

    def _load_saved_dir(self) -> Path | None:
        if self._state_file.is_file():
            try:
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                p = Path(data.get("game_dir", ""))
                if p.is_dir() and (p / "Gw2-64.exe").is_file():
                    return p
            except Exception:
                pass
        return None

    def _save_saved_dir(self) -> None:
        if not self._game_dir:
            return
        try:
            self._state_file.write_text(
                json.dumps({"game_dir": str(self._game_dir)}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    def _module_dir(self) -> Path | None:
        if not self._game_dir:
            return None
        return self._game_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"

    def _lang_dir(self) -> Path | None:
        mod = self._module_dir()
        return (mod / "TR") if mod else None

    def _read_tr_config(self) -> dict:
        cfg = {
            "backend": "offline",
            "threads": 2,
            "font_injector": True,
            "char_mode": "off",
            "keep_items_english": True,
            "api_key": "",
            "model_name": "",
        }
        lang_dir = self._lang_dir()
        for candidate in ([lang_dir / "config.json"] if lang_dir else []) + [self._res_dir / "TR" / "config.json"]:
            if candidate and candidate.is_file():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8-sig"))
                    if isinstance(raw, dict):
                        cfg.update(raw)
                        break
                except Exception:
                    pass
        if self._game_dir and (self._game_dir / "addons" / "turkish_font.disabled").is_file():
            cfg["font_injector"] = False
            cfg["char_mode"] = "ascii_6"
        elif cfg.get("font_injector", True) and cfg.get("char_mode") in ("", None):
            cfg["char_mode"] = "off"
        return cfg

    def _write_tr_config(self, updates: dict) -> dict:
        cfg = self._read_tr_config()
        cfg.update(updates)
        if "char_mode" not in updates:
            if "font_injector" in updates:
                cfg["char_mode"] = "off" if cfg.get("font_injector", True) else "ascii_6"
            elif not cfg.get("char_mode"):
                cfg["char_mode"] = "off" if cfg.get("font_injector", True) else "ascii_6"

        targets = [self._res_dir / "TR" / "config.json"]
        lang_dir = self._lang_dir()
        if lang_dir:
            targets.append(lang_dir / "config.json")
        for t in targets:
            try:
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return cfg

    def _read_contributor(self) -> tuple[str, str]:
        lang_dir = self._lang_dir()
        for candidate in ([lang_dir / "contributor.json"] if lang_dir else []) + [self._res_dir / "TR" / "contributor.json"]:
            if candidate and candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8-sig"))
                    author = str(data.get("author") or "Oyuncu").strip()
                    sk = data.get("show_keys", False)
                    sk_str = sk if sk in ("text", "all") else ("text" if sk is True else "off")
                    return author, sk_str
                except Exception:
                    pass
        return "Oyuncu", "off"

    def _write_contributor(self, author: str, show_keys: str) -> None:
        sk_val: bool | str = show_keys if show_keys in ("text", "all") else False
        payload = {"author": author.strip() or "Oyuncu", "show_keys": sk_val}
        targets = [self._res_dir / "TR" / "contributor.json"]
        lang_dir = self._lang_dir()
        if lang_dir:
            targets.append(lang_dir / "contributor.json")
        for t in targets:
            try:
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass

    def _read_keybind(self) -> dict:
        default_kb = {"alt": True, "ctrl": False, "shift": False, "key": "T", "scancode": 20, "label": "ALT + T"}
        if not self._game_dir:
            return default_kb
        binds_path = self._game_dir / "addons" / "Nexus" / "InputBinds.json"
        if not binds_path.is_file():
            return default_kb
        try:
            items = json.loads(binds_path.read_text(encoding="utf-8-sig"))
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict) and item.get("Identifier") == KEYBIND_ID:
                        sc = int(item.get("Code") or 20)
                        alt = bool(item.get("Alt"))
                        ctrl = bool(item.get("Ctrl"))
                        shift = bool(item.get("Shift"))
                        kname = SCANCODE_TO_KEY.get(sc, f"KEY({sc})")
                        parts = []
                        if ctrl:
                            parts.append("CTRL")
                        if alt:
                            parts.append("ALT")
                        if shift:
                            parts.append("SHIFT")
                        parts.append(kname)
                        return {
                            "alt": alt, "ctrl": ctrl, "shift": shift,
                            "key": kname, "scancode": sc, "label": " + ".join(parts)
                        }
        except Exception:
            pass
        return default_kb

    def _update_addon_config(self, sig: int, name: str, loaded: bool) -> None:
        if not self._game_dir:
            return
        cfg_path = self._game_dir / "addons" / "Nexus" / "AddonConfig.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        items = []
        if cfg_path.is_file():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                if isinstance(raw, list):
                    items = raw
            except Exception:
                items = []
        found = False
        for item in items:
            if isinstance(item, dict) and item.get("Signature") == sig:
                item["IsLoaded"] = loaded
                found = True
        if not found:
            items.append({
                "AllowUpdates": True,
                "IsDisabledUntilUpdate": False,
                "IsLoaded": loaded,
                "IsPermanentlyDisabled": False,
                "Name": name,
                "Signature": sig,
            })
        try:
            cfg_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _count_glossary_terms(self) -> int:
        lang_dir = self._lang_dir()
        candidates = ([lang_dir / "glossary_tr.json"] if lang_dir else []) + [
            self._res_dir / "TR" / "glossary_tr.json",
            self._res_dir / "src" / "glossary_tr.default.json",
        ]
        for cand in candidates:
            if cand and cand.is_file():
                try:
                    data = json.loads(cand.read_text(encoding="utf-8-sig"))
                    if isinstance(data, dict):
                        return len(data.get("exact") or {}) + len(data.get("terms") or {})
                except Exception:
                    pass
        return 0

    # ------------------------------------------------------------------ #
    # Public API Methods called from JavaScript
    # ------------------------------------------------------------------ #
    def get_status(self) -> dict:
        cfg = self._read_tr_config()
        author, show_keys = self._read_contributor()
        nexus_ok = bool(self._game_dir and (self._game_dir / "d3d11.dll").is_file())
        tt_ok = bool(self._game_dir and (self._game_dir / "addons" / "text_translator.dll").is_file())
        mod_dir = self._module_dir()
        lt_ok = bool(mod_dir and ((mod_dir / "Local_Translator_TR.exe").is_file() or (mod_dir / "module.toml").is_file()))
        model_ok = bool(
            (mod_dir and (mod_dir / "TR" / "model" / "model.bin").is_file())
            or (self._res_dir / "TR" / "model" / "model.bin").is_file()
        )
        raw_key = str(cfg.get("api_key") or "").strip()
        return {
            "version": VERSION,
            "game_dir": str(self._game_dir) if self._game_dir else "",
            "nexus_installed": nexus_ok,
            "tt_installed": tt_ok,
            "lt_installed": lt_ok,
            "model_installed": model_ok,
            "glossary_count": self._count_glossary_terms(),
            "font_injector": bool(cfg.get("font_injector", True)),
            "char_mode": cfg.get("char_mode", "off"),
            "keep_items_english": bool(cfg.get("keep_items_english", True)),
            "backend": cfg.get("backend", "offline"),
            "threads": int(cfg.get("threads") or 2),
            "api_key": "",
            "api_key_set": bool(raw_key),
            "api_key_masked": _mask_secret(raw_key),
            "model_name": cfg.get("model_name", ""),
            "author": author,
            "show_keys": show_keys,
            "keybind": self._read_keybind(),
        }

    def browse_game_dir(self) -> dict:
        import webview
        window = self._window or webview.active_window()
        if not window:
            return {"ok": False, "message": "Pencere hazır değil"}
        result = window.create_file_dialog(webview.FOLDER_DIALOG, directory=str(self._game_dir or "C:\\"))
        if result and len(result) > 0:
            chosen = Path(result[0])
            self._game_dir = chosen
            self._save_saved_dir()
            return {"ok": True, "status": self.get_status()}
        return {"ok": False, "status": self.get_status()}

    def open_url(self, url: str) -> dict:
        if not isinstance(url, str) or not url.lower().startswith(("https://", "http://")):
            return {"ok": False, "message": "Geçersiz bağlantı."}
        webbrowser.open(url)
        return {"ok": True}

    def check_for_updates(self) -> dict:
        """Checks for updates via direct manifest.json release asset first (no API rate limit),
        falling back to GitHub Releases API when manifest.json is not yet published (404)."""
        base = {
            "ok": False,
            "current_version": VERSION,
            "latest_version": VERSION,
            "update_available": False,
            "manifest_available": False,
            "release_name": "",
            "release_url": GITHUB_RELEASES_URL,
            "download_url": manifest_mod.HUB_DOWNLOAD_URL,
        }
        # 1. Preferred: direct manifest.json (no api.github.com rate limit)
        try:
            m = manifest_mod.fetch_manifest(timeout=5.0)
            update_available = _parse_semver(m.version) > _parse_semver(VERSION)
            result = {
                "ok": True,
                "current_version": VERSION,
                "latest_version": m.version,
                "update_available": update_available,
                "manifest_available": True,
                "release_name": f"GW2-TR v{m.version}",
                "release_url": m.notes_url,
                "download_url": manifest_mod.HUB_DOWNLOAD_URL,
            }
            if self._game_dir and self._game_dir.is_dir():
                cfg = self._read_tr_config()
                st = state_mod.InstallState().load()
                plan = manifest_mod.plan_update(
                    m,
                    self._game_dir,
                    local_state=st,
                    toggles={"font_injector": bool(cfg.get("font_injector", True))},
                )
                result["plan_summary"] = {
                    "download_count": len(plan.download),
                    "skip_count": len(plan.skip),
                    "total_bytes": plan.total_bytes,
                    "components": [it.component.id for it in plan.download],
                }
            return result
        except Exception:
            pass

        # 2. Fallback: GitHub Releases API (e.g. v0.12.0 before manifest.json existed)
        try:
            req = urllib.request.Request(
                GITHUB_LATEST_RELEASE_API,
                headers={
                    "User-Agent": f"GW2-TR-Hub/{VERSION}",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            tag = str(data.get("tag_name") or "").strip()
            latest = tag.lstrip("vV") if tag else VERSION
            release_url = str(data.get("html_url") or GITHUB_RELEASES_URL)
            release_name = str(data.get("name") or tag or f"v{latest}")
            download_url = ""
            for asset in data.get("assets") or []:
                if isinstance(asset, dict) and str(asset.get("name", "")).lower() == "gw2_tr_hub.exe":
                    download_url = str(asset.get("browser_download_url") or "")
                    break
            update_available = _parse_semver(latest) > _parse_semver(VERSION)
            return {
                "ok": True,
                "current_version": VERSION,
                "latest_version": latest,
                "update_available": update_available,
                "manifest_available": False,
                "release_name": release_name,
                "release_url": release_url,
                "download_url": download_url,
            }
        except Exception as exc:
            base["error"] = str(exc)
            return base

    def install_from_manifest(self, manifest_url: str = manifest_mod.MANIFEST_URL, state_root: Path | None = None) -> dict:
        """Performs manifest-driven incremental install/update with SHA-256 verification and rollback."""
        if not self._game_dir:
            return {"ok": False, "logs": ["HATA: Guild Wars 2 klasörü seçilmedi!"]}
        blockers = process_guard.blocking_processes()
        if blockers:
            return {
                "ok": False,
                "blocking_processes": blockers,
                "logs": [f"HATA: Önce {', '.join(blockers)} kapatılmalı. Dosya kilitleri nedeniyle güncelleme iptal edildi."],
                "status": self.get_status(),
            }

        logs: list[str] = []
        cfg = self._read_tr_config()
        st = state_mod.InstallState(state_root)
        current_comp = "manifest"
        try:
            m = manifest_mod.fetch_manifest(manifest_url, timeout=10.0)
            plan = manifest_mod.plan_update(
                m,
                self._game_dir,
                local_state=st.load(),
                toggles={"font_injector": bool(cfg.get("font_injector", True))},
            )
            logs.append(
                f"Manifest v{m.version} doğrulandı: {len(plan.download)} bileşen indirilecek "
                f"({plan.total_bytes / (1024 * 1024):.1f} MB), {len(plan.skip)} bileşen güncel/atlandı."
            )

            staged: dict[str, Path] = {}
            for item in plan.download:
                current_comp = f"{item.component.id} ({item.file.path})"
                logs.append(f"İndiriliyor: {item.component.label} ({item.file.size / (1024 * 1024):.1f} MB)...")
                staged[item.file.sha256] = downloader_mod.download_verified(
                    item.url,
                    item.file.sha256,
                    item.file.size,
                    st.downloads_dir,
                    validate=item.file.validate,
                )

            current_comp = "apply_plan"
            apply_res = applier_mod.apply_plan(plan, staged, self._game_dir, st)
            logs.append(f"Bileşenler atomik olarak uygulandı ({apply_res['applied_count']} dosya güncellendi).")
        except (downloader_mod.DownloadError, applier_mod.ApplyError, ValueError) as exc:
            logs.append(f"HATA [{current_comp}]: {exc}")
            return {"ok": False, "failed_component": current_comp, "logs": logs, "status": self.get_status()}
        except Exception as exc:
            logs.append(f"BEKLENMEYEN HATA [{current_comp}]: {exc}")
            return {"ok": False, "failed_component": current_comp, "logs": logs, "status": self.get_status()}

        # Clean up legacy early-boot version.dll proxy if no longer part of manifest
        manifest_ids = {c.id for c in m.components}
        if "loader.version_proxy" not in manifest_ids:
            legacy_ver = self._game_dir / "version.dll"
            if legacy_ver.is_file():
                try:
                    legacy_ver.unlink(missing_ok=True)
                    logs.append("Eski version.dll proxy dosyası temizlendi (font enjektörü artık yalnızca Nexus üzerinden çalışır).")
                except OSError:
                    pass

        # Post-install configuration & preservation
        addons_dir = self._game_dir / "addons"
        tt_cfg_dir = addons_dir / "text_translator"
        mod_dir = tt_cfg_dir / "modules" / "local_translator_tr"
        tr_dir = mod_dir / "TR"
        tr_dir.mkdir(parents=True, exist_ok=True)
        _merge_settings_toml(tt_cfg_dir / "settings.toml", list("local_translator_tr".encode("utf-8")))
        self._write_tr_config(cfg)
        self._update_addon_config(NEXUS_SIG_TEXT_TRANSLATOR, "Text Translator", True)
        self._update_addon_config(NEXUS_SIG_TURKISH_FONT, "GW2 Turkish Font Injector", bool(cfg.get("font_injector", True)))
        kb = self._read_keybind()
        self.set_keybind(kb)
        sync_res = self.sync_cache_characters()
        if sync_res.get("changed"):
            logs.append(sync_res["message"])

        return {"ok": True, "version": m.version, "logs": logs, "status": self.get_status()}

    def launch_game(self) -> dict:
        if not self._game_dir or not (self._game_dir / "Gw2-64.exe").is_file():
            return {"ok": False, "message": "Gw2-64.exe bulunamadı! Lütfen önce GW2 klasörünü seçin."}
        try:
            subprocess.Popen([str(self._game_dir / "Gw2-64.exe")], cwd=str(self._game_dir))
            return {"ok": True, "message": "Guild Wars 2 başlatıldı (Gw2-64.exe)."}
        except Exception as exc:
            return {"ok": False, "message": f"Oyun başlatılamadı: {exc}"}

    def install_nexus(self) -> dict:
        if not self._game_dir:
            return {"ok": False, "message": "Lütfen önce Guild Wars 2 klasörünü seçin."}
        blockers = process_guard.blocking_processes()
        if blockers:
            return {
                "ok": False,
                "blocking_processes": blockers,
                "message": f"Önce {', '.join(blockers)} kapatılmalı. Dosya kilitleri nedeniyle Nexus kurulumu iptal edildi.",
                "status": self.get_status(),
            }
        dst = self._game_dir / "d3d11.dll"
        bundled = self._res_dir / "assets" / "d3d11.dll"
        try:
            if bundled.is_file():
                _safe_copy_with_backup(bundled, dst)
                return {"ok": True, "message": "Raidcore Nexus (d3d11.dll) yerel paketten başarıyla kuruldu.", "status": self.get_status()}
            req = urllib.request.Request("https://api.raidcore.gg/nexus_d3d11.dll", headers={"User-Agent": f"GW2-TR-Hub/{VERSION}"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = resp.read()
            if not _validate_pe_dll(payload):
                return {
                    "ok": False,
                    "message": "İndirilen d3d11.dll dosyası geçerli bir Windows DLL doğrulamasından geçemedi. Kurulum iptal edildi.",
                    "status": self.get_status(),
                }
            if dst.is_file():
                try:
                    shutil.copy2(dst, dst.with_name(dst.name + ".bak"))
                except OSError:
                    pass
            tmp = dst.with_suffix(".dll.tmp")
            tmp.write_bytes(payload)
            os.replace(tmp, dst)
            return {"ok": True, "message": "Raidcore Nexus (d3d11.dll) resmi sunucudan doğrulandı ve kuruldu.", "status": self.get_status()}
        except Exception as exc:
            return {"ok": False, "message": f"Nexus kurulamadı ({exc}). Lütfen raidcore.gg adresinden indirin.", "status": self.get_status()}

    def install_all(self) -> dict:
        if not self._game_dir:
            return {"ok": False, "logs": ["HATA: Guild Wars 2 klasörü seçilmedi!"]}
        blockers = process_guard.blocking_processes()
        if blockers:
            return {
                "ok": False,
                "blocking_processes": blockers,
                "logs": [f"HATA: Önce {', '.join(blockers)} kapatılmalı. Dosya kilitleri nedeniyle kurulum iptal edildi."],
                "status": self.get_status(),
            }

        # Lightweight single-umbrella Hub: if DLLs are not bundled locally, install via manifest
        has_local_assets = (self._res_dir / "assets" / "addons" / "text_translator.dll").is_file()
        if not has_local_assets:
            return self.install_from_manifest()

        logs: list[str] = []
        errors: list[str] = []
        cfg = self._read_tr_config()

        # 1. Raidcore Nexus (d3d11.dll)
        nexus_dst = self._game_dir / "d3d11.dll"
        nexus_src = self._res_dir / "assets" / "d3d11.dll"
        if not nexus_dst.is_file() and nexus_src.is_file():
            try:
                _safe_copy_with_backup(nexus_src, nexus_dst)
                logs.append("Raidcore Nexus (d3d11.dll) kuruldu.")
            except PermissionError as exc:
                msg = f"HATA: d3d11.dll kopyalanamadı (dosya kilitli: {exc})."
                errors.append(msg)
                logs.append(msg)
        elif nexus_dst.is_file():
            logs.append("Raidcore Nexus (d3d11.dll) doğrulandı.")

        # 2. Text Translator Addon (text_translator.dll)
        addons_dir = self._game_dir / "addons"
        addons_dir.mkdir(parents=True, exist_ok=True)
        tt_src = self._res_dir / "assets" / "addons" / "text_translator.dll"
        if tt_src.is_file():
            try:
                changed = _safe_copy_with_backup(tt_src, addons_dir / "text_translator.dll")
                logs.append(
                    "Text Translator eklentisi (text_translator.dll) kuruldu/güncellendi."
                    if changed
                    else "Text Translator eklentisi (text_translator.dll) zaten güncel."
                )
            except PermissionError as exc:
                msg = f"HATA: text_translator.dll güncellenemedi (dosya kilitli: {exc}). Oyunu kapatıp tekrar deneyin."
                errors.append(msg)
                logs.append(msg)

        # 3. Turkish Font Injector (turkish_font.dll + version.dll dual-guard)
        font_src = self._res_dir / "assets" / "addons" / "turkish_font.dll"
        if font_src.is_file():
            try:
                _safe_copy_with_backup(font_src, addons_dir / "turkish_font.dll")
            except PermissionError as exc:
                msg = f"HATA: turkish_font.dll güncellenemedi (dosya kilitli: {exc}). Oyunu kapatıp tekrar deneyin."
                errors.append(msg)
                logs.append(msg)
        disabled_marker = addons_dir / "turkish_font.disabled"
        if cfg.get("font_injector", True):
            disabled_marker.unlink(missing_ok=True)
            logs.append("GW2 Turkish Font Injector AÇIK (Tam Türkçe Glif Modu: Ş, Ğ, İ, ı).")
        else:
            disabled_marker.write_text("disabled\n", encoding="utf-8")
            logs.append("GW2 Turkish Font Injector KAPALI (6 Harf İngilizce Modu: S, G, I, i).")

        # 4. Module directory & settings.toml (safe merge, preserving existing user settings)
        tt_cfg_dir = addons_dir / "text_translator"
        mod_dir = tt_cfg_dir / "modules" / "local_translator_tr"
        tr_dir = mod_dir / "TR"
        tr_dir.mkdir(parents=True, exist_ok=True)

        folder_bytes = list("local_translator_tr".encode("utf-8"))
        _merge_settings_toml(tt_cfg_dir / "settings.toml", folder_bytes)

        # Copy Local_Translator_TR.exe if built, or configure module.toml
        exe_candidates = [
            self._res_dir / "dist" / "Local_Translator_TR.exe",
            self._res_dir / "assets" / "Local_Translator_TR.exe",
            ROOT_DIR / "dist" / "Local_Translator_TR.exe",
        ]
        exe_copied = False
        for cand in exe_candidates:
            if cand.is_file():
                try:
                    _safe_copy_with_backup(cand, mod_dir / "Local_Translator_TR.exe")
                    exe_copied = True
                except PermissionError as exc:
                    msg = f"HATA: Local_Translator_TR.exe güncellenemedi (dosya kilitli: {exc})."
                    errors.append(msg)
                    logs.append(msg)
                break

        # Also copy Python source files to mod_dir so both .exe and python fallback work
        for py_name in ("version.py", "lt_module.py", "lt_server.py", "patch_db.py", "editor.py", "map_upload.py", "glossary_tr.default.json"):
            src_py = self._res_dir / "src" / py_name
            if src_py.is_file():
                shutil.copy2(src_py, mod_dir / py_name)
        ver_file = self._res_dir / "VERSION"
        if ver_file.is_file():
            shutil.copy2(ver_file, mod_dir / "VERSION")

        if exe_copied or (mod_dir / "Local_Translator_TR.exe").is_file():
            module_toml = (
                'name = "Local Translator TR"\n'
                'command = "Local_Translator_TR.exe"\n'
                'args = ["--lang", "tr"]\n'
            )
        else:
            module_toml = (
                'name = "Local Translator TR"\n'
                f'command = "{sys.executable.replace(chr(92), chr(92)*2)}"\n'
                'args = ["lt_module.py", "--lang", "tr"]\n'
            )
        (mod_dir / "module.toml").write_text(module_toml, encoding="utf-8")
        logs.append(f"Local Translator TR v{VERSION} modülü ve module.toml yapılandırıldı.")

        # 5. Copy TR/model, glossary_tr.json (preserve user edits), config.json, contributor.json
        src_tr = self._res_dir / "TR"
        src_glossary = src_tr / "glossary_tr.json"
        dst_glossary = tr_dir / "glossary_tr.json"
        if src_glossary.is_file() and not dst_glossary.is_file():
            shutil.copy2(src_glossary, dst_glossary)
            logs.append("Türkçe oyun sözlüğü (glossary_tr.json) kuruldu.")
        elif dst_glossary.is_file():
            logs.append("Mevcut kullanıcı sözlüğü (glossary_tr.json) korundu.")
        model_candidates = [
            src_tr / "model",
            ROOT_DIR / "TR" / "model",
        ]
        model_src = next((c for c in model_candidates if c.is_dir()), None)
        if model_src:
            dst_model = tr_dir / "model"
            dst_model.mkdir(parents=True, exist_ok=True)
            for mf in model_src.iterdir():
                if mf.is_file():
                    shutil.copy2(mf, dst_model / mf.name)
            logs.append("Çevrimdışı OPUS-MT Türkçe dil modeli (TR/model) doğrulandı.")

        self._write_tr_config(cfg)
        author, sk = self._read_contributor()
        self._write_contributor(author, sk)

        # 6. Enable addons in Nexus AddonConfig.json & ensure ALT+T keybind in InputBinds.json
        self._update_addon_config(NEXUS_SIG_TEXT_TRANSLATOR, "Text Translator", True)
        self._update_addon_config(NEXUS_SIG_TURKISH_FONT, "GW2 Turkish Font Injector", bool(cfg.get("font_injector", True)))
        kb = self._read_keybind()
        self.set_keybind(kb)
        logs.append(f"Oyun içi çeviri kısayolu [{kb['label']}] olarak ayarlandı.")

        # 7. Synchronize cache.db with current Font Injector mode
        sync_res = self.sync_cache_characters()
        if sync_res.get("changed"):
            logs.append(sync_res["message"])

        return {"ok": len(errors) == 0, "errors": errors, "logs": logs, "status": self.get_status()}

    def uninstall_mod(self, remove_nexus: bool = False) -> dict:
        """Safely uninstalls Guild Wars 2 Turkish Localization mod files.
        Preserves other Nexus addons (e.g. ArcDPS) and d3d11.dll unless remove_nexus=True."""
        if not self._game_dir:
            return {"ok": False, "message": "Guild Wars 2 klasörü bulunamadı."}

        logs = []
        addons_dir = self._game_dir / "addons"

        # 1. Terminate any running Local_Translator_TR process
        try:
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/IM", "Local_Translator_TR.exe", "/T"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
            )
        except Exception:
            pass

        # 2. Remove local_translator_tr module directory
        tt_mod_dir = addons_dir / "text_translator" / "modules" / "local_translator_tr"
        if tt_mod_dir.is_dir():
            try:
                shutil.rmtree(tt_mod_dir, ignore_errors=True)
                logs.append("Local Translator TR modülü silindi.")
            except Exception as e:
                logs.append(f"Modül silinirken uyarı: {e}")

        # If text_translator has no other modules, clean up or remove empty folder
        tt_dir = addons_dir / "text_translator"
        if tt_dir.is_dir():
            modules_dir = tt_dir / "modules"
            if modules_dir.is_dir() and not any(modules_dir.iterdir()):
                try:
                    shutil.rmtree(tt_dir, ignore_errors=True)
                    logs.append("Text Translator yapılandırma dizini temizlendi.")
                except Exception:
                    pass

        # 3. Remove text_translator.dll
        tt_dll = addons_dir / "text_translator.dll"
        if tt_dll.is_file():
            try:
                tt_dll.unlink(missing_ok=True)
                logs.append("text_translator.dll kaldırıldı.")
            except Exception as e:
                logs.append(f"text_translator.dll silinirken uyarı: {e}")

        # 4. Remove turkish_font.dll and marker
        font_dll = addons_dir / "turkish_font.dll"
        if font_dll.is_file():
            try:
                font_dll.unlink(missing_ok=True)
                logs.append("turkish_font.dll kaldırıldı.")
            except Exception as e:
                logs.append(f"turkish_font.dll silinirken uyarı: {e}")
        (addons_dir / "turkish_font.disabled").unlink(missing_ok=True)

        # 5. Remove version.dll (proxy hook)
        version_dll = self._game_dir / "version.dll"
        if version_dll.is_file():
            try:
                version_dll.unlink(missing_ok=True)
                logs.append("version.dll kaldırıldı.")
            except Exception as e:
                logs.append(f"version.dll silinirken uyarı: {e}")

        # 6. Clean up Nexus AddonConfig.json entries for our mods
        cfg_path = addons_dir / "Nexus" / "AddonConfig.json"
        if cfg_path.is_file():
            try:
                raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                if isinstance(raw, list):
                    filtered = [
                        item for item in raw
                        if isinstance(item, dict) and item.get("Signature") not in (NEXUS_SIG_TEXT_TRANSLATOR, NEXUS_SIG_TURKISH_FONT)
                    ]
                    cfg_path.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
                    logs.append("Nexus eklenti kayıtları temizlendi.")
            except Exception:
                pass

        # 7. Optionally remove d3d11.dll if requested
        if remove_nexus:
            d3d11 = self._game_dir / "d3d11.dll"
            if d3d11.is_file():
                try:
                    d3d11.unlink(missing_ok=True)
                    logs.append("Raidcore Nexus (d3d11.dll) kaldırıldı.")
                except Exception as e:
                    logs.append(f"d3d11.dll silinirken uyarı: {e}")

        return {
            "ok": True,
            "message": "Guild Wars 2 Türkçe yama bileşenleri başarıyla kaldırıldı.",
            "logs": logs,
            "status": self.get_status()
        }

    def toggle_mod(self, mod_id: str, enabled: bool) -> dict:
        if not self._game_dir:
            return {"ok": False, "message": "Önce GW2 klasörünü seçin."}
        if mod_id == "nexus":
            if enabled:
                return self.install_nexus()
            return {"ok": True, "message": "Raidcore Nexus ana çerçevedir.", "status": self.get_status()}
        elif mod_id == "text_translator":
            self._update_addon_config(NEXUS_SIG_TEXT_TRANSLATOR, "Text Translator", enabled)
            return {
                "ok": True,
                "message": f"Text Translator eklentisi {'etkinleştirildi' if enabled else 'devre dışı bırakıldı'}.",
                "status": self.get_status(),
            }
        elif mod_id == "local_translator":
            if enabled:
                self.install_all()
            return {
                "ok": True,
                "message": f"GW2 Local Translator TR {'aktif' if enabled else 'devre dışı'}.",
                "status": self.get_status(),
            }
        return {"ok": True, "message": "Güncellendi", "status": self.get_status()}

    def set_font_injector(self, enabled: bool) -> dict:
        """Toggles Turkish Font Injector ON/OFF and immediately converts/restores the 6 Range-2
        characters (ş, Ş, ğ, Ğ, İ, ı) in cache.db while keeping ç, Ç, ö, Ö, ü, Ü intact."""
        enabled = bool(enabled)
        target_char_mode = "off" if enabled else "ascii_6"
        if self._game_dir:
            addons_dir = self._game_dir / "addons"
            addons_dir.mkdir(parents=True, exist_ok=True)
            disabled_marker = addons_dir / "turkish_font.disabled"
            if enabled:
                disabled_marker.unlink(missing_ok=True)
            else:
                disabled_marker.write_text("disabled\n", encoding="utf-8")
            self._update_addon_config(NEXUS_SIG_TURKISH_FONT, "GW2 Turkish Font Injector", enabled)
        self._write_tr_config({"font_injector": enabled, "char_mode": target_char_mode})

        sync_info = self.sync_cache_characters()
        changed = sync_info.get("changed", 0)
        if enabled:
            msg = f"Turkish Font Injector AÇILDI: Tam Türkçe karakter desteği aktif ({changed} önbellek metni güncellendi)."
        else:
            msg = f"Turkish Font Injector KAPATILDI: Kutucuk çıkaran 6 harf (ş→s, ğ→g, İ→I, ı→i) dönüştürüldü ({changed} metin güncellendi; ç, ö, ü korundu)."
        return {"ok": True, "message": msg, "status": self.get_status()}

    def sync_cache_characters(self) -> dict:
        """Synchronizes existing translations in cache.db with current char_mode and show_keys."""
        mod_dir = self._module_dir()
        if not mod_dir:
            return {"ok": False, "changed": 0, "message": "Modül dizini bulunamadı."}
        cache_db = mod_dir / "cache.db"
        if not cache_db.is_file():
            return {"ok": True, "changed": 0, "message": "cache.db henüz oluşmamış (ilk oyun açılışında oluşturulur)."}
        cfg = self._read_tr_config()
        _, sk = self._read_contributor()
        sk_mode = sk if sk in ("text", "all") else None
        map_db = mod_dir / "TR" / "map_tr.db"
        try:
            changed = sync_key_tags(cache_db, "tr", sk_mode, cfg.get("char_mode", "off"), map_db=map_db)
            return {
                "ok": True,
                "changed": changed,
                "message": f"cache.db senkronize edildi: {changed} metin '{cfg.get('char_mode')}' moduna dönüştürüldü.",
            }
        except Exception as exc:
            return {"ok": False, "changed": 0, "message": f"cache.db güncellenemedi: {exc}"}

    def set_keep_items_english(self, enabled: bool) -> dict:
        self._write_tr_config({"keep_items_english": bool(enabled)})
        msg = (
            "Eşya ve mekan isimleri orijinal İngilizce dilinde korunacak."
            if enabled
            else "Eşya ve mekan isimleri de Türkçeye çevrilecek."
        )
        return {"ok": True, "message": msg, "status": self.get_status()}

    def set_backend(self, backend: str) -> dict:
        self._write_tr_config({"backend": backend})
        return {
            "ok": True,
            "message": f"Çeviri motoru '{backend.upper()}' olarak ayarlandı.",
            "status": self.get_status(),
        }

    def save_settings(self, payload: dict) -> dict:
        font_on = bool(payload.get("font_injector", True))
        updates = {
            "font_injector": font_on,
            "char_mode": "off" if font_on else "ascii_6",
            "keep_items_english": bool(payload.get("keep_items_english", True)),
            "backend": str(payload.get("backend", "offline")),
            "threads": int(payload.get("threads") or 2),
            "model_name": str(payload.get("model_name", "")),
        }
        submitted_key = str(payload.get("api_key", "")).strip()
        if payload.get("clear_api_key"):
            updates["api_key"] = ""
        elif submitted_key and "••••" not in submitted_key:
            updates["api_key"] = submitted_key
        self._write_tr_config(updates)
        self._write_contributor(
            str(payload.get("author", "Oyuncu")),
            str(payload.get("show_keys", "off")),
        )
        self.set_font_injector(font_on)
        return {"ok": True, "message": "Tüm yapılandırma ayarları kaydedildi ve uygulandı.", "status": self.get_status()}

    def set_keybind(self, kb: dict) -> dict:
        """Writes TEXTTRANSLATOR_TOGGLE_SHOW_TRANSLATED keybind into addons/Nexus/InputBinds.json."""
        if not self._game_dir:
            return {"ok": False, "message": "Önce GW2 klasörünü seçin."}
        binds_path = self._game_dir / "addons" / "Nexus" / "InputBinds.json"
        binds_path.parent.mkdir(parents=True, exist_ok=True)
        items = []
        if binds_path.is_file():
            try:
                raw = json.loads(binds_path.read_text(encoding="utf-8-sig"))
                if isinstance(raw, list):
                    items = raw
            except Exception:
                items = []

        scancode = int(kb.get("scancode") or 20)
        alt = bool(kb.get("alt", True))
        ctrl = bool(kb.get("ctrl", False))
        shift = bool(kb.get("shift", False))

        new_entry = {
            "Alt": alt,
            "Code": scancode,
            "Ctrl": ctrl,
            "Identifier": KEYBIND_ID,
            "Passthrough": False,
            "Shift": shift,
            "Type": 1,
        }
        replaced = False
        for i, item in enumerate(items):
            if isinstance(item, dict) and item.get("Identifier") == KEYBIND_ID:
                items[i] = new_entry
                replaced = True
                break
        if not replaced:
            items.append(new_entry)

        binds_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        updated_kb = self._read_keybind()
        return {
            "ok": True,
            "message": f"Oyun içi çeviri aç/kapa kısayolu [{updated_kb['label']}] olarak kaydedildi (InputBinds.json).",
            "status": self.get_status(),
        }

    # ------------------------------------------------------------------ #
    # Live & Offline Translation Editor API
    # ------------------------------------------------------------------ #
    def _local_editor(self) -> tuple[editor_mod.Editor | None, lt.KeyMap | None]:
        mod_dir = self._module_dir()
        if not mod_dir:
            return None, None
        tr_dir = mod_dir / "TR"
        tr_dir.mkdir(parents=True, exist_ok=True)
        cfg = self._read_tr_config()
        author, sk = self._read_contributor()
        patch = CachePatch(tr_dir / "patch_tr.db", "tr", 1)
        patch.char_mode = cfg.get("char_mode", "off")
        patch.show_keys = sk if sk in ("text", "all") else None
        keymap = lt.KeyMap(tr_dir / "map_tr.db")
        patch.map_path = keymap.path
        patch.suggestion_of = keymap.suggestion
        ed = editor_mod.Editor(patch, keymap, mod_dir / "cache.db", "tr", author)
        return ed, keymap

    def editor_search(self, query: str, exact: bool = False) -> dict:
        # Try live HTTP server on 127.0.0.1:8770 first (when game is running)
        try:
            url = f"http://127.0.0.1:{editor_mod.EDITOR_PORT}/api/search?q={urllib.parse.quote(query)}&exact={'1' if exact else '0'}"
            req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{editor_mod.EDITOR_PORT}"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "live": True, "rows": rows}
        except Exception:
            pass

        ed, km = self._local_editor()
        if not ed:
            return {"ok": False, "live": False, "rows": []}
        try:
            rows = ed.search(query, bool(exact))
            return {"ok": True, "live": False, "rows": rows}
        finally:
            ed.patch.close()
            if km:
                km.close()

    def editor_save(self, key: int, text: str) -> dict:
        # Try live HTTP server first
        try:
            url = f"http://127.0.0.1:{editor_mod.EDITOR_PORT}/api/save"
            body = json.dumps({"key": int(key), "text": text}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Host": f"127.0.0.1:{editor_mod.EDITOR_PORT}",
                    "Origin": f"http://127.0.0.1:{editor_mod.EDITOR_PORT}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                row = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "live": True, "row": row}
        except Exception:
            pass

        ed, km = self._local_editor()
        if not ed:
            return {"ok": False, "error": "GW2 klasörü bulunamadı."}
        try:
            row = ed.save(int(key), str(text))
            return {"ok": True, "live": False, "row": row}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            ed.patch.close()
            if km:
                km.close()

    def editor_undo(self, key: int) -> dict:
        try:
            url = f"http://127.0.0.1:{editor_mod.EDITOR_PORT}/api/undo"
            body = json.dumps({"key": int(key)}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={
                    "Host": f"127.0.0.1:{editor_mod.EDITOR_PORT}",
                    "Origin": f"http://127.0.0.1:{editor_mod.EDITOR_PORT}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                row = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "live": True, "row": row}
        except Exception:
            pass

        ed, km = self._local_editor()
        if not ed:
            return {"ok": False, "error": "GW2 klasörü bulunamadı."}
        try:
            row = ed.undo(int(key))
            return {"ok": True, "live": False, "row": row}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            ed.patch.close()
            if km:
                km.close()

    def editor_recent(self) -> dict:
        try:
            url = f"http://127.0.0.1:{editor_mod.EDITOR_PORT}/api/recent"
            req = urllib.request.Request(url, headers={"Host": f"127.0.0.1:{editor_mod.EDITOR_PORT}"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
                return {"ok": True, "live": True, "rows": rows}
        except Exception:
            pass

        ed, km = self._local_editor()
        if not ed:
            return {"ok": True, "live": False, "rows": []}
        try:
            return {"ok": True, "live": False, "rows": ed.recent()}
        finally:
            ed.patch.close()
            if km:
                km.close()


def main() -> None:
    import webview
    api = HubAPI()
    ui_path = resource_root() / "hub" / "ui" / "index.html"
    window = webview.create_window(
        title=f"GW2 TR — Mod Installation Hub (v{VERSION})",
        url=ui_path.as_uri(),
        js_api=api,
        width=1120,
        height=760,
        min_size=(900, 620),
    )
    api._window = window
    webview.start(debug=False)


if __name__ == "__main__":
    main()
