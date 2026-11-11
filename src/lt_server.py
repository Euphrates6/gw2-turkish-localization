"""Shared code of GW2 Nexus Local Translator (Turkish Edition - v0.12.0-TR).

Imported as a library by lt_module.py (the module started by Ideka's Text Translator addon)
and by the GW2 TR Hub desktop application.
Primary translation engine runs locally offline with CTranslate2 (OPUS-MT) on the CPU.
Optional cloud backends (Google, DeepL, Gemini, OpenAI) are also supported via TR/config.json.
"""
from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import zlib
from collections import deque
from dataclasses import dataclass
from pathlib import Path

GITHUB_REPO = "Euphrates6/gw2-turkish-localization"
DEFAULT_BRANCH = "main"


def raw_url(path: str, branch: str = DEFAULT_BRANCH) -> str:
    """URL of a file of the repository on raw.githubusercontent.com."""
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{branch}/{path}"


# --------------------------------------------------------------------------- #
# Turkish-aware Case & Character Helpers
# --------------------------------------------------------------------------- #
def tr_lower(text: str) -> str:
    """Turkish-aware lowercase conversion (avoids 'İ' -> 'i\\u0307' combining dot bug)."""
    if not text:
        return text
    return text.replace("İ", "i").replace("I", "ı").lower().replace("i\u0307", "i")


def tr_upper(text: str) -> str:
    """Turkish-aware uppercase conversion ('i' -> 'İ', 'ı' -> 'I')."""
    if not text:
        return text
    return text.replace("i\u0307", "i").replace("i", "İ").replace("ı", "I").upper()


def fix_turkish_chars(text: str, mode: str = "smart") -> str:
    """Normalize Turkish characters for GW2's font engine.
    'smart': Replaces ONLY the glyphs that GW2's font engine drops (ş, Ş, ğ, Ğ, İ),
             while preserving 100% authentic ç, Ç, ö, Ö, ü, Ü, ı which GW2 natively renders!
    'minimal': replaces non-Latin-1 characters (including ı -> i)
    'full' / 'ascii_full': replaces all accented Turkish characters (also ç, Ç, ö, Ö, ü, Ü)
            to guarantee 100% readability across all game UI fonts.
    'off': leaves text untouched.
    """
    if not text or mode in ("off", "", None, False):
        return text
    # Characters that GW2 English font engine natively lacks and drops/skips:
    text = (text.replace("i\u0307", "i")
                .replace("\u0307", "")
                .replace("ş", "s")
                .replace("Ş", "S")
                .replace("ğ", "g")
                .replace("Ğ", "G")
                .replace("İ", "I"))
    if mode in ("minimal", "full", "ascii_full", "ascii_6", "6char"):
        text = text.replace("ı", "i")
    if mode in ("full", "ascii_full"):
        text = (text.replace("ç", "c")
                    .replace("Ç", "C")
                    .replace("ö", "o")
                    .replace("Ö", "O")
                    .replace("ü", "u")
                    .replace("Ü", "U"))
    return text


# --------------------------------------------------------------------------- #
# Language of the module (Turkish-Only Architecture)
# --------------------------------------------------------------------------- #
class Language:
    def __init__(self, code: str, cache_key: str, label: str, model: str, recipe: dict[str, str],
                 article: str, plural: bool = False, mini: str | None = None) -> None:
        self.code = code
        self.cache_key = cache_key
        self.label = label
        self.data_dir = code.upper()
        self.model = model
        self.recipe = recipe
        self.article = re.compile(article, re.IGNORECASE) if article else None
        self.plural = False
        self.mini = mini

    def file(self, stem: str, ext: str) -> str:
        """glossary + .json -> glossary_tr.json"""
        return f"{stem}_{self.code}{ext}"


LANGUAGES = {
    "tr": Language(
        code="tr",
        cache_key="tr",
        label="TR",
        model="v0.12.0/opus-mt-en-tr-ct2.zip",
        recipe={
            "Recipe": "Tarif: ",
            "Recipes": "Tarifler: ",
            "Recipe[s]": 'Tarif[pl:"Tarifler"]: ',
        },
        article=r"(?:bir )",
        plural=False,
        mini="Mini ",
    ),
}
LANG = LANGUAGES["tr"]
PLURAL_RULES = None


def set_language(code: str = "tr") -> Language:
    """Set the module language (always defaults to 'tr' in Turkish-only edition)."""
    global LANG, GLOSSARY_URL, PATCH_URL, MODEL_URL, PLURAL_RULES
    LANG = LANGUAGES.get(code.lower(), LANGUAGES["tr"])
    GLOSSARY_URL = raw_url(f"glossary/{LANG.file('glossary', '.json')}")
    PATCH_URL = raw_url(f"patch/{LANG.file('patch', '.json')}")
    MODEL_URL = f"https://github.com/{GITHUB_REPO}/releases/download/{LANG.model}"
    PLURAL_RULES = None
    return LANG


GLOSSARY_URL = raw_url(f"glossary/{LANG.file('glossary', '.json')}")
PATCH_URL = raw_url(f"patch/{LANG.file('patch', '.json')}")
MODEL_URL = f"https://github.com/{GITHUB_REPO}/releases/download/{LANG.model}"
UPDATE_INTERVAL = 15 * 60
MAX_DOWNLOAD = 100_000_000

# Game markup that must come out of the translation untouched:
TOKEN_RE = re.compile(r'%[A-Za-z]+\d*%|</?[A-Za-z][^<>\n]*>|\[[^\[\]\n]*\]')
_RANGE_SIDE = r"(?:\d+(?:[.,]\d+)*(?:%%)?|%[A-Za-z]+\d*%)"
RANGE_RE = re.compile(rf"(?<![\w.,]){_RANGE_SIDE}\s?[–-]\s?{_RANGE_SIDE}(?!\w)")
PROTECT_VERSION = 10

# Plural markers of raw game strings ("Piece[s]", "Box[pl:\"Boxes\"]"):
PLURAL_RE = re.compile(r'(?<=\w)\[s\]|[\w\'’-]+\[pl:"([^"\[\]\n]*)"\]')
IT_PL_RE = re.compile(r'\[pl:"[^"\[\]\n]*"\]')
NUM_RE = re.compile(r"%num\d*%")


def resolve_plural(line: str) -> str:
    """English plural form of a raw game string."""
    return PLURAL_RE.sub(lambda m: "s" if m.group(1) is None else m.group(1), line)


def english_singular(line: str) -> str:
    """English singular form of a raw game string."""
    return PLURAL_RE.sub(lambda m: "" if m.group(1) is None else m.group(0).split("[pl:")[0], line)


def plural_name(line: str) -> bool:
    """True if line is an item/material/creature name carrying GW2 plural markers without %num%."""
    return PLURAL_RE.search(line) is not None and NUM_RE.search(line) is None


# Control characters: undecoded game data
GARBLED_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
PERCENT_RE = re.compile(r"%[A-Za-z]+\d*%|%%|%")


def fix_percent(text: str, english: str | None = None) -> str:
    """GW2 formats texts like printf: a lone '%' in the translation becomes '%%'."""
    if not text or "%" not in text:
        return text
    if english is not None and ("%" not in english or GARBLED_RE.search(english)):
        return text
    return PERCENT_RE.sub(lambda m: "%%" if m.group(0) == "%" else m.group(0), text)


def masculine(text: str) -> str:
    """No-op in Turkish (no grammatical gender)."""
    return text


EN_FEM_RE = re.compile(r'\[f:"[^"]*"\]')


def feminine(text: str, roles: dict[str, str] | None = None) -> str:
    """Strip any English feminine markers [f:"..."] copied by the model; Turkish roles are gender-neutral."""
    if not text:
        return text
    if "[f:" in text:
        text = EN_FEM_RE.sub("", text)
    return text


EN_ARTICLE_RE = re.compile(r"(?:the|a|an)\b", re.IGNORECASE)


def drop_article(text: str, english: str) -> str:
    """Drop leading 'Bir ' added by the model if the English name had no article."""
    if not text or "\n" in text or not LANG.article:
        return text
    pre, core, post = Glossary.WRAP_RE.fullmatch(text).groups()
    ecore = Glossary.WRAP_RE.fullmatch(english).group(2)
    m = LANG.article.match(core)
    if not m or EN_ARTICLE_RE.match(ecore.lstrip()):
        return text
    rest = core[m.end():]
    if not rest.strip():
        return text
    return pre + tr_upper(rest[:1]) + rest[1:] + post


# --------------------------------------------------------------------------- #
# 3-Layer Hybrid Item & Location Name Protection (Keep in Original English)
# --------------------------------------------------------------------------- #
RECIPE_RE = re.compile(r"(Recipe(?:\[s\]|s)?): (\S.*)")
MINI_RE = re.compile(r"Mini ([A-Z0-9][^<>]*)")
SENTENCE_END_RE = re.compile(r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)[.!?](?:\s|$)")

# Connectors allowed in lowercase inside English Title-Case item & location names
_TITLE_CONNECTORS = {
    "of", "the", "and", "in", "on", "to", "for", "with", "from", "at", "by",
    "a", "an", "or", "into", "over", "under", "upon", "vs", "vs.", "de", "la", "von", "van",
}
# Common UI imperative verbs / dialogue starters that should ALWAYS be translated even if capitalized
_UI_VERBS_AND_COMMON = {
    "accept", "activate", "add", "all", "apply", "Are", "are", "ask", "attack", "available",
    "back", "buy", "cancel", "change", "check", "choose", "claim", "clear", "click", "close",
    "collect", "combine", "complete", "completed", "confirm", "continue", "consume", "copy",
    "craft", "create", "current", "customize", "defeat", "delete", "deposit", "destroy",
    "disable", "discard", "dismiss", "display", "do", "does", "done", "double-click", "drag",
    "drop", " dye", "earn", "edit", "empty", "enable", "enter", "equip", "equipped", "escort",
    "examine", "exit", "explore", "filter", "find", "finish", "follow", "free", "gather",
    "get", "give", "go", "greet", "gsub", "help", "hide", "hold", "how", "identify", "ignore",
    "inspect", "interact", "invite", "join", "jump", "keep", "kill", "lfg", "leave", "level",
    "listen", "load", "lock", "log", "look", "mail", "make", "manage", "mark", "master",
    "meet", "merge", "move", "need", "new", "next", "no", "none", "not", "ok", "open",
    "options", "pack", "party", "pause", "pay", "pick", "place", "play", "press", "preview",
    "previous", "protect", "purchase", "put", "quit", "read", "ready", "receive", "recover",
    "refresh", "reject", "release", "remove", "rename", "repair", "repeat", "replace",
    "report", "request", "requires", "rescue", "reset", "restore", "retrieve", "return",
    "revive", "reward", "rewards", "right-click", "run", "salvage", "save", "search", "see",
    "select", "sell", "send", "set", "settings", "share", "show", "skip", "sort", "speak",
    "spend", "split", "start", "stay", "stop", "store", "submit", "summon", "survive", "swap",
    "switch", "take", "talk", "target", "teleport", "test", "thank", "this", "throw", "time",
    "toggle", "total", "track", "trade", "train", "transfer", "travel", "try", "turn", "type",
    "unequip", "unlock", "unlocked", "unusable", "up", "update", "upgrade", "use", "used",
    "using", "view", "visit", "wait", "walk", "warning", "watch", "what", "when", "where",
    "who", "why", "win", "withdraw", "work", "world", "yes", "you", "your",
}


GW2_STATS = {
    "Power", "Precision", "Toughness", "Vitality", "Ferocity", "Condition Damage",
    "Expertise", "Concentration", "Healing Power", "Agony Resistance",
    "Critical Chance", "Critical Damage", "Condition Duration", "Boon Duration",
    "Magic Find", "Armor", "Health",
}

GW2_BOONS_CONDITIONS = {
    "Aegis", "Alacrity", "Fury", "Might", "Protection", "Quickness", "Regeneration",
    "Resistance", "Resolution", "Stability", "Swiftness", "Vigor",
    "Bleeding", "Burning", "Confusion", "Poison", "Torment",
    "Blind", "Blinded", "Chilled", "Cripple", "Crippled", "Fear", "Immobilize",
    "Immobilized", "Slow", "Taunt", "Vulnerability", "Weakness",
    "Barrier", "Superspeed", "Stealth", "Daze", "Stun",
}

GW2_STAT_SETS = {
    "Berserker", "Berserker's", "Viper", "Viper's", "Marauder", "Marauder's",
    "Harrier", "Harrier's", "Minstrel", "Minstrel's", "Diviner", "Diviner's",
    "Celestial", "Assassin", "Assassin's", "Sinister", "Trailblazer", "Trailblazer's",
    "Giver", "Giver's", "Commander", "Commander's", "Ritualist", "Ritualist's",
    "Dragon", "Dragon's", "Soldier", "Soldier's", "Valkyrie", "Knight", "Knight's",
    "Cavalier", "Captain", "Captain's", "Rampager", "Rampager's", "Carrion", "Rabid",
    "Dire", "Shaman", "Shaman's", "Cleric", "Cleric's", "Magi", "Magi's",
    "Apothecary", "Settler", "Settler's", "Nomad", "Nomad's", "Marshal", "Marshal's",
    "Grieving", "Plaguedoctor", "Plaguedoctor's", "Crusader", "Zealot", "Zealot's",
    "Wanderer", "Wanderer's", "Vigilant",
}

_ALL_MECHANICS_TERMS = sorted(GW2_STATS | GW2_BOONS_CONDITIONS | GW2_STAT_SETS, key=lambda x: -len(x))
_MECHANICS_RX = "|".join(re.escape(t) for t in _ALL_MECHANICS_TERMS)

# Matches standalone stat lines (+120 Power, +%num1% Condition Damage, +5% Critical Chance, Might (5 stacks), etc.)
STAT_LINE_RE = re.compile(
    r"^[+\-]?\s*(?:\d+[\d,.]*|%num\d*%|%%)?\s*[%]?\s*(?:" + _MECHANICS_RX + r")(?:\s*\(.*?\))?\s*(?:[:=]\s*[+\-]?(?:\d+[\d,.]*|%num\d*%|%%)?[%]?)?$",
    re.IGNORECASE,
)


def is_stat_or_mechanic_line(line: str) -> bool:
    """Returns True if the line is a standalone stat bonus, stat-set name, or boon/condition line."""
    if not line or "\n" in line or "<br" in line.lower():
        return False
    pre, core, post = Glossary.WRAP_RE.fullmatch(line).groups()
    core_clean = core.strip()
    if not core_clean:
        return False
    return bool(STAT_LINE_RE.match(core_clean))


def is_item_or_location_name(line: str, glossary: "Glossary | None" = None) -> bool:
    """Detect whether a single-line string is a GW2 Item Name or Location/Map/POI Name
    that should remain in original English.
    """
    if not line or "\n" in line or "<br" in line.lower():
        return False
    # If glossary has an explicit exact override or pattern for this UI string, let glossary handle it
    if glossary is not None and glossary.lookup(line) is not None:
        return False
    # Layer 1: Raw game plural markers without %num% ("Iron Ore[s]", "Box[pl:\"Boxes\"]") are always item/creature names
    if plural_name(line):
        return True
    pre, core, post = Glossary.WRAP_RE.fullmatch(line).groups()
    core_clean = core.strip()
    if not core_clean:
        return False
    # Layer 2A: "Mini X" miniature items
    if MINI_RE.fullmatch(core_clean) and not SENTENCE_END_RE.search(core_clean):
        return True
    # Must not contain sentence punctuation (. ! ? ; : ") or variables (%num1%, %str1%)
    if re.search(r"[.!?;\"]|%[A-Za-z]+\d*%|%%", core_clean):
        return False
    # Extract words
    words = re.findall(r"[A-Za-z0-9'’-]+", core_clean)
    if not (2 <= len(words) <= 7):
        return False
    # If the first word is a common UI verb/instruction ("Speak to...", "Return to...", "Defeat the..."), translate it!
    if words[0].lower() in _UI_VERBS_AND_COMMON:
        return False
    # Check if any word is a finite verb / sentence word not typical of Title-Case item/map names
    for w in words:
        wl = w.lower()
        if wl in ("is", "are", "was", "were", "will", "can", "cannot", "must", "should", "have", "has", "had", "you", "your"):
            return False
    # Every word must be capitalized (Title Case) or an allowed small connector ("of", "the", "in")
    cap_count = 0
    for idx, w in enumerate(words):
        if w[0].isupper():
            cap_count += 1
        elif idx > 0 and w.lower() in _TITLE_CONNECTORS:
            continue
        else:
            return False
    return cap_count >= 2


def recipe_split(line: str) -> tuple[str, str, str] | None:
    """(Turkish head with markup before, English item name, markup after) or None:
    'Recipe[s]: X' and 'Mini X'."""
    if "\n" in line or ("Recipe" not in line and "Mini " not in line):
        return None
    pre, core, post = Glossary.WRAP_RE.fullmatch(line).groups()
    m = RECIPE_RE.fullmatch(core)
    if m:
        return pre + LANG.recipe[m.group(1)], m.group(2), post
    m = MINI_RE.fullmatch(core) if LANG.mini else None
    if m and not SENTENCE_END_RE.search(m.group(1)):
        return pre + LANG.mini, m.group(1), post
    return None


def recipe_name(head: str, text: str, english: str) -> str:
    """In Turkish, keep proper capitalization after 'Tarif: ' or 'Mini '."""
    return drop_article(text, english)


# --- Lines translated in pieces --------------------------------------------------------------------
PIECE_SEP_RE = re.compile(r"(<br\s*/?>|:\s+|\s*—\s*|(?<=[.!?…])\s+(?=[^\sa-z]))")
_EDGE = r"(?:%[A-Za-z]+\d*%|</?[A-Za-z][^<>\n]*>)"
PIECE_LEAD_RE = re.compile(rf"\s*(?:{_EDGE})*")
PIECE_TAIL_RE = re.compile(rf"(?:{_EDGE})*\s*$")
NO_SPLIT_RE = re.compile(r"\bGuild Wars(?: 2)?: "
                         r"|\b(?:vs|Mr|Mrs|Ms|Dr|St|Mt|Lt|Sgt|Capt|Gen|Jr|Sr|No|Vol)\.\s")
PIECE_SEPS = ("—", ": ", ". ", "! ", "? ", "<br")
END_PUNCT = tuple(".!?…")
MASK_RE = re.compile(r"\x00(\d+)\x00")


def _piece_edges(piece: str) -> tuple[str, str, str]:
    pre = PIECE_LEAD_RE.match(piece).group(0)
    if pre and piece[len(pre):len(pre) + 1].isspace():
        pre = re.match(r"\s*", piece).group(0)
    core = piece[len(pre):]
    post = PIECE_TAIL_RE.search(core).group(0)
    if post and core[:len(core) - len(post)][-1:].isspace() and post.strip():
        post = re.search(r"\s*$", core).group(0)
    return pre, core[:len(core) - len(post)] if post else core, post


def split_pieces(line: str, glossary: "Glossary") -> list[tuple[str, str]] | None:
    masks: list[str] = []

    def mask(m: re.Match) -> str:
        masks.append(m.group(0))
        return f"\x00{len(masks) - 1}\x00"

    for src, _ in glossary.terms:
        if src in line and any(sep in src for sep in PIECE_SEPS):
            line = glossary.term_regex(src).sub(mask, line)
    line = NO_SPLIT_RE.sub(mask, line)

    def unmask(text: str) -> str:
        while "\x00" in text:
            text = MASK_RE.sub(lambda m: masks[int(m.group(1))], text)
        return text

    out: list[tuple[str, str]] = []
    for i, part in enumerate(PIECE_SEP_RE.split(line)):
        if i % 2:
            out.append(("sep", part))
        elif part:
            pre, core, post = _piece_edges(part)
            if pre:
                out.append(("sep", pre))
            if core:
                text = re.search(r"[A-Za-z]", core) or ("\x00" in core and re.search(r"[A-Za-z]", unmask(core)))
                out.append(("txt" if text else "sep", unmask(core)))
            if post:
                out.append(("sep", post))
    if sum(k == "txt" for k, _ in out) <= 1 and not any(k == "sep" and t.strip() for k, t in out):
        return None
    return [(k, unmask(t)) for k, t in out]


_NUM_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
_NUM_WORDS.update({w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())})


def _english_numbers(text: str) -> set[int]:
    nums = {int(n) for n in re.findall(r"\d+", text)}
    for m in re.finditer(r"\b([a-z]+)(?:-([a-z]+))?\b", text.lower()):
        a, b = _NUM_WORDS.get(m.group(1)), _NUM_WORDS.get(m.group(2) or "")
        if a is not None:
            nums.update({a, a + (b or 0)} | ({b} if b is not None else set()))
    if re.search(r"\b(first|second|third|I{1,3})\b", text):
        nums.update(range(1, 4))
    return nums


def invented_piece(src: str, out: str) -> bool:
    words = max(len(src.split()), len(re.findall(r"\w+", src)))
    if len(out.split()) > 2 * words + 1:
        return True
    head = src.rstrip()
    rest = out[len(head):]
    if out.startswith(head) and len(rest) > 3 and (rest[0].isupper() or not rest.isalpha()):
        return True
    return bool({int(n) for n in re.findall(r"\d+", out)} - _english_numbers(src))


INVENTED_WORDS = 3
ADDED_MARKER_RE = re.compile(r'\[(?:pl|f):"[^"\[\]\n]*"\]')


def same_case(src: str, out: str) -> str:
    """First letter of `out` upper or lower case as in `src` (Turkish-aware)."""
    a = next((c for c in src if c.isalnum()), "")
    i = next((k for k, c in enumerate(out) if c.isalnum()), None)
    if not a.isalpha() or i is None or not out[i].isalpha():
        return out
    ch = tr_upper(out[i]) if a.isupper() else tr_lower(out[i])
    return out[:i] + ch + out[i + 1:]


def join_pieces(parts: list[tuple[str, str]], done: dict[str, str], fixed: set[str]) -> str:
    out, prev = [], ""
    for kind, t in parts:
        if kind == "sep":
            out.append(t)
            prev = t
            continue
        r = done.get(t, t)
        if t not in fixed and r != t and invented_piece(t, r):
            r = t
        if r != t:
            if r.endswith(".") and not r.endswith("..") and not t.rstrip().endswith(END_PUNCT):
                r = r[:-1]
            if prev.strip() in (":", "—"):
                r = same_case(t, r)
        out.append(r)
        prev = ""
    return "".join(out)


def _cased(word: str, like: str) -> str:
    return tr_upper(word[:1]) + word[1:] if like[:1].isupper() else tr_lower(word[:1]) + word[1:]


def bad_percent(text: str, english: str | None = None) -> bool:
    return fix_percent(text, english) != text


log = logging.getLogger("lt")


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir()))


# --------------------------------------------------------------------------- #
# Glossary
# --------------------------------------------------------------------------- #
class Glossary:
    WORDS = r"(?:[A-Z][\w'’-]*(?: [A-Z][\w'’-]*)*|\d+(?:[.,]\d+)?)"
    WRAP_RE = re.compile(
        r"((?:<[^<>\n]*>|%[A-Za-z]+\d*%)*)(.*?)((?:<[^<>\n]*>|%[A-Za-z]+\d*%)*)", re.S)

    def __init__(self) -> None:
        self.exact: dict[str, str] = {}
        self.terms: list[tuple[str, str]] = []
        self.term_map: dict[str, str] = {}
        self.patterns: list[tuple[re.Pattern, str]] = []
        self.version = 0
        self.fingerprint = ""
        self.feminine: dict[str, str] = {}
        self._term_rx: dict[str, re.Pattern] = {}
        self.problems: list[str] = []
        self.advice: dict[str, str] = {}

    def term_regex(self, src: str) -> re.Pattern:
        rx = self._term_rx.get(src)
        if rx is None:
            rx = self._term_rx[src] = re.compile(
                r"(?:(?<!\w)|(?<=\dQZ))" + re.escape(src) + r"(?:(?!\w)|(?=QZ\d))")
        return rx

    @staticmethod
    def old_term_regex(src: str) -> re.Pattern:
        return re.compile(r"(?<!\w)" + re.escape(src) + r"(?!\w)")

    def load_dict(self, data: dict) -> None:
        exact = data.get("exact", {})
        terms = data.get("terms", {})
        patterns = data.get("patterns", {})
        fem = data.get("feminine", {})
        if not all(isinstance(x, dict) for x in (exact, terms, patterns, fem)):
            raise ValueError("glossary: 'exact', 'terms', 'patterns' and 'feminine' must be objects")
        problems: list[str] = []
        compiled = []
        for k, v in patterns.items():
            k, v = str(k), str(v)
            n = k.count("{X}")
            if n != 1:
                problems.append(f"pattern with {n} {{X}} instead of 1: {k!r}")
                continue
            rx = re.escape(k).replace(re.escape("{X}"), f"(?P<X>{self.WORDS})")
            try:
                compiled.append((re.compile(rx), v))
            except re.error as exc:
                problems.append(f"pattern {k!r}: {exc}")
        self.exact = {str(k): str(v) for k, v in exact.items()}
        terms = {str(k): str(v) for k, v in terms.items()}
        for k in [k for k in terms if not k.strip()]:
            problems.append(f"empty term (translation {terms.pop(k)!r})")
        any_case = data.get("any_case", [])
        if not isinstance(any_case, list):
            problems.append("'any_case' must be a list of words")
            any_case = []
        lower: dict[str, str] = {}
        for k in any_case:
            k = str(k).strip()
            if k not in terms:
                problems.append(f"any_case word without its term: {k!r}")
                continue
            low = k[:1].lower() + k[1:]
            if low != k and low not in terms:
                v = terms[k]
                lower[k] = tr_lower(v[:1]) + v[1:]
        if lower:
            terms = {kk: vv for k, v in terms.items()
                     for kk, vv in ([(k, v)] + ([(k[:1].lower() + k[1:], lower[k])] if k in lower else []))}
        terms.update(self.case_variants(terms))
        self.terms = sorted(terms.items(), key=lambda kv: -len(kv[0]))
        self.term_map = dict(terms)
        self.patterns = sorted(compiled, key=lambda p: -len(p[0].pattern))
        self.feminine = {}
        self.advice = {}
        self.fingerprint = self.fingerprint_of(data)
        self.problems = problems
        if problems:
            log.warning("glossary: %d entries skipped: %s", len(problems), "; ".join(problems[:5]))
        self.version += 1

    @staticmethod
    def fingerprint_of(data: dict) -> str:
        content = {name: {str(k): str(v) for k, v in data.get(name, {}).items()}
                   for name in ("exact", "terms", "patterns")}
        raw = json.dumps(content, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def case_variants(terms: dict[str, str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in terms.items():
            if " " not in k.strip():
                continue
            low = k.lower()
            sentence = k[:1].upper() + k[1:].lower()
            if low != k and low not in terms:
                out[low] = tr_lower(v)
            if sentence not in (k, low) and sentence not in terms:
                out[sentence] = tr_upper(v[:1]) + tr_lower(v[1:])
        return out

    def lookup(self, line: str, keep_items: bool = False) -> str | None:
        if keep_items:
            if line in self.exact:
                return self.exact[line]
            pre, core, post = self.WRAP_RE.fullmatch(line).groups()
            if core in self.exact:
                return pre + self.exact[core] + post
            # If it's a single-word map/city name kept in English in terms (e.g. "Queensdale": "Queensdale")
            if core in self.term_map and self.term_map[core] == core:
                return line
            if is_stat_or_mechanic_line(line) or is_item_or_location_name(line, None):
                return line
        fixed, _ = self._lookup(line)
        if fixed is not None:
            return fixed
        if not plural_name(line):
            return None
        pre, core, post = self.WRAP_RE.fullmatch(line).groups()
        singular = english_singular(core)
        fixed, _ = self._lookup(singular)
        if fixed is None:
            return None
        if fixed == singular:
            return line
        return pre + fixed + post

    def _lookup(self, line: str) -> tuple[str | None, bool]:
        if line in self.exact:
            return self.exact[line], False
        pre, core, post = self.WRAP_RE.fullmatch(line).groups()
        if core in self.exact:
            return pre + self.exact[core] + post, False
        term = self.term_map.get(core)
        if term is not None:
            return pre + term + post, True
        for rx, repl in self.patterns:
            m = rx.fullmatch(core)
            if m:
                return pre + repl.replace("{X}", m.group("X")) + post, False
        return None, False

    def load_file(self, path: Path) -> bool:
        try:
            self.load_dict(json.loads(path.read_text(encoding="utf-8")))
            return True
        except FileNotFoundError:
            return False
        except Exception as exc:  # noqa: BLE001
            log.warning("glossary %s unreadable: %s", path, exc)
            return False


def latest_commit(repo: str, branch: str, what: str = "download") -> str | None:
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/commits/{branch}",
            headers={"User-Agent": "gw2-local-translator", "Accept": "application/vnd.github.sha"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            sha = resp.read(100).decode().strip()
        if re.fullmatch(r"[0-9a-f]{40}", sha):
            return sha
    except Exception as exc:  # noqa: BLE001
        log.debug("%s: latest commit of %s unknown (%s)", what, branch, exc)
    return None


def http_get(url: str, limit: int = MAX_DOWNLOAD, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "gw2-local-translator",
                                               "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(limit + 1)
        length = resp.headers.get("Content-Length")
        encoding = (resp.headers.get("Content-Encoding") or "").strip().lower()
    if len(raw) > limit:
        raise ValueError(f"file larger than {limit} bytes")
    if length and length.strip().isdigit() and int(length) != len(raw):
        raise ValueError(f"download incomplete ({len(raw)} of {int(length)} bytes)")
    if encoding == "gzip":
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        body = d.decompress(raw, limit + 1)
        if len(body) > limit or d.unconsumed_tail:
            raise ValueError(f"file larger than {limit} bytes")
        if not d.eof:
            raise ValueError("download incomplete (gzip data cut short)")
        return body
    if encoding not in ("", "identity"):
        raise ValueError(f"unexpected Content-Encoding {encoding!r}")
    return raw


class GlossaryUpdater(threading.Thread):
    what = "glossary"
    stem = "glossary"

    def __init__(self, glossary: Glossary, data_dir: Path, on_change, url: str) -> None:
        super().__init__(daemon=True, name=f"{self.what}-updater")
        self.glossary, self.on_change, self.url = glossary, on_change, url
        self.path = data_dir / LANG.file(self.stem, ".json")
        self.etag_path = self.path.with_suffix(".etag")
        self.checks = 0

    def run(self) -> None:
        time.sleep(3)
        while True:
            try:
                self.check()
            except Exception as exc:  # noqa: BLE001
                log.info("%s update skipped: %s", self.what, exc)
            self.checks += 1
            time.sleep(UPDATE_INTERVAL)

    def validate(self, data: dict) -> None:
        Glossary().load_dict(data)

    def apply(self, data: dict) -> None:
        self.glossary.load_dict(data)
        self.on_change()
        log.info("glossary updated: %s (%d exact, %d terms)", self.glossary.fingerprint,
                 len(self.glossary.exact), len(self.glossary.terms))

    RAW_RE = re.compile(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/(.+)")

    def current_url(self) -> str:
        m = self.RAW_RE.fullmatch(self.url)
        if not m:
            return self.url
        owner, repo, branch, path = m.groups()
        sha = latest_commit(f"{owner}/{repo}", branch, self.what)
        if sha:
            return f"https://raw.githubusercontent.com/{owner}/{repo}/{sha}/{path}"
        return self.url

    def check(self) -> None:
        req = urllib.request.Request(self.current_url(), headers={"User-Agent": "gw2-local-translator"})
        if self.etag_path.exists() and self.path.exists():
            req.add_header("If-None-Match", self.etag_path.read_text().strip())
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read(MAX_DOWNLOAD + 1)
                etag = resp.headers.get("ETag", "")
                length = resp.headers.get("Content-Length")
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                log.log(logging.DEBUG if self.checks else logging.INFO, "%s up to date", self.what)
                return
            raise
        if len(body) > MAX_DOWNLOAD:
            raise ValueError(f"file larger than {MAX_DOWNLOAD} bytes")
        if length and length.strip().isdigit() and int(length) != len(body):
            raise ValueError(f"download incomplete ({len(body)} of {int(length)} bytes)")
        data = json.loads(body.decode("utf-8"))
        self.validate(data)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, self.path)
        if etag:
            self.etag_path.write_text(etag)
        self.apply(data)


# --------------------------------------------------------------------------- #
# Patch & Pieces
# --------------------------------------------------------------------------- #
class Patch:
    def __init__(self, skip_path: Path | None = None) -> None:
        self.strings: dict[int, str] = {}
        self.auto: dict[int, str] = {}
        self.drop: set[int] = set()
        self.version = 0
        self.glossary_fp = ""
        self.glossary: Glossary | None = None
        self.lock = threading.Lock()
        self.skip_path = skip_path

    @staticmethod
    def _section(data: dict, name: str, required: bool) -> dict[int, str]:
        section = data.get(name, None if required else {})
        if not isinstance(section, dict):
            raise ValueError(f"patch: '{name}' must be an object {{key: text}}")
        out = {}
        for k, v in section.items():
            if not str(k).isdigit() or not isinstance(v, str) or not v.strip():
                raise ValueError(f"patch: bad entry {k!r} in '{name}'")
            out[int(k)] = v
        return out

    @classmethod
    def parse(cls, data: dict) -> tuple[int, dict[int, str], dict[int, str]]:
        strings = cls._section(data, "strings", True)
        auto = {k: v for k, v in cls._section(data, "auto", False).items() if k not in strings}
        return int(data.get("version", 0)), strings, auto

    @staticmethod
    def parse_drop(data: dict) -> set[int]:
        drop = data.get("drop", [])
        if not isinstance(drop, list) or not all(str(k).isdigit() for k in drop):
            raise ValueError("patch: 'drop' must be a list of keys")
        return {int(k) for k in drop}

    @staticmethod
    def parse_glossary(data: dict) -> str:
        fp = data.get("glossary", "")
        if not isinstance(fp, str):
            raise ValueError("patch: 'glossary' must be a string")
        return fp

    def load_dict(self, data: dict) -> None:
        version, strings, auto = self.parse(data)
        drop = self.parse_drop(data) - set(strings) - set(auto)
        fp = self.parse_glossary(data)
        with self.lock:
            self.version, self.strings, self.auto, self.drop = version, strings, auto, drop
            self.glossary_fp = fp

    def load_file(self, path: Path) -> bool:
        try:
            self.load_dict(json.loads(path.read_text(encoding="utf-8")))
            return True
        except FileNotFoundError:
            return False
        except Exception as exc:  # noqa: BLE001
            log.warning("patch %s unreadable: %s", path, exc)
            return False

    def to_dict(self) -> dict:
        with self.lock:
            data = {"version": self.version,
                    "strings": {str(k): self.strings[k] for k in sorted(self.strings)},
                    "auto": {str(k): self.auto[k] for k in sorted(self.auto)}}
            if self.drop:
                data["drop"] = sorted(self.drop)
            if self.glossary_fp:
                data["glossary"] = self.glossary_fp
            return data


PATCH_FORMAT = 1
PIECE_WIDTH = 20_000
PIECE_RE = re.compile(r"p(\d{4,7})\.json")
HASH_RE = re.compile(r"[0-9a-f]{16}")
OUTDATED_HASH = "0" * 16


def hash_int(hex16: str) -> int:
    u = int(hex16, 16)
    return u - (1 << 64) if u >= 1 << 63 else u


def piece_name(number: int) -> str:
    return f"p{number:04d}.json"


def piece_number(name: str) -> int | None:
    m = PIECE_RE.fullmatch(name)
    return int(m.group(1)) if m else None


def parse_index(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("format") != PATCH_FORMAT:
        raise ValueError("patch index: unknown format")
    version, width = data.get("version"), data.get("width")
    if not isinstance(version, int) or version < 0:
        raise ValueError("patch index: bad version")
    if not isinstance(width, int) or width <= 0:
        raise ValueError("patch index: bad width")
    fp = data.get("glossary", "")
    if not isinstance(fp, str):
        raise ValueError("patch index: 'glossary' must be a string")
    pieces = data.get("pieces")
    if not isinstance(pieces, dict):
        raise ValueError("patch index: 'pieces' must be an object")
    out = {}
    for name, info in pieces.items():
        number = piece_number(str(name))
        if number is None or not isinstance(info, dict):
            raise ValueError(f"patch index: bad piece {name!r}")
        sha, size = info.get("sha256"), info.get("size")
        if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError(f"patch index: bad sha256 for {name}")
        if not isinstance(size, int) or not 0 < size <= MAX_DOWNLOAD:
            raise ValueError(f"patch index: bad size for {name}")
        out[name] = (number, sha, size)
    return {"version": version, "glossary": fp, "width": width, "pieces": out}


def parse_piece(data: dict, number: int, width: int
                ) -> tuple[dict[int, str], dict[int, str], set[int], dict[int, str]]:
    if not isinstance(data, dict):
        raise ValueError("patch piece: not an object")
    strings = Patch._section(data, "strings", False)
    auto = {k: v for k, v in Patch._section(data, "auto", False).items() if k not in strings}
    drop = Patch.parse_drop(data) - set(strings) - set(auto)
    raw = data.get("src_hash", {})
    if not isinstance(raw, dict):
        raise ValueError("patch piece: 'src_hash' must be an object")
    hashes = {}
    for k, h in raw.items():
        if not str(k).isdigit() or not isinstance(h, str) or not HASH_RE.fullmatch(h):
            raise ValueError(f"patch piece: bad 'src_hash' entry {k!r}")
        if int(k) in strings or int(k) in auto:
            hashes[int(k)] = h
    low, high = number * width, (number + 1) * width
    for k in (*strings, *auto, *drop):
        if not low <= k < high:
            raise ValueError(f"patch piece {piece_name(number)}: key {k} outside {low}-{high - 1}")
    return strings, auto, drop, hashes


def parse_piece_versions(data: dict) -> dict[int, int]:
    raw = data.get("version", {})
    if not isinstance(raw, dict):
        raise ValueError("patch piece: 'version' must be an object")
    out = {}
    for k, n in raw.items():
        if not str(k).isdigit() or not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ValueError(f"patch piece: bad 'version' entry {k!r}")
        out[int(k)] = n
    return out


# --------------------------------------------------------------------------- #
# Local map & Suggestions
# --------------------------------------------------------------------------- #
def norm(text: str) -> str:
    return html.unescape(text).strip()


SUGGESTIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestions (
    id         INTEGER PRIMARY KEY,
    key        INTEGER NOT NULL,
    en_source  TEXT NOT NULL,
    suggestion_source TEXT,
    suggestion TEXT NOT NULL,
    author     TEXT NOT NULL,
    version    INTEGER NOT NULL,
    src_hash   INTEGER
);
CREATE INDEX IF NOT EXISTS suggestions_key ON suggestions(key, id);
"""


@dataclass(frozen=True)
class Suggestion:
    id: int
    key: int
    en_source: str
    suggestion_source: str | None
    suggestion: str
    author: str
    version: int
    src_hash: int | None


def like_pattern(words: str) -> str:
    escaped = words.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class KeyMap:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.closed = False
        self.con = sqlite3.connect(str(path), timeout=10, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=NORMAL")
        self.con.execute("""CREATE TABLE IF NOT EXISTS texts (
            key INTEGER PRIMARY KEY NOT NULL,
            en TEXT NOT NULL,
            it TEXT,
            how TEXT,
            seen INTEGER)""")
        self._upgrade_suggestions()
        self.con.executescript(SUGGESTIONS_SCHEMA)
        self.con.commit()
        try:
            self.con.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        except sqlite3.Error:
            pass
        self.lock = threading.Lock()

    def _upgrade_suggestions(self) -> None:
        cols = {r[1] for r in self.con.execute("PRAGMA table_info(suggestions)")}
        if "source" in cols:
            self.con.execute("ALTER TABLE suggestions RENAME COLUMN source TO en_source")
        if cols and "suggestion_source" not in cols:
            self.con.execute("ALTER TABLE suggestions ADD COLUMN suggestion_source TEXT")

    def save(self, rows: list[tuple[int, str, str | None, str]]) -> int:
        if not rows:
            return 0
        now = int(time.time())
        with self.lock:
            if self.closed:
                return 0
            with self.con:
                before = self.con.total_changes
                self.con.executemany(
                    "INSERT INTO texts (key, en, it, how, seen) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET en = excluded.en, it = excluded.it, "
                    "how = excluded.how, seen = excluded.seen "
                    "WHERE excluded.how = 'live' OR texts.how = 'backfill'",
                    [(k, en, it, how, now) for k, en, it, how in rows])
                return self.con.total_changes - before

    def count(self) -> int:
        with self.lock:
            return self.con.execute("SELECT count(*) FROM texts").fetchone()[0]

    def get(self, key: int) -> tuple[str, str | None, str | None] | None:
        with self.lock:
            return self.con.execute("SELECT en, it, how FROM texts WHERE key = ?", (key,)).fetchone()

    def search_english(self, words: str, limit: int, exact: bool = False) -> list[int]:
        sql, arg = ("en = ?", words) if exact else ("en LIKE ? ESCAPE '\\'", like_pattern(words))
        with self.lock:
            return [k for (k,) in self.con.execute(
                f"SELECT key FROM texts WHERE {sql} ORDER BY key LIMIT ?", (arg, limit))]

    _SUGG_COLS = "id, key, en_source, suggestion_source, suggestion, author, version, src_hash"

    def add_suggestion(self, key: int, en_source: str, suggestion_source: str | None, text: str,
                       author: str, version: int, src_hash: int | None) -> None:
        with self.lock:
            if self.closed:
                raise RuntimeError("map closed")
            with self.con:
                self.con.execute("INSERT INTO suggestions (key, en_source, suggestion_source, "
                                 "suggestion, author, version, src_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                 (key, en_source, suggestion_source, text, author, version, src_hash))

    def learn_english(self, rows: list[tuple[int, str]]) -> None:
        rows = [(k, en) for k, en in rows if en.strip()]
        if not rows:
            return
        now = int(time.time())
        with self.lock:
            if self.closed:
                return
            with self.con:
                self.con.executemany(
                    "INSERT INTO texts (key, en, it, how, seen) VALUES (?, ?, NULL, 'live', ?) "
                    "ON CONFLICT(key) DO UPDATE SET en = excluded.en, seen = excluded.seen",
                    [(k, en, now) for k, en in rows])
                self.con.executemany("UPDATE suggestions SET en_source = ? WHERE key = ? "
                                     "AND en_source = ''", [(en, k) for k, en in rows])

    def suggestions(self, key: int) -> list[Suggestion]:
        with self.lock:
            if self.closed:
                return []
            return [Suggestion(*r) for r in self.con.execute(
                f"SELECT {self._SUGG_COLS} FROM suggestions WHERE key = ? ORDER BY id DESC", (key,))]

    def suggestion(self, key: int) -> Suggestion | None:
        with self.lock:
            if self.closed:
                return None
            r = self.con.execute(
                f"SELECT {self._SUGG_COLS} FROM suggestions WHERE key = ? ORDER BY id DESC LIMIT 1",
                (key,)).fetchone()
        return Suggestion(*r) if r else None

    def recent_suggestions(self, limit: int = 50) -> list[Suggestion]:
        with self.lock:
            if self.closed:
                return []
            return [Suggestion(*r) for r in self.con.execute(
                f"SELECT {self._SUGG_COLS} FROM suggestions ORDER BY id DESC LIMIT ?", (limit,))]

    def remove_last_suggestion(self, key: int) -> bool:
        with self.lock:
            if self.closed:
                raise RuntimeError("map closed")
            with self.con:
                cur = self.con.execute("DELETE FROM suggestions WHERE id = (SELECT max(id) FROM "
                                       "suggestions WHERE key = ?)", (key,))
            return cur.rowcount > 0

    def close(self) -> None:
        with self.lock:
            if self.closed:
                return
            self.closed = True
            try:
                self.con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                try:
                    self.con.execute("PRAGMA journal_mode=DELETE")
                except sqlite3.Error:
                    pass
            finally:
                self.con.close()


# --------------------------------------------------------------------------- #
# Translators (Primary: Offline CT2 OPUS-MT | Optional: Cloud Backends)
# --------------------------------------------------------------------------- #
class FakeTranslator:
    def translate(self, texts: list[str]) -> list[str]:
        return [f"[{LANG.label}] {t}" for t in texts]


class CT2Translator:
    """Primary Offline Neural Machine Translator (OPUS-MT + CTranslate2)."""

    def __init__(self, model_dir: Path, threads: int) -> None:
        import ctranslate2
        import sentencepiece as spm

        self.tr = ctranslate2.Translator(
            str(model_dir), device="cpu", inter_threads=1, intra_threads=threads
        )
        self.sp_src = spm.SentencePieceProcessor(str(model_dir / "source.spm"))
        self.sp_tgt = spm.SentencePieceProcessor(str(model_dir / "target.spm"))
        self.lock = threading.Lock()

    def translate(self, texts: list[str]) -> list[str]:
        tokens = [self.sp_src.encode(t, out_type=str)[:400] + ["</s>"] for t in texts]
        longest = max(len(t) for t in tokens)
        with self.lock:
            results = self.tr.translate_batch(
                tokens, beam_size=2, max_decoding_length=min(512, longest * 2 + 16)
            )
        return [self.sp_tgt.decode(r.hypotheses[0]) for r in results]


class GoogleTranslator:
    """Optional Cloud Backend: Google Translate Web RPC."""

    def __init__(self, target_lang: str = "tr") -> None:
        self.target_lang = target_lang
        self.lock = threading.Lock()

    def _translate_single(self, text: str) -> str:
        if not text or not text.strip():
            return text
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl="
               + self.target_lang + "&dt=t&q=" + urllib.parse.quote(text))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return "".join(part[0] for part in data[0] if part and part[0])

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        with self.lock:
            try:
                combined = "\n".join(texts)
                url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl="
                       + self.target_lang + "&dt=t&q=" + urllib.parse.quote(combined))
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    translated_all = "".join(part[0] for part in data[0] if part and part[0])
                    lines = translated_all.split("\n")
                    if len(lines) == len(texts):
                        return lines
            except Exception as exc:
                log.warning("Google batch translate fallback: %s", exc)
            out = []
            for t in texts:
                try:
                    out.append(self._translate_single(t))
                except Exception:
                    out.append(t)
            return out


class DeepLTranslator:
    """Optional Cloud Backend: DeepL API."""

    def __init__(self, api_key: str, target_lang: str = "TR") -> None:
        self.api_key = api_key.strip()
        self.target_lang = target_lang.upper()
        self.endpoint = ("https://api-free.deepl.com/v2/translate"
                         if self.api_key.endswith(":fx")
                         else "https://api.deepl.com/v2/translate")
        self.lock = threading.Lock()

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        with self.lock:
            try:
                payload = json.dumps({
                    "text": texts, "source_lang": "EN", "target_lang": self.target_lang
                }).encode("utf-8")
                req = urllib.request.Request(
                    self.endpoint, data=payload,
                    headers={"Authorization": f"DeepL-Auth-Key {self.api_key}",
                             "Content-Type": "application/json", "User-Agent": "gw2-local-translator"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return [item["text"] for item in data.get("translations", [])]
            except Exception as exc:
                log.warning("DeepL translate failed: %s", exc)
                return texts


class GeminiTranslator:
    """Optional Cloud Backend: Google Gemini API."""

    def __init__(self, api_key: str, target_lang: str = "Turkish") -> None:
        self.api_key = api_key.strip()
        self.target_lang = target_lang
        self.endpoint = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                         f"gemini-1.5-flash:generateContent?key={self.api_key}")
        self.lock = threading.Lock()

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        with self.lock:
            prompt = (
                f"You are a professional video game translator for Guild Wars 2.\n"
                f"Translate the following list of English UI/dialogue texts into natural {self.target_lang}.\n"
                f"Keep all game variables and markup untouched (%num1%, %str1%, <c=...>, </c>, <br>, QZ0QZ).\n"
                f"Return ONLY a JSON array of strings of length {len(texts)}.\n\n"
                f"Input JSON: " + json.dumps(texts, ensure_ascii=False)
            )
            try:
                payload = json.dumps({
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json"}
                }).encode("utf-8")
                req = urllib.request.Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    parsed = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
                    if isinstance(parsed, list) and len(parsed) == len(texts):
                        return [str(x) for x in parsed]
            except Exception as exc:
                log.warning("Gemini translate failed: %s", exc)
            return texts


class OpenAITranslator:
    """Optional Cloud Backend: OpenAI API."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", target_lang: str = "Turkish") -> None:
        self.api_key = api_key.strip()
        self.model = model.strip() if model else "gpt-4o-mini"
        self.target_lang = target_lang
        self.endpoint = "https://api.openai.com/v1/chat/completions"
        self.lock = threading.Lock()

    def translate(self, texts: list[str]) -> list[str]:
        if not texts:
            return []
        with self.lock:
            prompt = (
                f"Translate the provided JSON list of Guild Wars 2 English game texts into natural {self.target_lang}.\n"
                f"Keep all placeholders and markup intact (%num1%, %str1%, <c=...>, </c>, <br>, QZ0QZ).\n"
                f"Output JSON: {{\"translations\": [...]}} with exact length {len(texts)}."
            )
            try:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": json.dumps({"texts": texts}, ensure_ascii=False)}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3
                }).encode("utf-8")
                req = urllib.request.Request(
                    self.endpoint, data=payload,
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
                )
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    parsed = json.loads(data["choices"][0]["message"]["content"])
                    translations = parsed.get("translations", [])
                    if isinstance(translations, list) and len(translations) == len(texts):
                        return [str(t) for t in translations]
            except Exception as exc:
                log.warning("OpenAI translate failed: %s", exc)
            return texts


CONFIG_FILE = "config.json"


def get_config(module_dir: Path, lang_dir: Path) -> dict:
    for p in (lang_dir / CONFIG_FILE, module_dir / CONFIG_FILE):
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8-sig"))
            except Exception as exc:
                log.warning("Could not parse %s: %s", p, exc)
    return {}


def ensure_model(model_dir: Path, data_dir: Path, url: str) -> None:
    if (model_dir / "model.bin").is_file():
        return
    log.info("model not found, downloading %s", url)
    headers = {"User-Agent": "gw2-local-translator"}
    sha_req = urllib.request.Request(url + ".sha256", headers=headers)
    with urllib.request.urlopen(sha_req, timeout=30) as resp:
        expected = resp.read(1024).decode().split()[0].lower()

    part = data_dir / "model.zip.part"
    digest = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp, \
            open(part, "wb") as out:
        while chunk := resp.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != expected:
        part.unlink(missing_ok=True)
        raise RuntimeError("model checksum mismatch")

    tmp = model_dir.with_name(model_dir.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with zipfile.ZipFile(part) as zf:
        for member in zf.namelist():
            if not (tmp / member).resolve().is_relative_to(tmp.resolve()):
                raise RuntimeError(f"unsafe path in model zip: {member}")
        zf.extractall(tmp)
    part.unlink(missing_ok=True)
    shutil.rmtree(model_dir, ignore_errors=True)
    os.replace(tmp, model_dir)
    log.info("model installed in %s", model_dir)


class Engine:
    BATCH = 24
    MAX_FAILURES = 2

    def __init__(self, translator, glossary: Glossary, cache_path: Path | None = None,
                 addon_db: Path | None = None, patch=None,
                 keep_items_english: bool = True) -> None:
        self.translator, self.glossary = translator, glossary
        self.keep_items_english = keep_items_english
        self.char_mode: str = "smart"
        self.cache: dict[str, str] = {}
        self.queue: deque[str] = deque()
        self.queued: set[str] = set()
        self.cv = threading.Condition()
        self.cache_path = cache_path
        self.addon_db = addon_db
        self.snapshot_path = cache_path.with_suffix(".glossary.json") if cache_path else None
        self.gen = 0
        self.done_count = 0
        self.patch = patch
        self.finished: list[str] | None = None
        self.failures: dict[str, int] = {}
        self.given_up: set[str] = set()
        self.time_prepare = 0.0
        self.time_model = 0.0
        self._load_cache()
        self.sync_glossary()
        threading.Thread(target=self._work, daemon=True, name="translator-worker").start()

    def _load_cache(self) -> None:
        if not self.cache_path or not self.cache_path.is_file():
            return
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                for row in f:
                    try:
                        item = json.loads(row)
                        self.cache[item["s"]] = item["t"]
                    except Exception:
                        continue
            log.info("cache loaded: %d translations", len(self.cache))
        except OSError as exc:
            log.warning("cache unreadable: %s", exc)

    def _append_cache(self, results: dict[str, str]) -> None:
        if not self.cache_path:
            return
        try:
            with open(self.cache_path, "a", encoding="utf-8") as f:
                for src, dst in results.items():
                    f.write(json.dumps({"s": src, "t": dst}, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("cannot save cache: %s", exc)

    def _rewrite_cache(self) -> None:
        if not self.cache_path:
            return
        tmp = self.cache_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for src, dst in self.cache.items():
                f.write(json.dumps({"s": src, "t": dst}, ensure_ascii=False) + "\n")
        os.replace(tmp, self.cache_path)

    def _read_snapshot(self) -> dict | None:
        try:
            data = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if "terms" not in data or not isinstance(data["terms"], dict):
            data = {"terms": data, "exact": None}
        return {"terms": {str(k): str(v) for k, v in data["terms"].items()},
                "exact": None if data.get("exact") is None else
                {str(k): str(v) for k, v in data["exact"].items()},
                "protect": int(data.get("protect", 1))}

    def outdated(self, line: str, version: int) -> bool:
        return ((version < 9 and recipe_split(line) is not None and "Mini " in line)
                or (version < 6 and RANGE_RE.search(line) is not None)
                or (version < 3 and PLURAL_RE.search(line) is not None)
                or (version < 2 and self._glued_term(line)))

    def _glued_term(self, line: str) -> bool:
        if not TOKEN_RE.search(line):
            return False
        protected = TOKEN_RE.sub("QZ0QZ", line)
        g = self.glossary
        for src, _ in g.terms:
            if src in protected and g.term_regex(src).search(protected) \
                    and not g.old_term_regex(src).search(protected):
                return True
        return False

    def sync_glossary(self) -> None:
        new_terms = dict(self.glossary.terms)
        new_exact = dict(self.glossary.exact)
        purge: set[str] = set()
        english: set[str] = set()
        with self.cv:
            self.gen += 1
            old = self._read_snapshot() if self.snapshot_path else None
            if old is None:
                changed = None
                dropped = len(self.cache)
                self.cache.clear()
            else:
                old_terms = old["terms"]
                changed = {k for k in old_terms.keys() | new_terms.keys()
                           if old_terms.get(k) != new_terms.get(k)}
                old_exact = old["exact"] if old["exact"] is not None else new_exact
                exact_changed = {k for k in old_exact.keys() | new_exact.keys()
                                 if old_exact.get(k) != new_exact.get(k)}
                for k in exact_changed:
                    if k in old_exact:
                        purge.add(old_exact[k])
                    elif k in self.cache:
                        purge.add(self.cache.pop(k))
                dropped = 0
                if changed and self.cache:
                    hit = re.compile("|".join(re.escape(k) for k in
                                              sorted(changed, key=len, reverse=True)))
                    stale = [s for s in self.cache if hit.search(s)]
                    for s in stale:
                        purge.add(self.cache.pop(s))
                    dropped = len(stale)
                changed = changed | exact_changed
                if old["protect"] < PROTECT_VERSION and self.cache:
                    redo = [s for s, t in self.cache.items() if self.outdated(s, old["protect"])
                            or (old["protect"] < 4 and bad_percent(t, s))]
                    for s in redo:
                        purge.add(self.cache.pop(s))
                    dropped += len(redo)
                    if old["protect"] < 7:
                        english = {s for s, t in self.cache.items()
                                   if t == s and self._needs_translation(s)}
                        for s in english:
                            del self.cache[s]
                        dropped += len(english)
                    if old["protect"] < 8:
                        invented = {s: t for s, t in self.cache.items() if self._invented(s, t)}
                        for s in invented:
                            del self.cache[s]
                        english |= set(invented.values())
                        dropped += len(invented)
            upgrade = old is not None and old["protect"] < PROTECT_VERSION
            try:
                if dropped or purge or (changed is None and self.cache_path
                                        and self.cache_path.exists()):
                    self._rewrite_cache()
                if self.snapshot_path and (changed is None or changed or upgrade
                                           or old["exact"] is None):
                    tmp = self.snapshot_path.with_suffix(".tmp")
                    tmp.write_text(json.dumps({"terms": new_terms, "exact": new_exact,
                                               "protect": PROTECT_VERSION},
                                              ensure_ascii=False, indent=0), encoding="utf-8")
                    os.replace(tmp, self.snapshot_path)
            except OSError as exc:
                log.warning("cannot save cache after glossary change: %s", exc)
        if purge:
            self._purge_addon_db(purge)
        if english:
            self._purge_addon_lines(english)

    def _purge_addon_db(self, texts: set[str]) -> None:
        pass

    def _purge_addon_lines(self, lines: set[str]) -> None:
        pass

    @classmethod
    def _invented(cls, line: str, out: str) -> bool:
        if out == line or not cls._needs_translation(line):
            return False
        src = resolve_plural(line)
        return (len(src.split()) <= INVENTED_WORDS
                and invented_piece(src, ADDED_MARKER_RE.sub("", out)))

    @staticmethod
    def _needs_translation(line: str) -> bool:
        if GARBLED_RE.search(line):
            return False
        return re.search(r"[A-Za-z]{2}", TOKEN_RE.sub("", line)) is not None

    def _work(self) -> None:
        while True:
            with self.cv:
                while not self.queue or self.translator is None:
                    self.cv.wait(1.0)
                batch = [self.queue.popleft() for _ in range(min(self.BATCH, len(self.queue)))]
                gen = self.gen
            try:
                results = self._translate_lines(batch)
            except Exception:
                log.exception("translation of a batch failed")
                results = None
            with self.cv:
                if gen != self.gen:
                    self.queue.extendleft(reversed(batch))
                    self.cv.notify_all()
                    continue
                if results is None:
                    results = {}
                    for line in batch:
                        n = self.failures.get(line, 0) + 1
                        if n >= self.MAX_FAILURES:
                            self.failures.pop(line, None)
                            self.given_up.add(line)
                        else:
                            self.failures[line] = n
                else:
                    for line in results:
                        self.failures.pop(line, None)
                self.cache.update(results)
                for line in batch:
                    self.queued.discard(line)
                if self.finished is not None:
                    self.finished.extend(batch)
                self.done_count += len(results)
                self._append_cache(results)
                self.cv.notify_all()

    def _protect(self, line: str) -> tuple[str, dict[str, str]]:
        restore: dict[str, str] = {}

        def stash(match: re.Match) -> str:
            ph = f"QZ{len(restore)}QZ"
            restore[ph] = match.group(0)
            return ph

        protected = TOKEN_RE.sub(stash, RANGE_RE.sub(stash, line))
        g = self.glossary
        for src, dst in g.terms:
            if src not in protected:
                continue
            pattern = g.term_regex(src)

            def stash_term(match: re.Match, dst: str = dst) -> str:
                ph = f"QZ{len(restore)}QZ"
                restore[ph] = dst
                return ph

            protected = pattern.sub(stash_term, protected)
        return protected, restore

    def _translate_lines(self, lines: list[str]) -> dict[str, str]:
        g = self.glossary
        # When keep_items_english is True:
        # - "Recipe: X" translates only "Tarif: " and keeps item name X in original English!
        # - "Mini X" stays "Mini X" in original English!
        # - Plural-marked item/material lines and Title-Case item/location lines stay in original English!
        if self.keep_items_english:
            kept: dict[str, str] = {}
            remaining: list[str] = []
            for line in lines:
                r = recipe_split(line)
                if r is not None:
                    head, name, tail = r
                    if head.endswith("Mini "):
                        kept[line] = line
                    else:
                        kept[line] = head + name + tail
                elif is_stat_or_mechanic_line(line) or is_item_or_location_name(line, g):
                    kept[line] = line
                else:
                    remaining.append(line)
            if not remaining:
                return kept
            lines = remaining
        else:
            kept = {}

        recipes = {line: r for line in lines if (r := recipe_split(line))}
        pieces = {line: p for line in lines if line not in recipes and not plural_name(line)
                  and (p := split_pieces(resolve_plural(line), g)) is not None}
        if not recipes and not pieces:
            out = self._translate_plain(lines)
            out.update(kept)
            return out
        names = [n for n in dict.fromkeys(r[1] for r in recipes.values())
                 if g.lookup(n) is None and n not in self.cache]
        texts = list(dict.fromkeys(t for p in pieces.values() for k, t in p if k == "txt"))
        done = {t: f for t in texts if (f := g.lookup(t)) is not None}
        fixed = set(done)
        done.update({t: self.cache[t] for t in texts if t not in done and t in self.cache})
        whole = [x for x in lines if x not in recipes and x not in pieces]
        results = self._translate_plain(list(dict.fromkeys(
            whole + names + [t for t in texts if t not in done])))
        for line, (head, name, tail) in recipes.items():
            fixed_name = g.lookup(name)
            it = fixed_name if fixed_name is not None else results.get(name, self.cache.get(name, name))
            results[line] = head + recipe_name(head, it, name) + tail
        done.update({t: results[t] for t in texts if t in results})
        for line, parts in pieces.items():
            results[line] = join_pieces(parts, done, fixed)
        keep = set(lines) | set(names)
        final = {k: v for k, v in results.items() if k in keep}
        final.update(kept)
        return final

    def _translate_plain(self, lines: list[str]) -> dict[str, str]:
        results: dict[str, str] = {}
        if not lines:
            return results
        t0 = time.perf_counter()
        srcs = [resolve_plural(line) for line in lines]
        prepared = [self._protect(src) for src in srcs]
        model_idx = [i for i, (p, _) in enumerate(prepared)
                     if re.search(r"[A-Za-z]", re.sub(r"QZ\d+QZ", "", p))]
        t1 = time.perf_counter()
        self.time_prepare += t1 - t0
        try:
            model_outs = self.translator.translate([prepared[i][0] for i in model_idx]) if model_idx else []
        finally:
            self.time_model += time.perf_counter() - t1
        outs = [p for p, _ in prepared]
        for i, out in zip(model_idx, model_outs):
            outs[i] = out
        for line, src, (prot, restore), out in zip(lines, srcs, prepared, outs):
            if (not out.strip() or not all(ph in out for ph in restore)
                    or out.count("%%") < prot.count("%%")):
                results[line] = line
                continue
            for ph, original in restore.items():
                out = out.replace(ph, original)
            if len(src.split()) <= INVENTED_WORDS and invented_piece(src, out):
                results[line] = line
                continue
            if out.endswith(".") and not out.endswith("..") and not line.rstrip().endswith(END_PUNCT):
                out = out[:-1]
            out = feminine(fix_percent(out, line)).replace("i\u0307", "i")
            if LANG.code == "tr":
                mode = getattr(self, "char_mode", "smart")
                out = fix_turkish_chars(out, mode)
            results[line] = out
        return results


# --------------------------------------------------------------------------- #
# Review Export / Import (Developer & Community Tools)
# --------------------------------------------------------------------------- #
REVIEW_COLUMNS = ["key", "english", "current_turkish", "patch_turkish", "new_translation"]


def export_review(map_path: Path, patch_path: Path, out: Path) -> int:
    import csv
    patch = Patch()
    patch.load_file(patch_path)
    english: dict[int, str] = {}
    turkish: dict[int, str] = {}
    if map_path.is_file():
        con = sqlite3.connect(f"file:{map_path}?mode=ro", uri=True)
        try:
            for k, en, it in con.execute("SELECT key, en, it FROM texts"):
                english[k] = en
                turkish[k] = it or ""
        finally:
            con.close()
    turkish.update(patch.auto)
    turkish.update(patch.strings)
    keys = sorted(english.keys() | turkish.keys() | patch.strings.keys())
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(REVIEW_COLUMNS)
        for k in keys:
            w.writerow([k, english.get(k, ""), turkish.get(k, ""), patch.strings.get(k, ""), ""])
    return len(keys)


def dump_patch(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=0, separators=(",", ":")) + "\n"


def _write_patch(patch: Patch, path: Path) -> None:
    data = patch.to_dict()
    for section in ("strings", "auto"):
        data[section] = {k: fix_percent(v) for k, v in data[section].items()}
    Patch.parse(data)
    Patch.parse_glossary(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(dump_patch(data), encoding="utf-8")
    os.replace(tmp, path)


def import_review(review: Path, patch_path: Path) -> tuple[int, int]:
    import csv
    patch = Patch()
    patch.load_file(patch_path)
    changed = removed = 0
    with open(review, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
        for row in csv.DictReader(f, dialect=dialect):
            key = (row.get("key") or "").strip()
            new = row.get("new_translation") or row.get("nuova_traduzione") or ""
            if not key.isdigit() or not new.strip():
                continue
            k = int(key)
            if new.strip() == "-":
                if patch.strings.pop(k, None) is not None:
                    removed += 1
            elif patch.strings.get(k) != new:
                patch.strings[k] = new
                patch.auto.pop(k, None)
                changed += 1
    if changed or removed:
        patch.version += 1
        _write_patch(patch, patch_path)
    return changed, removed
