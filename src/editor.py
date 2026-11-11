"""Local Translator TR: Canlı Çeviri Düzenleyici (http://127.0.0.1:8770).

TR\\contributor.json dosyası varsa ordaki yazar adını kullanır, yoksa varsayılan olarak
"Oyuncu" adıyla aktif olur:

    {"author": "Oyuncu", "show_keys": false}

Oyunda gördüğünüz metni (Türkçe, İngilizce veya String ID olarak) arayın, çeviriyi düzenleyin ve
kaydedin: map_tr.db içindeki suggestions tablosuna kaydedilir ve oyun açıksa 1-2 saniye içinde
canlı olarak oyuna gönderilir. "Geri Al" son düzenlemeyi siler ve bir önceki çeviriye döner.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import lt_server as lt
from patch_db import KIND_AUTO, KIND_DROP, KIND_REVIEWED, CachePatch, untagged

log = logging.getLogger("lt")

EDITOR_PORT = 8770
EDITOR_HOST = "suggestions.localhost"
CONTRIBUTOR_FILE = "contributor.json"
RESULTS = 50
MAX_BYTES = 65535
KINDS = {KIND_REVIEWED: "reviewed", KIND_AUTO: "automatic", KIND_DROP: "drop"}

MARKUP = [(re.compile(r'\[(?:pl|f):"[^"]*"\]'), ""), (re.compile(r"</?c(?:=[^>]*)?/?>"), ""),
          (re.compile(r"<br>"), " "), (re.compile(r"\[lbracket\]"), "["),
          (re.compile(r"\[rbracket\]"), "]"), (re.compile(r"\s+"), " ")]


def plain(text: str) -> str:
    """Metni oyunda göründüğü düz haliyle döndürür (arama için)."""
    for pattern, repl in MARKUP:
        text = pattern.sub(repl, text)
    return text.strip()


@dataclass(frozen=True)
class Contributor:
    author: str
    show_keys: str | None | object


NOT_SET = object()


def contributor(lang_dir: Path) -> Contributor | None:
    """TR\\contributor.json ayarlarını okur; dosya yoksa varsayılan 'Oyuncu' profilini oluşturur."""
    path = lang_dir / CONTRIBUTOR_FILE
    if not path.is_file():
        try:
            lang_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"author": "Oyuncu", "show_keys": False},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            return Contributor("Oyuncu", NOT_SET)
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return Contributor("Oyuncu", NOT_SET)
    except (OSError, ValueError) as exc:
        log.warning("%s unreadable: %s", path.name, exc)
        return Contributor("Oyuncu", NOT_SET)
    author = data.get("author") if isinstance(data, dict) else None
    if not isinstance(author, str) or not author.strip():
        author = "Oyuncu"
    mode = data.get("show_keys", NOT_SET) if isinstance(data, dict) else NOT_SET
    if mode is True:
        mode = "text"
    elif mode in (False, None, "off"):
        mode = None
    elif mode is not NOT_SET and mode not in ("text", "all"):
        log.warning("%s: show_keys must be \"text\", \"all\" or false, not %r", path.name, mode)
        mode = NOT_SET
    return Contributor(author.strip(), mode)


class Editor:
    def __init__(self, patch: CachePatch, keymap: lt.KeyMap, cache_db: Path, cache_key: str,
                 author: str) -> None:
        self.patch, self.keymap, self.cache_db, self.cache_key = patch, keymap, cache_db, cache_key
        self.author = author
        self.lock = threading.Lock()

    def _cache(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self.cache_db}?mode=ro", uri=True, timeout=10)

    def _shown(self, key: int) -> tuple[str | None, int | None]:
        """(text, src_hash) of the key in cache.db, the text without its "show keys" prefix."""
        if not self.cache_db.is_file():
            return None, None
        con = self._cache()
        try:
            r = con.execute("SELECT text, src_hash FROM translations WHERE cache_key = ? AND id = ?",
                            (self.cache_key, key)).fetchone()
        finally:
            con.close()
        if not r:
            return None, None
        return (untagged(key, r[0]) if r[0] is not None else None), r[1]

    def search(self, q: str, exact: bool = False) -> list[dict]:
        """Metinleri Türkçe (cache.db / map_tr.db), İngilizce veya String ID ile arar."""
        q = q.strip()
        if not q:
            return []
        keys: list[int] = []
        if q.isdigit():
            keys = [int(q)]
        else:
            if self.cache_db.is_file():
                if exact:
                    def match(t: str) -> bool:
                        return t == q
                else:
                    folded = lt.tr_lower(q)
                    folded_ascii = lt.fix_turkish_chars(folded, "ascii_6")

                    def match(t: str) -> bool:
                        tl = lt.tr_lower(t)
                        return folded in tl or folded_ascii in lt.fix_turkish_chars(tl, "ascii_6")
                try:
                    con = self._cache()
                    try:
                        for k, t in con.execute("SELECT id, text FROM translations WHERE cache_key = ? "
                                                "AND text IS NOT NULL", (self.cache_key,)):
                            if match(plain(untagged(k, t))):
                                keys.append(k)
                                if len(keys) >= RESULTS:
                                    break
                    finally:
                        con.close()
                except sqlite3.Error:
                    pass
            if len(keys) < RESULTS:
                for k in self.keymap.search_english(q, RESULTS, exact):
                    if k not in keys:
                        keys.append(k)
                        if len(keys) >= RESULTS:
                            break
        return [self.row(k) for k in keys[:RESULTS]]

    def row(self, key: int) -> dict:
        shown, h = self._shown(key)
        entry = self.patch.entry_version(key)
        patch = ({"kind": KINDS.get(entry[0]), "text": entry[1], "version": entry[2]}
                 if entry else None)
        mrow = self.keymap.get(key)
        history = self.keymap.suggestions(key)
        active = self.patch.valid_suggestion(key, h)
        last = history[0] if history else None
        en = (mrow[0] if mrow else "") or (last.en_source if last else "")
        prev = None
        if history:
            before = history[1] if len(history) > 1 else None
            if before is not None:
                prev = {"what": "suggestion", "author": before.author, "text": before.suggestion}
            elif entry and entry[0] != KIND_DROP:
                prev = {"what": KINDS[entry[0]], "text": entry[1]}
            else:
                prev = {"what": "module", "text": mrow[1] if mrow else None}
        return {"key": key, "shown": shown, "en": en, "patch": patch,
                "suggestion": ({"text": last.suggestion, "author": last.author,
                                "version": last.version, "valid": active is not None}
                               if last else None),
                "undo": len(history), "prev": prev}

    def recent(self) -> list[dict]:
        return [{"key": s.key, "text": s.suggestion, "author": s.author, "version": s.version}
                for s in self.keymap.recent_suggestions()]

    def save(self, key: int, text: str) -> dict:
        if not text.strip():
            raise ValueError("Metin boş olamaz")
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise ValueError("Metin çok uzun")
        with self.lock:
            shown, h = self._shown(key)
            mrow = self.keymap.get(key)
            if shown is None:
                entry = self.patch.entry_version(key)
                shown = entry[1] if entry and entry[0] != KIND_DROP else (mrow[1] if mrow else None)
            self.keymap.add_suggestion(key, mrow[0] if mrow else "", shown, text, self.author,
                                       self.patch.version, h if h else None)
            sent = self.patch.apply(self.cache_db, {key})
        log.info("editor: suggestion for key %d%s", key,
                 "" if sent else " (not sent: same text, or the game does not hold it yet)")
        return self.row(key)

    def undo(self, key: int) -> dict:
        """Son öneriyi siler; oyun bir önceki öneriye, yamaya veya modül çevirisine döner."""
        with self.lock:
            if not self.keymap.remove_last_suggestion(key):
                raise ValueError("Geri alınacak düzenleme yok")
            sent = self.patch.apply(self.cache_db, {key})
            shown, h = self._shown(key)
            entry = self.patch.entry_version(key)
            if not sent and self.patch.valid_suggestion(key, h) is None and (
                    entry is None or entry[0] == KIND_DROP):
                mrow = self.keymap.get(key)
                if mrow and mrow[1] and mrow[1] != shown:
                    sent = self.patch.send_text(key, h or 0, mrow[1])
                elif not mrow or not mrow[1]:
                    self._forget_in_cache(key)
        log.info("editor: suggestion for key %d undone", key)
        return self.row(key)

    def _forget_in_cache(self, key: int) -> None:
        if not self.cache_db.is_file():
            return
        con = sqlite3.connect(str(self.cache_db), timeout=10)
        try:
            with con:
                con.execute("DELETE FROM translations WHERE cache_key = ? AND id = ?",
                            (self.cache_key, key))
        finally:
            con.close()


def _handler(editor: Editor, port: int) -> type[BaseHTTPRequestHandler]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"{EDITOR_HOST}:{port}"}
    origins = {f"http://{h}" for h in hosts}

    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalTranslatorTR"

        def log_message(self, fmt, *args) -> None:
            log.debug("editor: " + fmt, *args)

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = HTTPStatus.OK) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            if self.headers.get("Host") in hosts:
                return True
            self._json({"error": "bad host"}, HTTPStatus.FORBIDDEN)
            return False

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return
            url = urlsplit(self.path)
            try:
                if url.path == "/":
                    page = PAGE.replace("{{AUTHOR}}", _html(editor.author))
                    self._send(HTTPStatus.OK, page.encode("utf-8"), "text/html; charset=utf-8")
                elif url.path == "/api/search":
                    query = parse_qs(url.query)
                    self._json(editor.search(query.get("q", [""])[0],
                                             query.get("exact", ["0"])[0] == "1"))
                elif url.path == "/api/recent":
                    self._json(editor.recent())
                else:
                    self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            except Exception as exc:  # noqa: BLE001
                log.warning("editor: %s failed: %s", url.path, exc)
                self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                return
            origin = self.headers.get("Origin")
            if (origin is not None and origin not in origins) or not self.headers.get(
                    "Content-Type", "").startswith("application/json"):
                self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
                return
            path = urlsplit(self.path).path
            if path not in ("/api/save", "/api/undo"):
                self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return
            try:
                size = int(self.headers.get("Content-Length") or 0)
                if size > 4 * MAX_BYTES:
                    raise ValueError("request too big")
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                key = int(data["key"])
                if not 0 <= key < 2 ** 32:
                    raise ValueError("bad key")
                if path == "/api/undo":
                    self._json(editor.undo(key))
                else:
                    self._json(editor.save(key, str(data["text"])))
            except (ValueError, KeyError, TypeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:  # noqa: BLE001
                log.warning("editor: %s failed: %s", path, exc)
                self._json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    return Handler


def _html(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def start(editor: Editor, port: int = EDITOR_PORT) -> ThreadingHTTPServer | None:
    """Arka planda canlı düzenleyici sunucusunu başlatır."""
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), _handler(editor, port))
    except OSError as exc:
        log.warning("editor page not started (port %d): %s", port, exc)
        return None
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True, name="editor").start()
    log.info("editor page: http://127.0.0.1:%d (http://%s:%d)", port, EDITOR_HOST, port)
    return server


PAGE = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GW2 TR - Canlı Çeviri Düzenleyici</title>
<style>
:root {
  --bg: #181818; --main: #1e1e1e; --panel: #252526; --text: #cccccc; --muted: #858585;
  --line: #333333; --hover: #37373d; --accent: #cccccc; --accent-text: #181818;
  --ok: #73c991; --err: #f48771;
  --badge-rev: #1f3a2b; --badge-auto: #2a2f36; --badge-sugg: #2d3748; --badge-old: #3d2e1c;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--main); color: var(--text);
       font: 13px/1.5 Inter, system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 920px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 16px; font-weight: 500; color: #ffffff; margin: 0 0 4px; letter-spacing: -0.01em; }
.sub { color: var(--muted); margin: 0 0 16px; font-size: 12px; }
form.search { display: flex; gap: 8px; margin-bottom: 8px; }
label.opt { display: block; margin: 0 0 16px; font-size: 12px; color: var(--text); cursor: pointer; }
label.opt input { margin: 0 6px 0 0; vertical-align: -2px; }
.hint { color: var(--muted); font-size: 11px; }
input[type=search] { flex: 1; min-width: 0; padding: 8px 12px; font: inherit; color: var(--text);
  background: var(--bg); border: 1px solid var(--line); border-radius: 2px; outline: none; }
input[type=search]:focus, textarea:focus { border-color: var(--muted); }
button { padding: 7px 14px; font: 500 12px/1.2 inherit; border-radius: 2px; border: 1px solid var(--accent);
  background: var(--accent); color: var(--accent-text); cursor: pointer; transition: opacity .15s; }
button.ghost { background: var(--panel); color: var(--text); border-color: var(--line); }
button.ghost:hover:not(:disabled) { background: var(--hover); }
button:disabled { opacity: .45; cursor: default; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 2px;
        padding: 12px 14px; margin-bottom: 10px; }
.head { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; margin-bottom: 6px;
        font-size: 12px; color: var(--muted); }
.key { font-family: "Roboto Mono", ui-monospace, Consolas, monospace; color: #ffffff; font-weight: 500; }
.badge { padding: 1px 7px; border-radius: 2px; font-size: 11px; color: var(--text); border: 1px solid var(--line); }
.b-reviewed { background: var(--badge-rev); } .b-automatic, .b-none { background: var(--badge-auto); }
.b-sugg { background: var(--badge-sugg); } .b-old { background: var(--badge-old); }
.en { color: var(--muted); font-size: 12px; margin: 0 0 8px; white-space: pre-wrap;
      font-family: "Roboto Mono", ui-monospace, Consolas, monospace; background: var(--bg);
      padding: 6px 8px; border-left: 2px solid var(--line); }
.note { font-size: 12px; margin: 6px 0 0; white-space: pre-wrap; }
.note-label { color: var(--muted); }
textarea { width: 100%; min-height: 64px; padding: 8px 10px; font: inherit; color: #ffffff;
  background: var(--bg); border: 1px solid var(--line); border-radius: 2px; resize: vertical; outline: none; }
.actions { display: flex; gap: 8px; align-items: center; margin-top: 8px; }
.status { font-size: 12px; } .status.ok { color: var(--ok); } .status.err { color: var(--err); }
.empty { color: var(--muted); padding: 8px 2px; font-size: 12px; }
h2 { font-size: 13px; font-weight: 500; color: var(--muted); text-transform: uppercase;
     letter-spacing: 0.06em; margin: 28px 0 10px; }
.recent .card { padding: 8px 12px; cursor: pointer; }
.recent .card:hover { background: var(--hover); }
.recent .it { white-space: pre-wrap; color: var(--text); }
</style>
</head>
<body>
<main>
  <h1>GW2 TR — Canlı Çeviri Düzenleyici</h1>
  <p class="sub">Profil: <b>{{AUTHOR}}</b>. Oyunda gördüğünüz metni (Türkçe, İngilizce veya String ID olarak) arayın, çeviriyi düzenleyip kaydedin: oyun açıksa birkaç saniye içinde anında güncellenir.</p>
  <form class="search" id="f">
    <input type="search" id="q" placeholder="Örn. Saldırı, Waypoint veya 37952" autofocus>
    <button type="submit">Ara</button>
  </form>
  <label class="opt"><input type="checkbox" id="exact"> Tam eşleşme ara
    <span class="hint">(yalnızca büyük/küçük harf dahil birebir aynı olan metinler)</span></label>
  <div id="results"></div>
  <h2>Son Düzenlemeler</h2>
  <div class="recent" id="recent"></div>
</main>
<script>
const $ = (s) => document.querySelector(s);
const KIND = { reviewed: "incelenmiş", automatic: "otomatik", drop: "silinmiş" };

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") e.className = v; else if (k.startsWith("on")) e[k] = v; else e.setAttribute(k, v);
  }
  for (const c of kids) if (c != null) e.append(c);
  return e;
}

function prevLabel(p) {
  if (p.what === "suggestion") return p.author + " önerisi";
  if (p.what === "module") return "modül çevirisi";
  return "yama, " + KIND[p.what];
}

function card(r, note) {
  const s = r.suggestion;
  const ta = el("textarea", {});
  ta.value = (s && s.valid ? s.text : null) ?? (r.patch ? r.patch.text : null) ?? r.shown ?? "";
  const status = el("span", { class: "status" + (note ? " ok" : "") }, note || "");
  const btn = el("button", { type: "button" }, "Kaydet");
  const undo = el("button", { type: "button", class: "ghost",
    title: r.undo ? "Son düzenlemeyi geri al (toplam " + r.undo + ")" : "Geri alınacak düzenleme yok" }, "Geri Al");
  undo.disabled = !r.undo;
  const self = el("div", { class: "card" });
  const post = async (url, body, busy, done) => {
    btn.disabled = undo.disabled = true; status.className = "status"; status.textContent = busy;
    try {
      const res = await fetch(url, { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.status);
      self.replaceWith(card(data, done));
      loadRecent();
    } catch (e) {
      status.className = "status err"; status.textContent = "Hata: " + e.message;
      btn.disabled = false; undo.disabled = !r.undo;
    }
  };
  btn.onclick = () => post("/api/save", { key: r.key, text: ta.value }, "Kaydediliyor…", "Kaydedildi ve oyuna gönderildi");
  undo.onclick = () => post("/api/undo", { key: r.key }, "Geri alınıyor…", "Geri alındı, önceki metin yüklendi");
  const badges = [];
  const kind = r.patch ? r.patch.kind : null;
  badges.push(el("span", { class: "badge b-" + (kind || "none") },
    kind ? "yama: " + KIND[kind] : "yamada yok"));
  if (s && s.valid) badges.push(el("span", { class: "badge b-sugg" }, s.author + " düzenlemesi"));
  else if (s) badges.push(el("span", { class: "badge b-old", title: "Yama veya İngilizce metin değiştiği için geçersiz" }, "eski düzenleme"));
  self.append(...[
    el("div", { class: "head" }, el("span", { class: "key" }, "#" + r.key), ...badges),
    r.en ? el("p", { class: "en" }, r.en) : null,
    ta,
    s && !s.valid ? el("p", { class: "note" },
      el("span", { class: "note-label" }, s.author + " tarafından eski düzenleme: "), s.text) : null,
    r.prev ? el("p", { class: "note" },
      el("span", { class: "note-label" }, "Geri Al ile döneceği metin (" + prevLabel(r.prev) + "): "),
      r.prev.text ?? "(metin yok: sonraki açılışta modül tekrar çevirir)") : null,
    el("div", { class: "actions" }, btn, undo, status)].filter((c) => c != null));
  return self;
}

async function search(q) {
  const box = $("#results");
  box.replaceChildren(el("p", { class: "empty" }, "Aranıyor…"));
  try {
    const res = await fetch("/api/search?q=" + encodeURIComponent(q) + ($("#exact").checked ? "&exact=1" : ""));
    const rows = await res.json();
    if (!res.ok) throw new Error(rows.error || res.status);
    box.replaceChildren(...(rows.length ? rows.map((r) => card(r)) : [el("p", { class: "empty" }, "Sonuç bulunamadı.")]));
  } catch (e) {
    box.replaceChildren(el("p", { class: "status err" }, "Hata: " + e.message));
  }
}

async function loadRecent() {
  try {
    const rows = await (await fetch("/api/recent")).json();
    $("#recent").replaceChildren(...(rows.length ? rows.map((r) =>
      el("div", { class: "card", onclick: () => { $("#q").value = r.key; search(String(r.key)); scrollTo(0, 0); } },
        el("div", { class: "head" }, el("span", { class: "key" }, "#" + r.key),
          el("span", {}, r.author + ", yama v" + r.version)),
        el("div", { class: "it" }, r.text))) : [el("p", { class: "empty" }, "Henüz düzenleme yapılmadı.")]));
  } catch (e) { /* page still usable */ }
}

$("#f").onsubmit = (ev) => { ev.preventDefault(); const q = $("#q").value.trim(); if (q) search(q); };
$("#exact").onchange = () => { const q = $("#q").value.trim(); if (q) search(q); };
loadRecent();
</script>
</body>
</html>
"""

