<p align="center">
  <a href="README.md">Türkçe</a> • <b>English</b>
</p>

# GW2-TR: Guild Wars 2 Turkish Localization & Mod Manager

[![Game](https://img.shields.io/badge/Game-Guild%20Wars%202-red)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue)]()
[![Framework](https://img.shields.io/badge/Addon%20Loader-Raidcore%20Nexus-orange)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen)](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-gray)](LICENSE)

An open-source mod project for Guild Wars 2 providing an offline neural machine translation engine, in-memory font injection for Turkish characters, and a desktop mod management hub.

---

## Components

The project consists of three core components:

* **Mod Manager (`GW2_TR_Hub.exe`):** Detects game installations, installs Raidcore Nexus addons (`d3d11.dll`, `version.dll`), configures hotkeys, and manages translation settings.
* **Turkish Font Injector (`turkish_font.dll`):** Injects Turkish character rendering (`ç, ğ, ı, ö, ş, ü`) into game memory (RAM) at runtime without altering game data files (`Gw2.dat`).
* **Local Translation Engine (`Local_Translator_TR.exe`):** Runs locally via CTranslate2 and OPUS-MT models. Item names, map locations, and gameplay attributes (stats, boons, conditions) are preserved in English for wiki and community compatibility, while dialogues and quest text are translated into Turkish.

---

## Installation

### Method 1: Automated Setup via GW2-TR Hub (Recommended)

1. Download and run `GW2_TR_Hub.exe` from [Releases](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest).
2. The application will detect your game folder automatically. If not found, select the folder containing `Gw2-64.exe` manually.
3. Click "Install / Update Components".
4. Launch the game once installation is complete.

### Method 2: Manual Installation

1. Download `GW2_TR_v0.12.0_Manuel_Paket.zip` from [Releases](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest).
2. Extract all contents (`d3d11.dll`, `version.dll`, `addons/`) directly into your Guild Wars 2 root folder (alongside `Gw2-64.exe`).
3. Launch the game normally.

---

## Usage & Hotkeys

* **`ALT + T`**: Toggles translation on/off in-game. The hotkey can be remapped via `GW2_TR_Hub`.
* **Translation Editor:** Access `http://127.0.0.1:8770` in your web browser while the game is running, or use the Editor tab in `GW2_TR_Hub` to inspect and modify translation entries.

---

## Building from Source

Requirements: Python 3.10+, Visual Studio C++ Build Tools (or MinGW `g++`), Rust toolchain (`cargo`).

```powershell
# Dependencies:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# Run tests:
python test_gw2_tr.py
python test_protocol.py

# Build binaries:
python build_all.py
python tools/assemble_manual_zip.py
```

---

## Credits & Acknowledgments

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Project architecture, RAM-Hook C++ Font Injector, GW2-TR Hub interface, and localization coordination. (Discord: `https://discord.com/users/287714928410755072`)
* **[NikeGipple](https://github.com/NikeGipple)**: Upstream [gw2-nexus-local-translator](https://github.com/NikeGipple/gw2-nexus-local-translator) translation engine architecture and IPC protocol.
* **[ideka](https://github.com/ideka)**: Original [Text Translator](https://github.com/ideka/text-translator-public) Nexus addon and [modulep](https://github.com/ideka/modulep) IPC protocol for Guild Wars 2.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) project for `Gw2.dat` AFNT font chunk analysis and memory injection research.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) reverse-engineering tools.
* **[Raidcore Team](https://raidcore.gg/Nexus)**: The Nexus D3D11 Addon Framework for Guild Wars 2.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Offline neural machine translation framework and OPUS-MT models.

---

## License

Distributed under the [MIT License](LICENSE).

*Legal Notice: Guild Wars 2, ArenaNet, and NCSoft are registered trademarks of their respective owners. This project is not affiliated with ArenaNet or NCSoft.*
