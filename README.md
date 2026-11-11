<p align="center">
  <b>Türkçe</b> • <a href="README.en.md">English</a>
</p>

# Guild Wars 2 — Türkçe Yerelleştirme ve Mod Kurulum Merkezi (GW2-TR)
### Guild Wars 2 Turkish Localization, Neural Translation Engine & Mod Installation Hub

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Storefront](https://img.shields.io/badge/Storefront-Epic%20Games%20%7C%20Steam%20%7C%20Standalone-purple.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Guild Wars 2 için geliştirilmiş **tek tıkla kurulum ve yönetim merkezi (GW2-TR Hub)**, **bellek içi (RAM-Hook) Türkçe font enjektörü**, **eşya/stat/mekan korumalı yerel çeviri motoru** ve **canlı çeviri düzenleyicisi** içeren tam kapsamlı Türkçe yerelleştirme ekosistemidir.

Steam, Epic Games Store ve orijinal ArenaNet istemcileriyle %100 uyumludur.

---

## 🌟 Öne Çıkan Özellikler

### 1. 🎛️ IDE Temalı Mod Yönetim Merkezi (`GW2_TR_Hub.exe`)
* **Tek Tıkla Kurulum & Otomasyon:** Steam, Epic Games ve kayıt defteri üzerindeki Guild Wars 2 kurulumunuzu otomatik algılar; Raidcore Nexus (`d3d11.dll`), çeviri motoru ve font enjektörünü tek tıkla kurup yapılandırır.
* **Modern Koyu IDE Estetiği:** `#181818`, `#1e1e1e`, `#252526` monochromatic koyu tema, Phosphor ikon seti ve gömülü çevrimdışı Tailwind CSS motoru.
* **Akıllı Çekmece (Drawer) Etkileşimi:** Mod satırlarının herhangi bir yerine tıklayarak alt ayar katmanlarına (kısayol ayarları, çeviri motoru seçimi, karakter modu) anında erişim.
* **Gömülü Hakkında & İletişim Paneli:** Sürüm detayları, GitHub deposu ve Discord geliştirici profili bağlantıları.

### 2. 🔤 Gelişmiş Bellek İçi Türkçe Font Enjektörü (`turkish_font.dll` & `version.dll`)
* **Oyun Dosyalarına Sıfır Müdahale:** `Gw2.dat` veri tabanına fiziksel müdahalede bulunmaz. Bellek içi (RAM) `FileArchive::ReadFile` fonksiyonunu yönlendirerek 53 adet RLE sıkıştırmalı Range-2 Türkçe font atlasını oyunun orijinal yazı tipleriyle birleştirir.
* **İsteğe Bağlı Çift Karakter Modu:**
  * **AÇIK (Tam Glif Modu):** `Ş, ş, Ğ, ğ, İ, ı, Ç, ç, Ö, ö, Ü, ü` harflerinin tamamı oyun içinde kusursuz görüntülenir.
  * **KAPALI (Akıllı 6 Harf Dönüşümü):** Font enjeksiyonu kapatıldığında oyun motorunda kutucuk (tofu) oluşturan yalnızca 6 harf (`Ş->S, ş->s, Ğ->G, ğ->g, İ->I, ı->i`) dönüştürülür; oyunun doğal olarak desteklediği `Ç, ç, Ö, ö, Ü, ü` harfleri Türkçe olarak korunur.
* **Otomatik Önbellek Senkronizasyonu:** Karakter modu her değiştirildiğinde `cache.db` veritabanındaki kayıtlar saniyeler içinde yeni moda dönüştürülür.

### 3. 🛡️ Eşya, Mekan, Stat, Set ve Boon/Condition Koruması
Oyun deneyiminizi bozmamak, Wiki aramalarında, Trading Post (Pazar) işlemlerinde ve uluslararası takım iletişiminde %100 uyum sağlamak için 3 katmanlı hibrit koruma:
* **Eşya İsimleri:** Silahlar, zırhlar, kupalar, materyaller orijinal İngilizce kalır (Örn: *Berserker's Pearl Broadsword*).
* **Mekan & Harita İsimleri:** Haritalar, bölgeler, Waypoint ve POI adları İngilizce kalır (Örn: *Queensdale*, *Lion's Arch*).
* **Statlar (Nitelikler):** `Power`, `Precision`, `Toughness`, `Vitality`, `Ferocity`, `Condition Damage`, `Expertise`, `Concentration`, `Healing Power`, `Agony Resistance`, `Critical Chance`, `Critical Damage`, `Boon Duration`, `Armor`, `Health` gibi tüm stat ve bonus satırları (`+120 Power`, `+%num1% Condition Damage`) orijinal İngilizce kalır.
* **Stat Setleri (Prefixes):** `Berserker's`, `Viper's`, `Marauder's`, `Celestial`, `Diviner's`, `Harrier's`, `Minstrel's` vb. tüm stat kombinasyonları korunur.
* **Boon & Condition'lar:** `Might`, `Fury`, `Quickness`, `Alacrity`, `Protection`, `Aegis`, `Bleeding`, `Burning`, `Torment`, `Vulnerability` gibi muharebe terimleri korunur.
* **Diyaloglar & Arayüz:** Görev açıklamaları, hikaye diyalogları, kullanıcı arayüzü butonları ve rehber metinleri eksiksiz Türkçeleştirilir.

### 4. 🧠 Çevrimdışı Sinirsel Çeviri & İsteğe Bağlı Bulut API
* **Öncelikli Yerel Motor (Offline OPUS-MT):** CTranslate2 ve SentencePiece tabanlı Türkçe sinirsel makine çevirisi modeli doğrudan yerel işlemcinizde (CPU) çalışır. Sıfır internet, sıfır kota, sıfır gecikme!
* **Opsiyonel Bulut Motorları:** İsteğe bağlı olarak Google Translate (ücretsiz), DeepL, Google Gemini veya OpenAI API anahtarlarınızı Hub üzerinden yapılandırabilirsiniz.

### 5. ⌨️ Anlık Oyun İçi Aç/Kapa Kısayolu (`ALT + T`)
* Oyundan çıkmadan tek tuşla çeviriyi kapatıp orijinal İngilizceye dönebilir, tekrar bastığınızda anında Türkçeye geçebilirsiniz.
* Kısayol doğrudan Hub arayüzündeki interaktif tuş kaydedici ile (ScanCode destekli) özelleştirilebilir ve Nexus `InputBinds.json` ile anında senkronize olur.

### 6. ✏️ Canlı ve Çevrimdışı Çeviri Düzenleyici (Translation Editor)
* **Canlı Mod:** Oyun açıkken tarayıcınızdan `http://127.0.0.1:8770` adresine girerek oyunda gördüğünüz çevirileri anında düzenleyebilirsiniz.
* **Çevrimdışı Mod:** Oyun kapalıyken bile Hub içerisindeki "Çeviri Düzenle" sekmesinden `cache.db`, `map_tr.db` ve `patch_tr.db` veritabanlarında anlık arama yapabilir, çevirileri düzeltebilir ve tek tıkla geri alabilirsiniz.

---

## 📥 İndirme / Download

En güncel dosyaları [GitHub Releases](../../releases/latest) sayfasından edinebilirsiniz:

| Dosya | Boyut | Açıklama |
| :--- | :--- | :--- |
| 🎛️ **[GW2_TR_Hub.exe](../../releases/latest)** | ~280 MB | **Önerilen:** Masaüstü Kurulum & Yönetim Merkezi (Tek Tıkla Kurulum, Canlı Düzenleyici) |
| 📦 **[GW2_TR_v0.12.0_Manuel_Paket.zip](../../releases/latest)** | ~298 MB | **Manuel:** Zip içeriğini doğrudan Guild Wars 2 ana dizinine çıkaran oyuncular için |
| ⚙️ **[Local_Translator_TR.exe](../../releases/latest)** | ~227 MB | Bağımsız arka plan yerel çeviri motoru |

---

## 🚀 Kurulum Rehberi

### Yöntem 1: GW2-TR Hub ile Tek Tıkla Kurulum (Önerilen)
1. **[`GW2_TR_Hub.exe`](../../releases/latest)** dosyasını indirin ve çalıştırın.
2. Program Guild Wars 2 klasörünüzü otomatik olarak algılayacaktır. (Gerekirse *"Gözat"* butonuyla `Gw2-64.exe` dosyasının bulunduğu klasörü seçebilirsiniz).
3. **"TÜM BİLEŞENLERİ KUR / GÜNCELLE"** butonuna tıklayın. Nexus (`d3d11.dll`), Text Translator, Font Enjektörü ve Çevrimdışı Türkçe modeli saniyeler içinde kurulacaktır.
4. **"Guild Wars 2 Başlat"** butonuna basarak doğrudan Türkçe oynamaya başlayın!

### Yöntem 2: Manuel Kurulum (Zip)
1. **[`GW2_TR_v0.12.0_Manuel_Paket.zip`](../../releases/latest)** dosyasını indirin.
2. Zip içerisindeki tüm dosya ve klasörleri (`d3d11.dll`, `version.dll`, `addons/`) doğrudan Guild Wars 2 oyununuzun ana klasörüne (`Gw2-64.exe` yanına) çıkartın.
3. Oyunu başlatın.

---

## 📁 Proje Mimarisi

```
gw2-turkish-localization/
├── assets/                  # Derlenmiş DLL'ler, eklentiler ve ikonlar
│   ├── turkish_font.dll     # C++ Range-2 AFNT font enjektörü (Gömülü 53 atlas)
│   ├── version.dll          # Rust tabanlı erken başlatma proxy köprüsü
│   ├── d3d11.dll            # Raidcore Nexus Addon Loader
│   ├── text_translator.dll  # Text Translator Nexus eklentisi
│   ├── app_icon.ico         # Çok katmanlı IDE altıgen Windows ikonu
│   └── app_icon.png         # 1024x1024 şeffaf PNG logo
├── hub/                     # Masaüstü Kurulum & Yönetim Merkezi (pywebview)
│   ├── app.py               # WebView2 & Nexus IPC köprüsü, kısayol yönetimi
│   └── ui/                  # Koyu IDE temalı arayüz (#181818, #1e1e1e)
│       ├── index.html       # 5 sekmeli ana panel (Mods, Editor, Downloads, Settings, About)
│       ├── tailwind.js      # Gömülü çevrimdışı Tailwind motoru
│       ├── phosphor.css     # Gömülü Phosphor ikon CSS'i
│       ├── Phosphor.woff2   # Gömülü Phosphor webfont
│       ├── app_icon.png     # Menü logosu
│       └── favicon.ico      # Sekme ikonu
├── src/                     # Python çeviri sunucusu ve motor çekirdeği
│   ├── lt_server.py         # v0.12.0 Türkçe-Özel motor (Stat/Eşya/Boon koruması)
│   ├── lt_module.py         # Text Translator IPC iletişim modülü
│   ├── patch_db.py          # SQLite WAL önbellek ve karakter modu senkronizasyonu
│   ├── editor.py            # Canlı ve Çevrimdışı Çeviri Düzenleyici (Web & Hub)
│   ├── map_upload.py        # Harita verisi yükleme yardımcısı
│   ├── glossary_tr.default.json
│   └── requirements.txt
├── tools/                   # Üretim ve bakım araçları
│   ├── make_icon.py         # Altıgen ikon üretim aracı
│   ├── update_glossary_mechanics.py # Stat & mekanik terim güncelleyici
│   └── assemble_manual_zip.py       # Manuel zip derleme otomasyonu
├── TR/                      # Türkçe dil modelleri ve yapılandırma
│   ├── config.json          # Varsayılan motor ayarları
│   ├── contributor.json     # Geliştirici profili
│   ├── glossary_tr.json     # 3.600+ terim, stat, set ve boon sözlüğü
│   └── model/               # 35 MB CTranslate2 OPUS-MT yerel sinirsel model
├── build_all.py             # Tek komutla tüm EXE ve paketleri derleme betiği
├── test_gw2_tr.py           # 6/6 test paketi (Font, Karakter, Stat, Cache, Keybind)
└── test_protocol.py         # Nexus Text Translator binary IPC test protokolü
```

---

## 🛠️ Kaynak Koddan Derleme (Build from Source)

Gereksinimler: Python 3.10+, Visual Studio C++ Build Tools (veya MinGW `g++`), Rust `cargo`.

```powershell
# 1. Bağımlılıkları yükleyin:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# 2. Testleri çalıştırın:
python test_gw2_tr.py
python test_protocol.py

# 3. Tüm çalıştırılabilir dosyaları ve paketleri derleyin:
python build_all.py
python tools/assemble_manual_zip.py

# Çıktılar dist/ klasöründe üretilecektir:
# - dist/GW2_TR_Hub.exe
# - dist/Local_Translator_TR.exe
# - dist/GW2_TR_v0.12.0_Manuel_Paket.zip
```

---

## 👥 Katkıda Bulunanlar & Teşekkürler (Credits & Acknowledgments)

Bu proje, açık kaynak topluluğunun değerli çalışmaları üzerine inşa edilmiştir:

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Proje mimarı, Türkçe Font Injector (RAM Hook), GW2-TR Hub arayüzü, stat/boon koruma filtreleri ve yerelleştirme koordinasyonu. (Discord: `https://discord.com/users/287714928410755072`)
* **[NikeGipple](https://github.com/NikeGipple)**: Temel alınan açık kaynaklı [gw2-nexus-local-translator](https://github.com/NikeGipple/gw2-nexus-local-translator) yerel çeviri motoru mimarisi ve bellek içi çeviri protokolü.
* **[ideka](https://github.com/ideka)**: Guild Wars 2 için geliştirilen temel [Text Translator](https://github.com/ideka/text-translator-public) Nexus eklentisi ve [modulep](https://github.com/ideka/modulep) IPC protokolü.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) projesiyle `Gw2.dat` AFNT font chunk analizi, decompressor ve bellek enjeksiyonu keşifleri.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) analiz araçları.
* **[Raidcore Ekibi](https://raidcore.gg/Nexus)**: Guild Wars 2 için geliştirilen harika Nexus D3D11 Addon Framework.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Çevrimdışı yerel sinirsel makine çevirisi altyapısı ve OPUS-MT Türkçe modelleri.

---

## 📜 Lisans & Yasal Uyarı (License & Legal)

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.

> **Yasal Uyarı:** Guild Wars 2, ArenaNet ve NCSoft markaları ve telif hakları ilgili sahiplerine aittir. Bu proje resmi bir ArenaNet ürünü değildir; oyuncu topluluğu tarafından kar amacı gütmeksizin geliştirilmiş açık kaynaklı bir yerelleştirme ve erişilebilirlik aracıdır.
