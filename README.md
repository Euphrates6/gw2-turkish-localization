<p align="center">
  <b>Türkçe</b> • <a href="README.en.md">English</a>
</p>

# GW2-TR: Guild Wars 2 Türkçe Yerelleştirme ve Mod Yöneticisi

[![Game](https://img.shields.io/badge/Game-Guild%20Wars%202-red)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20x64-blue)]()
[![Framework](https://img.shields.io/badge/Addon%20Loader-Raidcore%20Nexus-orange)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen)](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest)
[![License](https://img.shields.io/badge/License-MIT-gray)](LICENSE)

Guild Wars 2 için yerel (çevrimdışı) sinirsel çeviri motoru, bellek üzerinden Türkçe font desteği ve mod yönetim arayüzü sağlayan açık kaynaklı bir eklenti projesidir.

---

## Bileşenler

Proje üç ana bileşenden oluşmaktadır:

* **Mod Yöneticisi (`GW2_TR_Hub.exe`):** Oyun dizinini tespit ederek Raidcore Nexus eklentilerini (`d3d11.dll`, `version.dll`), çeviri motorunu ve font enjektörünü kurar; kısayol tuşlarını ve çeviri ayarlarını yönetir.
* **Türkçe Font Enjektörü (`turkish_font.dll`):** Oyun dosyalarını (`Gw2.dat`) değiştirmeden, çalışma anında oyun belleğine (RAM) müdahale ederek Türkçe karakterlerin (`ç, ğ, ı, ö, ş, ü`) render edilmesini sağlar.
* **Yerel Çeviri Motoru (`Local_Translator_TR.exe`):** CTranslate2 altyapısı ve OPUS-MT dil modeli ile arka planda yerel olarak çalışır. Oyun içi ekonomi, wiki ve rehber uyumluluğunu korumak amacıyla eşya adları, harita/bölge adları ve nitelik terimleri (stats, boons, conditions) orijinal İngilizce biçiminde tutulur; diyaloglar ve görev metinleri Türkçeye aktarılır.

---

## Kurulum

### Yöntem 1: GW2-TR Hub ile Otomatik Kurulum (Önerilen)

1. [Releases](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest) sayfasından `GW2_TR_Hub.exe` dosyasını indirin ve çalıştırın.
2. Program oyun klasörünü otomatik olarak algılayacaktır. Algılanamazsa `Gw2-64.exe` dosyasının bulunduğu dizini manuel olarak seçin.
3. "Bileşenleri Kur / Güncelle" butonuna tıklayın.
4. Kurulum tamamlandıktan sonra oyunu başlatın.

### Yöntem 2: Manuel Kurulum

1. [Releases](https://github.com/Euphrates6/gw2-turkish-localization/releases/latest) sayfasından `GW2_TR_v0.12.0_Manuel_Paket.zip` dosyasını indirin.
2. Arşiv içerisindeki dosyaları (`d3d11.dll`, `version.dll`, `addons/`) Guild Wars 2 ana dizinine (`Gw2-64.exe` yanına) çıkartın.
3. Oyunu başlatın.

---

## Kullanım ve Kısayollar

* **`ALT + T`**: Oyun içerisinde çeviriyi anlık olarak açar veya kapatır. Kısayol tuşu `GW2_TR_Hub` arayüzünden değiştirilebilir.
* **Çeviri Düzenleyici:** Oyun açıkken tarayıcıdan `http://127.0.0.1:8770` adresine girerek veya `GW2_TR_Hub` içerisindeki "Düzenleyici" sekmesinden veritabanındaki çeviriler doğrudan düzenlenebilir.

---

## Kaynak Koddan Derleme

Gereksinimler: Python 3.10+, Visual Studio C++ Build Tools (veya MinGW `g++`), Rust toolchain (`cargo`).

```powershell
# Bağımlılıklar:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# Testler:
python test_gw2_tr.py
python test_protocol.py

# Derleme:
python build_all.py
python tools/assemble_manual_zip.py
```

---

## Katkıda Bulunanlar ve Teşekkürler

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Proje mimarisi, RAM-Hook C++ Font Enjektörü, GW2-TR Hub arayüzü ve yerelleştirme koordinasyonu. (Discord: `https://discord.com/users/287714928410755072`)
* **[NikeGipple](https://github.com/NikeGipple)**: [gw2-nexus-local-translator](https://github.com/NikeGipple/gw2-nexus-local-translator) temel yerel çeviri motoru mimarisi ve IPC protokolü.
* **[ideka](https://github.com/ideka)**: Guild Wars 2 için [Text Translator](https://github.com/ideka/text-translator-public) Nexus eklentisi ve [modulep](https://github.com/ideka/modulep) IPC protokolü.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) projesi ile `Gw2.dat` AFNT font analizi ve bellek enjeksiyonu temelleri.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) analiz araçları.
* **[Raidcore Ekibi](https://raidcore.gg/Nexus)**: Guild Wars 2 Nexus Addon Loader altyapısı.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Çevrimdışı sinirsel makine çevirisi kütüphanesi ve OPUS-MT dil modelleri.

---

## Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında sunulmaktadır.

*Yasal Uyarı: Guild Wars 2, ArenaNet ve NCSoft ticari markaları ilgili şirketlere aittir. Bu proje ArenaNet veya NCSoft ile ilişkili değildir; topluluk tarafından geliştirilmiş açık kaynaklı bir yerelleştirme aracıdır.*
