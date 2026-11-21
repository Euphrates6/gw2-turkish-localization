"""Builds a validated release manifest.json + manifest.json.sha256 from release assets."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "hub"))

from version import VERSION  # noqa: E402
import manifest as manifest_mod  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def inspect_zip_members(zip_path: Path) -> list[dict]:
    members: list[dict] = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            raw = zf.read(info.filename)
            members.append({
                "name": info.filename.replace("\\", "/"),
                "sha256": sha256_bytes(raw),
                "size": len(raw),
            })
    return members


def build_manifest(assets_dir: Path, version: str = VERSION, repo: str = manifest_mod.GITHUB_REPO) -> dict:
    tag = f"v{version.lstrip('vV')}"
    components: dict[str, dict] = {}

    specs = [
        ("nexus", "Raidcore Nexus", "game", 5, True, "", True, "d3d11.dll", "d3d11.dll", "pe", ""),
        ("translator.exe", "Çeviri Motoru", "mod", 10, True, "", False, "Local_Translator_TR.exe", "Local_Translator_TR.exe", "pe", ""),
        ("model.opus_mt_tr", "Çevrimdışı OPUS-MT Modeli", "mod", 20, True, "", False, "TR/model", "opus-mt-en-tr-ct2.zip", "", "zip"),
        ("addon.text_translator", "Text Translator Eklentisi", "game", 30, True, "", False, "addons/text_translator.dll", "text_translator.dll", "pe", ""),
        ("addon.font_injector", "Türkçe Font Enjektörü", "game", 31, False, "font_injector", False, "addons/turkish_font.dll", "turkish_font.dll", "pe", ""),
    ]

    for cid, label, target, order, req, toggle, if_missing, rel_path, asset_name, validate, archive in specs:
        asset_path = assets_dir / asset_name
        if not asset_path.is_file():
            continue
        fentry: dict = {
            "path": rel_path,
            "asset": asset_name,
            "sha256": sha256_file(asset_path),
            "size": asset_path.stat().st_size,
        }
        if validate:
            fentry["validate"] = validate
        if archive == "zip":
            fentry["archive"] = "zip"
            fentry["members"] = inspect_zip_members(asset_path)

        comp: dict = {
            "label": label,
            "target": target,
            "order": order,
            "required": req,
            "files": [fentry],
        }
        if toggle:
            comp["toggle"] = toggle
        if if_missing:
            comp["if_missing"] = True
        components[cid] = comp

    data = {
        "schema_version": manifest_mod.SCHEMA_VERSION,
        "version": version.lstrip("vV"),
        "channel": "stable",
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes_url": f"https://github.com/{repo}/releases/tag/{tag}",
        "base_url": f"https://github.com/{repo}/releases/download/{tag}/",
        "install": {
            "game_required": True,
            "block_if_running": ["Gw2-64.exe", "Gw2.exe", "Local_Translator_TR.exe"],
            "targets": {
                "game": "{game_dir}",
                "cfg": "{game_dir}/addons/text_translator",
                "mod": "{game_dir}/addons/text_translator/modules/local_translator_tr",
            },
        },
        "preserve": [
            "{mod}/TR/config.json",
            "{mod}/TR/contributor.json",
            "{mod}/TR/glossary_tr.json",
            "{mod}/TR/map_tr.db",
            "{mod}/cache.db",
            "{cfg}/settings.toml",
            "{game}/addons/Nexus/AddonConfig.json",
            "{game}/addons/Nexus/InputBinds.json",
        ],
        "components": components,
    }
    manifest_mod.validate_schema(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate release manifest.json and manifest.json.sha256")
    parser.add_argument("--assets-dir", type=Path, required=True, help="Directory containing release asset files")
    parser.add_argument("--out", type=Path, default=None, help="Output manifest.json path (default: <assets-dir>/manifest.json)")
    parser.add_argument("--version", type=str, default=VERSION, help="Release version (default: VERSION file)")
    args = parser.parse_args()

    out_path = args.out or (args.assets_dir / "manifest.json")
    data = build_manifest(args.assets_dir, version=args.version)
    encoded = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    out_path.write_bytes(encoded)
    sha = sha256_bytes(encoded)
    out_path.with_name(out_path.name + ".sha256").write_text(f"{sha}  {out_path.name}\n", encoding="utf-8")
    print(f"[+] Wrote {out_path} ({len(data['components'])} components, sha256={sha[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
