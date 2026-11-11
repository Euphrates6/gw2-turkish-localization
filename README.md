<p align="center">
  <b>Türkçe</b> • <a href="README.en.md">English</a>
</p>

# Guild Wars 2 — Türkçe Yerelleştirme (GW2-TR)
### Guild Wars 2 Turkish Localization & Mod Hub

[![Guild Wars 2](https://img.shields.io/badge/Game-Guild%20Wars%202-red.svg)](https://www.guildwars2.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20(64--bit)-blue.svg)]()
[![Nexus](https://img.shields.io/badge/Framework-Raidcore%20Nexus-orange.svg)](https://raidcore.gg/Nexus)
[![Release](https://img.shields.io/badge/Release-v0.12.0-brightgreen.svg)](../../releases/latest)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Guild Wars 2 için çevrimdışı yapay zeka çeviri motoru, bellek içi Türkçe font desteği ve kolay yönetim arayüzü sunan açık kaynaklı yerelleştirme projesidir.

---

## 🌟 Temel Özellikler

* **Kolay Kurulum (`GW2_TR_Hub.exe`):** Oyun dizinini otomatik algılar; Raidcore Nexus altyapısını, çeviri motorunu ve font enjektörünü tek tıkla kurup günceller.
* **Bellek İçi Türkçe Font Desteği:** Oyun dosyalarına (`Gw2.dat`) dokunmadan, bellek üzerinden Türkçe karakterlerin (`ç, ğ, ı, ö, ş, ü`) eksiksiz görüntülenmesini sağlar.
* **Çevrimdışı Çeviri Motoru:** Yerel sinirsel model (OPUS-MT) sayesinde internet bağlantısı gerektirmeden çalışır. Oyun içi ekonomi ve rehber uyumu için eşya ve yetenek terimleri korunur.
* **Anında Aç/Kapa Kısayolu (`ALT + T`):** Oyun açıkken tek tuşla orijinal İngilizce metinlere dönebilir, tekrar bastığınızda Türkçeye geçebilirsiniz. Kısayol arayüzden özelleştirilebilir.
* **Çeviri Düzenleyici:** Oyun içi çevirileri arayüz üzerinden veya tarayıcıdan anlık olarak düzenleyip kaydedebilirsiniz.

---

## 📥 İndirme

En güncel sürümleri [GitHub Releases](../../releases/latest) sayfasından indirebilirsiniz:

| Dosya | Boyut | Açıklama |
| :--- | :--- | :--- |
| 🎛️ **[GW2_TR_Hub.exe](../../releases/latest)** | ~280 MB | **Önerilen:** Otomatik kurulum, mod yönetimi ve çeviri düzenleyici içeren yönetim merkezi |
| 📦 **[GW2_TR_v0.12.0_Manuel_Paket.zip](../../releases/latest)** | ~298 MB | **Manuel:** Kurulum arayüzü olmadan doğrudan oyun klasörüne çıkartılan bağımsız paket |

---

## 🚀 Kurulum

### Yöntem 1: GW2-TR Hub ile Kurulum (Önerilen)
1. **[`GW2_TR_Hub.exe`](../../releases/latest)** dosyasını indirin ve açın.
2. Oyun klasörünüz otomatik algılanacaktır. Gerekirse *"Gözat"* butonuyla `Gw2-64.exe` dosyasının bulunduğu klasörü seçin.
3. **"TÜM BİLEŞENLERİ KUR / GÜNCELLE"** butonuna tıklayın.
4. Kurulum tamamlandığında oyunu başlatıp Türkçe oynamaya başlayabilirsiniz.

### Yöntem 2: Manuel Kurulum (Zip)
1. **[`GW2_TR_v0.12.0_Manuel_Paket.zip`](../../releases/latest)** dosyasını indirin.
2. Arşiv içerisindeki tüm dosyaları (`d3d11.dll`, `version.dll`, `addons/`) Guild Wars 2 oyun klasörünüze (`Gw2-64.exe` yanına) çıkartın.
3. Oyunu her zamanki gibi başlatın.

---

## ⌨️ Oyun İçi Kısayol

* **`ALT + T`**: Çeviriyi anında açar / kapatır. Kısayol tuşunu `GW2_TR_Hub` arayüzündeki ayarlar kısmından dilediğiniz gibi değiştirebilirsiniz.

---

## 🛠️ Kaynak Koddan Derleme

```powershell
# Bağımlılıkları yükleyin:
pip install -r src/requirements.txt pyinstaller pywebview Pillow

# Testleri çalıştırın:
python test_gw2_tr.py
python test_protocol.py

# Dağıtım paketlerini derleyin:
python build_all.py
python tools/assemble_manual_zip.py
```

---

## 👥 Katkıda Bulunanlar & Teşekkürler (Credits & Acknowledgments)

Bu proje, açık kaynak topluluğunun değerli çalışmaları üzerine inşa edilmiştir:

* **[Euphrates6 (Fırat)](https://github.com/Euphrates6)**: Proje mimarı, Türkçe Font Injector (RAM Hook), GW2-TR Hub arayüzü ve yerelleştirme koordinasyonu. (Discord: `https://discord.com/users/287714928410755072`)
* **[NikeGipple](https://github.com/NikeGipple)**: Temel alınan açık kaynaklı [gw2-nexus-local-translator](https://github.com/NikeGipple/gw2-nexus-local-translator) yerel çeviri motoru mimarisi ve bellek içi çeviri protokolü.
* **[ideka](https://github.com/ideka)**: Guild Wars 2 için geliştirilen temel [Text Translator](https://github.com/ideka/text-translator-public) Nexus eklentisi ve [modulep](https://github.com/ideka/modulep) IPC protokolü.
* **[nourlie](https://github.com/nourlie)**: [GlyphCore](https://github.com/nourlie/GlyphCore) projesiyle `Gw2.dat` AFNT font chunk analizi, decompressor ve bellek enjeksiyonu keşifleri.
* **[morluto](https://github.com/morluto)**: [REA (Reverse Engineering Assistant)](https://github.com/morluto/rea) analiz araçları.
* **[Raidcore Ekibi](https://raidcore.gg/Nexus)**: Guild Wars 2 için geliştirilen harika Nexus D3D11 Addon Framework.
* **[Helsinki-NLP](https://github.com/Helsinki-NLP)** & **[OpenNMT CTranslate2](https://github.com/OpenNMT/CTranslate2)**: Çevrimdışı yerel sinirsel makine çevirisi altyapısı ve OPUS-MT Türkçe modelleri.

---

## 📜 Lisans & Yasal Uyarı

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.

> **Yasal Uyarı:** Guild Wars 2, ArenaNet ve NCSoft markaları ve telif hakları ilgili sahiplerine aittir. Bu proje resmi bir ArenaNet ürünü değildir; oyuncu topluluğu tarafından kar amacı gütmeksizin geliştirilmiş açık kaynaklı bir yerelleştirme ve erişilebilirlik aracıdır.
