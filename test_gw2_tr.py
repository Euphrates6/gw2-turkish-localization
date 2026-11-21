"""Comprehensive verification suite for GW2-TR (v0.12.0 Turkish-Only Hub & Engine)."""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "hub"))

import lt_server as lt  # noqa: E402
from patch_db import CachePatch, sync_key_tags  # noqa: E402
import editor  # noqa: E402
import app as hub_app  # noqa: E402


def test_turkish_only_and_case() -> None:
    assert list(lt.LANGUAGES.keys()) == ["tr"], f"Expected only 'tr', got {list(lt.LANGUAGES.keys())}"
    assert lt.tr_lower("İKSİR IŞIK") == "iksir ışık"
    assert "\u0307" not in lt.tr_lower("İ")
    assert lt.tr_upper("iksir ışık") == "İKSİR IŞIK"
    print("[PASS] 1. Turkish-only language & Turkish case conversion (no U+0307 box bug)")


def test_font_injector_6_char_fallback() -> None:
    sample = "Şifalı Ğırtlak İksiri ve Çöl Örümceği Üzümü"
    off_out = lt.fix_turkish_chars(sample, "off")
    smart_out = lt.fix_turkish_chars(sample, "smart")
    ascii6_out = lt.fix_turkish_chars(sample, "ascii_6")
    full_out = lt.fix_turkish_chars(sample, "full")
    assert off_out == sample
    assert smart_out == "Sifalı Gırtlak Iksiri ve Çöl Örümcegi Üzümü", f"Got: {smart_out}"
    assert ascii6_out == "Sifali Girtlak Iksiri ve Çöl Örümcegi Üzümü", f"Got: {ascii6_out}"
    assert full_out == "Sifali Girtlak Iksiri ve Col Orumcegi Uzumu", f"Got: {full_out}"
    print("[PASS] 2. Turkish char modes: off, smart (native GW2 font), ascii_6, full ASCII")


def test_item_and_location_protection() -> None:
    g = lt.Glossary()
    g.load_file(ROOT / "TR" / "glossary_tr.json")

    # 1. Exact UI terms should still translate to Turkish
    assert g.lookup("Inventory", keep_items=True) == g.exact.get("Inventory")

    # 2. Item & location names should stay in English when keep_items=True
    items_and_locations = [
        "Berserker's Pearl Greatsword",
        "Superior Sigil of Force",
        "Pile[s] of Bloodstone Dust",
        "Queensdale",
        "Divinity's Reach",
        "Shaemoor Waypoint",
        "Lion's Arch",
    ]
    for name in items_and_locations:
        res = g.lookup(name, keep_items=True)
        assert res == name, f"Expected item/location {name!r} to stay in English, got {res!r}"

    # 3. Sentences / descriptions should require translation (lookup returns None so Engine translates them)
    sentences = [
        "Speak with the scout to learn more about this area.",
        "Gain might when you critically hit an enemy.",
        "Double-click to consume.",
    ]
    for s in sentences:
        assert not lt.is_item_or_location_name(s), f"Sentence {s!r} wrongly detected as item/location"
    print("[PASS] 3. Item & Location Name Protection (3-layer filter keeps items/maps in English, translates sentences & UI)")


def test_cache_db_sync_and_editor() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        cache_db = tmp_path / "cache.db"
        map_db = tmp_path / "map_tr.db"
        patch_db = tmp_path / "patch_tr.db"

        con = sqlite3.connect(str(cache_db))
        con.execute(
            "CREATE TABLE translations (id INTEGER, cache_key TEXT, src_hash INTEGER, "
            "version INTEGER, timestamp INTEGER, text TEXT, PRIMARY KEY (id, cache_key))"
        )
        con.execute(
            "INSERT INTO translations VALUES (101, 'tr', 12345, 1, 1000, 'Şifalı Çöl İksiri')"
        )
        con.commit()
        con.close()

        km = lt.KeyMap(map_db)
        km.save([(101, "Healing Desert Potion", "Şifalı Çöl İksiri", "live")])

        # Switch Font Injector OFF -> ascii_6
        changed_off = sync_key_tags(cache_db, "tr", None, "ascii_6", map_db=map_db)
        assert changed_off == 1
        con = sqlite3.connect(str(cache_db))
        txt_off = con.execute("SELECT text FROM translations WHERE id = 101").fetchone()[0]
        con.close()
        assert txt_off == "Sifali Çöl Iksiri", f"Got {txt_off!r}"

        # Switch Font Injector back ON -> off (restored authentic Turkish from map_tr.db!)
        changed_on = sync_key_tags(cache_db, "tr", None, "off", map_db=map_db)
        assert changed_on == 1
        con = sqlite3.connect(str(cache_db))
        txt_on = con.execute("SELECT text FROM translations WHERE id = 101").fetchone()[0]
        con.close()
        assert txt_on == "Şifalı Çöl İksiri", f"Got {txt_on!r}"

        # Test Live/Offline Editor search, save, and undo
        patch = CachePatch(patch_db, "tr", 1)
        patch.map_path = map_db
        patch.suggestion_of = km.suggestion
        ed = editor.Editor(patch, km, cache_db, "tr", "Firat")

        found = ed.search("Şifalı")
        assert len(found) == 1 and found[0]["key"] == 101

        saved_row = ed.save(101, "Kutsal Çöl İksiri (Özel)")
        assert saved_row["suggestion"]["text"] == "Kutsal Çöl İksiri (Özel)"
        assert saved_row["undo"] == 1

        con = sqlite3.connect(str(cache_db))
        txt_edited = con.execute("SELECT text FROM translations WHERE id = 101").fetchone()[0]
        con.close()
        assert txt_edited == "Kutsal Çöl İksiri (Özel)"

        undone_row = ed.undo(101)
        assert undone_row["undo"] == 0
        patch.close()
        km.close()
        print("[PASS] 4. Cache.db Font Injector char_mode sync & Translation Editor (search/save/undo)")


def test_hub_keybind_and_config() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        gw2_dir = Path(tmp)
        (gw2_dir / "Gw2-64.exe").write_bytes(b"MZ")
        api = hub_app.HubAPI()
        api._game_dir = gw2_dir

        res = api.set_keybind({"alt": True, "ctrl": False, "shift": False, "key": "T", "scancode": 20})
        assert res["ok"]
        binds = json.loads((gw2_dir / "addons" / "Nexus" / "InputBinds.json").read_text(encoding="utf-8"))
        assert binds[0]["Identifier"] == "TEXTTRANSLATOR_TOGGLE_SHOW_TRANSLATED"
        assert binds[0]["Alt"] is True and binds[0]["Code"] == 20
        assert res["status"]["keybind"]["label"] == "ALT + T"
        print("[PASS] 5. Hub API Nexus InputBinds.json (ALT + T) & AddonConfig integration")


def test_stats_boons_and_conditions_protection() -> None:
    # 1. Standalone stat lines, boons, conditions, and stat-sets
    stat_samples = [
        "+120 Power",
        "+%num1% Condition Damage",
        "+5% Critical Chance",
        "Power",
        "Toughness",
        "+10 Agony Resistance",
        "Might",
        "Might (5 stacks)",
        "Quickness",
        "Berserker's",
        "Viper's",
        "Celestial",
        "+150 Healing Power",
        "Armor: 1050",
        "+%num1% Boon Duration",
    ]
    for sample in stat_samples:
        assert lt.is_stat_or_mechanic_line(sample), f"Expected {sample!r} to be recognized as stat/mechanic line"

    # Sentences are NOT standalone lines (they get protected at the word/term level)
    assert not lt.is_stat_or_mechanic_line("Increases Power by 100.")
    assert not lt.is_stat_or_mechanic_line("Grants Might and Fury to nearby allies.")

    # 2. End-to-end Translator test with stats, boons, conditions
    g = lt.Glossary()
    g.load_file(ROOT / "TR" / "glossary_tr.json")

    class DummyTranslator:
        def translate(self, texts: list[str]) -> list[str]:
            return [f"[TR] {t}" for t in texts]

    t = lt.Engine(DummyTranslator(), g, keep_items_english=True)

    lines = [
        "+120 Power",
        "+%num1% Condition Damage",
        "Might",
        "Berserker's",
        "Grants Might and Fury to nearby allies.",
        "Increases Power by 100.",
    ]
    res = t._translate_lines(lines)

    # Standalone stat lines remain 100% original English
    assert res["+120 Power"] == "+120 Power"
    assert res["+%num1% Condition Damage"] == "+%num1% Condition Damage"
    assert res["Might"] == "Might"
    assert res["Berserker's"] == "Berserker's"

    # In sentences, Might, Fury, Power are preserved via _protect masking
    assert "Might" in res["Grants Might and Fury to nearby allies."]
    assert "Fury" in res["Grants Might and Fury to nearby allies."]
    assert "Power" in res["Increases Power by 100."]

    print("[PASS] 6. GW2 Stats, Boons, Conditions & Stat-Set Name Protection (Standalone & Sentences)")


def test_hub_font_injector_api_key_and_gemini() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gw2_dir = tmp_path / "gw2"
        res_dir = tmp_path / "res"
        (gw2_dir / "addons").mkdir(parents=True)
        (gw2_dir / "Gw2-64.exe").write_bytes(b"MZ")
        (res_dir / "TR").mkdir(parents=True)

        # Dynamic glossary_count test
        (res_dir / "TR" / "glossary_tr.json").write_text(
            json.dumps({"exact": {"Play": "Oyna", "Quit": "Çık"}, "terms": {"Hero": "Kahraman"}}, ensure_ascii=False),
            encoding="utf-8",
        )

        api = hub_app.HubAPI()
        api._game_dir = gw2_dir
        api._res_dir = res_dir

        # 1. Dynamic glossary_count
        st0 = api.get_status()
        assert st0["glossary_count"] == 3, f"Expected dynamic glossary_count=3, got {st0['glossary_count']}"

        # 2. Font Injector ON -> char_mode must be 'off' (full Turkish glyphs)
        res_on = api.set_font_injector(True)
        assert res_on["ok"]
        cfg_on = api._read_tr_config()
        assert cfg_on["font_injector"] is True
        assert cfg_on["char_mode"] == "off", f"Expected char_mode='off', got {cfg_on['char_mode']!r}"

        # 3. Font Injector OFF -> char_mode must be 'ascii_6'
        res_off = api.set_font_injector(False)
        assert res_off["ok"]
        cfg_off = api._read_tr_config()
        assert cfg_off["font_injector"] is False
        assert cfg_off["char_mode"] == "ascii_6", f"Expected char_mode='ascii_6', got {cfg_off['char_mode']!r}"

        # 4. Toggle back ON -> char_mode must return to 'off'
        api.set_font_injector(True)
        assert api._read_tr_config()["char_mode"] == "off"

        # 5. API key masking & preservation across save_settings
        api.save_settings({
            "font_injector": True,
            "keep_items_english": True,
            "backend": "gemini",
            "threads": 2,
            "api_key": "AIzaSySecretKey1234567890",
            "model_name": "gemini-2.5-flash",
            "author": "Tester",
            "show_keys": "off",
        })
        st_key = api.get_status()
        assert st_key["api_key"] == "", "Raw API key must not be exposed in get_status()"
        assert st_key["api_key_set"] is True
        assert "SecretKey" not in st_key["api_key_masked"]
        assert st_key["char_mode"] == "off"

        # Re-saving settings with blank api_key preserves existing key
        api.save_settings({
            "font_injector": True,
            "keep_items_english": False,
            "backend": "gemini",
            "threads": 4,
            "api_key": "",
            "model_name": "gemini-2.5-flash",
            "author": "Tester",
            "show_keys": "off",
        })
        assert api._read_tr_config()["api_key"] == "AIzaSySecretKey1234567890"

        # 6. GeminiTranslator: API key not in URL + model parameter respected
        gem = lt.GeminiTranslator("AIzaSySecretKey1234567890", "gemini-2.5-flash")
        assert "AIzaSySecretKey1234567890" not in gem.endpoint, "API key must not be in URL query string"
        assert "gemini-2.5-flash:generateContent" in gem.endpoint
        assert gem.target_lang == "Turkish"

        print("[PASS] 7. Hub Font Injector char_mode ('off'/'ascii_6'), dynamic glossary_count, masked API key & Gemini header")


def test_safe_install_and_version_consistency() -> None:
    import lt_module  # noqa: E402
    from version import VERSION  # noqa: E402

    # 1. Single VERSION source consistency
    file_ver = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert VERSION == file_ver
    assert lt_module.VERSION == VERSION
    assert hub_app.VERSION == VERSION
    assert f"v{VERSION}/" in lt.LANG.model

    # 2. PE DLL validation rejects HTML/garbage and accepts valid PE header
    assert not hub_app._validate_pe_dll(b"<html>404 Not Found</html>")
    assert not hub_app._validate_pe_dll(b"MZ" + b"\x00" * 100)  # too small
    valid_pe = bytearray(70_000)
    valid_pe[0:2] = b"MZ"
    valid_pe[0x3C:0x40] = (0x80).to_bytes(4, "little")
    valid_pe[0x80:0x84] = b"PE\x00\x00"
    assert hub_app._validate_pe_dll(bytes(valid_pe))

    # 3. settings.toml merge preserves existing user settings and creates .bak
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.toml"
        settings_path.write_text(
            'active_module = { Windows = [1, 2, 3] }\n'
            'show_translated = false\n'
            'pause_refreshes = true\n'
            'custom_flag = 42\n',
            encoding="utf-8",
        )
        folder_bytes = list("local_translator_tr".encode("utf-8"))
        hub_app._merge_settings_toml(settings_path, folder_bytes)
        merged = settings_path.read_text(encoding="utf-8")
        assert f"active_module = {{ Windows = {folder_bytes} }}" in merged
        assert "show_translated = false" in merged
        assert "pause_refreshes = true" in merged
        assert "custom_flag = 42" in merged
        assert settings_path.with_name("settings.toml.bak").is_file()

    print("[PASS] 8. Single VERSION source, PE DLL validation, and safe settings.toml merge + backup")


def test_atlas_blob_integrity() -> None:
    import struct

    blob_path = ROOT / "font-injector" / "turkish_atlases.bin"
    if not blob_path.is_file():
        print("[SKIP] 9. Atlas blob integrity check (turkish_atlases.bin not present locally)")
        return
    data = blob_path.read_bytes()
    assert len(data) > 4
    (count,) = struct.unpack_from("<I", data, 0)
    assert count == 156, f"Expected 156 atlas entries, got {count}"
    offset = 4
    seen_ids: set[int] = set()
    for _ in range(count):
        assert offset + 8 <= len(data)
        file_id, length = struct.unpack_from("<II", data, offset)
        offset += 8
        assert length > 0 and offset + length <= len(data)
        seen_ids.add(file_id)
        offset += length
    assert offset == len(data), f"Trailing bytes in atlas blob: {len(data) - offset}"
    assert len(seen_ids) == 53, f"Expected 53 unique atlas fileIds, got {len(seen_ids)}"
    print(f"[PASS] 9. Atlas blob integrity ({count} entries / {len(seen_ids)} unique fileIds, {len(data):,} bytes consumed cleanly)")


def test_hub_update_checker() -> None:
    from unittest.mock import patch as mock_patch

    assert hub_app._parse_semver("v0.13.0") > hub_app._parse_semver("0.12.0")
    assert hub_app._parse_semver("v0.12.0-TR") == hub_app._parse_semver("0.12.0")
    assert hub_app._parse_semver("1.0.0") > hub_app._parse_semver("0.99.9")

    class _FakeResp:
        def __init__(self, payload: dict) -> None:
            self._raw = json.dumps(payload).encode("utf-8")

        def read(self) -> bytes:
            return self._raw

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    api = hub_app.HubAPI()

    # 1. Newer release available (mock manifest 404 -> fallback to GitHub Releases API)
    newer_payload = {
        "tag_name": "v9.9.9",
        "name": "GW2-TR v9.9.9",
        "html_url": "https://github.com/Euphrates6/gw2-turkish-localization/releases/tag/v9.9.9",
        "assets": [
            {"name": "GW2_TR_Hub.exe", "browser_download_url": "https://example.com/GW2_TR_Hub.exe"},
        ],
    }
    with mock_patch.object(hub_app.manifest_mod, "fetch_manifest", side_effect=OSError("404")):
        with mock_patch("urllib.request.urlopen", return_value=_FakeResp(newer_payload)):
            res = api.check_for_updates()
            assert res["ok"] is True
            assert res["update_available"] is True
            assert res["latest_version"] == "9.9.9"
            assert res["download_url"] == "https://example.com/GW2_TR_Hub.exe"

        # 2. Same version -> no update
        same_payload = {"tag_name": f"v{hub_app.VERSION}", "html_url": "https://example.com/rel", "assets": []}
        with mock_patch("urllib.request.urlopen", return_value=_FakeResp(same_payload)):
            res_same = api.check_for_updates()
            assert res_same["ok"] is True
            assert res_same["update_available"] is False

        # 3. Network failure -> graceful fallback
        with mock_patch("urllib.request.urlopen", side_effect=OSError("offline")):
            res_err = api.check_for_updates()
            assert res_err["ok"] is False
            assert res_err["update_available"] is False

    print("[PASS] 10. Hub GitHub Releases update checker (newer, up-to-date, offline fallback)")


def test_process_guard_glossary_preserve_and_perm_error() -> None:
    from unittest.mock import patch as mock_patch
    import process_guard  # noqa: E402

    # 11. Process guard blocks when GW2 or Local_Translator_TR is running, allows unrelated processes
    assert process_guard.blocking_processes({"notepad.exe", "explorer.exe"}) == []
    assert process_guard.blocking_processes({"Gw2-64.exe", "chrome.exe"}) == ["gw2-64.exe"]
    assert process_guard.blocking_processes({"Local_Translator_TR.exe", "GW2.EXE"}) == [
        "gw2.exe",
        "local_translator_tr.exe",
    ]

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        gw2_dir = tmp_path / "gw2"
        res_dir = tmp_path / "res"
        (gw2_dir / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR").mkdir(parents=True)
        (gw2_dir / "Gw2-64.exe").write_bytes(b"MZ")
        (res_dir / "TR").mkdir(parents=True)
        (res_dir / "assets" / "addons").mkdir(parents=True)
        (res_dir / "TR" / "glossary_tr.json").write_text('{"exact": {"Default": "Varsayilan"}, "terms": {}}', encoding="utf-8")
        (res_dir / "assets" / "addons" / "text_translator.dll").write_bytes(b"NEW_DLL_CONTENT")

        api = hub_app.HubAPI()
        api._game_dir = gw2_dir
        api._res_dir = res_dir

        # Blocked when Gw2-64.exe is running
        with mock_patch.object(process_guard, "running_process_names", return_value={"gw2-64.exe"}):
            res_blocked = api.install_all()
            assert res_blocked["ok"] is False
            assert "gw2-64.exe" in res_blocked["blocking_processes"]
            res_nx_blocked = api.install_nexus()
            assert res_nx_blocked["ok"] is False
            assert "gw2-64.exe" in res_nx_blocked["blocking_processes"]

        # 12. User's existing glossary_tr.json is preserved across install_all
        user_glossary = gw2_dir / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR" / "glossary_tr.json"
        custom_content = '{"exact": {"Custom": "Ozel"}, "terms": {}}'
        user_glossary.write_text(custom_content, encoding="utf-8")

        with mock_patch.object(process_guard, "running_process_names", return_value={"explorer.exe"}):
            res_ok = api.install_all()
            assert res_ok["ok"] is True
            assert user_glossary.read_text(encoding="utf-8") == custom_content

        # 13. PermissionError on locked DLL must fail install_all (ok == False)
        with mock_patch.object(process_guard, "running_process_names", return_value=set()):
            with mock_patch.object(hub_app, "_safe_copy_with_backup", side_effect=PermissionError("locked")):
                res_perm = api.install_all()
                assert res_perm["ok"] is False
                assert len(res_perm["errors"]) >= 1

    print("[PASS] 11-13. Process guard blocking, user glossary preservation, and PermissionError failure handling")


def test_manifest_state_and_incremental_plan() -> None:
    import zipfile
    import manifest as manifest_mod  # noqa: E402
    import state as state_mod  # noqa: E402
    sys.path.insert(0, str(ROOT / "tools"))
    import build_manifest as bm  # noqa: E402

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        assets_dir = tmp_path / "release_assets"
        game_dir = tmp_path / "gw2"
        state_dir = tmp_path / "appdata"
        assets_dir.mkdir()
        game_dir.mkdir()

        # Create sample release assets including a zip model archive
        (assets_dir / "d3d11.dll").write_bytes(b"MZ" + b"N" * 100)
        (assets_dir / "text_translator.dll").write_bytes(b"MZ" + b"T" * 120)
        (assets_dir / "turkish_font.dll").write_bytes(b"MZ" + b"F" * 140)
        with zipfile.ZipFile(assets_dir / "opus-mt-en-tr-ct2.zip", "w") as zf:
            zf.writestr("model.bin", b"MODEL_BYTES_V1")
            zf.writestr("source.spm", b"SPM_BYTES_V1")

        # 1. Build & validate manifest via tools/build_manifest.py
        raw_manifest = bm.build_manifest(assets_dir, version="0.13.0")
        m = manifest_mod.validate_schema(raw_manifest)
        assert m.version == "0.13.0"
        assert len(m.components) == 4
        assert [c.id for c in m.components] == [
            "nexus",
            "model.opus_mt_tr",
            "addon.text_translator",
            "addon.font_injector",
        ]

        # 2. Path traversal in manifest must be rejected
        bad_manifest = json.loads(json.dumps(raw_manifest))
        bad_manifest["components"]["addon.text_translator"]["files"][0]["path"] = "../../evil.dll"
        try:
            manifest_mod.validate_schema(bad_manifest)
            raise AssertionError("Expected path traversal rejection")
        except ValueError:
            pass

        # 3. Fresh install plan downloads all 4 enabled components
        plan_fresh = manifest_mod.plan_update(m, game_dir, local_state={}, toggles={"font_injector": True})
        assert len(plan_fresh.download) == 4
        assert plan_fresh.total_bytes > 0

        # 4. Simulate installed files: Nexus present, model unchanged, font_injector toggled OFF
        (game_dir / "d3d11.dll").write_bytes(b"USER_CUSTOM_NEXUS")
        mod_dir = game_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"
        (mod_dir / "TR" / "model").mkdir(parents=True)
        (mod_dir / "TR" / "model" / "model.bin").write_bytes(b"MODEL_BYTES_V1")
        (mod_dir / "TR" / "model" / "source.spm").write_bytes(b"SPM_BYTES_V1")
        (game_dir / "addons" / "text_translator.dll").write_bytes(b"OLD_TT_DLL")

        st = state_mod.InstallState(state_dir)
        st.save({
            "version": "0.12.0",
            "files": {
                "addons/text_translator/modules/local_translator_tr/tr/model/model.bin": bm.sha256_bytes(b"MODEL_BYTES_V1"),
                "addons/text_translator/modules/local_translator_tr/tr/model/source.spm": bm.sha256_bytes(b"SPM_BYTES_V1"),
                "addons/text_translator.dll": bm.sha256_bytes(b"OLD_TT_DLL"),
            },
        })
        loaded_state = st.load()
        assert loaded_state["version"] == "0.12.0"

        # Incremental plan: skips Nexus (if_missing), skips unchanged model, skips disabled font_injector, downloads ONLY text_translator.dll!
        plan_inc = manifest_mod.plan_update(m, game_dir, local_state=loaded_state, toggles={"font_injector": False})
        assert [item.component.id for item in plan_inc.download] == ["addon.text_translator"]
        skip_reasons = {comp.id: reason for comp, _, reason in plan_inc.skip}
        assert skip_reasons["nexus"] == "already_present"
        assert skip_reasons["model.opus_mt_tr"] == "up_to_date"
        assert skip_reasons["addon.font_injector"] == "disabled"

        # 5. Journal lifecycle
        st.write_journal({"version": "0.13.0", "step": "apply"})
        assert st.pending_journal() is not None
        st.commit_journal()
        assert st.pending_journal() is None

    print("[PASS] 14. Manifest schema, path traversal guard, InstallState journal, and incremental update planner")


def test_downloader_zip_security_and_atomic_rollback() -> None:
    import zipfile
    from unittest.mock import patch as mock_patch
    import downloader as dl_mod  # noqa: E402
    import applier as app_mod  # noqa: E402
    import manifest as manifest_mod  # noqa: E402
    import state as state_mod  # noqa: E402

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        dl_dir = tmp_path / "downloads"
        ext_dir = tmp_path / "extract"
        game_dir = tmp_path / "gw2"
        state_dir = tmp_path / "state"
        game_dir.mkdir()

        # 1. Zip path traversal must be blocked
        evil_zip = tmp_path / "evil.zip"
        with zipfile.ZipFile(evil_zip, "w") as zf:
            zf.writestr("../escape.txt", b"EVIL")
        try:
            dl_mod.extract_zip_safe(evil_zip, ext_dir)
            raise AssertionError("Expected zip path traversal rejection")
        except dl_mod.DownloadError:
            pass

        # 2. Verified download + content-addressed dedupe
        valid_pe = bytearray(20_000)
        valid_pe[0:2] = b"MZ"
        valid_pe[0x3C:0x40] = (0x80).to_bytes(4, "little")
        valid_pe[0x80:0x84] = b"PE\x00\x00"
        pe_bytes = bytes(valid_pe)
        import hashlib
        pe_sha = hashlib.sha256(pe_bytes).hexdigest()

        class _ChunkResp:
            status = 200
            def __init__(self, data: bytes) -> None:
                self._buf = data
                self._pos = 0
            def read(self, n: int = -1) -> bytes:
                if self._pos >= len(self._buf):
                    return b""
                chunk = self._buf[self._pos:self._pos + n]
                self._pos += len(chunk)
                return chunk
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False

        with mock_patch("urllib.request.urlopen", return_value=_ChunkResp(pe_bytes)) as m_open:
            p1 = dl_mod.download_verified("https://example.com/a.dll", pe_sha, len(pe_bytes), dl_dir, validate="pe")
            assert p1.is_file()
            assert m_open.call_count == 1
            # Second call reuses verified cached file without hitting network
            p2 = dl_mod.download_verified("https://example.com/a.dll", pe_sha, len(pe_bytes), dl_dir, validate="pe")
            assert p2 == p1
            assert m_open.call_count == 1

        # 3. Atomic apply + automatic rollback when a later component fails
        existing_dll = game_dir / "addons" / "text_translator.dll"
        existing_dll.parent.mkdir(parents=True)
        existing_dll.write_bytes(b"ORIGINAL_V1_DLL")

        raw_m = {
            "schema_version": 1,
            "version": "0.13.0",
            "base_url": "https://example.com/dl/",
            "install": {"targets": {"game": "{game_dir}"}},
            "components": {
                "c1": {
                    "label": "First",
                    "target": "game",
                    "order": 1,
                    "files": [{"path": "addons/text_translator.dll", "asset": "a.dll", "sha256": pe_sha, "size": len(pe_bytes)}],
                },
                "c2": {
                    "label": "Missing Staged",
                    "target": "game",
                    "order": 2,
                    "files": [{"path": "addons/turkish_font.dll", "asset": "b.dll", "sha256": "0" * 64, "size": 100}],
                },
            },
        }
        m = manifest_mod.validate_schema(raw_m)
        plan = manifest_mod.plan_update(m, game_dir)
        st = state_mod.InstallState(state_dir)
        try:
            # c1 succeeds, c2 is missing from staged_assets -> must roll back c1!
            app_mod.apply_plan(plan, {pe_sha: p1}, game_dir, st)
            raise AssertionError("Expected ApplyError and rollback")
        except app_mod.ApplyError:
            pass
        assert existing_dll.read_bytes() == b"ORIGINAL_V1_DLL", "Rollback must restore original DLL!"

        # 4. install_from_manifest must write module.toml, settings.toml, and preserve/create glossary_tr.json
        res_dir = tmp_path / "res"
        (res_dir / "TR").mkdir(parents=True)
        (res_dir / "TR" / "glossary_tr.json").write_text('{"exact": {"Play": "Oyna"}, "terms": {}}', encoding="utf-8")
        api = hub_app.HubAPI()
        api._game_dir = game_dir
        api._res_dir = res_dir
        single_m = manifest_mod.validate_schema({
            "schema_version": 1,
            "version": "0.13.0",
            "base_url": "https://example.com/dl/",
            "install": {"targets": {"game": "{game_dir}"}},
            "components": {
                "c1": {
                    "label": "First",
                    "target": "game",
                    "order": 1,
                    "files": [{"path": "addons/text_translator.dll", "asset": "a.dll", "sha256": pe_sha, "size": len(pe_bytes)}],
                },
            },
        })
        with mock_patch.object(hub_app.process_guard, "blocking_processes", return_value=[]):
            with mock_patch.object(hub_app.manifest_mod, "fetch_manifest", return_value=single_m):
                with mock_patch.object(hub_app.downloader_mod, "download_verified", return_value=p1):
                    res_m = api.install_from_manifest(state_root=tmp_path / "mstate")
                    assert res_m["ok"] is True
        mod_dir = game_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"
        assert (mod_dir / "module.toml").is_file(), "install_from_manifest must create module.toml"
        assert 'command = "Local_Translator_TR.exe"' in (mod_dir / "module.toml").read_text(encoding="utf-8")
        assert (mod_dir / "TR" / "glossary_tr.json").is_file()

    print("[PASS] 15. Verified downloader (dedupe + PE), zip traversal block, and atomic applier rollback")


if __name__ == "__main__":
    test_turkish_only_and_case()
    test_font_injector_6_char_fallback()
    test_item_and_location_protection()
    test_cache_db_sync_and_editor()
    test_hub_keybind_and_config()
    test_stats_boons_and_conditions_protection()
    test_hub_font_injector_api_key_and_gemini()
    test_safe_install_and_version_consistency()
    test_atlas_blob_integrity()
    test_hub_update_checker()
    test_process_guard_glossary_preserve_and_perm_error()
    test_manifest_state_and_incremental_plan()
    test_downloader_zip_security_and_atomic_rollback()
    print("\nALL 13 TEST SUITES (15 CHECKS) PASSED SUCCESSFULLY!")
