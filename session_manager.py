"""Storico incrementale e snapshot della verifica."""
import datetime as dt
import difflib
import hashlib
import json
import shutil
from pathlib import Path

from project_manager import HISTORY_DIR, VerificationProject
from utils import parse_extensions


class SessionManager:
    def __init__(self, local_directory, verification_name=None, alert_threshold=30,
                 remote_directory="", extensions=""):
        self.project = VerificationProject(local_directory)
        self.session_dir = self.project.root
        self.session_id = self.project.manifest.get("name", verification_name or "Verifica")
        self.alert_threshold = int(alert_threshold)
        self.remote_directory = remote_directory or self.project.manifest.get("remote_directory", "")
        self.extensions = extensions or self.project.manifest.get("file_extensions", "")
        self.dismissed_alerts = self._load_dismissed_alerts()
        # Una sessione riaperta può puntare a file già popolati sul server:
        # il primo rilevamento è una baseline, non un comportamento sospetto.
        self._baseline_pending = True

    def log_event(self, event_type, data):
        self.project.log_event(event_type, data)

    def _load_dismissed_alerts(self):
        """Recupera le chiusure manuali, persistenti anche dopo il riavvio."""
        dismissed = set()
        events_path = self.project.root / "00_SMXSystem" / "events.jsonl"
        if not events_path.is_file():
            return dismissed
        try:
            with events_path.open("r", encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    if event.get("event_type") != "alert_dismissed":
                        continue
                    data = event.get("data", {})
                    student = data.get("student")
                    snapshot = data.get("snapshot_id")
                    if student and snapshot:
                        dismissed.add((student, snapshot))
        except (OSError, json.JSONDecodeError):
            pass
        return dismissed

    def dismiss_alert(self, student, snapshot_id):
        """Chiude l'allarme per la sola versione attualmente visualizzata."""
        if not snapshot_id:
            return
        self.dismissed_alerts.add((student, snapshot_id))
        self.log_event("alert_dismissed", {"student": student, "snapshot_id": snapshot_id})

    def is_alert_dismissed(self, student, snapshot_id):
        return (student, snapshot_id) in self.dismissed_alerts

    @staticmethod
    def _hash_folder(folder):
        digest = hashlib.sha256()
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            digest.update(str(path.relative_to(folder)).encode("utf-8"))
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()

    def _source_files(self, folder):
        extensions = parse_extensions(self.extensions)
        return [
            path for path in sorted(p for p in folder.rglob("*") if p.is_file())
            if not extensions or any(path.name.lower().endswith(extension) for extension in extensions)
        ]

    def _read_sources(self, folder):
        contents = []
        for path in self._source_files(folder):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="latin-1", errors="replace")
            except OSError:
                continue
            contents.append(f"### {path.relative_to(folder)}\n{text}")
        return "\n\n".join(contents)

    def _count_source_lines(self, folder):
        total = 0
        for path in self._source_files(folder):
            try:
                with path.open("r", encoding="utf-8") as stream:
                    total += sum(1 for _line in stream)
            except UnicodeDecodeError:
                with path.open("r", encoding="latin-1", errors="replace") as stream:
                    total += sum(1 for _line in stream)
            except OSError:
                continue
        return total

    def capture(self, student, source_folder, line_count=None, baseline=False):
        source = Path(source_folder)
        if not source.is_dir():
            return None
        student_dir = self.project.root / HISTORY_DIR / student
        timeline = student_dir / "timeline.jsonl"
        previous = self.get_history(student)
        folder_hash = self._hash_folder(source)
        if previous and previous[-1].get("hash") == folder_hash:
            return None
        stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        snapshot_dir = student_dir / "snapshots" / stamp
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, snapshot_dir / "files")
        content = self._read_sources(source)
        if line_count is None:
            line_count = self._count_source_lines(source)
        entry = {"timestamp": dt.datetime.now().astimezone().isoformat(), "file_name": student,
                 "line_count": int(line_count), "hash": folder_hash, "snapshot_id": stamp,
                 "content": content, "baseline": bool(baseline)}
        timeline.parent.mkdir(parents=True, exist_ok=True)
        with timeline.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
        if previous:
            delta = entry["line_count"] - previous[-1]["line_count"]
            diff = "\n".join(difflib.unified_diff(previous[-1].get("content", "").splitlines(),
                                                   content.splitlines(), lineterm=""))
            (snapshot_dir / "changes.diff").write_text(diff, encoding="utf-8")
            if not baseline and delta > self.alert_threshold:
                self.log_event("alert_suspicion", {"student": student, "delta": delta})
                entry["alert_delta"] = delta
        self.log_event("snapshot_created", {"student": student, "snapshot": stamp,
                                             "line_count": int(line_count)})
        return entry

    def add_sample(self, samples):
        captured = []
        baseline = self._baseline_pending
        for item in samples:
            if item.get("source_folder"):
                entry = self.capture(
                    item["name"], item["source_folder"], item.get("line_count"), baseline=baseline
                )
                if entry is not None:
                    captured.append(entry)
        # Dopo il primo giro ogni variazione successiva viene valutata normalmente.
        if samples:
            self._baseline_pending = False
        return captured

    def get_history(self, name):
        timeline = self.project.root / HISTORY_DIR / name / "timeline.jsonl"
        if not timeline.is_file():
            return []
        result = []
        with timeline.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    result.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return result

    def list_snapshots(self, name):
        return [(item["snapshot_id"], item["timestamp"], item["line_count"])
                for item in self.get_history(name)]

    def restore(self, name, snapshot_id):
        return self.project.restore_snapshot(name, snapshot_id, self.remote_directory)
