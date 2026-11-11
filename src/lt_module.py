"""Local Translator TR: Guild Wars 2 Türkçe Çeviri Modülü (v0.12.0 çekirdeği).

Ideka'nın "Text Translator" Nexus eklentisi ile modulep v2 protokolü üzerinden haberleşir.
Yalnızca Türkçe (tr) dilini destekler.
Özellikler:
- Çevrimdışı CTranslate2 + OPUS-MT çeviri motoru (ana öncelik) + opsiyonel bulut motorları
- GW2 Turkish Font Injector durumuna göre dinamik karakter modu:
  * Font Injector AÇIK ("full"): ş, Ş, ğ, Ğ, İ, ı, ç, Ç, ö, Ö, ü, Ü tam görünür
  * Font Injector KAPALI ("ascii_6"): yalnızca oyunda kutucuk çıkaran 6 harf (ş->s, Ş->S, ğ->g,
    Ğ->G, İ->I, ı->i) dönüştürülür; ç, Ç, ö, Ö, ü, Ü korunur
- Eşya ve Mekan İsimlerini İngilizce Koruma (3 katmanlı hibrit filtre)
- Canlı Çeviri Düzenleyici (127.0.0.1:8770)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import re
import sqlite3
import struct
import sys
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lt_server as lt  # noqa: E402
from patch_db import (CachePatch, PieceUpdater, SHOW_MODES, has_table, key_tag,  # noqa: E402
                      shown_text, sync_key_tags, untagged)
import editor  # noqa: E402
import map_upload  # noqa: E402

VERSION = "0.12.0"
PROTOCOL = 2
SOURCE_LANG = 0
RESULT_VERSION = 1
CACHE_KEY = lt.LANG.cache_key
MAX_MESSAGE = 0x10_0000
KIND_TEXT, KIND_CANCEL = 0, 1

STATS_EVERY = 300
SHOW_KEYS_FILE = "show_keys.txt"
CONFIG_FILE = "config.json"


def show_keys_mode(lang_dir: Path) -> str | None:
    try:
        words = (lang_dir / SHOW_KEYS_FILE).read_text(encoding="utf-8", errors="replace").split()
    except OSError:
        return None
    return "all" if words and words[0].lower() in ("all", "hepsi", "tum") else "text"


def load_tr_config(lang_dir: Path, module_dir: Path) -> dict:
    """TR/config.json ayarlarını okur ve Font Injector durumunu tespit eder."""
    cfg = {
        "backend": "offline",
        "threads": 0,
        "font_injector": True,
        "char_mode": "full",
        "keep_items_english": True,
        "api_key": "",
        "model_name": "",
    }
    cfg_path = lang_dir / CONFIG_FILE
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            if isinstance(raw, dict):
                cfg.update(raw)
        except Exception as exc:  # noqa: BLE001
            log.warning("config.json okunamadi (%s): varsayilan ayarlar kullaniliyor", exc)

    # Check if turkish_font.disabled marker exists in addons/ directory
    # module_dir is typically <GW2>/addons/text_translator/modules/local_translator_tr
    addons_dir = module_dir.parent.parent.parent
    disabled_marker = addons_dir / "turkish_font.disabled"
    if disabled_marker.is_file() or cfg.get("font_injector") is False or cfg.get("char_mode") == "ascii_6":
        cfg["font_injector"] = False
        cfg["char_mode"] = "ascii_6"
    else:
        cfg["font_injector"] = True
        cfg["char_mode"] = "full"
    return cfg


TRIVIAL_RE = re.compile(r"\(\(\d+\)\)|\(new string\)")

log = logging.getLogger("lt")


# --------------------------------------------------------------------------- #
# Streams and protocol
# --------------------------------------------------------------------------- #
def binary_streams():
    if os.name != "nt":
        return sys.stdin.buffer, sys.stdout.buffer, sys.stderr.buffer
    import ctypes
    import msvcrt
    k32 = ctypes.windll.kernel32
    k32.GetStdHandle.restype = ctypes.c_void_p
    out = []
    for num, mode in ((-10, "rb"), (-11, "wb"), (-12, "wb")):
        h = k32.GetStdHandle(ctypes.c_uint32(num & 0xFFFFFFFF))
        if not h or h == ctypes.c_void_p(-1).value:
            out.append(None)
            continue
        fd = msvcrt.open_osfhandle(h, os.O_RDONLY if mode == "rb" else 0)
        msvcrt.setmode(fd, os.O_BINARY)
        out.append(os.fdopen(fd, mode, buffering=0))
    return tuple(out)


def put_string(text: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > 0xFFFF:
        raise ValueError("string longer than 65535 bytes")
    return struct.pack("<H", len(raw)) + raw


class Channel:
    def __init__(self, rx, tx) -> None:
        self.rx, self.tx = rx, tx
        self.lock = threading.Lock()

    def _read_exact(self, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = self.rx.read(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def read(self) -> bytes | None:
        head = self._read_exact(4)
        if head is None:
            return None
        (size,) = struct.unpack("<I", head)
        if size > MAX_MESSAGE:
            raise ValueError(f"message too big ({size} bytes)")
        return self._read_exact(size)

    def send(self, contents: list[bytes]) -> None:
        data = b"".join(struct.pack("<I", len(c)) + c for c in contents)
        with self.lock:
            self.tx.write(data)
            self.tx.flush()

    def handshake(self) -> None:
        self.send([struct.pack("<IiI", PROTOCOL, SOURCE_LANG, RESULT_VERSION) + put_string(CACHE_KEY)])

    @staticmethod
    def text(key: int, src_hash: int, text: str) -> bytes:
        return bytes([KIND_TEXT]) + struct.pack("<IQ", key, src_hash) + put_string(text)

    @staticmethod
    def parse_text(msg: bytes) -> tuple[int, int, str] | None:
        if len(msg) < 15 or msg[0] != KIND_TEXT:
            return None
        key, src_hash, n = struct.unpack_from("<IQH", msg, 1)
        return key, src_hash, msg[15:15 + n].decode("utf-8", "replace")

    @staticmethod
    def cancel(key: int) -> bytes:
        return bytes([KIND_CANCEL]) + struct.pack("<I", key)


BELOW_NORMAL_PRIORITY_CLASS = 0x4000


def lower_priority() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.GetCurrentProcess.restype = ctypes.c_void_p
        k32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        k32.SetPriorityClass.restype = ctypes.c_int
        if k32.SetPriorityClass(k32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS):
            log.info("process priority: below normal")
        else:
            log.warning("cannot lower the process priority (Windows error %d)", ctypes.GetLastError())
    except Exception as exc:  # noqa: BLE001
        log.warning("cannot lower the process priority: %s", exc)


def model_threads(requested: int | None = None) -> int:
    cpus = os.cpu_count() or 2
    if requested and requested > 0:
        return min(requested, cpus)
    return max(1, min(2, cpus // 4))


class StderrHandler(logging.Handler):
    LETTERS = {logging.ERROR: "e", logging.WARNING: "w", logging.INFO: "i", logging.DEBUG: "d"}

    def __init__(self, stream) -> None:
        super().__init__()
        self.stream = stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            letter = self.LETTERS.get(record.levelno, "e" if record.levelno > logging.ERROR else "i")
            msg = self.format(record).replace("\r", "").replace("\n", "\0")
            self.stream.write(f"{letter}: {msg}\n".encode("utf-8", "replace"))
            self.stream.flush()
        except Exception:  # noqa: BLE001
            pass


# --------------------------------------------------------------------------- #
# Glossary cleanup on the addon's cache.db
# --------------------------------------------------------------------------- #
class ModuleEngine(lt.Engine):
    def _purge_addon_db(self, texts: set[str]) -> None:
        texts = {t for t in texts if len(t.strip()) >= 3}
        if not texts:
            return

        def find(con: sqlite3.Connection) -> set[int]:
            doomed: set[int] = set()
            for t in texts:
                doomed.update(k for (k,) in con.execute(
                    "SELECT id FROM translations WHERE cache_key = ? AND instr(text, ?) > 0",
                    (CACHE_KEY, t)))
            return doomed

        self._forget(find, "glossary changed")

    def _purge_addon_lines(self, lines: set[str]) -> None:
        if not lines:
            return

        def find(con: sqlite3.Connection) -> set[int]:
            return {k for k, text in con.execute(
                        "SELECT id, text FROM translations WHERE cache_key = ?", (CACHE_KEY,))
                    if any(line in lines for line in untagged(k, text).split("\n"))}

        self._forget(find, "left in English or with invented text, translated again")

    def _forget(self, find, why: str) -> None:
        db = self.addon_db
        if not has_table(db):
            return
        try:
            con = sqlite3.connect(str(db), timeout=10)
            try:
                with con:
                    doomed = find(con)
                    if self.patch:
                        doomed -= self.patch.protected(doomed)
                    if self.patch:
                        self.patch.suppress(doomed)
                    con.executemany("DELETE FROM translations WHERE cache_key = ? AND id = ?",
                                    [(CACHE_KEY, k) for k in doomed])
            finally:
                con.close()
            log.info("cache.db: %d old translations removed (%s; asked again at next game start)",
                     len(doomed), why)
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot clean %s: %s", db, exc)


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class IdCheck:
    def __init__(self, keymap: lt.KeyMap | None, on_fail=None, on_pass=None) -> None:
        self.keymap = keymap
        self.on_fail, self.on_pass = on_fail, on_pass
        self.match = self.mismatch = 0
        self.failed = False
        self.reported = False
        self.known: dict[int, str] = {}
        if keymap:
            with keymap.lock:
                self.known = dict(keymap.con.execute(
                    "SELECT key, en FROM texts WHERE how NOT LIKE 'contrib%'"))

    def see(self, key: int, en: str) -> None:
        if self.reported or key not in self.known:
            return
        if lt.norm(self.known[key]) == lt.norm(en):
            self.match += 1
        else:
            self.mismatch += 1
        if self.match + self.mismatch >= 50:
            self.reported = True
            if self.mismatch > self.match:
                self.failed = True
                log.error("string IDs do not match the map (%d equal, %d different): "
                          "patch DISABLED", self.match, self.mismatch)
                if self.on_fail:
                    threading.Thread(target=self.on_fail, args=(f"{self.match} equal, "
                                     f"{self.mismatch} different",), daemon=True,
                                     name="patch-withdraw").start()
            else:
                log.info("string IDs check: %d equal, %d different -> same IDs as the map",
                         self.match, self.mismatch)
                if self.on_pass:
                    threading.Thread(target=self.on_pass, daemon=True, name="patch-ids-ok").start()


class Stats:
    def __init__(self, engine: ModuleEngine, every: float = STATS_EVERY) -> None:
        self.engine = engine
        self.every = every
        self.since = time.monotonic()
        self.cpu_since = time.process_time()
        self.base = self._totals()
        self.counts = {"patch": 0, "cache": 0, "model": 0, "empty": 0}
        self.stale = 0
        self.waits: list[float] = []
        self.queue_max = 0
        self.sends = 0
        self.live = 0

    def _totals(self) -> tuple[int, float, float, int]:
        e = self.engine
        return e.done_count, e.time_prepare, e.time_model, len(e.given_up)

    def due(self) -> bool:
        return time.monotonic() - self.since >= self.every

    def report(self, waiting: dict[int, float]) -> str | None:
        now = time.monotonic()
        cpu_now = time.process_time()
        elapsed = max(now - self.since, 1e-6)
        cpu = (cpu_now - self.cpu_since) * 100 / elapsed
        period = f"{elapsed / 60:.0f} min" if elapsed >= 90 else f"{elapsed:.0f} s"
        done, prep, model, gave_up = (a - b for a, b in zip(self._totals(), self.base))
        total = sum(self.counts.values())
        text = None
        if total or done or cpu >= 1 or self.stale or self.live:
            parts = ", ".join(f"{k} {v * 100 / total:.0f}%" for k, v in self.counts.items()) if total else ""
            text = (f"stats {period}: cpu {cpu:.0f}% of one core ({os.cpu_count() or '?'} cores); "
                    f"{total} requests" + (f" ({parts})" if parts else ""))
            if self.waits:
                w = sorted(self.waits)
                p95 = w[min(len(w) - 1, int(len(w) * 0.95))]
                text += (f"; model wait avg {sum(w) / len(w):.1f} s, p95 {p95:.1f} s, "
                         f"max {w[-1]:.1f} s")
            if waiting:
                text += (f"; still waiting {len(waiting)} "
                         f"(oldest {now - min(waiting.values()):.0f} s)")
            text += f"; queue max {self.queue_max} lines; sent {self.sends} groups"
            busy = prep + model
            speed = f"{done / busy:.1f} lines/s, " if busy > 0 else ""
            text += (f"; translated {done} lines in {busy:.1f} s ({speed}glossary {prep:.1f} s, "
                     f"model {model:.1f} s)")
            if gave_up:
                text += f"; given up {gave_up} lines"
            if self.stale:
                text += f"; patch outdated (English changed) {self.stale} texts"
            if self.live:
                text += f"; patch sent to the game {self.live} texts"
        self.since, self.cpu_since, self.base = now, cpu_now, self._totals()
        self.counts = dict.fromkeys(self.counts, 0)
        self.waits = []
        self.queue_max = 0
        self.sends = 0
        self.stale = 0
        self.live = 0
        return text


class Dispatcher:
    def __init__(self, engine: ModuleEngine, patch: CachePatch, keymap: lt.KeyMap | None,
                 channel: Channel, stats_every: float = STATS_EVERY,
                 cache_db: Path | None = None) -> None:
        self.engine, self.patch, self.keymap, self.channel = engine, patch, keymap, channel
        self.inbox: queue.SimpleQueue[tuple[int, int, str]] = queue.SimpleQueue()
        self.pending: dict[int, tuple[str, int]] = {}
        self.missing: dict[int, set[str]] = {}
        self.waiting: dict[str, set[int]] = {}
        self.ids = IdCheck(keymap, on_fail=lambda why: patch.withdraw(cache_db, why),
                           on_pass=lambda: patch.ids_ok(cache_db))
        self.answered = 0
        self.show_keys = patch.show_keys
        self.char_mode = patch.char_mode
        self.arrived: dict[int, float] = {}
        self.suggested: set[int] = set()
        self.stats = Stats(engine, stats_every)
        with engine.cv:
            engine.finished = []

    def submit(self, key: int, src_hash: int, text: str) -> None:
        self.inbox.put((key, src_hash, text))
        with self.engine.cv:
            self.engine.cv.notify_all()

    def _result(self, line: str) -> str:
        fixed = self.engine.glossary.lookup(line, keep_items=self.engine.keep_items_english)
        return fixed if fixed is not None else self.engine.cache.get(line, line)

    def _ready(self, line: str) -> bool:
        e = self.engine
        return (line in e.cache or line in e.given_up
                or e.glossary.lookup(line, keep_items=e.keep_items_english) is not None
                or not lt.Engine._needs_translation(line))

    def _enqueue(self, line: str) -> None:
        e = self.engine
        if line not in e.queued:
            e.queued.add(line)
            e.queue.append(line)

    def _try(self, key: int, src_hash: int, text: str,
             out: list[tuple[int, int, str, str]]) -> bool:
        lines = text.split("\n")
        missing = {line for line in lines if not self._ready(line)}
        if not missing:
            self.pending.pop(key, None)
            self.missing.pop(key, None)
            started = self.arrived.pop(key, None)
            if started is None:
                self.stats.counts["cache"] += 1
            else:
                self.stats.counts["model"] += 1
                self.stats.waits.append(time.monotonic() - started)
            out.append((key, src_hash, text, "\n".join(self._result(line) for line in lines)))
            return False
        self.pending[key] = (text, src_hash)
        self.missing[key] = missing
        self.arrived.setdefault(key, time.monotonic())
        for line in missing:
            self.waiting.setdefault(line, set()).add(key)
            self._enqueue(line)
        return True

    def _forget(self, key: int) -> None:
        self.arrived.pop(key, None)
        if self.pending.pop(key, None) is None:
            return
        for line in self.missing.pop(key, ()):
            keys = self.waiting.get(line)
            if keys is not None:
                keys.discard(key)
                if not keys:
                    del self.waiting[line]

    def run(self) -> None:
        e = self.engine
        while True:
            out: list[tuple[int, int, str, str]] = []
            with e.cv:
                if self.inbox.empty() and not e.finished:
                    e.cv.wait(0.5)
                queued = False
                while True:
                    try:
                        key, src_hash, text = self.inbox.get_nowait()
                    except queue.Empty:
                        break
                    self._forget(key)
                    self.ids.see(key, text)
                    if not text.strip() or TRIVIAL_RE.fullmatch(text.strip()):
                        self.stats.counts["empty"] += 1
                        out.append((key, src_hash, text, text))
                        continue
                    off = self.ids.failed or self.patch.ids_failed()
                    s = None if off else self.patch.valid_suggestion(
                        key, lt.hash_int(f"{src_hash:016x}"))
                    if s is not None:
                        self.stats.counts["patch"] += 1
                        self.suggested.add(key)
                        out.append((key, src_hash, text, s.suggestion))
                        continue
                    fixed, stale = (None, False) if off else self.patch.lookup(key, src_hash)
                    if stale:
                        self.stats.stale += 1
                    if fixed is not None:
                        self.stats.counts["patch"] += 1
                        out.append((key, src_hash, text, fixed))
                        continue
                    queued = self._try(key, src_hash, text, out) or queued
                done, e.finished = e.finished, []
                for line in done:
                    for key in self.waiting.pop(line, ()):
                        left = self.missing.get(key)
                        if left is None:
                            continue
                        left.discard(line)
                        if not left:
                            queued = self._try(key, self.pending[key][1], self.pending[key][0],
                                               out) or queued
                if queued:
                    e.cv.notify_all()
                self.stats.queue_max = max(self.stats.queue_max, len(e.queue))
                report = self.stats.report(self.arrived) if self.stats.due() else None
            if report:
                log.info("%s", report)
            if out:
                self._send(out)

    def push(self, rows: list[tuple[int, int, str]]) -> int:
        msgs = []
        for key, h, text in rows:
            try:
                msgs.append(Channel.text(key, h, lt.fix_turkish_chars(text, self.char_mode)))
            except ValueError:
                log.warning("patch text of key %d too long: not sent", key)
        if not msgs:
            return 0
        with self.engine.cv:
            for key, _h, _t in rows:
                self._forget(key)
            self.stats.live += len(msgs)
        self.channel.send(msgs)
        return len(msgs)

    def _send(self, out: list[tuple[int, int, str, str]]) -> None:
        msgs = []
        for key, h, en, tr_text in out:
            display_tr = shown_text(key, tr_text, self.show_keys, self.char_mode)
            try:
                msgs.append(Channel.text(key, h, display_tr))
            except ValueError:
                msgs.append(Channel.text(key, h, key_tag(key, en, self.show_keys) + en))
        self.channel.send(msgs)
        self.stats.sends += 1
        before = self.answered
        self.answered += len(out)
        if before // 1000 != self.answered // 1000:
            log.info("%d texts answered, %d waiting for the model, %d lines in queue",
                     self.answered, len(self.pending), len(self.engine.queue))
        if self.keymap and not self.ids.failed:
            try:
                # map_tr.db always stores authentic Turkish (tr_text) so switching Font Injector ON
                # can restore full Turkish characters without re-translating!
                self.keymap.save(map_rows(out, self.suggested))
                self.keymap.learn_english([(k, en) for k, _h, en, _tr in out if k in self.suggested])
            except Exception as exc:  # noqa: BLE001
                log.debug("map save failed: %s", exc)
        self.suggested.difference_update(k for k, _h, _en, _tr in out)


def map_rows(out: list[tuple[int, int, str, str]], suggested: set[int]
             ) -> list[tuple[int, str, str | None, str]]:
    rows: list[tuple[int, str, str | None, str]] = []
    for k, _h, en, tr_text in out:
        if k in suggested or not en.strip():
            continue
        if en != tr_text:
            rows.append((k, en, tr_text, "live"))
        elif lt.Engine._needs_translation(en):
            rows.append((k, en, None, "live"))
    return rows


def cache_db_watcher(patch: CachePatch, cache_db: Path, map_db: Path | None = None) -> None:
    """Addon cache.db'yi oluşturur oluşturmaz yama, show_keys ve char_mode (Font Injector)
    senkronizasyonunu uygular."""
    for _ in range(720):
        try:
            if has_table(cache_db, need_hash=True):
                n = sync_key_tags(cache_db, CACHE_KEY, patch.show_keys, patch.char_mode, map_db=map_db)
                if n:
                    log.info("cache.db: %d metin guncellendi (show_keys=%s, char_mode=%s)",
                             n, patch.show_keys or "off", patch.char_mode)
                patch.apply(cache_db)
                return
        except Exception as exc:  # noqa: BLE001
            log.warning("cannot apply the patch to %s: %s", cache_db, exc)
            return
        time.sleep(5)


def module_language(module_dir: Path, requested: str | None) -> str | None:
    """Bu derleme yalnızca Türkçe ('tr') dilini destekler."""
    if requested and requested.lower() not in lt.LANGUAGES:
        return None
    return "tr"


def main() -> int:
    module_dir = lt.app_dir()
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="tr", help="Dil kodu (yalnızca tr)")
    ap.add_argument("--fake", action="store_true", help="Test modu: '[TR] text'")
    ap.add_argument("--lang-dir", type=Path, default=None, help="Veri klasörü (varsayılan TR\\)")
    ap.add_argument("--cache-db", type=Path, default=module_dir / "cache.db")
    ap.add_argument("--patch-file", type=Path, default=None, help="Yerel yama dosyası")
    ap.add_argument("--no-update", action="store_true")
    ap.add_argument("--branch", default=lt.DEFAULT_BRANCH)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--editor-port", type=int, default=editor.EDITOR_PORT, metavar="PORT")
    ap.add_argument("--threads", type=int, default=None)
    ap.add_argument("--stats-every", type=int, default=STATS_EVERY, metavar="SECONDS")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--upload-url", default=map_upload.UPLOAD_URL, help=argparse.SUPPRESS)
    ap.add_argument("--upload-first", type=float, default=map_upload.FIRST_DELAY, help=argparse.SUPPRESS)
    ap.add_argument("--export-review", type=Path, metavar="CSV")
    ap.add_argument("--import-review", type=Path, metavar="CSV")
    ap.add_argument("--show-keys", choices=(*SHOW_MODES, "off"))
    args, unknown = ap.parse_known_args()

    code = module_language(module_dir, args.lang)
    if code is None:
        (module_dir / "local_translator.log").write_text(
            f"Local Translator TR v{VERSION}: yalnızca Türkçe (tr) desteklenmektedir (--lang {args.lang!r})\n",
            encoding="utf-8")
        return 3
    global CACHE_KEY
    lang = lt.set_language("tr")
    CACHE_KEY = lang.cache_key
    if args.lang_dir is None:
        args.lang_dir = module_dir / lang.data_dir

    if args.export_review:
        n = lt.export_review(args.lang_dir / lang.file("map", ".db"),
                             args.patch_file or args.lang_dir / lang.file("patch", ".json"),
                             args.export_review)
        print(f"{n} rows written to {args.export_review}")
        return 0
    if args.import_review:
        if not args.patch_file:
            print(f"--import-review needs --patch-file (patch\\{lang.file('patch', '.json')})")
            return 1
        changed, removed = lt.import_review(args.import_review, args.patch_file)
        print(f"patch {args.patch_file}: {changed} added/changed, {removed} removed")
        return 0
    if args.show_keys:
        flag = args.lang_dir / SHOW_KEYS_FILE
        mode = None if args.show_keys == "off" else args.show_keys
        if mode:
            flag.write_text(f"{mode}\n\nLocal Translator TR: metinler String ID ile başlar.\n",
                            encoding="utf-8")
        else:
            flag.unlink(missing_ok=True)
        cfg = load_tr_config(args.lang_dir, module_dir)
        map_db = args.lang_dir / lang.file("map", ".db")
        n = sync_key_tags(args.cache_db, CACHE_KEY, mode, cfg["char_mode"], map_db=map_db)
        print(f"show keys {args.show_keys}: {n} texts changed in {args.cache_db}")
        return 0

    rx, tx, err = binary_streams()
    if rx is None or tx is None:
        return 2
    channel = Channel(rx, tx)
    channel.handshake()
    sys.stdout = open(os.devnull, "w")

    args.lang_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [RotatingFileHandler(
        module_dir / lang.file("local_translator", ".log"), maxBytes=500_000, backupCount=1,
        encoding="utf-8")]
    handlers[0].setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    if err is not None:
        h = StderrHandler(err)
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter("%(message)s"))
        handlers.append(h)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO, handlers=handlers)

    cfg = load_tr_config(args.lang_dir, module_dir)
    log.info("Local Translator %s v%s started (protocol %d, cache_key=%s, backend=%s, char_mode=%s, keep_items=%s)",
             lang.label, VERSION, PROTOCOL, CACHE_KEY, cfg["backend"], cfg["char_mode"], cfg["keep_items_english"])
    lower_priority()
    if unknown:
        log.warning("ignored unknown arguments: %s", " ".join(unknown))

    early: list[tuple[int, int, str]] = []
    holder: dict[str, Dispatcher] = {}
    maps: list[lt.KeyMap] = []
    ready = threading.Event()

    def reader() -> None:
        try:
            while True:
                msg = channel.read()
                if msg is None:
                    break
                req = Channel.parse_text(msg)
                if req is None:
                    continue
                if ready.is_set():
                    holder["d"].submit(*req)
                else:
                    early.append(req)
        except Exception:  # noqa: BLE001
            log.exception("stdin reader failed")
        log.info("addon closed the connection: exiting")
        for m in maps:
            try:
                m.close()
            except Exception as exc:  # noqa: BLE001
                log.warning("map not closed cleanly: %s", exc)
        logging.shutdown()
        os._exit(0)

    threading.Thread(target=reader, daemon=True, name="stdin-reader").start()

    glossary = lt.Glossary()
    gfile = lang.file("glossary", ".json")
    if glossary.load_file(args.lang_dir / gfile):
        where = gfile
    elif glossary.load_file(lt.bundled_dir() / lang.file("glossary", ".default.json")):
        where = "built-in default"
    else:
        where = "none yet"
    log.info("glossary %s (%s): %d exact, %d terms, %d patterns", glossary.fingerprint or "-", where,
             len(glossary.exact), len(glossary.terms), len(glossary.patterns))
    fake = args.fake or (args.lang_dir / "fake.txt").is_file()
    t0 = time.perf_counter()
    patch = CachePatch(args.lang_dir / lang.file("patch", ".db"), CACHE_KEY, RESULT_VERSION)
    patch.glossary = glossary
    patch.char_mode = cfg["char_mode"]
    contrib = editor.contributor(args.lang_dir)
    if contrib and contrib.show_keys is not editor.NOT_SET:
        patch.show_keys, where = contrib.show_keys, editor.CONTRIBUTOR_FILE
    else:
        patch.show_keys, where = show_keys_mode(args.lang_dir), SHOW_KEYS_FILE
    if patch.show_keys:
        log.info("SHOW KEYS mode '%s' (%s): texts start with their string ID", patch.show_keys, where)
    try:
        patch.migrate(args.lang_dir)
    except Exception:  # noqa: BLE001
        log.exception("cannot import the local patch files")
    if args.patch_file:
        if patch.import_file(args.patch_file, "patch-file"):
            log.info("test patch loaded: %s", args.patch_file)
    c = patch.counts()
    log.info("patch v%d: %d reviewed, %d automatic, %d drop (ready in %.2f s)",
             patch.version, c["reviewed"], c["auto"], c["drop"], time.perf_counter() - t0)

    engine = ModuleEngine(lt.FakeTranslator() if fake else None, glossary,
                          args.lang_dir / lang.file("cache", ".jsonl"), args.cache_db,
                          patch=patch, keep_items_english=bool(cfg.get("keep_items_english", True)))
    keymap = None
    try:
        keymap = lt.KeyMap(args.lang_dir / lang.file("map", ".db"))
        maps.append(keymap)
        log.info("map: %d strings known", keymap.count())
    except Exception as exc:  # noqa: BLE001
        log.warning("map disabled: %s", exc)

    dispatcher = Dispatcher(engine, patch, keymap, channel, max(10, args.stats_every),
                            args.cache_db)
    holder["d"] = dispatcher
    patch.sender = dispatcher.push
    if contrib and keymap:
        patch.map_path, patch.suggestion_of = keymap.path, keymap.suggestion
        log.info("contributor %s: suggestions on", contrib.author)
        if args.editor_port:
            editor.start(editor.Editor(patch, keymap, args.cache_db, CACHE_KEY, contrib.author),
                         args.editor_port)
    ready.set()
    for req in early:
        dispatcher.submit(*req)
    early.clear()
    threading.Thread(target=dispatcher.run, daemon=True, name="dispatcher").start()

    if fake:
        log.info("TEST MODE: answering '[%s] text', no real translation", lang.label)
    else:
        def load_translator() -> None:
            backend = str(cfg.get("backend", "offline")).lower()
            api_key = str(cfg.get("api_key", "")).strip()
            model_name = str(cfg.get("model_name", "")).strip()
            try:
                translator = None
                if backend == "google":
                    translator = lt.GoogleTranslator()
                    log.info("cloud translator loaded: Google Translate")
                elif backend == "deepl" and api_key:
                    translator = lt.DeepLTranslator(api_key)
                    log.info("cloud translator loaded: DeepL")
                elif backend == "gemini" and api_key:
                    translator = lt.GeminiTranslator(api_key, model_name or "gemini-2.5-flash")
                    log.info("cloud translator loaded: Gemini (%s)", model_name or "gemini-2.5-flash")
                elif backend == "openai" and api_key:
                    translator = lt.OpenAITranslator(api_key, model_name or "gpt-4o-mini")
                    log.info("cloud translator loaded: OpenAI (%s)", model_name or "gpt-4o-mini")
                else:
                    if backend != "offline":
                        log.warning("backend '%s' requires an API key; falling back to offline OPUS-MT", backend)
                    model = args.lang_dir / "model"
                    lt.ensure_model(model, args.lang_dir, lt.MODEL_URL)
                    req_threads = args.threads or int(cfg.get("threads") or 0) or None
                    threads = model_threads(req_threads)
                    translator = lt.CT2Translator(model, threads=threads)
                    log.info("offline OPUS-MT model loaded (%d threads)", threads)
                with engine.cv:
                    engine.translator = translator
                    engine.cv.notify_all()
            except Exception:  # noqa: BLE001
                log.exception("could not prepare the translation engine (%s)", backend)
        threading.Thread(target=load_translator, daemon=True, name="model-loader").start()

    threading.Thread(target=cache_db_watcher,
                     args=(patch, args.cache_db, keymap.path if keymap else None),
                     daemon=True, name="cache-db").start()
    if args.upload:
        if keymap is None:
            log.warning("map upload: no map, nothing to send")
        else:
            try:
                map_upload.MapUploader(keymap.path, args.lang_dir, lang.code, VERSION, args.upload_url,
                                       max(0.0, args.upload_first)).start()
            except ValueError as exc:
                log.warning("map upload off: %s", exc)
    if not args.no_update:
        def glossary_changed() -> None:
            engine.sync_glossary()
            try:
                if has_table(args.cache_db):
                    patch.apply(args.cache_db)
            except Exception as exc:  # noqa: BLE001
                log.warning("cannot apply the patch to %s: %s", args.cache_db, exc)

        lt.GlossaryUpdater(glossary, args.lang_dir, glossary_changed,
                           lt.raw_url(f"glossary/{gfile}", args.branch)).start()
        if not args.patch_file:
            PieceUpdater(patch, lang.code, args.cache_db, args.branch).start()

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    sys.exit(main())

