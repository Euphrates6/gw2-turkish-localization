import os
import shutil
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RELEASE_DIR = BASE_DIR / "release_package"
MODULES_DIR = RELEASE_DIR / "addons" / "text_translator" / "modules"

def assemble():
    print("Assembling release package...")

    # 1. Ensure addons and base directories
    (RELEASE_DIR / "addons" / "text_translator").mkdir(parents=True, exist_ok=True)
    MODULES_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Main Turkish Module: local_translator_tr
    main_mod = MODULES_DIR / "local_translator_tr"
    main_mod.mkdir(parents=True, exist_ok=True)

    # Copy onedir executable and _internal
    dist_dir = BASE_DIR / "dist" / "Local_Translator_TR_Light"
    if not dist_dir.exists():
        dist_dir = BASE_DIR / "dist" / "Local_Translator_TR"
    shutil.copy2(dist_dir / "Local_Translator_TR.exe", main_mod / "Local_Translator_TR.exe")
    
    internal_dest = main_mod / "_internal"
    if internal_dest.exists():
        shutil.rmtree(internal_dest)
    shutil.copytree(dist_dir / "_internal", internal_dest)

    # Copy TR folder (config.json, glossary_tr.json)
    tr_dest = main_mod / "TR"
    tr_dest.mkdir(parents=True, exist_ok=True)
    
    glossary_src = BASE_DIR / "glossary" / "glossary_tr.json"
    if not glossary_src.exists():
        glossary_src = BASE_DIR / "src" / "glossary_tr.default.json"
    if glossary_src.exists():
        shutil.copy2(glossary_src, tr_dest / "glossary_tr.json")

    # Copy config.json
    config_data = {
        "backend": "google",
        "deepl_api_key": "",
        "gemini_api_key": "",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "char_mode": "smart",
        "translate_chat": False
    }
    (tr_dest / "config.json").write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Clean up obsolete model directory if present in package
    pkg_model = tr_dest / "model"
    if pkg_model.exists():
        shutil.rmtree(pkg_model)

    # Copy text_translator.dll (Nexus Text Translator addon)
    translator_src = RELEASE_DIR / "addons" / "text_translator.dll"
    if translator_src.exists():
        print(f"Using text_translator.dll from {translator_src}")

    # Copy turkish_font.dll if present
    font_src = BASE_DIR / "font-addon" / "turkish_font.dll"
    font_dest = RELEASE_DIR / "addons" / "turkish_font.dll"
    if font_src.exists():
        shutil.copy2(font_src, font_dest)
        print(f"Copied turkish_font.dll from {font_src}")

    # Copy d3d11.dll (Nexus) if present
    nexus_src = RELEASE_DIR / "d3d11.dll"
    if nexus_src.exists():
        print(f"Using d3d11.dll (Nexus) from {nexus_src}")

    # Copy version.dll (Early-boot Turkish font injector & Nexus bridge loader)
    version_src = BASE_DIR / "loader" / "target" / "release" / "version.dll"
    if version_src.exists():
        shutil.copy2(version_src, RELEASE_DIR / "version.dll")
        print(f"Copied version.dll from {version_src}")
    elif (RELEASE_DIR / "version.dll").exists():
        print(f"Using existing version.dll in {RELEASE_DIR / 'version.dll'}")

    # Main module.toml
    main_toml = """name = "Guild Wars 2 Turkce Yerellestirme"
command = "Local_Translator_TR.exe"
args = ["--lang", "tr"]
"""
    (main_mod / "module.toml").write_text(main_toml, encoding="utf-8")

    # 3. Add Motor_Secici.bat to main module
    bat_content = """@echo off
chcp 65001 >nul
cls
:MENU
echo ============================================================
echo   GUILD WARS 2 TURKCE YERELLESTIRME - CEVIRI MOTORU SECICI
echo ============================================================
echo.
echo   [1] Google Ceviri (Varsayilan, Ucretsiz, Hizli, Sinirsiz)
echo   [2] DeepL API     (Cok Kaliteli Ceviri - API Key Gerekir)
echo   [3] Gemini AI     (Google Gemini 1.5 Flash - API Key Gerekir)
echo   [4] OpenAI GPT    (GPT-4o-mini / GPT-4o - API Key Gerekir)
echo   [5] Ayarlari Ac   (config.json dosyasini duzenle)
echo   [6] Cikis
echo.
echo ============================================================
set /p choice="Seciminizi yapin [1-6]: "

if "%choice%"=="1" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'google'; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo.
    echo [BASARILI] Ceviri motoru GOOGLE CEVIRI olarak ayarlandi!
    timeout /t 2 >nul
    goto MENU
)
if "%choice%"=="2" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'deepl'; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo.
    echo [BASARILI] Ceviri motoru DEEPL API olarak ayarlandi!
    echo NOT: TR\\config.json icinde deepl_api_key alanini doldurmayi unutmayin.
    timeout /t 3 >nul
    goto MENU
)
if "%choice%"=="3" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'gemini'; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo.
    echo [BASARILI] Ceviri motoru GEMINI AI olarak ayarlandi!
    echo NOT: TR\\config.json icinde gemini_api_key alanini doldurmayi unutmayin.
    timeout /t 3 >nul
    goto MENU
)
if "%choice%"=="4" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'openai'; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo.
    echo [BASARILI] Ceviri motoru OPENAI GPT olarak ayarlandi!
    echo NOT: TR\\config.json icinde openai_api_key alanini doldurmayi unutmayin.
    timeout /t 3 >nul
    goto MENU
)
if "%choice%"=="5" (
    notepad.exe TR\\config.json
    goto MENU
)
if "%choice%"=="6" (
    exit
)
goto MENU
"""
    (main_mod / "Ceviri_Motoru_Secici.bat").write_text(bat_content, encoding="utf-8")

    # 4. Create README_TURKCE.txt in main module and release root
    readme_text = """========================================================================
           GUILD WARS 2 TURKCE YERELLESTIRME (ULTRA-LIGHT)
========================================================================

Guild Wars 2 icin gelistirilmis tam kapsamli Turkce font ve ceviri motoru.

[OZELLIKLER]:
1. %100 Orijinal Turkce Font Destegi (version.dll):
   - 156 font boyutunun tamamini kapsayan ozel bellek enjeksiyonu.
   - c, C, g, G, i, I, o, O, s, S, u, U karakterleri orijinal kalitede.

2. Coklu Ceviri Motoru (Backend) Destegi:
   - Google Ceviri (Varsayilan, ucretsiz, limitsiz ve cok hizli).
   - DeepL API (Daha profesyonel ceviri, API key gerektirir).
   - Gemini Yapay Zeka (Google Gemini 1.5 Flash ile dogal ceviri, API key gerektirir).
   - OpenAI GPT (GPT-4o-mini / GPT-4o ile gelismis yapay zeka cevirisi, API key gerektirir).

[KURULUM]:
- GW2_Turkce_Yama.exe (Kurucu Panel) ile tek tikla kurulabilir!
- Veya bu klasordeki tum dosyalari Guild Wars 2 oyununuzun kurulu oldugu
  klasore (Gw2-64.exe dosyasinin yanina) kopyalayabilirsiniz.

Iyi oyunlar dileriz!
========================================================================
"""
    (main_mod / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    (RELEASE_DIR / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")

    # 5. Remove obsolete sibling duplicate module folders to keep package ultra-light
    obsolete_presets = [
        "local_translator_tr_deepl",
        "local_translator_tr_ai",
        "local_translator_tr_openai",
        "local_translator_tr_local",
    ]
    for folder_name in obsolete_presets:
        obsolete_dir = MODULES_DIR / folder_name
        if obsolete_dir.exists():
            shutil.rmtree(obsolete_dir)
            print(f"Removed duplicate module folder: {folder_name}")

    print("Ultra-light assembly complete!")

if __name__ == "__main__":
    assemble()
