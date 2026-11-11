"""Local Translator (Turkish Edition): the curated patch kept by the module in a SQLite archive
(TR\\patch_tr.db), written into Text Translator's cache.db and updated from GitHub piece by piece.
Also manages character normalization synchronization (6-char ASCII fallback vs Authentic Turkish)
across cache.db when the user toggles the GW2 Turkish Font Injector.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import sqlite3
import threading
import time
import urllib.error
from pathlib import Path

import lt_server as lt

log = logging.getLogger("lt")

KIND_REVIEWED, KIND_AUTO, KIND_DROP = 0, 1, 2
CHUNK = 2000
PUSH_BLOCK = 2000
PUSH_PAUSE = 0.2
SQL_VARS = 500
STALE_LOG_LIMIT = 20
WAL_LIMIT = 1_000_000

SCHEMA = """
CREATE TABLE IF NOT EXISTS patch (
    key   INTEGER PRIMARY KEY NOT NULL,
    kind  INTEGER NOT NULL,      -- 0 reviewed (strings), 1 automatic (auto), 2 drop
    text  TEXT,                  -- NULL for drop
    src_hash INTEGER,            -- hash of the English text (lt_server.hash_int), 0 = outdated, or NULL
    piece INTEGER,               -- piece number (key // width), NULL when loaded from a single file
    version INTEGER              -- patch version of the last change of the entry
);
CREATE INDEX IF NOT EXISTS patch_piece ON patch(piece);
CREATE TABLE IF NOT EXISTS pieces (name TEXT PRIMARY KEY NOT NULL, sha256 TEXT NOT NULL,
                                   entries INTEGER, size INTEGER);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY NOT NULL, v TEXT);
CREATE TABLE IF NOT EXISTS applied (key INTEGER PRIMARY KEY NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS skip (key INTEGER PRIMARY KEY NOT NULL);
CREATE TABLE IF NOT EXISTS dropped (key INTEGER PRIMARY KEY NOT NULL);
"""

TAG_SKIP_RE = re.compile(r"%[A-Za-z]+\d*%|\[[^\]]*\]|<[^>]*>")
WORD_RE = re.compile(r"[^\W\d_]")

SHOW_MODES = ("text", "all")


def key_tag(key: int, text: str, mode: str | None) -> str:
    if mode == "all":
        return f"{key} - " if text.strip() else ""
    if mode == "text":
        return f"{key} - " if WORD_RE.search(TAG_SKIP_RE.sub("", text)) else ""
    return ""


def shown_text(key: int, text: str | None, mode: str | None, char_mode: str = "off") -> str | None:
    """The text with its key prefix and character mode normalization, as stored in cache.db."""
    if text is None:
        return None
    norm_text = lt.fix_turkish_chars(text, char_mode)
    return key_tag(key, norm_text, mode) + norm_text


def untagged(key: int, text: str) -> str:
    tag = f"{key} - "
    return text[len(tag):] if text.startswith(tag) else text


def sync_key_tags(db: Path | None, cache_key: str, mode: str | None, char_mode: str = "off",
                  map_db: Path | None = None) -> int:
    """Synchronize both 'show keys' prefixes and Turkish character mode ('off' vs '6char')
    on all rows of cache.db."""
    if not has_table(db):
        return 0
    # Load authentic Turkish texts from map_tr.db if restoring from 6char -> off
    authentic_map: dict[int, str] = {}
    if char_mode in ("full", "off", "", None) and map_db and map_db.is_file():
        try:
            mcon = sqlite3.connect(f"file:{map_db}?mode=ro", uri=True, timeout=5)
            try:
                authentic_map = {
                    k: it for k, it in mcon.execute("SELECT key, it FROM texts WHERE it IS NOT NULL")
                }
            finally:
                mcon.close()
        except Exception:
            pass

    con = sqlite3.connect(str(db), timeout=10, isolation_level=None)
    done, last = 0, -1
    try:
        while True:
            rows = con.execute("SELECT id, text FROM translations WHERE cache_key = ? AND id > ? "
                               f"ORDER BY id LIMIT {CHUNK}", (cache_key, last)).fetchall()
            if not rows:
                return done
            last = rows[-1][0]
            changes = []
            for key, text in rows:
                base = untagged(key, text)
                if char_mode in ("full", "off", "", None) and key in authentic_map:
                    orig = authentic_map[key]
                    if lt.fix_turkish_chars(orig, "ascii_6") == base:
                        base = orig
                want = shown_text(key, base, mode, char_mode)
                if want != text:
                    changes.append((want, cache_key, key))
            if changes:
                con.execute("BEGIN")
                try:
                    con.executemany("UPDATE translations SET text = ? WHERE cache_key = ? AND id = ?",
                                    changes)
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
                done += len(changes)
    finally:
        con.close()


def has_table(db: Path | None, need_hash: bool = False) -> bool:
    if not db or not db.is_file():
        return False
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
    try:
        cols = {r[1] for r in con.execute("PRAGMA table_info(translations)")}
    finally:
        con.close()
    return bool(cols) and (not need_hash or "src_hash" in cols)


def _chunks(items: list, size: int = SQL_VARS):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except Exception as exc:
        log.warning("%s unreadable: %s", path.name, exc)
        return None


class CachePatch:
    """The patch archive of the module (patch_tr.db) and its application to cache.db."""

    def __init__(self, path: Path, cache_key: str, result_version: int,
                 char_mode: str = "off") -> None:
        self.path = path
        self.cache_key, self.result_version = cache_key, result_version
        self.char_mode = char_mode
        self.glossary: lt.Glossary | None = None
        self.show_keys: str | None = None
        self.sender = None
        self._sent: dict[int, int] = {}
        self.map_path: Path | None = None
        self.suggestion_of = None
        self.lock = threading.RLock()
        self.rlock = threading.Lock()
        self._stale_lock = threading.Lock()
        self._stale_seen: set[int] = set()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.writer = self._connect()
        self._upgrade()
        self.writer.executescript(SCHEMA)
        self.reader = self._connect()
        self._load_meta()
        self._shrink_wal()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=30, isolation_level=None,
                              check_same_thread=False)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute(f"PRAGMA journal_size_limit={WAL_LIMIT}")
        return con

    def _upgrade(self) -> None:
        con = self.writer
        cols = {r[1] for r in con.execute("PRAGMA table_info(patch)")}
        if not cols:
            return
        if "h" in cols:
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute("ALTER TABLE patch DROP COLUMN h")
                con.execute("ALTER TABLE patch ADD COLUMN src_hash INTEGER")
                con.execute("DROP TABLE IF EXISTS stale")
                con.execute("DELETE FROM pieces")
                con.execute("DELETE FROM meta WHERE k = 'commit'")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
        if "version" not in cols:
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute("ALTER TABLE patch ADD COLUMN version INTEGER")
                con.execute("DELETE FROM pieces")
                con.execute("DELETE FROM meta WHERE k = 'commit'")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise

    def _shrink_wal(self) -> None:
        try:
            self.writer.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass

    def close(self) -> None:
        with self.lock, self.rlock:
            for con in (self.reader, self.writer):
                try:
                    con.close()
                except sqlite3.Error:
                    pass

    def _load_meta(self) -> None:
        with self.rlock:
            m = dict(self.reader.execute("SELECT k, v FROM meta"))
        self.version = int(m.get("version") or 0)
        self.glossary_fp = m.get("glossary") or ""
        self.width = int(m.get("width") or 0)
        self.commit = m.get("commit") or ""
        self.source = m.get("source") or ""
        self.skip_version = int(m["skip_version"]) if m.get("skip_version") else None
        self.migrated = bool(m.get("migrated"))
        self.file_sig = m.get("file_sig") or ""
        self._ids_failed = json.loads(m["ids_failed"]) if m.get("ids_failed") else None

    @staticmethod
    def _set_meta(con: sqlite3.Connection, **values) -> None:
        for k, v in values.items():
            if v is None:
                con.execute("DELETE FROM meta WHERE k = ?", (k,))
            else:
                con.execute("INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)", (k, str(v)))

    def counts(self) -> dict[str, int]:
        with self.rlock:
            rows = self.reader.execute(
                "SELECT kind, count(*), count(src_hash) FROM patch GROUP BY kind").fetchall()
        out = {"reviewed": 0, "auto": 0, "drop": 0, "hash": 0}
        for kind, n, h in rows:
            out[("reviewed", "auto", "drop")[kind]] = n
            out["hash"] += h
        return out

    def pieces(self) -> dict[str, str]:
        with self.rlock:
            return dict(self.reader.execute("SELECT name, sha256 FROM pieces"))

    def auto_current(self) -> bool:
        g = self.glossary
        return bool(self.glossary_fp) and g is not None and self.glossary_fp == g.fingerprint

    def _skip_active(self) -> bool:
        if self.skip_version is None or self.auto_current():
            return False
        return bool(self.glossary_fp) or self.skip_version == self.version

    def protected(self, keys: set[int]) -> set[int]:
        kinds = (KIND_REVIEWED, KIND_AUTO) if self.auto_current() else (KIND_REVIEWED,)
        out: set[int] = set()
        with self.rlock:
            for part in _chunks(sorted(keys)):
                out.update(k for (k,) in self.reader.execute(
                    f"SELECT key FROM patch WHERE kind IN ({','.join('?' * len(kinds))}) "
                    f"AND key IN ({','.join('?' * len(part))})", (*kinds, *part)))
        return out

    def suppress(self, keys: set[int]) -> None:
        if not keys:
            return
        with self.lock:
            con = self.writer
            auto: set[int] = set()
            for part in _chunks(sorted(keys)):
                auto.update(k for (k,) in con.execute(
                    f"SELECT key FROM patch WHERE kind = {KIND_AUTO} "
                    f"AND key IN ({','.join('?' * len(part))})", part))
            if not auto:
                return
            before = {k for (k,) in con.execute("SELECT key FROM skip")} if self._skip_active() else set()
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute("DELETE FROM skip")
                con.executemany("INSERT INTO skip (key) VALUES (?)", [(k,) for k in sorted(before | auto)])
                self._set_meta(con, skip_version=self.version)
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            self.skip_version = self.version

    def entry_version(self, key: int) -> tuple[int, str | None, int] | None:
        with self.rlock:
            row = self.reader.execute("SELECT kind, text, version FROM patch WHERE key = ?",
                                      (key,)).fetchone()
        return None if row is None else (row[0], row[1], self.version if row[2] is None else row[2])

    def valid_suggestion(self, key: int, src_hash: int | None) -> lt.Suggestion | None:
        s = self.suggestion_of(key) if self.suggestion_of else None
        if s is None:
            return None
        if s.src_hash is not None and src_hash not in (None, 0) and s.src_hash != src_hash:
            return None
        entry = self.entry_version(key)
        if entry is not None and s.version < entry[2]:
            return None
        return s

    def lookup(self, key: int, src_hash: int) -> tuple[str | None, bool]:
        with self.rlock:
            row = self.reader.execute("SELECT kind, text, src_hash FROM patch WHERE key = ?",
                                      (key,)).fetchone()
            if row is None or row[0] == KIND_DROP:
                return None, False
            kind, text, h = row
            if kind == KIND_AUTO and self._skip_active() and self.reader.execute(
                    "SELECT 1 FROM skip WHERE key = ?", (key,)).fetchone():
                return None, False
        if h is None or h == lt.hash_int(f"{src_hash:016x}"):
            return text, False
        with self._stale_lock:
            new = key not in self._stale_seen
            self._stale_seen.add(key)
            n = len(self._stale_seen)
        if new and n <= STALE_LOG_LIMIT:
            log.info("patch: the English text of key %d changed: translated locally", key)
        return None, True

    def ids_failed(self) -> bool:
        return self._ids_failed is not None

    def _set_ids_failed(self, value: dict | None) -> None:
        con = self.writer
        con.execute("BEGIN IMMEDIATE")
        try:
            self._set_meta(con, ids_failed=None if value is None else json.dumps(value))
            con.execute("COMMIT")
        except BaseException:
            con.execute("ROLLBACK")
            raise
        self._ids_failed = value

    def _shown(self, row: str, column: str = "text") -> str:
        if self.show_keys or self.char_mode not in ("off", "", None):
            return f"lt_shown({row}.key, {row}.{column})"
        return f"{row}.{column}"

    def _open_cache(self, db: Path) -> sqlite3.Connection:
        con = sqlite3.connect(str(db), timeout=10, isolation_level=None)
        mode = self.show_keys
        cmode = self.char_mode
        con.create_function("lt_shown", 2, lambda k, t: shown_text(k, t, mode, cmode), deterministic=True)
        con.execute("ATTACH DATABASE ? AS p", (str(self.path),))
        if self.map_path and self.map_path.is_file():
            con.execute("ATTACH DATABASE ? AS m", (str(self.map_path),))
        return con

    def _has_suggestions(self, con: sqlite3.Connection) -> bool:
        return con.execute("SELECT 1 FROM pragma_database_list WHERE name = 'm'").fetchone() is not None \
            and con.execute("SELECT 1 FROM m.sqlite_master WHERE name = 'suggestions'").fetchone() is not None

    def _suggestions_sql(self) -> str:
        return (f"SELECT s.key, {self._shown('s', 'suggestion')}, coalesce(s.src_hash, t.src_hash, 0) "
                "FROM m.suggestions s "
                "JOIN main.translations t ON t.cache_key = ? AND t.id = s.key "
                "LEFT JOIN p.patch pt ON pt.key = s.key "
                "WHERE s.id = (SELECT max(id) FROM m.suggestions s2 WHERE s2.key = s.key) "
                "AND (s.src_hash IS NULL OR coalesce(t.src_hash, 0) IN (0, s.src_hash)) "
                "AND (pt.key IS NULL OR s.version >= coalesce(pt.version, ?))")

    def _delete_rows(self, con: sqlite3.Connection, table: str) -> int:
        done, last = 0, -1
        while True:
            rows = con.execute(f"SELECT key FROM temp.{table} WHERE key > ? ORDER BY key "
                               f"LIMIT {CHUNK}", (last,)).fetchall()
            if not rows:
                return done
            con.execute("BEGIN")
            try:
                con.executemany("DELETE FROM main.translations WHERE cache_key = ? AND id = ?",
                                [(self.cache_key, r[0]) for r in rows])
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            done += len(rows)
            last = rows[-1][0]

    def _push(self, rows: list[tuple[int, int, str]]) -> int:
        sent = 0
        for i in range(0, len(rows), PUSH_BLOCK):
            if i:
                time.sleep(PUSH_PAUSE)
            block = rows[i:i + PUSH_BLOCK]
            sent += self.sender([(k, h % (1 << 64), t) for k, h, t in block])
            self._sent.update((k, hash(t)) for k, _h, t in block)
        return sent

    def send_text(self, key: int, src_hash: int, text: str) -> int:
        return self._push([(key, src_hash, shown_text(key, text, self.show_keys, self.char_mode))]) \
            if self.sender else 0

    def apply(self, db: Path | None, keys: set[int] | None = None) -> int:
        push: list[tuple[int, int, str]] = []
        new = 0
        with self.lock:
            with self.rlock:
                empty = self.reader.execute("SELECT 1 FROM patch LIMIT 1").fetchone() is None
                has_auto = self.reader.execute(
                    f"SELECT 1 FROM patch WHERE kind = {KIND_AUTO} LIMIT 1").fetchone() is not None
            if (empty and not self.map_path) or not has_table(db, need_hash=True):
                return 0
            if self.ids_failed():
                return 0
            ck = self.cache_key
            con = self._open_cache(db)
            try:
                restrict = ""
                if keys is not None:
                    con.execute("CREATE TEMP TABLE k (key INTEGER PRIMARY KEY)")
                    con.executemany("INSERT OR IGNORE INTO temp.k VALUES (?)", [(x,) for x in keys])
                    restrict = " AND {0}.key IN (SELECT key FROM temp.k)"
                skip_on = 1 if has_auto and self._skip_active() else 0
                con.execute("CREATE TEMP TABLE w (key INTEGER PRIMARY KEY, text TEXT, h INTEGER, "
                            "kind INTEGER)")
                shown = self._shown("pt")
                con.execute(
                    f"INSERT INTO temp.w SELECT pt.key, {shown}, coalesce(pt.src_hash, t.src_hash, 0), "
                    "pt.kind FROM p.patch pt "
                    "JOIN main.translations t ON t.cache_key = ? AND t.id = pt.key "
                    f"WHERE pt.kind IN ({KIND_REVIEWED}, {KIND_AUTO}) AND t.text IS NOT {shown} "
                    "AND pt.src_hash IS NOT 0 "
                    "AND NOT (pt.src_hash IS NOT NULL "
                    "AND coalesce(t.src_hash, 0) NOT IN (0, pt.src_hash)) "
                    f"AND NOT (pt.kind = {KIND_AUTO} AND ? AND pt.key IN (SELECT key FROM p.skip))"
                    + restrict.format("pt"), (ck, skip_on))
                con.execute(
                    f"INSERT OR IGNORE INTO temp.w SELECT pt.key, {shown}, pt.src_hash, pt.kind "
                    f"FROM p.patch pt WHERE pt.kind IN ({KIND_REVIEWED}, {KIND_AUTO}) "
                    "AND pt.src_hash IS NOT NULL AND pt.src_hash IS NOT 0 "
                    "AND NOT EXISTS (SELECT 1 FROM main.translations t "
                    "WHERE t.cache_key = ? AND t.id = pt.key) "
                    f"AND NOT (pt.kind = {KIND_AUTO} AND ? AND pt.key IN (SELECT key FROM p.skip))"
                    + restrict.format("pt"), (ck, skip_on))
                con.execute("CREATE TEMP TABLE r (key INTEGER PRIMARY KEY)")
                if has_auto:
                    con.execute(
                        "INSERT OR IGNORE INTO temp.r SELECT a.key FROM p.applied a "
                        "JOIN main.translations t ON t.cache_key = ? AND t.id = a.key "
                        f"WHERE t.text = {self._shown('a')} AND NOT EXISTS (SELECT 1 FROM p.patch pt "
                        f"WHERE pt.key = a.key AND pt.kind IN ({KIND_REVIEWED}, {KIND_AUTO}))"
                        + restrict.format("a"), (ck,))
                new_drop = con.execute(
                    f"SELECT count(*) FROM p.patch WHERE kind = {KIND_DROP} "
                    "AND key NOT IN (SELECT key FROM p.dropped)").fetchone()[0]
                if new_drop:
                    con.execute(
                        "INSERT OR IGNORE INTO temp.r SELECT pt.key FROM p.patch pt "
                        "JOIN main.translations t ON t.cache_key = ? AND t.id = pt.key "
                        f"WHERE pt.kind = {KIND_DROP} AND pt.key NOT IN (SELECT key FROM p.dropped)"
                        + restrict.format("pt"), (ck,))
                if self._has_suggestions(con):
                    con.execute("CREATE TEMP TABLE s (key INTEGER PRIMARY KEY, text TEXT, h INTEGER)")
                    con.execute("INSERT INTO temp.s " + self._suggestions_sql() + restrict.format("s"),
                                (ck, self.version))
                    con.execute("DELETE FROM temp.w WHERE key IN (SELECT key FROM temp.s)")
                    con.execute("DELETE FROM temp.w WHERE key IN (SELECT key FROM m.suggestions) "
                                "AND NOT EXISTS (SELECT 1 FROM main.translations t "
                                "WHERE t.cache_key = ? AND t.id = temp.w.key)", (ck,))
                    con.execute("DELETE FROM temp.r WHERE key IN (SELECT key FROM temp.s)")
                    con.execute("INSERT INTO temp.w SELECT s.key, s.text, s.h, NULL FROM temp.s s "
                                "JOIN main.translations t ON t.cache_key = ? AND t.id = s.key "
                                "WHERE t.text IS NOT s.text", (ck,))
                if self.sender:
                    push = [r for r in con.execute("SELECT key, h, text FROM temp.w ORDER BY key")
                            if self._sent.get(r[0]) != hash(r[2])]
                    if push:
                        fresh = {k for (k,) in con.execute(
                            "SELECT w.key FROM temp.w w WHERE NOT EXISTS (SELECT 1 FROM "
                            "main.translations t WHERE t.cache_key = ? AND t.id = w.key)", (ck,))}
                        new = sum(1 for r in push if r[0] in fresh)
                else:
                    # Offline mode (Hub Editor with game closed): write temp.w directly into cache.db
                    con.execute("BEGIN")
                    try:
                        con.execute(
                            "UPDATE main.translations SET text = (SELECT w.text FROM temp.w w "
                            "WHERE w.key = main.translations.id) "
                            "WHERE cache_key = ? AND id IN (SELECT key FROM temp.w)", (ck,))
                        con.execute("COMMIT")
                    except BaseException:
                        con.execute("ROLLBACK")
                        raise
                removed = self._delete_rows(con, "r")
                con.execute("BEGIN")
                try:
                    clear_skip = self.auto_current() and self.skip_version is not None
                    if clear_skip:
                        con.execute("DELETE FROM p.skip")
                        con.execute("DELETE FROM p.meta WHERE k = 'skip_version'")
                    if new_drop:
                        con.execute("DELETE FROM p.dropped")
                        con.execute(f"INSERT INTO p.dropped SELECT key FROM p.patch "
                                    f"WHERE kind = {KIND_DROP}")
                    if keys is None:
                        con.execute("DELETE FROM p.applied")
                    else:
                        con.execute("DELETE FROM p.applied WHERE key IN (SELECT key FROM temp.k)")
                    con.execute(
                        "INSERT INTO p.applied SELECT pt.key, pt.text FROM p.patch pt "
                        "JOIN main.translations t ON t.cache_key = ? AND t.id = pt.key "
                        f"WHERE pt.kind = {KIND_AUTO} AND t.text = {shown}"
                        + restrict.format("pt"), (ck,))
                    if push:
                        con.execute(
                            "INSERT OR REPLACE INTO p.applied SELECT pt.key, pt.text FROM temp.w w "
                            f"JOIN p.patch pt ON pt.key = w.key WHERE w.kind = {KIND_AUTO}")
                    con.execute("COMMIT")
                except BaseException:
                    con.execute("ROLLBACK")
                    raise
                if clear_skip:
                    self.skip_version = None
            finally:
                con.close()
            if keys is None:
                self._shrink_wal()
        sent = 0
        if push:
            try:
                sent = self._push(push)
            except Exception as exc:
                log.warning("patch v%d: texts not sent to the game: %s", self.version, exc)
            if sent:
                log.info("patch v%d: %d translations sent to the game (%d changed, %d new)",
                         self.version, sent, len(push) - new, new)
        return sent + removed

    def withdraw(self, db: Path | None, reason: str) -> int:
        with self.lock:
            self._set_ids_failed({"patch_version": self.version, "reason": reason,
                                  "time": int(time.time())})
            if not has_table(db):
                return 0
            con = self._open_cache(db)
            try:
                con.execute("CREATE TEMP TABLE r (key INTEGER PRIMARY KEY)")
                con.execute(
                    "INSERT OR IGNORE INTO temp.r SELECT t.id FROM main.translations t "
                    "JOIN p.patch pt ON pt.key = t.id "
                    f"WHERE t.cache_key = ? AND pt.kind IN ({KIND_REVIEWED}, {KIND_AUTO}) "
                    f"AND t.text = {self._shown('pt')}", (self.cache_key,))
                removed = self._delete_rows(con, "r")
                con.execute("DELETE FROM p.applied")
            finally:
                con.close()
        return removed

    def ids_ok(self, db: Path | None) -> None:
        if not self.ids_failed():
            return
        with self.lock:
            self._set_ids_failed(None)
        self.apply(db)

    INSERT = "INSERT INTO patch (key, kind, text, src_hash, piece, version) VALUES (?, ?, ?, ?, ?, ?)"

    @staticmethod
    def _rows_of(strings: dict[int, str], auto: dict[int, str], drop: set[int],
                 hashes: dict[int, str], piece: int | None,
                 versions: dict[int, int] | None = None) -> list[tuple]:
        hs = {k: lt.hash_int(v) for k, v in hashes.items()}
        vs = versions or {}
        rows = [(k, KIND_REVIEWED, v, hs.get(k), piece, vs.get(k)) for k, v in strings.items()]
        rows += [(k, KIND_AUTO, v, hs.get(k), piece, vs.get(k)) for k, v in auto.items()]
        rows += [(k, KIND_DROP, None, None, piece, None) for k in drop]
        return rows

    def _replace_all(self, con: sqlite3.Connection, data: dict, source: str, commit: str) -> None:
        version, strings, auto = lt.Patch.parse(data)
        drop = lt.Patch.parse_drop(data) - set(strings) - set(auto)
        fp = lt.Patch.parse_glossary(data)
        con.execute("DELETE FROM patch")
        con.execute("DELETE FROM pieces")
        con.executemany(self.INSERT, self._rows_of(strings, auto, drop, {}, None))
        self._set_meta(con, version=version, glossary=fp, width=None, commit=commit or None,
                       source=source)

    def import_data(self, data: dict, source: str, commit: str = "") -> None:
        with self.lock:
            con = self.writer
            con.execute("BEGIN IMMEDIATE")
            try:
                self._replace_all(con, data, source, commit)
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            self._load_meta()
            self._shrink_wal()

    def import_file(self, path: Path, source: str) -> bool:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.import_data(data, source)
            return True
        except FileNotFoundError:
            return False
        except Exception as exc:
            log.warning("patch %s unreadable: %s", path, exc)
            return False

    @staticmethod
    def _file_sig(path: Path) -> str:
        st = path.stat()
        return f"{st.st_size}:{st.st_mtime_ns}"

    def migrate(self, lang_dir: Path) -> None:
        pfile = lang_dir / lt.LANG.file("patch", ".json")
        if self.migrated:
            if not pfile.is_file():
                return
            sig = self._file_sig(pfile)
            if sig == self.file_sig:
                return
            data = _read_json(pfile)
            try:
                if isinstance(data, dict):
                    version = int(data.get("version", 0))
                    if version >= self.version or self.source == "patch-file":
                        self.import_data(data, "file")
            except Exception:
                pass
            with self.lock:
                con = self.writer
                con.execute("BEGIN IMMEDIATE")
                self._set_meta(con, file_sig=sig)
                con.execute("COMMIT")
                self.file_sig = sig
            return
        with self.lock:
            con = self.writer
            con.execute("BEGIN IMMEDIATE")
            self._set_meta(con, migrated=1)
            con.execute("COMMIT")
            self._load_meta()

    def update_pieces(self, index: dict, files: dict[str, Path], removed: list[str],
                      commit: str) -> set[int] | None:
        width = index["width"]
        with self.lock:
            con = self.writer
            full = self.source != "pieces" or self.width != width
            numbers = sorted({index["pieces"][n][0] for n in files}
                             | {lt.piece_number(n) for n in removed})
            old: dict[int, tuple] = {}
            new: dict[int, tuple] = {}
            con.execute("BEGIN IMMEDIATE")
            try:
                if full:
                    con.execute("DELETE FROM patch")
                    con.execute("DELETE FROM pieces")
                else:
                    for part in _chunks(numbers):
                        marks = ",".join("?" * len(part))
                        for k, kind, text, h, v in con.execute(
                                "SELECT key, kind, text, src_hash, version FROM patch "
                                f"WHERE piece IN ({marks})", part):
                            old[k] = (kind, text, h, v)
                        con.execute(f"DELETE FROM patch WHERE piece IN ({marks})", part)
                    con.executemany("DELETE FROM pieces WHERE name = ?",
                                    [(n,) for n in (*files, *removed)])
                for name in sorted(files):
                    number, sha, size = index["pieces"][name]
                    body = files[name].read_bytes()
                    if len(body) != size or hashlib.sha256(body).hexdigest() != sha:
                        raise ValueError(f"piece {name} does not match the index")
                    data = json.loads(body)
                    strings, auto, drop, hashes = lt.parse_piece(data, number, width)
                    rows = self._rows_of(strings, auto, drop, hashes, number,
                                         lt.parse_piece_versions(data))
                    con.executemany(self.INSERT, rows)
                    con.execute("INSERT INTO pieces (name, sha256, entries, size) VALUES (?, ?, ?, ?)",
                                (name, sha, len(rows), size))
                    if not full:
                        new.update((r[0], (r[1], r[2], r[3], r[5])) for r in rows)
                self._set_meta(con, version=index["version"], glossary=index["glossary"],
                               width=width, commit=commit or None, source="pieces")
                con.execute("COMMIT")
            except BaseException:
                con.execute("ROLLBACK")
                raise
            self._load_meta()
            self._shrink_wal()
        if full:
            return None
        return {k for k in old.keys() | new.keys() if old.get(k) != new.get(k)}


class PieceUpdater(threading.Thread):
    def __init__(self, patch: CachePatch, lang: str, db: Path | None,
                 branch: str = lt.DEFAULT_BRANCH, repo: str = lt.GITHUB_REPO,
                 raw_base: str | None = None, use_api: bool = True) -> None:
        super().__init__(daemon=True, name="patch-updater")
        self.patch, self.lang, self.db = patch, lang, db
        self.branch, self.repo, self.use_api = branch, repo, use_api
        self.raw_base = (raw_base or f"https://raw.githubusercontent.com/{repo}").rstrip("/")
        self.tmp = patch.path.with_name(lt.LANG.file("patch", ".download"))
        self.checks = 0

    def run(self) -> None:
        time.sleep(3)
        while True:
            try:
                self.check()
            except Exception as exc:
                log.info("patch update skipped: %s", exc)
            self.checks += 1
            time.sleep(lt.UPDATE_INTERVAL)

    def _newer_ok(self, version: int) -> bool:
        return version >= self.patch.version or self.patch.source == "patch-file"

    def check(self) -> str:
        p = self.patch
        commit = lt.latest_commit(self.repo, self.branch, "patch") if self.use_api else None
        if commit and commit == p.commit and p.source in ("pieces", "github-file"):
            return "same commit"
        base = f"{self.raw_base}/{commit or self.branch}/patch/"
        try:
            index = lt.parse_index(json.loads(lt.http_get(base + f"{self.lang}/index.json",
                                                          limit=2_000_000)))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return self._single_file(base + f"patch_{self.lang}.json", commit or "")
            raise
        if not self._newer_ok(index["version"]):
            return "older"
        local = p.pieces()
        full = p.source != "pieces" or p.width != index["width"]
        want = [n for n, (_, sha, _) in index["pieces"].items() if full or local.get(n) != sha]
        removed = [] if full else sorted(n for n in local if n not in index["pieces"])
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir(parents=True)
        try:
            files: dict[str, Path] = {}
            for name in want:
                _, sha, expected = index["pieces"][name]
                body = lt.http_get(base + f"{self.lang}/{name}", limit=expected)
                if len(body) != expected or hashlib.sha256(body).hexdigest() != sha:
                    raise ValueError(f"piece {name} does not match the index")
                files[name] = self.tmp / name
                files[name].write_bytes(body)
            before = (p.glossary_fp, p.version)
            changed = p.update_pieces(index, files, removed, commit or "")
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)
        try:
            if changed is None or before[0] != p.glossary_fp:
                p.apply(self.db)
            elif changed:
                p.apply(self.db, changed)
        except Exception as exc:
            log.warning("cannot apply the patch to %s: %s", self.db, exc)
        return f"{len(want)} pieces, {len(removed)} removed"

    def _single_file(self, url: str, commit: str) -> str:
        p = self.patch
        data = json.loads(lt.http_get(url).decode("utf-8"))
        version = lt.Patch.parse(data)[0]
        if not self._newer_ok(version):
            return "older"
        p.import_data(data, "github-file", commit)
        try:
            p.apply(self.db)
        except Exception as exc:
            log.warning("cannot apply the patch to %s: %s", self.db, exc)
        return "single file"
