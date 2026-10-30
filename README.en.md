<p align="center">
  <a href="README.md">Türkçe</a> • <b>English</b>
</p>

# Guild Wars 2 Turkish Localization, Font Engine & Universal Addon Loader

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Framework](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.11.0--TR-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A comprehensive **Turkish localization suite, featuring two separate standalone 1-click installers (Offline & Online), a 156-font in-memory font injector**, and an **Epic Games Store / Steam / Standalone compatible universal bridge loader** designed for Guild Wars 2.

It restores and dynamically renders all missing Turkish glyphs (**ç, Ç, ğ, Ğ, ı, İ, ö, Ö, ş, Ş, ü, Ü**) across all 156 font sizes without missing boxes (`[]`) or question marks, while providing real-time in-game translation for dialogues, quests, UI, and story text.

---

## 🚀 Two Separate Editions / İki Ayrı Kurulum Seçeneği

This project is partitioned into **two distinct standalone packages** to cater to different hardware and internet requirements:

| Feature | 🖥️ Offline Edition (Çevrimdışı Sürüm) | ☁️ Online Light Edition (Çevrimiçi Sürüm) |
| :--- | :--- | :--- |
| **Standalone Installer** | `GW2_Turkce_Yama_Cevrimdisi.exe` | `GW2_Turkce_Yama_Cevrimici.exe` |
| **Manual Zip Bundle** | `Local_Translator_Cevrimdisi_TR.zip` (~112 MB) | `Local_Translator_Cevrimici_TR.zip` (~18 MB) |
| **Engine** | **CTranslate2 + OPUS-MT** Local Neural Model | **Google Translate** (Free) / **DeepL** / **Gemini** / **GPT** |
| **Internet Required** | ❌ **Zero Internet** (100% Offline) | ✔️ Requires active internet connection |
| **Translation Latency** | ⚡ **0 ms** (Runs on local CPU) | ~100-300 ms (Web RPC / Cloud API) |
| **API Key / Quota** | ❌ **None needed**, private & unlimited | None for Google; optional API key for AI |
| **Model Included** | ✔️ Pre-packaged OPUS-MT model (Plug & Play) | Cloud-based |
| **Thread Control** | ✔️ Configurable CPU cores (2, 4, 6, 8) | Minimal CPU footprint |

---

## 📥 Download

Download the latest release binaries from GitHub Releases:

* 💻 **[Download GW2_Turkce_Yama_Cevrimdisi.exe (GitHub Releases)](../../releases/latest)** *(Offline 1-Click Installer)*
  * Completely offline, powered by local CTranslate2 & OPUS-MT neural model.
  * No internet, no quotas, zero lag.
* 📦 **[Download Local_Translator_Cevrimdisi_TR.zip](../../releases/latest)** *(Offline Manual Package)*

* ☁️ **[Download GW2_Turkce_Yama_Cevrimici.exe (GitHub Releases)](../../releases/latest)** *(Online Ultra-Light Installer)*
  * Tiny package size (~18 MB).
  * Powered by Google Translate (default, free, unlimited), DeepL, Google Gemini 1.5 Flash, or OpenAI GPT.
* 📦 **[Download Local_Translator_Cevrimici_TR.zip](../../releases/latest)** *(Online Manual Package)*

---

## Key Features

### 1. Standalone 1-Click Installers & Control Panels
* Zero addon management or zip extraction needed by players.
* Automatically detects Steam, Epic Games Store, and ArenaNet Standalone game paths.
* Dedicated configuration: CPU thread selection for Offline edition, multi-backend selector for Online edition.
* 1-click launch game or clean uninstall to restore vanilla game.

### 2. 100% Native Turkish Font Engine (`turkish_font.dll` & `version.dll`)
* Analyzed all **156 font sizes** stored in `Gw2.dat` and dynamically rasterized extended Latin glyphs (Range 2: Latin Extended-A) using vector font rendering (`fontdue`).
* Hooks into the in-memory `FileArchive::ReadFile` routine to inject Turkish character atlases at runtime without modifying game files on disk.
* No need to downgrade or transliterate letters (`s, i, g`); characters render cleanly in the game's authentic visual style.

### 3. Universal Bridge Loader (`version.dll`)
* A lightweight, zero-dependency Rust DLL proxy that bypasses client restrictions where `d3d11.dll` is skipped (notably in **Epic Games Store** `-eglv2` and modern launchers).
* Automatically invoked via `Gw2-64.exe` static import tables during startup; transparently chainloads **Raidcore Nexus**, the **Turkish Font Injector**, and the **Translation Server**.

### 4. Safe & Zero Ban Risk
* Zero physical modifications to `Gw2.dat` or game binaries.
* Adheres strictly to ArenaNet third-party program policies via standard Windows DLL forwarding and the Raidcore Nexus ecosystem.

---

## Quick Installation

### Method 1: 1-Click Installer (Recommended)
1. Download your preferred edition installer (`GW2_Turkce_Yama_Cevrimdisi.exe` or `GW2_Turkce_Yama_Cevrimici.exe`).
2. Run the executable. It will automatically detect your game directory. Click **"Türkçe Yamayı Kur"** (Install).
3. Click **"Oyunu Başlat"** (Launch Game) and enjoy Guild Wars 2 in Turkish!

### Method 2: Manual Installation
1. Download `Local_Translator_Cevrimdisi_TR.zip` or `Local_Translator_Cevrimici_TR.zip` from [**Releases**](../../releases/latest).
2. Extract all contents (`version.dll`, `d3d11.dll`, `addons/`, etc.) directly into your **Guild Wars 2 root directory** (where `Gw2-64.exe` is located).
3. Launch the game normally via Epic Games Launcher, Steam, or the Standalone client.

### Toggling Translation On/Off In-Game (Instant Toggle Keybind)
To view original English item names, skill tooltips, or wiki terms without restarting the game, you can switch between Turkish and English with a single keypress:
1. In-game, press **`Ctrl + O`** to open the Nexus overlay.
2. Navigate to the **`Keybinds`** tab.
3. Locate **`Toggle Show Translated`** under the **Text Translator** header.
4. Click the input box and press your preferred shortcut key (e.g., **`Alt + T`**, **`F11`**, or **`Pause/Break`**).
5. Now, pressing that key in-game instantly toggles translations in real-time.

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
│   ├── lt_server.py         # CTranslate2 / Google / DeepL / Gemini / OpenAI server
│   ├── lt_module.py         # Nexus Text Translator IPC protocol handler
│   └── patch_db.py          # SQLite cache & glossary manager
├── glossary/                # GW2 game terminology & Turkish glossary
│   └── glossary_tr.json
├── TR/
│   ├── config.json          # Default configuration template
│   └── model/               # OPUS-MT Turkish neural model (Offline Edition)
│       ├── model.bin
│       ├── shared_vocabulary.json
│       ├── source.spm
│       ├── target.spm
│       └── config.json
├── installer/               # Modern PySide6 standalone installers & control panels
│   ├── gw2_control_panel.py
│   ├── GW2_Turkce_Yama_Cevrimdisi.spec
│   └── GW2_Turkce_Yama_Cevrimici.spec
├── assemble_release.py      # Dual-target staging script (offline & online)
└── create_zip.py            # Dual-target zip packaging script
```

---

## Building from Source

### 1. Translation Modules (Python / PyInstaller)
```bash
# Offline local edition (bundles CTranslate2):
pyinstaller Local_Translator_TR.spec

# Online ultra-light edition:
pyinstaller Local_Translator_TR_light.spec
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

### 4. Assembling Packages & Building Installers
```bash
# Stage both offline and online packages:
python assemble_release.py --all

# Create distributable zip archives:
python create_zip.py

# Build the standalone installer executables:
pyinstaller --distpath dist installer/GW2_Turkce_Yama_Cevrimdisi.spec
pyinstaller --distpath dist installer/GW2_Turkce_Yama_Cevrimici.spec
```

---

## Credits & Acknowledgments

This project is built upon the invaluable contributions of the open-source and Guild Wars 2 modding communities:

* **[ideka](https://github.com/ideka)**: Original author of the [Text Translator](https://github.com/ideka/text-translator-public) Nexus addon and the [module protocol](https://github.com/ideka/modulep).
* **[NikeGipple](https://github.com/NikeGipple)**: Creator of the [GW2 Local Translator](https://github.com/NikeGipple/gw2-nexus-local-translator) module project and base architecture.
* **[nourlie](https://github.com/nourlie)**: Research on `Gw2.dat` AFNT font chunk structure, decompressor analysis, and memory injection patterns in [GlyphCore](https://github.com/nourlie/GlyphCore).
* **[morluto](https://github.com/morluto)**: Reverse engineering tooling and research via [REA](https://github.com/morluto/rea).
* **[Raidcore Team](https://raidcore.gg/Nexus)**: The incredible Nexus D3D11 Addon Engine for Guild Wars 2.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Offline neural machine translation models.
* **Developer & Turkish Localization:** **[Euphrates6](https://github.com/Euphrates6)** & **Antigravity (Google DeepMind)** — 156-font vector rasterization, Epic Games compatible Rust bridge architecture, AI integration, and full Turkish localization.

---

## License & Legal

This project is licensed under the [MIT License](LICENSE).

> **Disclaimer:** Guild Wars 2, ArenaNet, and NCSoft are registered trademarks of their respective owners. This project is an unofficial, community-driven, non-commercial open-source localization tool not affiliated with ArenaNet.
