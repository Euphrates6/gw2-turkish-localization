"""Adds Guild Wars 2 stats, boons, conditions, combat effects, and stat-set prefixes
to TR/glossary_tr.json and src/glossary_tr.default.json so they remain in English.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TERMS_TO_ADD: dict[str, str] = {
    # Primary & Secondary Attributes
    "Power": "Power",
    "Precision": "Precision",
    "Toughness": "Toughness",
    "Vitality": "Vitality",
    "Ferocity": "Ferocity",
    "Condition Damage": "Condition Damage",
    "Expertise": "Expertise",
    "Concentration": "Concentration",
    "Healing Power": "Healing Power",
    "Agony Resistance": "Agony Resistance",

    # Derived Attributes
    "Critical Chance": "Critical Chance",
    "Critical Damage": "Critical Damage",
    "Boon Duration": "Boon Duration",
    "Condition Duration": "Condition Duration",
    "Magic Find": "Magic Find",

    # Boons
    "Aegis": "Aegis",
    "Alacrity": "Alacrity",
    "Fury": "Fury",
    "Might": "Might",
    "Protection": "Protection",
    "Quickness": "Quickness",
    "Regeneration": "Regeneration",
    "Resistance": "Resistance",
    "Resolution": "Resolution",
    "Stability": "Stability",
    "Swiftness": "Swiftness",
    "Vigor": "Vigor",

    # Conditions (Damaging & Non-Damaging)
    "Bleeding": "Bleeding",
    "Burning": "Burning",
    "Confusion": "Confusion",
    "Poison": "Poison",
    "Torment": "Torment",
    "Blind": "Blind",
    "Blinded": "Blinded",
    "Chilled": "Chilled",
    "Cripple": "Cripple",
    "Crippled": "Crippled",
    "Fear": "Fear",
    "Immobilize": "Immobilize",
    "Immobilized": "Immobilized",
    "Slow": "Slow",
    "Taunt": "Taunt",
    "Vulnerability": "Vulnerability",
    "Weakness": "Weakness",

    # Common Combat Effects & Control
    "Barrier": "Barrier",
    "Superspeed": "Superspeed",
    "Stealth": "Stealth",
    "Daze": "Daze",
    "Stun": "Stun",

    # Stat Set Names (Prefixes)
    "Berserker": "Berserker",
    "Berserker's": "Berserker's",
    "Viper": "Viper",
    "Viper's": "Viper's",
    "Marauder": "Marauder",
    "Marauder's": "Marauder's",
    "Harrier": "Harrier",
    "Harrier's": "Harrier's",
    "Minstrel": "Minstrel",
    "Minstrel's": "Minstrel's",
    "Diviner": "Diviner",
    "Diviner's": "Diviner's",
    "Celestial": "Celestial",
    "Assassin": "Assassin",
    "Assassin's": "Assassin's",
    "Sinister": "Sinister",
    "Trailblazer": "Trailblazer",
    "Trailblazer's": "Trailblazer's",
    "Giver": "Giver",
    "Giver's": "Giver's",
    "Commander": "Commander",
    "Commander's": "Commander's",
    "Ritualist": "Ritualist",
    "Ritualist's": "Ritualist's",
    "Dragon": "Dragon",
    "Dragon's": "Dragon's",
    "Soldier": "Soldier",
    "Soldier's": "Soldier's",
    "Valkyrie": "Valkyrie",
    "Knight": "Knight",
    "Knight's": "Knight's",
    "Cavalier": "Cavalier",
    "Captain": "Captain",
    "Captain's": "Captain's",
    "Rampager": "Rampager",
    "Rampager's": "Rampager's",
    "Carrion": "Carrion",
    "Rabid": "Rabid",
    "Dire": "Dire",
    "Shaman": "Shaman",
    "Shaman's": "Shaman's",
    "Cleric": "Cleric",
    "Cleric's": "Cleric's",
    "Magi": "Magi",
    "Magi's": "Magi's",
    "Apothecary": "Apothecary",
    "Settler": "Settler",
    "Settler's": "Settler's",
    "Nomad": "Nomad",
    "Nomad's": "Nomad's",
    "Marshal": "Marshal",
    "Marshal's": "Marshal's",
    "Grieving": "Grieving",
    "Plaguedoctor": "Plaguedoctor",
    "Plaguedoctor's": "Plaguedoctor's",
    "Crusader": "Crusader",
    "Zealot": "Zealot",
    "Zealot's": "Zealot's",
    "Wanderer": "Wanderer",
    "Wanderer's": "Wanderer's",
    "Vigilant": "Vigilant",
}


def update_glossary(path: Path) -> int:
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    terms: dict[str, str] = data.get("terms", {})
    added = 0
    for k, v in TERMS_TO_ADD.items():
        if k not in terms or terms[k] != v:
            terms[k] = v
            added += 1
    # Sort keys case-insensitively
    data["terms"] = dict(sorted(terms.items(), key=lambda x: x[0].lower()))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return added


def main() -> None:
    for target in (ROOT / "TR" / "glossary_tr.json", ROOT / "src" / "glossary_tr.default.json"):
        n = update_glossary(target)
        print(f"[+] Updated {target}: {n} terms updated.")


if __name__ == "__main__":
    main()

