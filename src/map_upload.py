"""Map upload (optional): send the new rows of the map to the project's collector.

Only with "--upload" in module.toml; without it this file is never used and the module sends
nothing anywhere.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UPLOAD_URL = "https://upload.kindling.nexus/v1/map"
FORMAT = 1
FIRST_DELAY = 5 * 60
INTERVAL = 3 * 3600
RETRY = 30 * 60
PAUSE = 5
CHUNK_ROWS = 20_000
CHUNK_BYTES = 6_000_000
TIMEOUT = 30
SINCE = 1_791_201_600
MAX_EN = 10_000
MAX_KEY = 0xFFFF_FFFF
STATE_FILE = "upload_state.json"

log = logging.getLogger("lt")


def valid_row(key, en, seen) -> bool:
    if type(key) is not int or not 1 <= key <= MAX_KEY:
        return False
    if type(en) is not str or not en.strip() or len(en) > MAX_EN:
        return False
    try:
        en.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return type(seen) is int and seen >= SINCE


class Stop(Exception):
    """The collector closed the uploads (410)."""


class MapUploader(threading.Thread):
    def __init__(self, map_path: Path, data_dir: Path, lang: str, version: str,
                 url: str = UPLOAD_URL, first_delay: float = FIRST_DELAY) -> None:
        super().__init__(daemon=True, name="map-upload")
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" and not (parts.scheme == "http" and parts.hostname in ("127.0.0.1", "localhost")):
            raise ValueError(f"upload address must be https (or http on 127.0.0.1 for tests): {url}")
        self.map_path, self.state_path = map_path, data_dir / STATE_FILE
        self.lang, self.version, self.url = lang, version, url
        self.first_delay = first_delay
        self.stopped = threading.Event()
        self.rounds = 0

    def load_state(self) -> tuple[int, int]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            seen, key = data["seen"], data["key"]
            if type(seen) is int and type(key) is int:
                return seen, key
            raise ValueError("not integers")
        except FileNotFoundError:
            return 0, 0
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.info("map upload: %s unreadable (%s): everything is sent again", self.state_path.name, exc)
            return 0, 0

    def save_state(self, seen: int, key: int, rows: int) -> None:
        data = {"format": FORMAT, "seen": seen, "key": key,
                "last_ok": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": rows}
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def read_piece(self, after: tuple[int, int], until: int) -> tuple[list[list], tuple[int, int] | None]:
        uri = self.map_path.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            cur = con.execute(
                "SELECT key, en, seen FROM texts WHERE how = 'live' AND seen >= ? AND seen <= ? "
                "AND (seen > ? OR (seen = ? AND key > ?)) ORDER BY seen, key LIMIT ?",
                (SINCE, until, after[0], after[0], after[1], CHUNK_ROWS))
            rows, last, size = [], None, 0
            for key, en, seen in cur:
                last = (seen, key)
                if valid_row(key, en, seen):
                    rows.append([key, en, seen])
                    size += len(en.encode("utf-8")) + 32
                    if size >= CHUNK_BYTES:
                        break
            return rows, last
        finally:
            con.close()

    def post(self, rows: list[list]) -> None:
        body = gzip.compress(json.dumps({"format": FORMAT, "lang": self.lang, "module": self.version,
                                         "rows": rows}, ensure_ascii=False,
                                        separators=(",", ":")).encode("utf-8"), mtime=0)
        req = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Content-Type": "application/gzip", "User-Agent": f"gw2-local-translator/{self.version}"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            answer = json.loads(resp.read(10_000) or b"{}")
        if not answer.get("ok"):
            raise ValueError(f"unexpected answer {answer!r}")

    def round(self) -> float | None:
        self.rounds += 1
        if not self.map_path.is_file():
            return INTERVAL
        after = self.load_state()
        until = int(time.time()) - 2
        if after[0] > until + 60:
            log.info("map upload: the PC clock went back; everything is sent again")
            after = (0, 0)
        sent = pieces = 0
        while not self.stopped.is_set():
            try:
                rows, last = self.read_piece(after, until)
            except sqlite3.Error as exc:
                log.info("map upload: map not readable now (%s): retry later", exc)
                return RETRY
            if last is None:
                break
            if rows:
                if pieces:
                    self.stopped.wait(PAUSE)
                try:
                    self.post(rows)
                except urllib.error.HTTPError as exc:
                    return self.refused(exc.code, sent)
                except Exception as exc:  # noqa: BLE001
                    log.info("map upload: collector not reachable (%s): retry in %d min%s", exc,
                             RETRY // 60, f" ({sent} texts sent before)" if sent else "")
                    return RETRY
                sent += len(rows)
                pieces += 1
            after = last
            self.save_state(after[0], after[1], sent)
        if sent:
            log.info("map upload: %d texts sent (%d piece%s) - thank you!", sent, pieces, "" if pieces == 1 else "s")
        else:
            log.debug("map upload: nothing new")
        return INTERVAL

    def refused(self, code: int, sent: int) -> float | None:
        done = f" ({sent} texts sent before)" if sent else ""
        if code == 410:
            log.info("map upload: closed by the project; no more uploads until the next game start%s", done)
            return None
        if code in (429, 503):
            log.info("map upload: collector busy or full (%d): retry in %d hours%s", code, INTERVAL // 3600, done)
        elif code >= 500:
            log.info("map upload: collector error (%d): retry in %d min%s", code, RETRY // 60, done)
            return RETRY
        else:
            log.warning("map upload: refused by the collector (%d): retry in %d hours%s", code,
                        INTERVAL // 3600, done)
        return INTERVAL

    def run(self) -> None:
        log.info("map upload ON (--upload): new texts seen in the game are sent to %s every %d hours",
                 urllib.parse.urlsplit(self.url).hostname, INTERVAL // 3600)
        wait = self.first_delay
        while not self.stopped.wait(wait):
            try:
                wait = self.round()
            except Exception:  # noqa: BLE001
                log.exception("map upload failed")
                wait = INTERVAL
            if wait is None:
                return

