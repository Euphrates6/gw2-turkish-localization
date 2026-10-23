<p align="center">
  <b>Türkçe</b> • <a href="README.en.md">English</a>
</p>

# Guild Wars 2 Türkçe Yerelleştirme, Font Motoru ve Çeviri Modülü
### Guild Wars 2 Turkish Localization, Font Engine & Universal Addon Loader

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.10.0--TR-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Guild Wars 2 için geliştirilmiş **tam kapsamlı Türkçe yerelleştirme paketi, 156 font boyutunu kapsayan Türkçe font enjektörü** ve Epic Games Store / Steam / Standalone istemcilerle %100 uyumlu **evrensel köprü yükleyicisi**.

Oyunun İngilizce istemcisinde eksik olan tüm Türkçe karakterleri (**ç, Ç, ğ, Ğ, ı, İ, ö, Ö, ş, Ş, ü, Ü**) oyunun orijinal yazı tipleriyle eksiksiz gösterir ve diyalogları, görevleri, arayüzü anlık olarak Türkçeye çevirir.

---

## İndir / Download

En güncel, kullanıma hazır hepsi-bir-arada sürümü indirmek için:

[**Local_Translator_0.10.0_TR.zip İndir (GitHub Releases)**](../../releases/latest) *(~267 MB)*

---

## Temel Özellikler

### 1. %100 Orijinal Türkçe Font Desteği (`turkish_font.dll`)
* Guild Wars 2'nin `Gw2.dat` arşivindeki **156 font boyutunun tamamı** analiz edilmiş ve genişletilmiş Latin glifleri (Range 2: Latin Extended-A) `fontdue` vektörel motoruyla rasterize edilmiştir.
* Oyun dosyalarına fiziksel zarar vermeden, bellek içi (RAM) `FileArchive::ReadFile` fonksiyonunu yönlendirerek Türkçe karakterleri orijinal oyun fontu kalitesinde ekrana çizer.
* Harfleri kırpmaya veya İngilizceye benzetmeye (`s, i, g`) gerek kalmaz; kutucuk veya soru işareti hatası oluşmaz.

### 2. Evrensel Köprü Yükleyici (`version.dll`)
* Guild Wars 2'nin özellikle **Epic Games Store** (`-eglv2`) ve yeni istemcilerde `d3d11.dll` dosyasını güvenlik sebebiyle atlamasını engelleyen Rust tabanlı, sıfır bağımlılıklı şeffaf bir köprüdür.
* `Gw2-64.exe`'nin statik import tablosundan faydalanarak oyun başlarken otomatik devreye girer; **Nexus**, **Türkçe Font Enjektörü** ve **Çeviri Motorunu** doğrudan oyuna bağlar.

### 3. Çoklu Çeviri Motoru (Multi-Backend Support)
İhtiyacınıza ve donanımınıza göre tek tıkla çeviri motorunu değiştirebilirsiniz:
* **Google Çeviri (Varsayılan):** Tamamen ücretsiz, sınırsız, kurulum gerektirmez ve son derece hızlıdır.
* **DeepL API:** Yüksek kaliteli, profesyonel oyun çevirisi (Ücretsiz veya Pro API anahtarı gerektirir).
* **Google Gemini AI:** Google Gemini 1.5 Flash ile son derece doğal ve akıcı yapay zeka çevirisi.
* **OpenAI GPT:** GPT-4o-mini / GPT-4o yapay zeka motoru.
* **Yerel Çevrimdışı Model:** Helsinki-NLP Opus-MT ve CTranslate2 altyapısıyla internet gerektirmeyen cihaz içi çeviri.

### 4. Güvenli ve Sıfır Ban Riski
* `Gw2.dat` oyun veri tabanını fiziksel olarak modifiye etmez.
* Raidcore Nexus ekosistemi ve güvenli Windows DLL yönlendirmesiyle çalışır; ArenaNet üçüncü parti kullanım politikalarıyla tam uyumludur.

---

## Kurulum (Tek Adımda Kolay Kurulum)

1. [**Releases**](../../releases/latest) sayfasından `Local_Translator_0.10.0_TR.zip` dosyasını indirin.
2. Zip içerisindeki tüm dosya ve klasörleri (`version.dll`, `d3d11.dll`, `addons/` vb.) doğrudan **Guild Wars 2 oyununuzun kurulu olduğu ana klasöre** (`Gw2-64.exe` dosyasının yanına) çıkartın.
3. Oyunu her zamanki gibi başlatın (Epic Games Launcher, Steam veya Standalone).
4. Oyuna girdikten sonra klavyenizden **`Ctrl + O`** tuşuna basarak (veya sol üstteki Nexus simgesine tıklayarak) Nexus menüsünü açabilir, eklentilerinizi yönetebilirsiniz.

### Çeviri Motorunu Değiştirme
`addons\text_translator\modules\local_translator_tr\` klasöründeki **`Ceviri_Motoru_Secici.bat`** dosyasını çift tıklayarak Google, DeepL, Gemini, OpenAI veya Yerel Model arasında tek tuşla geçiş yapabilirsiniz.

### Çeviri Modunu Oyun İçinde Açıp Kapatma (Anlık Toggle Kısayolu)
İngilizce terimleri, wiki aramalarını veya yetenek isimlerini orijinal dilinde görmek için oyundan çıkmadan tek tuşla Türkçe ve İngilizce arasında geçiş yapabilirsiniz:
1. Oyunda **`Ctrl + O`** tuşuna basarak Nexus menüsünü açın.
2. Üstteki **`Keybinds`** sekmesine geçin.
3. **Text Translator** altındaki **`Toggle Show Translated`** seçeneğini bulun.
4. Yanındaki boş kutucuğa tıklayarak dilediğiniz bir kısayol tuşu atayın (Örn: **`Alt + T`**, **`F11`** veya **`Pause/Break`**).
5. Bu tuşa her bastığınızda oyun RAM seviyesinde anında Türkçe ve orijinal İngilizce arasında geçiş yapar.

---

## Proje Mimarisi

```
gw2-turkish-localization/
├── loader/                  # Rust ile yazılmış sıfır bağımlılıklı version.dll proxy köprüsü
│   ├── Cargo.toml
│   └── src/lib.rs
├── font-addon/              # C++ ile yazılmış bellek içi AFNT font enjektörü (turkish_font.dll)
│   ├── main.cpp
│   ├── Nexus.h
│   └── resource.rc
├── src/                     # Python çeviri sunucusu ve çoklu motor adaptörleri
│   ├── lt_server.py         # Google / DeepL / Gemini / OpenAI / Opus-MT çeviri sunucusu
│   ├── lt_module.py         # Nexus Text Translator IPC iletişim protokolü
│   └── patch_db.py          # SQLite önbellek ve sözlük yönetimi
├── glossary/                # GW2 oyun terimleri ve Türkçe sözlük
│   └── glossary_tr.json
├── TR/                      # Varsayılan yapılandırma şablonları
│   └── config.json
├── assemble_release.py      # Otomatik paketleme ve dağıtım betiği
└── create_zip.py            # Release zip sıkıştırıcı
```

---

## Kaynak Koddan Derleme (Build from Source)

### 1. Çeviri Modülü (Python)
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pyinstaller Local_Translator_TR.spec
```

### 2. Köprü Yükleyici (Rust)
```bash
cd loader
cargo build --release
# Çıktı: loader/target/release/version.dll
```

### 3. Font Eklentisi (C++)
```bash
cd font-addon
windres resource.rc -O coff -o resource.res
g++ -O3 -shared main.cpp resource.res -o turkish_font.dll -lucrt -lkernel32
```

Tüm bileşenleri tek pakette toplamak için:
```bash
python assemble_release.py
python create_zip.py
```

---

## Katkıda Bulunanlar & Teşekkürler (Credits & Acknowledgments)

Bu proje, açık kaynak topluluğunun değerli çalışmaları üzerine inşa edilmiştir:

* **[ideka](https://github.com/ideka)**: Guild Wars 2 için geliştirilen temel [Text Translator](https://github.com/ideka/text-translator-public) Nexus eklentisi ve [modül protokolü](https://github.com/ideka/modulep).
* **[NikeGipple](https://github.com/NikeGipple)**: Temel alınan açık kaynaklı [GW2 Local Translator](https://github.com/NikeGipple/gw2-nexus-local-translator) yerel çeviri modülü mimarisi ve altyapısı.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) projesiyle `Gw2.dat` AFNT font chunk yapısı, decompressor analizi ve bellek enjeksiyonu keşifleri.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) analiz araçları.
* **[Raidcore Ekibi](https://raidcore.gg/Nexus)**: Guild Wars 2 için geliştirilen harika Nexus D3D11 Addon Engine.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Çevrimdışı yerel makine çeviri modelleri.
* **Geliştirici & Türkçe Uyarlama:** **[Euphrates6](https://github.com/Euphrates6)** & **Antigravity (Google DeepMind)** — 156 font boyutunun vektörel çizimi, Epic Games uyumlu Rust köprü mimarisi, yapay zeka entegrasyonu ve tam Türkçe karakter optimizasyonu.

---

## Lisans & Yasal Uyarı (License & Legal)

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.

> **Yasal Uyarı:** Guild Wars 2, ArenaNet ve NCSoft markaları ve telif hakları ilgili sahiplerine aittir. Bu proje resmi bir ArenaNet ürünü değildir; oyuncu topluluğu tarafından kar amacı gütmeksizin geliştirilmiş açık kaynaklı bir yerelleştirme aracıdır.
