# -*- coding: utf-8 -*-
"""Guild Wars 2 Türkçe Yerelleştirme - Modern Kontrol Paneli ve Kurucu

Bu uygulama, Guild Wars 2 için geliştirilmiş Türkçe font motorunu ve çeviri sistemini
otomatik olarak tespit edip tek tıkla kurar, yönetir ve kaldırır.
Hem Çevrimdışı (Offline CTranslate2) hem de Çevrimiçi (Google / AI) sürümlerini destekler.
"""
from __future__ import annotations

import sys
import os
import json
import glob
import shutil
import zipfile
import winreg
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSize
from PySide6.QtGui import QIcon, QFont, QColor, QCursor, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QRadioButton, QButtonGroup,
    QFileDialog, QMessageBox, QProgressBar, QFrame, QScrollArea,
    QGraphicsDropShadowEffect, QSizePolicy, QComboBox
)

APP_VERSION = "v0.11.0"


def get_bundle_dir() -> Path:
    """PyInstaller bundle directory or current script directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_edition() -> str:
    """Detects whether this installer runs in 'offline' (Çevrimdışı) or 'online' (Çevrimiçi) mode."""
    # 1. Command-line flag
    for arg in sys.argv[1:]:
        a = arg.lower().strip("-")
        if a in ("offline", "cevrimdisi", "yerel", "local"):
            return "offline"
        if a in ("online", "cevrimici", "bulut", "light"):
            return "online"

    # 2. Executable name
    exe_stem = Path(sys.executable).stem.lower()
    if "cevrimdisi" in exe_stem or "offline" in exe_stem:
        return "offline"
    if "cevrimici" in exe_stem or "online" in exe_stem:
        return "online"

    # 3. Bundled zip payload presence
    bundle = get_bundle_dir()
    has_offline_zip = (bundle / "Local_Translator_Cevrimdisi_TR.zip").exists()
    has_online_zip = (bundle / "Local_Translator_Cevrimici_TR.zip").exists()

    if has_offline_zip and not has_online_zip:
        return "offline"
    if has_online_zip and not has_offline_zip:
        return "online"

    # Default to offline if both or neither exist
    return "offline"


def find_gw2_installations() -> list[Path]:
    """Find all potential Gw2-64.exe locations across Steam, Epic, Registry and common drives."""
    found: list[Path] = []
    seen: set[str] = set()

    def add_if_valid(p: Path):
        try:
            resolved = p.resolve()
            s = str(resolved).lower()
            if s not in seen and resolved.is_file() and resolved.name.lower() == "gw2-64.exe":
                seen.add(s)
                found.append(resolved)
        except Exception:
            pass

    # 1. ArenaNet Registry (Standalone)
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for subkey in (r"SOFTWARE\ArenaNet\Guild Wars 2", r"SOFTWARE\WOW6432Node\ArenaNet\Guild Wars 2"):
            try:
                with winreg.OpenKey(root, subkey) as k:
                    val, _ = winreg.QueryValueEx(k, "Path")
                    if val:
                        p = Path(val)
                        if p.is_dir():
                            add_if_valid(p / "Gw2-64.exe")
                        else:
                            add_if_valid(p)
            except OSError:
                pass

    # 2. Steam Registry & Library Folders
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            steam_path, _ = winreg.QueryValueEx(k, "SteamPath")
            if steam_path:
                sp = Path(steam_path)
                add_if_valid(sp / "steamapps" / "common" / "Guild Wars 2" / "Gw2-64.exe")
                add_if_valid(sp / "steamapps" / "common" / "GuildWars2" / "Gw2-64.exe")
                vdf = sp / "steamapps" / "libraryfolders.vdf"
                if vdf.exists():
                    text = vdf.read_text(encoding="utf-8", errors="ignore")
                    for line in text.splitlines():
                        if '"path"' in line.lower():
                            parts = line.split('"')
                            if len(parts) >= 4:
                                lib = Path(parts[3])
                                add_if_valid(lib / "steamapps" / "common" / "Guild Wars 2" / "Gw2-64.exe")
                                add_if_valid(lib / "steamapps" / "common" / "GuildWars2" / "Gw2-64.exe")
    except OSError:
        pass

    # 3. Epic Games Store Manifests
    for manifest_path in glob.glob(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests\*.item"):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                display_name = d.get("DisplayName", "")
                app_name = d.get("AppName", "")
                if "guild" in display_name.lower() or "guild" in app_name.lower():
                    inst = Path(d.get("InstallLocation", ""))
                    add_if_valid(inst / "Gw2-64.exe")
        except Exception:
            pass

    # 4. Common Paths across all drive letters
    subdirs = [
        "GuildWars2", "Guild Wars 2",
        "Epic Games/GuildWars2", "Epic Games/Guild Wars 2",
        "Program Files/Guild Wars 2", "Program Files/GuildWars2",
        "Program Files (x86)/Guild Wars 2", "Program Files (x86)/GuildWars2",
        "Games/Guild Wars 2", "Games/GuildWars2",
        "Oyunlar/Guild Wars 2", "Oyunlar/GuildWars2",
    ]
    for drive in ["C", "D", "E", "F", "G"]:
        for s in subdirs:
            add_if_valid(Path(f"{drive}:/{s}/Gw2-64.exe"))

    return found


def is_gw2_running() -> bool:
    """Check if Gw2-64.exe is running."""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq Gw2-64.exe", "/NH"],
            creationflags=subprocess.CREATE_NO_WINDOW
        ).decode("latin-1", errors="ignore")
        return "gw2-64.exe" in output.lower()
    except Exception:
        return False


class InstallWorker(QThread):
    progress = Signal(int, str)
    finished_signal = Signal(bool, str)

    def __init__(self, target_dir: Path, config_data: dict, edition: str):
        super().__init__()
        self.target_dir = target_dir
        self.config_data = config_data
        self.edition = edition

    def run(self):
        try:
            self.progress.emit(10, "Kurulum dosyaları taranıyor...")
            bundle_dir = get_bundle_dir()

            # Locate payload zip or release directory
            if self.edition == "offline":
                zip_candidates = [
                    bundle_dir / "Local_Translator_Cevrimdisi_TR.zip",
                    Path("Local_Translator_Cevrimdisi_TR.zip"),
                    bundle_dir / "Local_Translator_0.10.0_TR.zip",
                    Path("Local_Translator_0.10.0_TR.zip"),
                ]
                release_dir = bundle_dir / "release_package_offline"
                if not release_dir.exists():
                    release_dir = Path("release_package_offline")
            else:
                zip_candidates = [
                    bundle_dir / "Local_Translator_Cevrimici_TR.zip",
                    Path("Local_Translator_Cevrimici_TR.zip"),
                    bundle_dir / "Local_Translator_0.11.0_TR.zip",
                    Path("Local_Translator_0.11.0_TR.zip"),
                ]
                release_dir = bundle_dir / "release_package_online"
                if not release_dir.exists():
                    release_dir = Path("release_package_online")

            zip_payload = None
            for cand in zip_candidates:
                if cand.exists():
                    zip_payload = cand
                    break

            if zip_payload and zip_payload.exists():
                self.progress.emit(25, f"Arşiv açılıyor ({zip_payload.name})...")
                with zipfile.ZipFile(zip_payload, "r") as z:
                    total_files = len(z.infolist())
                    for idx, member in enumerate(z.infolist(), 1):
                        z.extract(member, self.target_dir)
                        if idx % 10 == 0:
                            pct = 25 + int((idx / total_files) * 50)
                            self.progress.emit(pct, f"Dosyalar kopyalanıyor: {member.filename}")
            elif release_dir.exists():
                self.progress.emit(25, "Paket dosyaları kopyalanıyor...")
                shutil.copytree(release_dir, self.target_dir, dirs_exist_ok=True)
            else:
                self.finished_signal.emit(False, f"Kurulum paketi bulunamadı! Lütfen zip dosyasının programla aynı klasörde olduğundan emin olun.")
                return

            self.progress.emit(85, "Çeviri motoru yapılandırılıyor...")
            # Save chosen config
            config_path = self.target_dir / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(json.dumps(self.config_data, indent=2, ensure_ascii=False), encoding="utf-8")

            self.progress.emit(100, "Kurulum başarıyla tamamlandı!")
            ed_label = "Çevrimdışı (Local PC)" if self.edition == "offline" else "Çevrimiçi (Google / AI)"
            self.finished_signal.emit(True, f"Guild Wars 2 Türkçe Yerelleştirme ({ed_label}) başarıyla kuruldu!")
        except Exception as e:
            self.finished_signal.emit(False, f"Kurulum sırasında hata oluştu: {e}")


class UninstallWorker(QThread):
    progress = Signal(int, str)
    finished_signal = Signal(bool, str)

    def __init__(self, target_dir: Path):
        super().__init__()
        self.target_dir = target_dir

    def run(self):
        try:
            self.progress.emit(20, "Kaldırılacak dosyalar taranıyor...")
            files_to_remove = [
                self.target_dir / "version.dll",
                self.target_dir / "d3d11.dll",
                self.target_dir / "README_TURKCE.txt",
                self.target_dir / "addons" / "turkish_font.dll",
                self.target_dir / "addons" / "text_translator.dll",
            ]
            for idx, f in enumerate(files_to_remove, 1):
                if f.exists():
                    f.unlink()
                self.progress.emit(20 + idx * 10, f"Siliniyor: {f.name}")

            # Remove translation module directory
            mod_dir = self.target_dir / "addons" / "text_translator" / "modules" / "local_translator_tr"
            if mod_dir.exists():
                shutil.rmtree(mod_dir, ignore_errors=True)

            self.progress.emit(90, "Temizlik tamamlanıyor...")
            # If text_translator modules is empty, remove text_translator folder
            tt_dir = self.target_dir / "addons" / "text_translator"
            if tt_dir.exists() and not any(tt_dir.iterdir()):
                shutil.rmtree(tt_dir, ignore_errors=True)

            self.progress.emit(100, "Kaldırma işlemi tamamlandı!")
            self.finished_signal.emit(True, "Türkçe yama başarıyla kaldırıldı. Oyun orijinal haline getirildi.")
        except Exception as e:
            self.finished_signal.emit(False, f"Kaldırma sırasında hata oluştu: {e}")


class MainWindow(QMainWindow):
    def __init__(self, edition: str):
        super().__init__()
        self.edition = edition
        self.gw2_path: Path | None = None
        self.worker: QThread | None = None

        if self.edition == "offline":
            self.title_text = "Guild Wars 2 Türkçe Yerelleştirme"
            self.subtitle_text = f"Çevrimdışı Sürüm • %100 Yerel PC Makine Çevirisi • {APP_VERSION}"
            self.window_title = f"Guild Wars 2 Türkçe Yerelleştirme (Çevrimdışı) {APP_VERSION}"
        else:
            self.title_text = "Guild Wars 2 Türkçe Yerelleştirme"
            self.subtitle_text = f"Çevrimiçi Sürüm • Ultra-Hafif Paket (~18 MB) • {APP_VERSION}"
            self.window_title = f"Guild Wars 2 Türkçe Yerelleştirme (Çevrimiçi) {APP_VERSION}"

        self.setWindowTitle(self.window_title)
        self.setMinimumSize(800, 720)
        self.resize(840, 760)

        self.apply_dark_theme()
        self.init_ui()
        self.auto_detect_gw2()

    def apply_dark_theme(self):
        """Ultra-premium dark theme inspired by modern gaming aesthetics."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121316;
            }
            QWidget {
                color: #e4e4e7;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QFrame.card {
                background-color: #1a1b20;
                border: 1px solid #2a2b33;
                border-radius: 12px;
            }
            QLabel.title {
                font-size: 22px;
                font-weight: bold;
                color: #ffffff;
            }
            QLabel.subtitle {
                font-size: 13px;
                color: #a1a1aa;
            }
            QLabel.section {
                font-size: 15px;
                font-weight: bold;
                color: #f59e0b;
                margin-bottom: 4px;
            }
            QLabel.badge_active {
                background-color: #064e3b;
                color: #34d399;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 14px;
                border: 1px solid #059669;
            }
            QLabel.badge_inactive {
                background-color: #27272a;
                color: #9ca3af;
                font-weight: bold;
                border-radius: 6px;
                padding: 6px 14px;
                border: 1px solid #3f3f46;
            }
            QPushButton {
                background-color: #27272a;
                color: #ffffff;
                border: 1px solid #3f3f46;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #3f3f46;
                border-color: #52525b;
            }
            QPushButton.primary {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #ea580c);
                color: #ffffff;
                border: none;
                font-size: 14px;
                padding: 12px 24px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton.primary:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #f97316);
            }
            QPushButton.success {
                background-color: #059669;
                color: #ffffff;
                border: none;
                font-size: 14px;
                padding: 12px 24px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton.success:hover {
                background-color: #10b981;
            }
            QPushButton.danger {
                background-color: #7f1d1d;
                color: #fca5a5;
                border: 1px solid #991b1b;
                border-radius: 8px;
                padding: 8px 16px;
            }
            QLineEdit, QComboBox {
                background-color: #121316;
                border: 1px solid #3f3f46;
                border-radius: 6px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #f59e0b;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            QRadioButton {
                font-size: 13px;
                color: #e4e4e7;
                spacing: 10px;
                padding: 3px 0px;
            }
            QRadioButton:hover {
                color: #f59e0b;
            }
            QProgressBar {
                background-color: #121316;
                border: 1px solid #27272a;
                border-radius: 6px;
                height: 16px;
                text-align: center;
                color: #ffffff;
                font-size: 11px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d97706, stop:1 #ea580c);
                border-radius: 5px;
            }
        """)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header
        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(4)

        title_lbl = QLabel(self.title_text)
        title_lbl.setProperty("class", "title")
        subtitle_lbl = QLabel(self.subtitle_text)
        subtitle_lbl.setProperty("class", "subtitle")

        header_text_layout.addWidget(title_lbl)
        header_text_layout.addWidget(subtitle_lbl)
        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()

        self.status_badge = QLabel("Taranıyor...")
        self.status_badge.setProperty("class", "badge_inactive")
        header_layout.addWidget(self.status_badge)
        main_layout.addLayout(header_layout)

        # 2. Oyun Konumu Kartı (Game Directory Card)
        path_card = QFrame()
        path_card.setProperty("class", "card")
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(18, 14, 18, 14)
        path_layout.setSpacing(8)

        path_header = QLabel("OYUN KURULUM DİZİNİ")
        path_header.setProperty("class", "section")
        path_layout.addWidget(path_header)

        path_input_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Guild Wars 2 ana klasörü (Gw2-64.exe dosyasının bulunduğu yer)...")
        self.path_edit.textChanged.connect(self.on_path_changed)
        path_input_layout.addWidget(self.path_edit)

        browse_btn = QPushButton("Gözat...")
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self.on_browse)
        path_input_layout.addWidget(browse_btn)
        path_layout.addLayout(path_input_layout)

        self.path_info_lbl = QLabel("Oyun aranıyor...")
        self.path_info_lbl.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        path_layout.addWidget(self.path_info_lbl)
        main_layout.addWidget(path_card)

        # 3. Çeviri Motoru & Ayarlar Kartı
        settings_card = QFrame()
        settings_card.setProperty("class", "card")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(18, 14, 18, 14)
        settings_layout.setSpacing(10)

        if self.edition == "offline":
            # OFFLINE EDITION UI
            engine_header = QLabel("ÇEVRİMDIŞI ÇEVİRİ MOTORU (YEREL PC)")
            engine_header.setProperty("class", "section")
            settings_layout.addWidget(engine_header)

            desc_box = QFrame()
            desc_box.setStyleSheet("background-color: #121316; border: 1px solid #27272a; border-radius: 8px; padding: 12px;")
            desc_layout = QVBoxLayout(desc_box)
            desc_layout.setSpacing(6)

            info_title = QLabel("💻 Yerel OPUS-MT & CTranslate2 Motoru (Sıfır İnternet, Sıfır Lag)")
            info_title.setStyleSheet("color: #34d399; font-weight: bold; font-size: 14px;")
            desc_layout.addWidget(info_title)

            info_p1 = QLabel("• <b>İnternet bağlantısı gerektirmez:</b> Tüm oyun metinleri doğrudan bilgisayarınızın işlemcisi (CPU) üzerinde anında çevrilir.")
            info_p1.setStyleSheet("color: #d4d4d8; font-size: 12px;")
            info_p1.setWordWrap(True)
            desc_layout.addWidget(info_p1)

            info_p2 = QLabel("• <b>Kota ve API anahtarı yok:</b> Ücretsiz, sınırsız ve tamamen gizli. Paket içerisindeki yapay zeka modeli hazır olarak gelir.")
            info_p2.setStyleSheet("color: #d4d4d8; font-size: 12px;")
            info_p2.setWordWrap(True)
            desc_layout.addWidget(info_p2)
            settings_layout.addWidget(desc_box)

            # CPU Threads Selector
            thread_layout = QHBoxLayout()
            thread_lbl = QLabel("İşlemci Çekirdek Kullanımı (CPU Threads):")
            thread_lbl.setStyleSheet("color: #e4e4e7; font-weight: bold;")
            thread_layout.addWidget(thread_lbl)

            self.thread_combo = QComboBox()
            self.thread_combo.addItem("4 Çekirdek (Önerilen - Hızlı & Dengeli)", 4)
            self.thread_combo.addItem("2 Çekirdek (Düşük Donanımlı İşlemciler)", 2)
            self.thread_combo.addItem("6 Çekirdek (Yüksek Performans)", 6)
            self.thread_combo.addItem("8 Çekirdek (Maksimum Çeviri Hızı)", 8)
            self.thread_combo.addItem("Otomatik (İşlemcinin %25'i)", 0)
            self.thread_combo.setFixedWidth(280)
            thread_layout.addWidget(self.thread_combo)
            thread_layout.addStretch()
            settings_layout.addLayout(thread_layout)

        else:
            # ONLINE EDITION UI
            engine_header = QLabel("ÇEVİRİ MOTORU SEÇİMİ (BULUT & YAPAY ZEKA)")
            engine_header.setProperty("class", "section")
            settings_layout.addWidget(engine_header)

            self.engine_group = QButtonGroup(self)
            engines_layout = QVBoxLayout()
            engines_layout.setSpacing(8)

            self.rb_google = QRadioButton("Google Çeviri (Varsayılan - Ücretsiz, Hızlı, Sınırsız, Kurulumsuz)")
            self.rb_google.setMinimumHeight(24)
            self.engine_group.addButton(self.rb_google, 1)
            engines_layout.addWidget(self.rb_google)

            self.rb_gemini = QRadioButton("Google Gemini 1.5 Flash (Yapay Zeka - Akıcı Oyun Çevirisi, API Key Gerekir)")
            self.rb_gemini.setMinimumHeight(24)
            self.engine_group.addButton(self.rb_gemini, 2)
            engines_layout.addWidget(self.rb_gemini)

            self.rb_deepl = QRadioButton("DeepL API (Yüksek Kaliteli Çeviri - API Key Gerekir)")
            self.rb_deepl.setMinimumHeight(24)
            self.engine_group.addButton(self.rb_deepl, 3)
            engines_layout.addWidget(self.rb_deepl)

            self.rb_openai = QRadioButton("OpenAI GPT (GPT-4o-mini / GPT-4o - API Key Gerekir)")
            self.rb_openai.setMinimumHeight(24)
            self.engine_group.addButton(self.rb_openai, 4)
            engines_layout.addWidget(self.rb_openai)

            settings_layout.addLayout(engines_layout)

            # API Key container
            self.api_key_frame = QWidget()
            api_layout = QVBoxLayout(self.api_key_frame)
            api_layout.setContentsMargins(0, 4, 0, 0)
            api_layout.setSpacing(4)

            self.api_lbl = QLabel("API Anahtarı:")
            self.api_lbl.setStyleSheet("color: #d4d4d8; font-weight: bold;")

            api_input_row = QHBoxLayout()
            self.api_edit = QLineEdit()
            self.api_edit.setPlaceholderText("API anahtarınızı buraya yapıştırın...")
            self.api_edit.setEchoMode(QLineEdit.Password)
            api_input_row.addWidget(self.api_edit)

            self.toggle_key_btn = QPushButton("👁 Göster")
            self.toggle_key_btn.setCursor(Qt.PointingHandCursor)
            self.toggle_key_btn.setFixedWidth(100)
            self.toggle_key_btn.clicked.connect(self.toggle_api_key_visibility)
            api_input_row.addWidget(self.toggle_key_btn)

            api_layout.addWidget(self.api_lbl)
            api_layout.addLayout(api_input_row)
            settings_layout.addWidget(self.api_key_frame)

            self.rb_google.setChecked(True)
            self.api_key_frame.setVisible(False)
            self.engine_group.idToggled.connect(self.on_engine_toggled)

        # Save settings button
        save_layout = QHBoxLayout()
        save_layout.addStretch()
        self.save_btn = QPushButton("Ayarları Kaydet")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.clicked.connect(self.save_settings)
        save_layout.addWidget(self.save_btn)
        settings_layout.addLayout(save_layout)

        main_layout.addWidget(settings_card)

        # 4. Progress bar & status message
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setStyleSheet("color: #f59e0b; font-weight: bold;")
        self.progress_lbl.setVisible(False)
        main_layout.addWidget(self.progress_lbl)

        # 5. Aksiyon Butonları (Action Buttons)
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)

        self.install_btn = QPushButton("Türkçe Yamayı Kur")
        self.install_btn.setProperty("class", "primary")
        self.install_btn.setCursor(Qt.PointingHandCursor)
        self.install_btn.clicked.connect(self.install_patch)
        actions_layout.addWidget(self.install_btn)

        self.play_btn = QPushButton("Oyunu Başlat")
        self.play_btn.setProperty("class", "success")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.clicked.connect(self.launch_game)
        actions_layout.addWidget(self.play_btn)

        self.uninstall_btn = QPushButton("Yamayı Kaldır")
        self.uninstall_btn.setProperty("class", "danger")
        self.uninstall_btn.setCursor(Qt.PointingHandCursor)
        self.uninstall_btn.clicked.connect(self.uninstall_patch)
        actions_layout.addWidget(self.uninstall_btn)

        main_layout.addLayout(actions_layout)

        # 6. Bilgilendirme Kartı (Info Footer)
        info_card = QFrame()
        info_card.setStyleSheet("background-color: #18191e; border: 1px dashed #3f3f46; border-radius: 8px; padding: 10px;")
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(4)
        tip_title = QLabel("💡 Oyuncular İçin Önemli İpuçları:")
        tip_title.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 12px;")
        tip_text1 = QLabel("• <b>Addon veya menü karmaşası yok:</b> Kurulum tamamlandığında oyuna doğrudan girebilirsiniz; metinler ve fontlar kendiliğinden Türkçe açılır.")
        tip_text1.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        tip_text1.setWordWrap(True)
        tip_text2 = QLabel("• <b>Anlık İngilizceye Dönüş:</b> Oyun içinde orijinal İngilizceyi görmek isterseniz <code>Ctrl + O</code> -> Keybinds -> Text Translator 'Toggle' tuşu atayabilirsiniz.")
        tip_text2.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        tip_text2.setWordWrap(True)
        info_layout.addWidget(tip_title)
        info_layout.addWidget(tip_text1)
        info_layout.addWidget(tip_text2)
        main_layout.addWidget(info_card)

    def toggle_api_key_visibility(self):
        if hasattr(self, "api_edit"):
            if self.api_edit.echoMode() == QLineEdit.Password:
                self.api_edit.setEchoMode(QLineEdit.Normal)
                self.toggle_key_btn.setText("🔒 Gizle")
            else:
                self.api_edit.setEchoMode(QLineEdit.Password)
                self.toggle_key_btn.setText("👁 Göster")

    def on_engine_toggled(self, btn_id: int, checked: bool):
        if not checked or not hasattr(self, "api_key_frame"):
            return
        if btn_id == 1:  # Google
            self.api_key_frame.setVisible(False)
        elif btn_id == 2:  # Gemini
            self.api_key_frame.setVisible(True)
            self.api_lbl.setText("Google Gemini API Key (aistudio.google.com):")
        elif btn_id == 3:  # DeepL
            self.api_key_frame.setVisible(True)
            self.api_lbl.setText("DeepL API Key:")
        elif btn_id == 4:  # OpenAI
            self.api_key_frame.setVisible(True)
            self.api_lbl.setText("OpenAI API Key (platform.openai.com):")

    def auto_detect_gw2(self):
        candidates = find_gw2_installations()
        if candidates:
            first_match = candidates[0]
            self.set_gw2_path(first_match.parent)
            self.path_info_lbl.setText(f"✓ Guild Wars 2 otomatik olarak tespit edildi: {first_match.parent}")
            self.path_info_lbl.setStyleSheet("color: #34d399; font-size: 12px; font-weight: bold;")
        else:
            self.path_info_lbl.setText("Guild Wars 2 otomatik bulunamadı. Lütfen 'Gözat' butonuna tıklayarak Gw2-64.exe klasörünü seçin.")
            self.path_info_lbl.setStyleSheet("color: #f87171; font-size: 12px;")
            self.update_status(False)

    def on_browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Guild Wars 2 Kurulu Olduğu Klasörü Seçin")
        if folder:
            p = Path(folder)
            if (p / "Gw2-64.exe").exists():
                self.set_gw2_path(p)
            elif p.name.lower() == "gw2-64.exe":
                self.set_gw2_path(p.parent)
            else:
                QMessageBox.warning(self, "Hata", "Seçilen klasörde 'Gw2-64.exe' dosyası bulunamadı!\nLütfen oyunun ana kurulum klasörünü seçin.")

    def set_gw2_path(self, path: Path):
        self.gw2_path = path
        self.path_edit.blockSignals(True)
        self.path_edit.setText(str(path))
        self.path_edit.blockSignals(False)
        self.check_patch_status()
        self.load_existing_config()

    def on_path_changed(self, text: str):
        p = Path(text.strip())
        if (p / "Gw2-64.exe").exists():
            self.gw2_path = p
            self.path_info_lbl.setText(f"✓ Gw2-64.exe doğrulandı: {p}")
            self.path_info_lbl.setStyleSheet("color: #34d399; font-size: 12px;")
            self.check_patch_status()
            self.load_existing_config()
        else:
            self.gw2_path = None
            self.path_info_lbl.setText("Bu klasörde Gw2-64.exe bulunamadı.")
            self.path_info_lbl.setStyleSheet("color: #f87171; font-size: 12px;")
            self.update_status(False)

    def check_patch_status(self):
        if not self.gw2_path:
            self.update_status(False)
            return

        has_version = (self.gw2_path / "version.dll").exists()
        has_d3d11 = (self.gw2_path / "d3d11.dll").exists()
        has_module = (self.gw2_path / "addons" / "text_translator" / "modules" / "local_translator_tr" / "Local_Translator_TR.exe").exists()

        if has_version and has_d3d11 and has_module:
            self.update_status(True)
        else:
            self.update_status(False)

    def update_status(self, is_installed: bool):
        if is_installed:
            self.status_badge.setText("● Türkçe Yama Kurulu ve Aktif")
            self.status_badge.setProperty("class", "badge_active")
            self.install_btn.setText("Yamayı Yeniden Kur / Güncelle")
            self.uninstall_btn.setEnabled(True)
        else:
            self.status_badge.setText("○ Türkçe Yama Kurulu Değil")
            self.status_badge.setProperty("class", "badge_inactive")
            self.install_btn.setText("Türkçe Yamayı Kur")
            self.uninstall_btn.setEnabled(False)
        self.status_badge.style().unpolish(self.status_badge)
        self.status_badge.style().polish(self.status_badge)

    def load_existing_config(self):
        if not self.gw2_path:
            return
        cfg_file = self.gw2_path / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR" / "config.json"
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                if self.edition == "offline":
                    th = data.get("threads", 4)
                    for i in range(self.thread_combo.count()):
                        if self.thread_combo.itemData(i) == th:
                            self.thread_combo.setCurrentIndex(i)
                            break
                else:
                    backend = data.get("backend", "google")
                    if backend == "google":
                        self.rb_google.setChecked(True)
                    elif backend == "gemini":
                        self.rb_gemini.setChecked(True)
                        self.api_edit.setText(data.get("gemini_api_key", ""))
                    elif backend == "deepl":
                        self.rb_deepl.setChecked(True)
                        self.api_edit.setText(data.get("deepl_api_key", ""))
                    elif backend == "openai":
                        self.rb_openai.setChecked(True)
                        self.api_edit.setText(data.get("openai_api_key", ""))
            except Exception:
                pass

    def get_current_config(self) -> dict:
        if self.edition == "offline":
            threads_val = self.thread_combo.currentData()
            return {
                "backend": "local",
                "threads": threads_val if threads_val else 4,
                "char_mode": "smart",
                "translate_chat": False
            }
        else:
            backend = "google"
            if self.rb_gemini.isChecked():
                backend = "gemini"
            elif self.rb_deepl.isChecked():
                backend = "deepl"
            elif self.rb_openai.isChecked():
                backend = "openai"

            key = self.api_edit.text().strip()
            return {
                "backend": backend,
                "deepl_api_key": key if backend == "deepl" else "",
                "gemini_api_key": key if backend == "gemini" else "",
                "openai_api_key": key if backend == "openai" else "",
                "openai_model": "gpt-4o-mini",
                "char_mode": "smart",
                "translate_chat": False
            }

    def save_settings(self):
        if not self.gw2_path:
            QMessageBox.warning(self, "Hata", "Lütfen önce oyun klasörünü belirleyin.")
            return

        cfg_path = self.gw2_path / "addons" / "text_translator" / "modules" / "local_translator_tr" / "TR" / "config.json"
        if not cfg_path.parent.exists():
            QMessageBox.information(self, "Bilgi", "Türkçe yama henüz kurulmamış. 'Türkçe Yamayı Kur' butonuna bastığınızda seçilen ayar uygulanacaktır.")
            return

        try:
            cfg = self.get_current_config()
            cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            if self.edition == "offline":
                QMessageBox.information(self, "Başarılı", f"Çevrimdışı motor ayarları kaydedildi (Threads: {cfg.get('threads')})!")
            else:
                QMessageBox.information(self, "Başarılı", f"Çeviri motoru '{cfg['backend'].upper()}' olarak kaydedildi!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayar dosyası kaydedilemedi: {e}")

    def install_patch(self):
        if not self.gw2_path:
            QMessageBox.warning(self, "Hata", "Lütfen geçerli bir Guild Wars 2 klasörü seçin.")
            return

        if is_gw2_running():
            reply = QMessageBox.question(
                self, "Oyun Açık",
                "Guild Wars 2 şu anda çalışıyor!\nKurulum yapabilmek için oyunu kapatmanız gerekmektedir. Şimdi kapatılsın mı?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                os.system("taskkill /f /im Gw2-64.exe >nul 2>&1")
            else:
                return

        self.set_ui_busy(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_lbl.setVisible(True)

        cfg = self.get_current_config()
        self.worker = InstallWorker(self.gw2_path, cfg, self.edition)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_install_finished)
        self.worker.start()

    def on_worker_progress(self, pct: int, msg: str):
        self.progress_bar.setValue(pct)
        self.progress_lbl.setText(msg)

    def on_install_finished(self, success: bool, msg: str):
        self.set_ui_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        if success:
            QMessageBox.information(self, "Tebrikler!", msg)
            self.check_patch_status()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def uninstall_patch(self):
        if not self.gw2_path:
            return

        if is_gw2_running():
            QMessageBox.warning(self, "Uyarı", "Yamayı kaldırabilmek için önce Guild Wars 2'yi kapatmalısınız.")
            return

        reply = QMessageBox.question(
            self, "Yamayı Kaldır",
            "Türkçe yamayı kaldırmak ve oyunu orijinal İngilizce haline döndürmek istediğinizden emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.set_ui_busy(True)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_lbl.setVisible(True)

        self.worker = UninstallWorker(self.gw2_path)
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished_signal.connect(self.on_uninstall_finished)
        self.worker.start()

    def on_uninstall_finished(self, success: bool, msg: str):
        self.set_ui_busy(False)
        self.progress_bar.setVisible(False)
        self.progress_lbl.setVisible(False)
        if success:
            QMessageBox.information(self, "Kaldırıldı", msg)
            self.check_patch_status()
        else:
            QMessageBox.critical(self, "Hata", msg)

    def launch_game(self):
        if not self.gw2_path:
            QMessageBox.warning(self, "Hata", "Oyun klasörü belirlenemedi.")
            return

        exe = self.gw2_path / "Gw2-64.exe"
        if not exe.exists():
            QMessageBox.critical(self, "Hata", f"{exe} dosyası bulunamadı!")
            return

        try:
            subprocess.Popen([str(exe)], cwd=str(self.gw2_path))
            QMessageBox.information(self, "Oyun Başlatıldı", "Guild Wars 2 başlatıldı. İyi oyunlar!")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Oyun başlatılamadı: {e}")

    def set_ui_busy(self, busy: bool):
        self.install_btn.setEnabled(not busy)
        self.uninstall_btn.setEnabled(not busy)
        self.play_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        self.path_edit.setEnabled(not busy)


def main():
    edition = get_edition()
    app = QApplication(sys.argv)
    window = MainWindow(edition=edition)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
