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


if __name__ == "__main__":
    test_turkish_only_and_case()
    test_font_injector_6_char_fallback()
    test_item_and_location_protection()
    test_cache_db_sync_and_editor()
    test_hub_keybind_and_config()
    test_stats_boons_and_conditions_protection()
    print("\nALL 6 TEST SUITES PASSED SUCCESSFULLY!")
