<p align="center">
  <a href="README.md">Türkçe</a> • <b>English</b>
</p>

# Guild Wars 2 — Turkish Localization (GW2-TR)
### Guild Wars 2 Turkish Localization & Mod Hub

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An open-source Turkish localization project for Guild Wars 2, offering an offline neural translation engine, in-memory font support, and a simple management hub.

---

## 🌟 Key Features

* **Easy Setup (`GW2_TR_Hub.exe`):** Automatically detects your game directory; installs and updates Raidcore Nexus, the translation engine, and font injector with one click.
* **In-Memory Turkish Font Support:** Enables complete Turkish character (`ç, ğ, ı, ö, ş, ü`) rendering in-game via RAM hooks without modifying game files (`Gw2.dat`).
* **Offline Translation Engine:** Runs on a local neural model (OPUS-MT) with zero internet dependency. Item names and core terms are preserved for gameplay and guide compatibility.
* **Instant Toggle Keybind (`ALT + T`):** Switch between English and Turkish on the fly while in-game. Fully customizable through the Hub interface.
* **Translation Editor:** Edit and fine-tune in-game translations live or offline directly from the Hub interface or your browser.

---

## 📥 Downloads

Get the latest releases on the [GitHub Releases](../../releases/latest) page:

| File | Size | Description |
| :--- | :--- | :--- |
| 🎛️ **[GW2_TR_Hub.exe](../../releases/latest)** | ~280 MB | **Recommended:** Desktop installation hub with mod management and translation editor |
| 📦 **[GW2_TR_v0.12.0_Manuel_Paket.zip](../../releases/latest)** | ~298 MB | **Manual:** Standalone zip package for manual extraction directly into the game root directory |

---

## 🚀 Installation

### Method 1: GW2-TR Hub Setup (Recommended)
1. Download and run **[`GW2_TR_Hub.exe`](../../releases/latest)**.
2. Your game folder is automatically detected (or click *"Browse"* to select the folder containing `Gw2-64.exe`).
3. Click **"INSTALL / UPDATE ALL COMPONENTS"**.
4. Once completed, launch the game and play in Turkish!

### Method 2: Manual Installation (Zip)
1. Download **[`GW2_TR_v0.12.0_Manuel_Paket.zip`](../../releases/latest)**.
2. Extract all contents (`d3d11.dll`, `version.dll`, `addons/`) directly into your Guild Wars 2 root folder (alongside `Gw2-64.exe`).
3. Launch the game normally.

---

## ⌨️ In-Game Keybind

* **`ALT + T`**: Instantly toggles translation on/off. You can customize this hotkey in the `GW2_TR_Hub` settings.

---

## 🛠️ Building from Source

```powershell
# Install dependencies:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# Run verification tests:
python test_gw2_tr.py
python test_protocol.py

# Build distribution packages:
python build_all.py
python tools/assemble_manual_zip.py
```

---

## 👥 Credits & Acknowledgments

This project is built upon the invaluable contributions of the open-source community:

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Project architect, Turkish Font Injector (RAM Hook), GW2-TR Hub interface, and localization coordination. (Discord: `https://discord.com/users/287714928410755072`)
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
