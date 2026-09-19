"""Acquisizione in sola lettura e storico dei siti web pubblici degli alunni.

Il modulo non usa credenziali e non effettua mai richieste di scrittura.  Uno
snapshot contiene esclusivamente le risorse pubbliche raggiungibili dalla home
page dello stesso dominio.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

MONITOR_DIR = "00_DomainMonitor"
USER_AGENT = "SMX-DomainMonitor/1.0 (classroom progress monitoring)"
TRACKED_SUFFIXES = (".html", ".htm", ".css", ".js", ".json", ".xml", ".txt", ".md")


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self._chunks, self._source_chunks, self._ignored = set(), [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._ignored += 1
        for name, value in attrs:
            if name.lower() in ("href", "src") and value:
                self.links.add(value.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._ignored:
            self._ignored -= 1

    def handle_data(self, data):
        # Il testo di script e style è significativo per la codebase, anche se
        # non lo mostriamo come contenuto della pagina HTML.
        if data.strip():
            self._source_chunks.append(data.strip())
        if not self._ignored and data.strip():
            self._chunks.append(re.sub(r"\s+", " ", data).strip())

    @property
    def text(self):
        return "\n".join(self._chunks + self._source_chunks)


def normalize_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError("Inserisci un dominio o un URL")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("L'URL deve iniziare con http:// o https://")
    return value.rstrip("/") + "/"


def _safe_name(value: str) -> str:
    return re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE).strip("._") or "sito"


class DomainMonitor:
    def __init__(self, project_directory: str):
        self.root = Path(project_directory) / MONITOR_DIR
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "reports").mkdir(exist_ok=True)
        (self.root / "snapshots").mkdir(exist_ok=True)

    def _robot_parser(self, start_url: str):
        parsed = urlparse(start_url)
        robots = RobotFileParser()
        robots.set_url(f"{parsed.scheme}://{parsed.netloc}/robots.txt")
        try:
            robots.read()
            return robots
        except Exception:
            return None  # assenza/non raggiungibilità robots: prosegui con crawl limitato

    def _fetch(self, url: str):
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,text/css,application/javascript,text/plain,*/*;q=0.2"})
        with urlopen(request, timeout=15) as response:
            raw = response.read(1_500_000)
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), content_type, raw.decode(charset, errors="replace")

    @staticmethod
    def _is_allowed(url: str, host: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or parsed.netloc != host:
            return False
        path = parsed.path.lower()
        return not path or path.endswith("/") or path.endswith(TRACKED_SUFFIXES)

    def scan(self, student: str, url: str, max_pages: int = 60, progress=None) -> dict:
        start_url = normalize_url(url)
        host = urlparse(start_url).netloc
        robots = self._robot_parser(start_url)
        todo, seen, files, errors = [start_url], set(), {}, []
        while todo and len(seen) < max_pages:
            current = urldefrag(todo.pop(0))[0]
            if current in seen or not self._is_allowed(current, host):
                continue
            seen.add(current)
            if robots and not robots.can_fetch(USER_AGENT, current):
                errors.append(f"robots.txt esclude: {current}")
                continue
            try:
                final_url, content_type, body = self._fetch(current)
                parser = _PageParser()
                if content_type in ("text/html", "application/xhtml+xml"):
                    parser.feed(body)
                    for link in parser.links:
                        candidate = urldefrag(urljoin(final_url, link))[0]
                        if self._is_allowed(candidate, host) and candidate not in seen:
                            todo.append(candidate)
                    comparable = parser.text
                else:
                    comparable = body
                key = urlparse(final_url).path or "/"
                files[key] = {"url": final_url, "type": content_type, "sha256": hashlib.sha256(comparable.encode("utf-8")).hexdigest(), "lines": len(comparable.splitlines()), "content": comparable}
            except Exception as exc:
                errors.append(f"{current}: {exc}")
            if progress:
                progress(len(seen), max_pages, student)
            time.sleep(0.15)
        now = dt.datetime.now().astimezone()
        snapshot = {"student": student, "url": start_url, "scanned_at": now.isoformat(), "files": files, "errors": errors, "limit_reached": bool(todo)}
        self._save_and_report(snapshot)
        return snapshot

    def _student_dir(self, student: str) -> Path:
        directory = self.root / "snapshots" / _safe_name(student)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _last_snapshot(self, student: str):
        paths = sorted(self._student_dir(student).glob("*.json"))
        if not paths:
            return None
        try:
            return json.loads(paths[-1].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _save_and_report(self, snapshot: dict):
        previous = self._last_snapshot(snapshot["student"])
        stamp = dt.datetime.fromisoformat(snapshot["scanned_at"]).strftime("%Y%m%d_%H%M%S")
        path = self._student_dir(snapshot["student"]) / f"{stamp}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        report = self._build_report(snapshot, previous)
        report_path = self.root / "reports" / f"{stamp}_{_safe_name(snapshot['student'])}.md"
        report_path.write_text(report, encoding="utf-8")
        snapshot["report_path"] = str(report_path)
        snapshot["previous"] = previous is not None

    def _build_report(self, current: dict, previous: dict | None) -> str:
        current_files = current["files"]
        old_files = previous.get("files", {}) if previous else {}
        added = sorted(set(current_files) - set(old_files))
        removed = sorted(set(old_files) - set(current_files))
        changed = sorted(path for path in set(current_files) & set(old_files) if current_files[path]["sha256"] != old_files[path]["sha256"])
        delta_lines = sum(current_files[p]["lines"] for p in added) - sum(old_files[p]["lines"] for p in removed)
        for path in changed:
            delta_lines += current_files[path]["lines"] - old_files[path]["lines"]
        lines = [f"# SMX Domain Report — {current['student']}", "", f"- Sito: {current['url']}", f"- Acquisizione: {current['scanned_at']}", f"- Risorse monitorate: {len(current_files)}", ""]
        if not previous:
            lines += ["## Baseline", "", "Prima acquisizione: questa versione è il riferimento per i confronti successivi."]
        else:
            lines += ["## Delta stile Git", "", f"`{len(added)} file aggiunti, {len(changed)} modificati, {len(removed)} rimossi, {delta_lines:+d} righe`", ""]
            for label, items, mark in (("Aggiunti", added, "+"), ("Modificati", changed, "~"), ("Rimossi", removed, "-")):
                if items:
                    lines += [f"### {label}", ""] + [f"- `{mark} {item}`" for item in items] + [""]
            for path in changed[:10]:
                diff = difflib.unified_diff(old_files[path]["content"].splitlines(), current_files[path]["content"].splitlines(), fromfile="precedente/" + path, tofile="corrente/" + path, lineterm="")
                rendered = list(diff)
                if rendered:
                    lines += [f"### Diff: `{path}`", "", "```diff"] + rendered[:160] + ["```", ""]
        if current["errors"]:
            lines += ["## Avvisi", ""] + [f"- {error}" for error in current["errors"]]
        if current["limit_reached"]:
            lines += ["", "- Limite di pagine raggiunto: aumenta il limite solo se necessario."]
        return "\n".join(lines) + "\n"
