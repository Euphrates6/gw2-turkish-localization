import os
import sys
import shutil
import json
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def find_file(candidates: list[Path]) -> Path | None:
    for c in candidates:
        if c.exists():
            return c
    return None

def copy_shared_components(target_root: Path):
    """Copies Nexus d3d11.dll, early-boot version.dll, text_translator.dll, and turkish_font.dll."""
    target_root.mkdir(parents=True, exist_ok=True)
    addons_dir = target_root / "addons"
    addons_dir.mkdir(parents=True, exist_ok=True)

    # 1. d3d11.dll (Nexus)
    d3d11_candidates = [
        BASE_DIR / "release_package" / "d3d11.dll",
        BASE_DIR / "release_package_online" / "d3d11.dll",
        BASE_DIR / "release_package_offline" / "d3d11.dll",
        Path("E:/GuildWars2/d3d11.dll"),
    ]
    d3d11_src = find_file(d3d11_candidates)
    if d3d11_src:
        shutil.copy2(d3d11_src, target_root / "d3d11.dll")
        print(f"  [OK] Copied d3d11.dll from {d3d11_src}")
    else:
        print("  [WARN] d3d11.dll not found!")

    # 2. version.dll (Nexus bridge loader & early font injector)
    version_candidates = [
        BASE_DIR / "loader" / "target" / "release" / "version.dll",
        BASE_DIR / "release_package" / "version.dll",
        BASE_DIR / "release_package_online" / "version.dll",
        BASE_DIR / "release_package_offline" / "version.dll",
        Path("E:/GuildWars2/version.dll"),
    ]
    version_src = find_file(version_candidates)
    if version_src:
        shutil.copy2(version_src, target_root / "version.dll")
        print(f"  [OK] Copied version.dll from {version_src}")
    else:
        print("  [WARN] version.dll not found!")

    # 3. text_translator.dll (Nexus Text Translator addon)
    translator_candidates = [
        BASE_DIR / "release_package" / "addons" / "text_translator.dll",
        BASE_DIR / "release_package_online" / "addons" / "text_translator.dll",
        BASE_DIR / "release_package_offline" / "addons" / "text_translator.dll",
        Path("E:/GuildWars2/addons/text_translator.dll"),
    ]
    translator_src = find_file(translator_candidates)
    if translator_src:
        shutil.copy2(translator_src, addons_dir / "text_translator.dll")
        print(f"  [OK] Copied text_translator.dll from {translator_src}")
    else:
        print("  [WARN] text_translator.dll not found!")

    # 4. turkish_font.dll (In-memory AFNT font injector)
    font_candidates = [
        BASE_DIR / "font-addon" / "turkish_font.dll",
        BASE_DIR / "release_package" / "addons" / "turkish_font.dll",
        BASE_DIR / "release_package_online" / "addons" / "turkish_font.dll",
        BASE_DIR / "release_package_offline" / "addons" / "turkish_font.dll",
        Path("E:/GuildWars2/addons/turkish_font.dll"),
    ]
    font_src = find_file(font_candidates)
    if font_src:
        shutil.copy2(font_src, addons_dir / "turkish_font.dll")
        print(f"  [OK] Copied turkish_font.dll from {font_src}")
    else:
        print("  [WARN] turkish_font.dll not found!")


def assemble_offline(target_dir: Path | None = None):
    """Assembles the 100% offline local machine translation release package (CTranslate2 + OPUS-MT)."""
    if target_dir is None:
        target_dir = BASE_DIR / "release_package_offline"

    print(f"\n=======================================================")
    print(f" Assembling ÇEVRİMDIŞI (Offline Local) Release Package: {target_dir}")
    print(f"=======================================================")

    main_mod = target_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"
    main_mod.mkdir(parents=True, exist_ok=True)

    # 1. Copy Shared Components (d3d11.dll, version.dll, text_translator.dll, turkish_font.dll)
    copy_shared_components(target_dir)

    # 2. Copy Full Offline Binary (CTranslate2 bundled)
    dist_dir = BASE_DIR / "dist" / "Local_Translator_TR"
    if not dist_dir.exists():
        dist_dir = Path("C:/Users/firat/.gemini/antigravity-ide/scratch/gw2-local-translator-tr/dist/Local_Translator_TR")

    if not dist_dir.exists():
        raise FileNotFoundError(f"Offline binary directory not found at {dist_dir}!")

    print(f"  [+] Copying offline binary from {dist_dir}...")
    shutil.copy2(dist_dir / "Local_Translator_TR.exe", main_mod / "Local_Translator_TR.exe")
    
    internal_dest = main_mod / "_internal"
    if internal_dest.exists():
        shutil.rmtree(internal_dest)
    shutil.copytree(dist_dir / "_internal", internal_dest)

    # 3. Copy TR folder: glossary_tr.json and offline model
    tr_dest = main_mod / "TR"
    tr_dest.mkdir(parents=True, exist_ok=True)

    glossary_src = BASE_DIR / "glossary" / "glossary_tr.json"
    if not glossary_src.exists():
        glossary_src = BASE_DIR / "src" / "glossary_tr.default.json"
    if glossary_src.exists():
        shutil.copy2(glossary_src, tr_dest / "glossary_tr.json")
        print(f"  [+] Copied glossary from {glossary_src}")

    # Copy Offline OPUS-MT Turkish Model
    model_src = BASE_DIR / "TR" / "model"
    if not (model_src / "model.bin").exists():
        model_src = Path("C:/Users/firat/.gemini/antigravity-ide/scratch/gw2-local-translator-tr/TR/model")

    if (model_src / "model.bin").exists():
        model_dest = tr_dest / "model"
        if model_dest.exists():
            shutil.rmtree(model_dest)
        shutil.copytree(model_src, model_dest)
        print(f"  [+] Bundled OPUS-MT Turkish model from {model_src} ({sum(f.stat().st_size for f in model_dest.glob('*')) / (1024*1024):.1f} MB)")
    else:
        print("  [WARN] OPUS-MT model directory not found! Make sure TR/model contains model.bin.")

    # 4. Write offline config.json
    config_data = {
        "backend": "local",
        "threads": 4,
        "char_mode": "smart",
        "translate_chat": False
    }
    (tr_dest / "config.json").write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # 5. Write module.toml
    module_toml = """name = "Guild Wars 2 Turkce (Cevrimdisi - Local PC)"
command = "Local_Translator_TR.exe"
args = ["--lang", "tr", "--backend", "local", "--no-update"]
"""
    (main_mod / "module.toml").write_text(module_toml, encoding="utf-8")

    # 6. Motor_Secici.bat
    bat_content = """@echo off
chcp 65001 >nul
cls
:MENU
echo ============================================================
echo   GW2 TURKCE YERELLESTIRME (CEVRIMDISI SURUM) - MOTOR AYARI
echo ============================================================
echo.
echo   Bu surum TAMAMEN CEVRIMDISI olarak bilgisayarinizda calisir.
echo   Internet baglantisi veya herhangi bir API key gerektirmez.
echo.
echo   [1] CTranslate2 Yerel Model (Varsayilan, 4 Cekirdek)
echo   [2] CTranslate2 Yerel Model (Dusuk CPU, 2 Cekirdek)
echo   [3] CTranslate2 Yerel Model (Yuksek Hiz, 6 Cekirdek)
echo   [4] Ayarlari Ac (config.json)
echo   [5] Cikis
echo.
echo ============================================================
set /p choice="Seciminizi yapin [1-5]: "

if "%choice%"=="1" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'local'; $c.threads = 4; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo [BASARILI] 4 Cekirdek olarak ayarlandi!
    timeout /t 2 >nul
    goto MENU
)
if "%choice%"=="2" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'local'; $c.threads = 2; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo [BASARILI] 2 Cekirdek olarak ayarlandi!
    timeout /t 2 >nul
    goto MENU
)
if "%choice%"=="3" (
    powershell -Command "$c = Get-Content 'TR\\config.json' | ConvertFrom-Json; $c.backend = 'local'; $c.threads = 6; $c | ConvertTo-Json | Set-Content 'TR\\config.json'"
    echo [BASARILI] 6 Cekirdek olarak ayarlandi!
    timeout /t 2 >nul
    goto MENU
)
if "%choice%"=="4" (
    notepad.exe TR\\config.json
    goto MENU
)
if "%choice%"=="5" (
    exit
)
goto MENU
"""
    (main_mod / "Ceviri_Motoru_Secici.bat").write_text(bat_content, encoding="utf-8")

    # 7. README_TURKCE.txt
    readme_text = """========================================================================
         GUILD WARS 2 TURKCE YERELLESTIRME (CEVRIMDISI SURUM)
========================================================================

Guild Wars 2 icin gelistirilmis %100 yerel ve cevrimdisi calisan Turkce
yerellestirme, font motoru ve yapay zeka makine cevirisi.

[OZELLIKLER]:
1. Gelismis Turkce Font ve Karakter Destegi (version.dll + turkish_font.dll):
   - Bellek ici ozel font enjeksiyonu ve genisletilmis karakter destegi.
   - Akilli karakter modu (smart) ile arayuzdeki olasi harf kayiplari engellenir.

2. Tamamen Cevrimdisi Makine Cevirisi (CTranslate2 + OPUS-MT):
   - Internet baglantisi gerektirmez; tamamen cevrimdisi calisir.
   - Herhangi bir API anahtari, abonelik veya kota siniri yoktur.
   - Oyun metinleri aninda bilgisayarinizin islemcisinde cevrilir.
   - Orijinal GW2 terimler sozrugu (glossary) dahildir.

[KURULUM]:
- GW2_Turkce_Yama_Cevrimdisi.exe ile tek tikla kurulabilir!
- Veya bu klasordeki tum dosyalari Guild Wars 2 oyununuzun ana klasorune
  (Gw2-64.exe dosyasinin yanina) kopyalayabilirsiniz.

Iyi oyunlar dileriz!
========================================================================
"""
    (main_mod / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    (target_dir / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    print(f"  [DONE] Çevrimdışı paket hazırlandı: {target_dir}")


def assemble_online(target_dir: Path | None = None):
    """Assembles the ultra-lightweight online translation release package (Google / DeepL / Gemini / OpenAI)."""
    if target_dir is None:
        target_dir = BASE_DIR / "release_package_online"

    print(f"\n=======================================================")
    print(f" Assembling ÇEVRİMİÇİ (Online Ultra-Light) Release Package: {target_dir}")
    print(f"=======================================================")

    main_mod = target_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"
    main_mod.mkdir(parents=True, exist_ok=True)

    # 1. Copy Shared Components
    copy_shared_components(target_dir)

    # 2. Copy Ultra-Light Binary
    dist_dir = BASE_DIR / "dist" / "Local_Translator_TR_Light"
    if not dist_dir.exists():
        dist_dir = BASE_DIR / "dist" / "Local_Translator_TR"

    if not dist_dir.exists():
        raise FileNotFoundError(f"Light binary directory not found at {dist_dir}!")

    print(f"  [+] Copying online light binary from {dist_dir}...")
    shutil.copy2(dist_dir / "Local_Translator_TR.exe", main_mod / "Local_Translator_TR.exe")
    
    internal_dest = main_mod / "_internal"
    if internal_dest.exists():
        shutil.rmtree(internal_dest)
    shutil.copytree(dist_dir / "_internal", internal_dest)

    # 3. Copy TR folder: glossary_tr.json (No model)
    tr_dest = main_mod / "TR"
    tr_dest.mkdir(parents=True, exist_ok=True)

    glossary_src = BASE_DIR / "glossary" / "glossary_tr.json"
    if not glossary_src.exists():
        glossary_src = BASE_DIR / "src" / "glossary_tr.default.json"
    if glossary_src.exists():
        shutil.copy2(glossary_src, tr_dest / "glossary_tr.json")
        print(f"  [+] Copied glossary from {glossary_src}")

    # Ensure model folder is cleaned up for ultra-light package
    pkg_model = tr_dest / "model"
    if pkg_model.exists():
        shutil.rmtree(pkg_model)

    # 4. Write online config.json
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

    # 5. Write module.toml
    module_toml = """name = "Guild Wars 2 Turkce (Cevrimici - Google / AI)"
command = "Local_Translator_TR.exe"
args = ["--lang", "tr"]
"""
    (main_mod / "module.toml").write_text(module_toml, encoding="utf-8")

    # 6. Motor_Secici.bat
    bat_content = """@echo off
chcp 65001 >nul
cls
:MENU
echo ============================================================
echo   GW2 TURKCE YERELLESTIRME (CEVRIMICI SURUM) - MOTOR SECICI
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

    # 7. README_TURKCE.txt
    readme_text = """========================================================================
         GUILD WARS 2 TURKCE YERELLESTIRME (CEVRIMICI SURUM)
========================================================================

Guild Wars 2 icin gelistirilmis ultra-hafif cevrimici Turkce font ve ceviri paketi.

[OZELLIKLER]:
1. Gelismis Turkce Font ve Karakter Destegi (version.dll + turkish_font.dll):
   - Bellek ici ozel font enjeksiyonu ve genisletilmis karakter destegi.
   - Akilli karakter modu (smart) ile arayuzdeki olasi harf kayiplari engellenir.

2. Coklu Bulut Ceviri Motoru Destegi:
   - Google Ceviri (Varsayilan, ucretsiz, limitsiz ve cok hizli).
   - DeepL API (Daha profesyonel ceviri, API key gerektirir).
   - Gemini Yapay Zeka (Google Gemini 1.5 Flash ile dogal ceviri, API key gerektirir).
   - OpenAI GPT (GPT-4o-mini / GPT-4o ile gelismis yapay zeka cevirisi, API key gerektirir).

[KURULUM]:
- GW2_Turkce_Yama_Cevrimici.exe ile tek tikla kurulabilir!
- Veya bu klasordeki tum dosyalari Guild Wars 2 oyununuzun ana klasorune
  (Gw2-64.exe dosyasinin yanina) kopyalayabilirsiniz.

Iyi oyunlar dileriz!
========================================================================
"""
    (main_mod / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    (target_dir / "README_TURKCE.txt").write_text(readme_text, encoding="utf-8")
    print(f"  [DONE] Çevrimiçi paket hazırlandı: {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Assemble GW2 Turkish Localization Release Packages")
    parser.add_argument("--offline", action="store_true", help="Assemble only offline package")
    parser.add_argument("--online", action="store_true", help="Assemble only online package")
    parser.add_argument("--all", action="store_true", help="Assemble both packages")
    args = parser.parse_args()

    if args.offline:
        assemble_offline()
    elif args.online:
        assemble_online()
    else:
        assemble_offline()
        assemble_online()

if __name__ == "__main__":
    main()
