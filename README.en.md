<p align="center">
  <a href="README.md">Türkçe</a> • <b>English</b>
</p>

# Guild Wars 2 Turkish Localization, Font Engine & Universal Addon Loader

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Framework](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.10.0--TR-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive **Turkish localization suite, a 156-font in-memory font injector**, and an **Epic Games Store / Steam / Standalone compatible universal bridge loader** designed for Guild Wars 2.

It restores and dynamically renders all missing Turkish glyphs (**ç, Ç, ğ, Ğ, ı, İ, ö, Ö, ş, Ş, ü, Ü**) across all 156 font sizes without missing boxes (`[]`) or question marks, while providing real-time in-game translation for dialogues, quests, UI, and story text.

---

## Download

To download the latest, all-in-one, ready-to-play release:

[**Download Local_Translator_0.10.0_TR.zip (GitHub Releases)**](../../releases/latest) *(~267 MB)*

---

## Key Features

### 1. 100% Native Turkish Font Engine (`turkish_font.dll`)
* Analyzed all **156 font sizes** stored in `Gw2.dat` and dynamically rasterized extended Latin glyphs (Range 2: Latin Extended-A) using vector font rendering (`fontdue`).
* Hooks into the in-memory `FileArchive::ReadFile` routine to inject Turkish character atlases at runtime without modifying game files on disk.
* No need to downgrade or transliterate letters (`s, i, g`); characters render cleanly in the game's authentic visual style.

### 2. Universal Bridge Loader (`version.dll`)
* A lightweight, zero-dependency Rust DLL proxy that bypasses client restrictions where `d3d11.dll` is skipped (notably in **Epic Games Store** `-eglv2` and modern launchers).
* Automatically invoked via `Gw2-64.exe` static import tables during startup; transparently chainloads **Raidcore Nexus**, the **Turkish Font Injector**, and the **Translation Server**.

### 3. Multi-Backend Translation Engines
Switch translation backends with a single click depending on your preference and hardware:
* **Google Translate (Default):** 100% free, unlimited, fast, and requires zero API setup.
* **DeepL API:** High-precision, context-aware game translation (requires Free or Pro API key).
* **Google Gemini AI:** Fluid, natural translations powered by Google Gemini 1.5 Flash.
* **OpenAI GPT:** Supports GPT-4o-mini and GPT-4o.
* **Offline Local Model:** Zero internet dependency running locally on-device via Helsinki-NLP Opus-MT and CTranslate2.

### 4. Safe & Zero Ban Risk
* Zero physical modifications to `Gw2.dat` or game binaries.
* Adheres strictly to ArenaNet third-party program policies via standard Windows DLL forwarding and the Raidcore Nexus ecosystem.

---

## Quick Installation

1. Download `Local_Translator_0.10.0_TR.zip` from the [**Releases**](../../releases/latest) page.
2. Extract all contents (`version.dll`, `d3d11.dll`, `addons/`, etc.) directly into your **Guild Wars 2 root directory** (where `Gw2-64.exe` is located).
3. Launch the game normally via Epic Games Launcher, Steam, or the Standalone client.
4. In-game, press **`Ctrl + O`** (or click the Nexus icon in the top-left corner) to open the Nexus overlay and manage addons.

### Switching Translation Engines
Open `addons\text_translator\modules\local_translator_tr\` and run **`Ceviri_Motoru_Secici.bat`** to switch between Google, DeepL, Gemini, OpenAI, or the Offline model with a single keystroke.

---

## Repository Architecture

```
gw2-turkish-localization/
├── loader/                  # Zero-dependency Rust version.dll proxy bridge
│   ├── Cargo.toml
│   └── src/lib.rs
├── font-addon/              # C++ in-memory AFNT font injector (turkish_font.dll)
│   ├── main.cpp
│   ├── Nexus.h
│   └── resource.rc
├── src/                     # Python translation server & multi-engine adapters
│   ├── lt_server.py         # Google / DeepL / Gemini / OpenAI / Opus-MT server
│   ├── lt_module.py         # Nexus Text Translator IPC protocol handler
│   └── patch_db.py          # SQLite cache & glossary manager
├── glossary/                # GW2 game terminology & Turkish glossary
│   └── glossary_tr.json
├── TR/                      # Default configuration templates
│   └── config.json
├── assemble_release.py      # Automated packaging and staging pipeline
└── create_zip.py            # Release zip builder
```

---

## Building from Source

### 1. Translation Module (Python)
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller Local_Translator_TR.spec
```

### 2. Bridge Loader (Rust)
```bash
cd loader
cargo build --release
# Output: loader/target/release/version.dll
```

### 3. Font Addon (C++)
```bash
cd font-addon
windres resource.rc -O coff -o resource.res
g++ -O3 -shared main.cpp resource.res -o turkish_font.dll -lucrt -lkernel32
```

To package everything into a release bundle:
```bash
python assemble_release.py
python create_zip.py
```

---

## Credits & Acknowledgments

This project is built upon the invaluable contributions of the open-source and Guild Wars 2 modding communities:

* **[ideka](https://github.com/ideka)**: Original creator of the [Text Translator](https://github.com/ideka/text-translator-public) Nexus addon and the [GW2 Local Translator](https://github.com/ideka/gw2-local-translator) module architecture.
* **[nourlie](https://github.com/nourlie)**: Research on `Gw2.dat` AFNT font chunk structure, decompressor analysis, and memory injection patterns in [GlyphCore](https://github.com/nourlie/GlyphCore).
* **[morluto](https://github.com/morluto)**: Reverse engineering tooling and research via [REA](https://github.com/morluto/rea).
* **[Raidcore Team](https://raidcore.gg/Nexus)**: The incredible Nexus D3D11 Addon Engine for Guild Wars 2.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Offline neural machine translation models.
* **Developer & Turkish Localization:** **[Euphrates6](https://github.com/Euphrates6)** & **Antigravity (Google DeepMind)** — 156-font vector rasterization, Epic Games compatible Rust bridge architecture, AI integration, and full Turkish localization.

---

## License & Legal

This project is licensed under the [MIT License](LICENSE).

> **Disclaimer:** Guild Wars 2, ArenaNet, and NCSoft are registered trademarks of their respective owners. This project is an unofficial, community-driven, non-commercial open-source localization tool not affiliated with ArenaNet.
