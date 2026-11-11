<p align="center">
  <a href="README.md">Türkçe</a> • <b>English</b>
</p>

# Guild Wars 2 — Turkish Localization & Mod Installation Hub (GW2-TR)
### Guild Wars 2 Turkish Localization, Neural Translation Engine & Mod Installation Hub

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A complete Turkish localization ecosystem for Guild Wars 2, featuring a **one-click IDE-themed desktop Mod Installation Hub (`GW2_TR_Hub.exe`)**, **in-memory RAM-hook Turkish font & glyph injector**, **offline neural machine translation engine with item/stat/location protection**, and **live translation editor**.

Fully compatible with Steam, Epic Games Store, and the standalone ArenaNet client.

---

## 🌟 Key Features

### 1. 🎛️ IDE-Themed Mod Installation Hub (`GW2_TR_Hub.exe`)
* **1-Click Auto-Detection & Installation:** Automatically locates your Guild Wars 2 directory (Steam, Epic Games, Registry) and installs Raidcore Nexus (`d3d11.dll`), the Text Translator addon, Turkish font injector, and offline translation models with one click.
* **Modern Dark IDE Aesthetics:** Monochromatic dark palette (`#181818`, `#1e1e1e`, `#252526`), Phosphor icon set, and embedded offline Tailwind CSS engine.
* **Interactive Drawer UX:** Click anywhere on mod rows to expand detailed configuration drawers (in-game keybind recorder, engine selector, glyph mode).
* **Built-In About & Community Panel:** Direct access to version information, GitHub repository, and Discord developer contact.

### 2. 🔤 Advanced In-Memory Turkish Font Injector (`turkish_font.dll` & `version.dll`)
* **Zero Modification to Game Data:** Leaves `Gw2.dat` untouched. Hooks the RAM `FileArchive::ReadFile` function to blend 53 RLE-compressed Range-2 Turkish font atlases into the game's native fonts.
* **Dual Character Modes:**
  * **ON (Full Glyph Mode):** All 12 Turkish characters (`Ş, ş, Ğ, ğ, İ, ı, Ç, ç, Ö, ö, Ü, ü`) render with authentic high-resolution glyphs.
  * **OFF (Smart 6-Character Fallback):** Disables font injection and converts only the 6 Range-2 characters that produce box/tofu glyphs (`Ş->S, ş->s, Ğ->G, ğ->g, İ->I, ı->i`), while preserving natively supported `Ç, ç, Ö, ö, Ü, ü`.
* **Automatic Cache Sync:** Toggling character modes automatically converts and restores all cached strings in `cache.db` within seconds.

### 3. 🛡️ Comprehensive Item, Location, Stat, Set & Boon/Condition Protection
Ensures seamless compatibility with the official Wiki, Trading Post, and international team chat via a 3-layer hybrid protection filter:
* **Item Names:** Weapons, armor, materials, trophies remain in original English (e.g. *Berserker's Pearl Broadsword*).
* **Locations & POIs:** Map names, regions, Waypoints, and Points of Interest remain in English (e.g. *Queensdale*, *Lion's Arch*).
* **Attributes & Stats:** `Power`, `Precision`, `Toughness`, `Vitality`, `Ferocity`, `Condition Damage`, `Expertise`, `Concentration`, `Healing Power`, `Agony Resistance`, `Critical Chance`, `Critical Damage`, `Boon Duration`, `Armor`, `Health` and bonus lines (`+120 Power`, `+%num1% Condition Damage`) remain in original English.
* **Stat Sets (Prefixes):** `Berserker's`, `Viper's`, `Marauder's`, `Celestial`, `Diviner's`, `Harrier's`, `Minstrel's`, etc.
* **Boons & Conditions:** `Might`, `Fury`, `Quickness`, `Alacrity`, `Protection`, `Aegis`, `Bleeding`, `Burning`, `Torment`, `Vulnerability`, etc.
* **Dialogues & UI:** Quest descriptions, story dialogues, UI buttons, and guide texts are translated into fluent Turkish.

### 4. 🧠 Offline Neural Translation & Optional Cloud APIs
* **Primary Offline Engine (OPUS-MT):** High-speed local CTranslate2 + SentencePiece model running on your CPU. Zero internet required, zero API costs, zero telemetry, zero latency!
* **Optional Cloud Backends:** Optional integration with Google Translate (free), DeepL, Google Gemini, or OpenAI API keys configurable via the Hub.

### 5. ⌨️ Instant In-Game Toggle Keybind (`ALT + T`)
* Toggle translation on and off with a single keystroke while in-game. Custom keybinds can be recorded directly in the Hub and sync seamlessly with Nexus `InputBinds.json`.

### 6. ✏️ Live & Offline Translation Editor
* **Live Mode:** Access `http://127.0.0.1:8770` in your web browser while the game is running to edit translations on the fly.
* **Offline Mode:** Search, edit, and undo translations in `cache.db`, `map_tr.db`, and `patch_tr.db` directly inside the Hub application even when the game is closed.

---

## 📥 Downloads

Get the latest releases on the [GitHub Releases](../../releases/latest) page:

| File | Size | Description |
| :--- | :--- | :--- |
| 🎛️ **[GW2_TR_Hub.exe](../../releases/latest)** | ~280 MB | **Recommended:** Desktop Mod Installation & Management Hub (1-Click Setup, Live Editor) |
| 📦 **[GW2_TR_v0.12.0_Manuel_Paket.zip](../../releases/latest)** | ~298 MB | **Manual:** Standalone zip package for manual extraction into Guild Wars 2 root directory |
| ⚙️ **[Local_Translator_TR.exe](../../releases/latest)** | ~227 MB | Standalone background translation engine |

---

## 🚀 Installation Guide

### Method 1: GW2-TR Hub 1-Click Setup (Recommended)
1. Download and run **[`GW2_TR_Hub.exe`](../../releases/latest)**.
2. The Hub will automatically detect your Guild Wars 2 folder (or use *"Browse"* to select the folder containing `Gw2-64.exe`).
3. Click **"INSTALL / UPDATE ALL COMPONENTS"**. Raidcore Nexus (`d3d11.dll`), Text Translator, Font Injector, and Offline Turkish models will be installed in seconds.
4. Click **"Launch Guild Wars 2"** to start playing in Turkish!

### Method 2: Manual Installation (Zip)
1. Download **[`GW2_TR_v0.12.0_Manuel_Paket.zip`](../../releases/latest)**.
2. Extract all contents (`d3d11.dll`, `version.dll`, `addons/`) directly into your Guild Wars 2 installation directory (next to `Gw2-64.exe`).
3. Launch the game normally.

---

## 📁 Repository Structure

```
gw2-turkish-localization/
├── assets/                  # Precompiled DLLs, addons, and desktop icons
│   ├── turkish_font.dll     # C++ Range-2 AFNT font injector (53 embedded atlases)
│   ├── version.dll          # Rust early-boot proxy loader
│   ├── d3d11.dll            # Raidcore Nexus Addon Loader
│   ├── text_translator.dll  # Text Translator Nexus addon
│   ├── app_icon.ico         # Multi-size IDE hexagon Windows icon
│   └── app_icon.png         # 1024x1024 transparent PNG logo
├── hub/                     # Desktop Mod Installation Hub (pywebview)
│   ├── app.py               # WebView2 & Nexus IPC bridge, keybind API
│   └── ui/                  # Dark IDE-themed interface (#181818, #1e1e1e)
│       ├── index.html       # 5-tab main UI (Mods, Editor, Downloads, Settings, About)
│       ├── tailwind.js      # Embedded offline Tailwind engine
│       ├── phosphor.css     # Embedded Phosphor icons CSS
│       ├── Phosphor.woff2   # Embedded Phosphor webfont
│       ├── app_icon.png     # Menu logo
│       └── favicon.ico      # Tab icon
├── src/                     # Python translation engine core
│   ├── lt_server.py         # v0.12.0 Turkish-only engine (Stat/Item/Boon protection)
│   ├── lt_module.py         # Text Translator IPC communication module
│   ├── patch_db.py          # SQLite WAL cache and character mode synchronizer
│   ├── editor.py            # Live and offline translation editor
│   ├── map_upload.py        # Map data uploader
│   ├── glossary_tr.default.json
│   └── requirements.txt
├── tools/                   # Maintenance and build utilities
│   ├── make_icon.py         # Hexagon icon generator
│   ├── update_glossary_mechanics.py # Stat & mechanics term updater
│   └── assemble_manual_zip.py       # Standalone manual zip packager
├── TR/                      # Turkish language models and configuration
│   ├── config.json          # Default engine configuration
│   ├── contributor.json     # Developer profile
│   ├── glossary_tr.json     # 3,600+ terms, stats, sets, and boons glossary
│   └── model/               # 35 MB CTranslate2 OPUS-MT local neural model
├── build_all.py             # Single-command build script for all EXEs and DLLs
├── test_gw2_tr.py           # 6/6 test suites (Font, Character, Stat, Cache, Keybind)
└── test_protocol.py         # Nexus Text Translator binary IPC test protocol
```

---

## 🛠️ Building from Source

Requirements: Python 3.10+, Visual Studio C++ Build Tools (or MinGW `g++`), Rust `cargo`.

```powershell
# 1. Install dependencies:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# 2. Run verification tests:
python test_gw2_tr.py
python test_protocol.py

# 3. Build all binaries and packages:
python build_all.py
python tools/assemble_manual_zip.py

# Artifacts are produced in dist/:
# - dist/GW2_TR_Hub.exe
# - dist/Local_Translator_TR.exe
# - dist/GW2_TR_v0.12.0_Manuel_Paket.zip
```

---

## 👥 Credits & Acknowledgments

This project is built upon the invaluable contributions of the open-source community:

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Project architect, Turkish Font Injector (RAM Hook), GW2-TR Hub interface, stat/boon protection filters, and localization coordination. (Discord: `https://discord.com/users/287714928410755072`)
* **[NikeGipple](https://github.com/NikeGipple)**: Upstream [gw2-nexus-local-translator](https://github.com/NikeGipple/gw2-nexus-local-translator) translation engine architecture and in-memory translation protocol.
* **[ideka](https://github.com/ideka)**: Original [Text Translator](https://github.com/ideka/text-translator-public) Nexus addon and [modulep](https://github.com/ideka/modulep) IPC protocol for Guild Wars 2.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) project for `Gw2.dat` AFNT font chunk structure, decompressor analysis, and RAM injection discoveries.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) reverse-engineering tools.
* **[Raidcore Team](https://raidcore.gg/Nexus)**: The incredible Nexus D3D11 Addon Framework for Guild Wars 2.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Offline neural machine translation framework and OPUS-MT Turkish models.

---

## 📜 License & Legal

This project is licensed under the [MIT License](LICENSE).

> **Legal Notice:** Guild Wars 2, ArenaNet, and NCSoft are registered trademarks of their respective owners. This project is an unofficial, community-driven, non-commercial localization and accessibility tool.
