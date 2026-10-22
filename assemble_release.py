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
    dist_dir = BASE_DIR / "dist" / "Local_Translator_TR"
    shutil.copy2(dist_dir / "Local_Translator_TR.exe", main_mod / "Local_Translator_TR.exe")
    
    internal_dest = main_mod / "_internal"
    if internal_dest.exists():
        shutil.rmtree(internal_dest)
    shutil.copytree(dist_dir / "_internal", internal_dest)

    # Copy TR folder (config.json, glossary_tr.json, model/)
    tr_dest = main_mod / "TR"
    tr_dest.mkdir(parents=True, exist_ok=True)
    
    glossary_src = BASE_DIR / "release_package" / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR" / "glossary_tr.json"
    glossary_dst = tr_dest / "glossary_tr.json"
    if glossary_src.resolve() != glossary_dst.resolve() and glossary_src.exists():
        shutil.copy2(glossary_src, glossary_dst)

    # Copy config.json
    config_data = {
        "backend": "google",
        "deepl_api_key": "",
        "gemini_api_key": "",
        "openai_api_key": "",
        "openai_model": "gpt-4o-mini",
        "char_mode": "off",
        "translate_chat": False
    }
    (tr_dest / "config.json").write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")

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

    # Copy model
    model_src = BASE_DIR / "TR" / "model"
    model_dest = tr_dest / "model"
    if not model_dest.exists() and model_src.exists():
        shutil.copytree(model_src, model_dest)
        print(f"Copied model from {model_src}")

    # Main module.toml
    main_toml = """name = "Turkce (Google Ceviri - Varsayilan)"
command = "Local_Translator_TR.exe"
args = ["--lang", "tr", "--backend", "google"]
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
echo   [5] Yerel Model   (Tamamen Offline, Bilgisayarda Calisir)
echo   [6] Ayarlari Ac   (config.json dosyasini duzenle)
echo   [7] Cikis
echo.
echo ============================================================
set /p choice="Seciminizi yapin [1-7]: "

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
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'local'; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo.
    echo [BASARILI] Ceviri motoru YEREL MODEL olarak ayarlandi!
    timeout /t 2 >nul
    goto MENU
)
if "%choice%"=="6" (
    notepad.exe TR\\config.json
    goto MENU
)
if "%choice%"=="7" (
    exit
)
goto MENU
"""
    (main_mod / "Ceviri_Motoru_Secici.bat").write_text(bat_content, encoding="utf-8")

    # 4. Create README_TURKCE.txt in main module and release root
    readme_text = """========================================================================
           GUILD WARS 2 TURKCE YERELLESTIRME MODU (NEXUS)
========================================================================

Bu mod, Raidcore Nexus uzerinden calisan 'Text Translator' eklentisini
kullanarak Guild Wars 2 oyununu anlik olarak Turkceye cevirir.

[YAPILAN IYILESTIRMELER]:
1. Tam Orijinal Turkce Font Enjeksiyonu (version.dll):
   - Gw2-64.exe calistigi ilk mikrosaniyede devreye giren ozel kanca sayesinde,
     oyundaki 156 font boyutunun tamamina Latin Extended-A atlaslari enjekte edilir.
   - Harfleri kirpmaya veya degistirmeye gerek kalmadan tum Turkce karakterler
     (c, C, g, G, i, I, o, O, s, S, u, U) %100 orijinal ve dogal gorunur (char_mode: off).

2. Coklu Ceviri Motoru (Backend) Destegi:
   - Google Ceviri (Varsayilan, ucretsiz, limitsiz ve cok hizli).
   - DeepL API (Daha profesyonel ceviri, API key gerektirir).
   - Gemini Yapay Zeka (Google Gemini 1.5 Flash ile dogal ceviri, API key gerektirir).
   - OpenAI GPT (GPT-4o-mini / GPT-4o ile gelismis yapay zeka cevirisi, API key gerektirir).
   - Yerel Offline Model (Internet gerektirmeyen cihaz ici makine cevirisi).

[KURULUM]:
1. Bu zip icerisindeki "addons" klasorunu, Guild Wars 2 oyununuzun kurulu
   oldugu ana klasore (Gw2-64.exe dosyasinin yanina) kopyalayin.
2. Eger Nexus mod yukleyiciniz kuruluysa baska hicbir sey yapmaniza gerek yoktur.
3. Oyunu baslatin.

[CEVIRI MOTORUNU DEGISTIRME]:
- Yontem 1: addons\\text_translator\\modules\\local_translator_tr\\ klasorundeki
  "Ceviri_Motoru_Secici.bat" dosyasini cift tiklayarak tek tusla degistirebilirsiniz.
- Yontem 2: "TR\\config.json" dosyasini Not Defteri ile acip "backend" degerini
  "google", "deepl", "gemini", "openai" veya "local" yapabilirsiniz.
- Yontem 3: Oyun icinde Nexus menusu (varsayilan Alt+Shift+T veya ~ tusu) ->
  Text Translator -> Modules kismindan istediginiz motoru secip baslatabilirsiniz.

[OYUN ICINDE CEVIRIYI ACIP KAPATMA (TOGGLE KISAYOLU)]:
Orijinal Ingilizce terimleri gormek istediginizde oyunu kapatmadan aninda
Turkce ile Ingilizce arasinda gecis yapabilirsiniz:
1. Oyun icinde klavyenizden "Ctrl + O" tusuna basarak Nexus menusunu acin.
2. Ust kisimdaki "Keybinds" sekmesine gelin.
3. Listeden "Text Translator" altindaki "Toggle Show Translated" secenegini bulun.
4. Yanindaki kutucuga tiklayip istediginiz bir tusu (ornek: Alt + T veya F11) atayin.
5. Artik bu tusa her bastiginizda oyun anlik olarak Turkce ve Ingilizce arasinda degisir!

Iyi oyunlar dileriz!
========================================================================
"""
    (main_mod / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    (RELEASE_DIR / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")

    # 5. Sibling module presets (DeepL, Gemini AI, OpenAI GPT, Offline Local)
    onefile_exe = BASE_DIR / "dist" / "Local_Translator_TR_onefile.exe"
    
    presets = [
        ("local_translator_tr_deepl", "Turkce (DeepL API)", "deepl"),
        ("local_translator_tr_ai", "Turkce (Yapay Zeka - Gemini)", "gemini"),
        ("local_translator_tr_openai", "Turkce (Yapay Zeka - OpenAI GPT)", "openai"),
        ("local_translator_tr_local", "Turkce (Cevrimdisi Model)", "local"),
    ]

    for folder_name, display_name, backend_name in presets:
        p_dir = MODULES_DIR / folder_name
        p_dir.mkdir(parents=True, exist_ok=True)
        # copy onefile exe as Local_Translator_TR.exe
        shutil.copy2(onefile_exe, p_dir / "Local_Translator_TR.exe")
        toml = f"""name = "{display_name}"
command = "Local_Translator_TR.exe"
args = ["--lang", "tr", "--backend", "{backend_name}", "--lang-dir", "../local_translator_tr/TR"]
"""
        (p_dir / "module.toml").write_text(toml, encoding="utf-8")

    print("Assembly complete!")

if __name__ == "__main__":
    assemble()
