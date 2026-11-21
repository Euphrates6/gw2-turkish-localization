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
    print("\nALL 9 TEST SUITES PASSED SUCCESSFULLY!")
