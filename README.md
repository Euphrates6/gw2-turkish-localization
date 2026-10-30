<p align="center">
  <b>Türkçe</b> • <a href="README.en.md">English</a>
</p>

# Guild Wars 2 Türkçe Yerelleştirme, Font Motoru ve Çeviri Modülü
### Guild Wars 2 Turkish Localization, Font Engine & Universal Addon Loader

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.11.0--TR-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Guild Wars 2 için geliştirilmiş **tam kapsamlı Türkçe yerelleştirme paketi, iki ayrı bağımsız tek tıkla kurucu paneli (Çevrimdışı & Çevrimiçi), 156 font boyutunu kapsayan Türkçe font enjektörü** ve Epic Games Store / Steam / Standalone istemcilerle %100 uyumlu **evrensel köprü yükleyicisi**.

Oyunun İngilizce istemcisinde eksik olan tüm Türkçe karakterleri (**ç, Ç, ğ, Ğ, ı, İ, ö, Ö, ş, Ş, ü, Ü**) oyunun orijinal yazı tipleriyle eksiksiz gösterir ve diyalogları, görevleri, arayüzü anlık olarak Türkçeye çevirir.

---

## 🚀 İki Ayrı Kurulum Seçeneği / Two Installation Editions

Kullanım tercihinize ve donanımınıza göre projede **2 ayrı bağımsız kurulum paketi** sunulmaktadır:

| Özellik | 🖥️ Çevrimdışı Sürüm (Offline Local) | ☁️ Çevrimiçi Sürüm (Online Light) |
| :--- | :--- | :--- |
| **Kurulum Dosyası** | `GW2_Turkce_Yama_Cevrimdisi.exe` | `GW2_Turkce_Yama_Cevrimici.exe` |
| **Manuel Zip Paketi** | `Local_Translator_Cevrimdisi_TR.zip` (~112 MB) | `Local_Translator_Cevrimici_TR.zip` (~18 MB) |
| **Çeviri Motoru** | **CTranslate2 + OPUS-MT** Yerel Makine Modeli | **Google Translate** (Ücretsiz) / **DeepL** / **Gemini** / **GPT** |
| **İnternet İhtiyacı** | ❌ **Sıfır İnternet** (Tamamen Çevrimdışı) | ✔️ İnternet bağlantısı gerekir |
| **Gecikme (Latency)** | ⚡ **0 ms** (Doğrudan Yerel CPU) | ~100-300 ms (Web API çağrısı) |
| **API Anahtarı / Kota** | ❌ **Gerekmez**, sınırsız ve gizli | Google için gerekmez; AI için API Key girilebilir |
| **Yapay Zeka Modeli** | ✔️ Pakete gömülü (Tak-Çalıştır) | Bulut üzerinde çalışır |
| **İşlemci Ayarı** | ✔️ Çekirdek sayısı seçilebilir (2, 4, 6, 8) | Minimum CPU tüketimi |

---

## 📥 İndir / Download

En güncel sürümleri indirmek için GitHub Releases sayfasını ziyaret edebilirsiniz:

* 💻 **[GW2_Turkce_Yama_Cevrimdisi.exe İndir (GitHub Releases)](../../releases/latest)** *(Çevrimdışı Tek Tıkla Kurucu)*
  * Tamamen yerel bilgisayarınızda çalışır; internete, API anahtarına ihtiyaç duymaz.
  * Pakete gömülü OPUS-MT Türkçe yapay zeka modelini tek tıkla kurar.
* 📦 **[Local_Translator_Cevrimdisi_TR.zip İndir](../../releases/latest)** *(Çevrimdışı Manuel Kurulum)*

* ☁️ **[GW2_Turkce_Yama_Cevrimici.exe İndir (GitHub Releases)](../../releases/latest)** *(Çevrimiçi Ultra-Hafif Kurucu)*
  * Ultra-küçük indirme boyutu (~18 MB).
  * Google Çeviri (varsayılan, ücretsiz, limitsiz), DeepL, Google Gemini 1.5 Flash veya OpenAI GPT kullanır.
* 📦 **[Local_Translator_Cevrimici_TR.zip İndir](../../releases/latest)** *(Çevrimiçi Manuel Kurulum)*

---

## Temel Özellikler

### 1. Bağımsız Tek Tıkla Kurucu & Kontrol Panelleri
* Oyuncuları zip açma, klasör arama ve karmaşık addon menüleriyle uğraştırmaz.
* Steam, Epic Games ve Registry üzerindeki Guild Wars 2 kurulumlarını otomatik tespit eder.
* Çevrimdışı sürümde CPU çekirdek optimizasyonu, çevrimiçi sürümde ise tek tıkla motor geçişi sağlar.
* Tek tıkla oyunu başlatabilir veya yamayı tamamen kaldırarak oyunu orijinal haline döndürebilirsiniz.

### 2. %100 Orijinal Türkçe Font Desteği (`turkish_font.dll` & `version.dll`)
* Guild Wars 2'nin `Gw2.dat` arşivindeki **156 font boyutunun tamamı** analiz edilmiş ve genişletilmiş Latin glifleri (Range 2: Latin Extended-A) `fontdue` vektörel motoruyla rasterize edilmiştir.
* Oyun dosyalarına fiziksel zarar vermeden, bellek içi (RAM) `FileArchive::ReadFile` fonksiyonunu yönlendirerek Türkçe karakterleri orijinal oyun fontu kalitesinde ekrana çizer.
* Harfleri kırpmaya veya İngilizceye benzetmeye (`s, i, g`) gerek kalmaz; kutucuk veya soru işareti hatası oluşmaz.

### 3. Evrensel Köprü Yükleyici (`version.dll`)
* Guild Wars 2'nin özellikle **Epic Games Store** (`-eglv2`) ve yeni istemcilerde `d3d11.dll` dosyasını güvenlik sebebiyle atlamasını engelleyen Rust tabanlı, sıfır bağımlılıklı şeffaf bir köprüdür.
* `Gw2-64.exe`'nin statik import tablosundan faydalanarak oyun başlarken otomatik devreye girer; **Nexus**, **Türkçe Font Enjektörü** ve **Çeviri Motorunu** doğrudan oyuna bağlar.

### 4. Güvenli ve Sıfır Ban Riski
* `Gw2.dat` oyun veri tabanını fiziksel olarak modifiye etmez.
* Raidcore Nexus ekosistemi ve güvenli Windows DLL yönlendirmesiyle çalışır; ArenaNet üçüncü parti kullanım politikalarıyla tam uyumludur.

---

## Kurulum

### Yöntem 1: Tek Tıkla Kurulum (Önerilen)
1. Tercih ettiğiniz sürümün kurucusunu indirin (`GW2_Turkce_Yama_Cevrimdisi.exe` veya `GW2_Turkce_Yama_Cevrimici.exe`).
2. Programı çalıştırın; oyun klasörünüz otomatik olarak algılanacaktır.
3. **"Türkçe Yamayı Kur"** butonuna tıklayın.
4. **"Oyunu Başlat"** butonuna basarak doğrudan Türkçe oynamaya başlayın!

### Yöntem 2: Manuel Kurulum
1. [Releases](../../releases/latest) sayfasından `Local_Translator_Cevrimdisi_TR.zip` veya `Local_Translator_Cevrimici_TR.zip` dosyasını indirin.
2. Zip içerisindeki tüm dosya ve klasörleri (`version.dll`, `d3d11.dll`, `addons/` vb.) doğrudan **Guild Wars 2 oyununuzun ana klasörüne** (`Gw2-64.exe` dosyasının yanına) çıkartın.
3. Oyunu her zamanki gibi başlatın.

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
│   ├── lt_server.py         # CTranslate2 / Google / DeepL / Gemini / OpenAI sunucusu
│   ├── lt_module.py         # Nexus Text Translator IPC iletişim protokolü
│   └── patch_db.py          # SQLite önbellek ve sözlük yönetimi
├── glossary/                # GW2 oyun terimleri ve Türkçe sözlük
│   └── glossary_tr.json
├── TR/
│   ├── config.json          # Varsayılan yapılandırma
│   └── model/               # OPUS-MT Türkçe yerel yapay zeka modeli (Çevrimdışı Sürüm)
│       ├── model.bin
│       ├── shared_vocabulary.json
│       ├── source.spm
│       ├── target.spm
│       └── config.json
├── installer/               # Modern PySide6 tabanlı kontrol panelleri ve kurucular
│   ├── gw2_control_panel.py
│   ├── GW2_Turkce_Yama_Cevrimdisi.spec
│   └── GW2_Turkce_Yama_Cevrimici.spec
├── assemble_release.py      # Çevrimdışı ve Çevrimiçi paket derleme betiği
└── create_zip.py            # Release zip sıkıştırıcı
```

---

## Kaynak Koddan Derleme (Build from Source)

### 1. Çeviri Modüllerini Derleme (Python / PyInstaller)
```bash
# Çevrimdışı sürüm (CTranslate2 dahil):
pyinstaller Local_Translator_TR.spec

# Çevrimiçi ultra-hafif sürüm:
pyinstaller Local_Translator_TR_light.spec
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

### 4. Paketleri Toplama ve Zip Oluşturma
```bash
# Çevrimdışı ve Çevrimiçi paketleri hazırla:
python assemble_release.py --all

# Dağıtım ziplerini oluştur:
python create_zip.py

# Kurucu çalıştırılabilir dosyalarını (EXE) derle:
pyinstaller --distpath dist installer/GW2_Turkce_Yama_Cevrimdisi.spec
pyinstaller --distpath dist installer/GW2_Turkce_Yama_Cevrimici.spec
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
