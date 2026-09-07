"""Gestione persistente del progetto-verifica SMX."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

SYSTEM_DIR = "00_SMXSystem"
PROJECT_FILE = f"{SYSTEM_DIR}/smx_project.json"
LEGACY_PROJECT_FILE = "smx_project.json"
SESSION_EXTENSION = ".smxSession"
HISTORY_DIR = "00_SMXHistory"
RECOVERY_DIR = "00_SMXRecovery"


def _safe_name(value: str) -> str:
    value = re.sub(r"[^\w.-]+", "_", (value or "Verifica").strip(), flags=re.UNICODE)
    return value.strip("._") or "Verifica"


def atomic_json_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class VerificationProject:
    def __init__(self, local_directory: str):
        self.root = Path(local_directory).expanduser().resolve()
        self.manifest_path = self.root / PROJECT_FILE
        if not self.manifest_path.is_file():
            # Migrazione trasparente delle verifiche create prima della nuova
            # struttura: il manifest era nella radice della Dir Locale.
            legacy_path = self.root / LEGACY_PROJECT_FILE
            if legacy_path.is_file():
                self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(legacy_path), str(self.manifest_path))
        if not self.manifest_path.is_file():
            raise ValueError(f"La cartella non contiene {PROJECT_FILE}")
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))

    @classmethod
    def create(cls, local_directory: str, name: str, remote_directory: str = "",
               extensions: str = ".cpp", alert_threshold: int = 30):
        root = Path(local_directory).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        for folder in (SYSTEM_DIR, HISTORY_DIR, RECOVERY_DIR, "00_MixOutput", "00_Pdf"):
            (root / folder).mkdir(exist_ok=True)
        now = dt.datetime.now().astimezone().isoformat()
        manifest = {
            "schema_version": 1, "name": name.strip() or "Verifica",
            "created_at": now, "updated_at": now, "status": "active",
            "remote_directory": str(Path(remote_directory).resolve()) if remote_directory else "",
            "file_extensions": extensions, "alert_threshold": int(alert_threshold),
        }
        atomic_json_write(root / PROJECT_FILE, manifest)
        project = cls(str(root))
        project.log_event("project_created", {"remote_directory": manifest["remote_directory"]})
        project.save_session_file()
        return project

    @classmethod
    def create_in(cls, parent: str, name: str, **kwargs):
        parent_path = Path(parent).expanduser().resolve()
        if (parent_path / PROJECT_FILE).is_file():
            raise ValueError("Non puoi creare una verifica dentro un'altra Dir Locale SMX")
        stamp = dt.datetime.now().strftime("%Y%m%d_%H-%M-%S")
        return cls.create(str(parent_path / f"{stamp}_{_safe_name(name)}"), name, **kwargs)

    def save(self, **changes):
        self.manifest.update(changes)
        self.manifest["updated_at"] = dt.datetime.now().astimezone().isoformat()
        atomic_json_write(self.manifest_path, self.manifest)

    def log_event(self, event_type: str, data: dict | None = None):
        entry = {"timestamp": dt.datetime.now().astimezone().isoformat(),
                 "event_type": event_type, "data": data or {}}
        path = self.root / SYSTEM_DIR / "events.jsonl"
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def copy_from_remote(self):
        import data_handler
        remote = self.manifest.get("remote_directory", "")
        if not remote or not os.path.isdir(remote):
            raise ValueError("Directory remota non disponibile")
        copied = data_handler._copy_test_folders(remote, str(self.root), report_text=None)
        self.log_event("remote_collection", {"folders": copied})
        return copied

    def archive(self, destination: str) -> str:
        destination = Path(destination).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        archive = destination / f"{_safe_name(self.manifest['name'])}_{dt.datetime.now():%Y%m%d_%H%M%S}.smx.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in self.root.rglob("*"):
                if path.is_file():
                    bundle.write(path, path.relative_to(self.root).as_posix())
        self.log_event("archive_created", {"path": str(archive)})
        return str(archive)

    def save_session_file(self, destination: str | None = None) -> str:
        """Crea un file portabile .smxSession con l'intero progetto-verifica."""
        if destination:
            session_path = Path(destination).expanduser().resolve()
            if session_path.suffix.lower() != SESSION_EXTENSION.lower():
                session_path = session_path.with_suffix(SESSION_EXTENSION)
        else:
            session_path = self.root / SYSTEM_DIR / f"{_safe_name(self.manifest['name'])}{SESSION_EXTENSION}"
        session_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_event("session_saved", {"path": str(session_path)})
        temporary = session_path.with_suffix(session_path.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as bundle:
                for path in self.root.rglob("*"):
                    if not path.is_file() or path.resolve() in (session_path, temporary):
                        continue
                    bundle.write(path, path.relative_to(self.root).as_posix())
            os.replace(temporary, session_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return str(session_path)

    @classmethod
    def load_session_file(cls, session_file: str, destination_parent: str):
        """Estrae una .smxSession in una nuova Dir Locale e restituisce il progetto."""
        source = Path(session_file).expanduser().resolve()
        parent = Path(destination_parent).expanduser().resolve()
        if not source.is_file() or source.suffix.lower() != SESSION_EXTENSION.lower():
            raise ValueError("Seleziona un file .smxSession valido")
        parent.mkdir(parents=True, exist_ok=True)
        base_name = _safe_name(source.stem)
        destination = parent / base_name
        counter = 2
        while destination.exists():
            destination = parent / f"{base_name}_{counter}"
            counter += 1
        destination.mkdir()
        try:
            with zipfile.ZipFile(source, "r") as bundle:
                names = {name.replace("\\", "/") for name in bundle.namelist()}
                if PROJECT_FILE not in names and LEGACY_PROJECT_FILE not in names:
                    raise ValueError("Il file non contiene una sessione SMX valida")
                for member in bundle.infolist():
                    target = (destination / member.filename).resolve()
                    if target != destination and destination not in target.parents:
                        raise ValueError("Il file sessione contiene un percorso non valido")
                    bundle.extract(member, destination)
            project = cls(str(destination))
            project.log_event("session_loaded", {"source": str(source)})
            return project
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise

    def restore_snapshot(self, student: str, snapshot_id: str, remote_directory: str | None = None):
        source = self.root / HISTORY_DIR / student / "snapshots" / snapshot_id / "files"
        remote_root = Path(remote_directory or self.manifest.get("remote_directory", "")).resolve()
        target = (remote_root / student).resolve()
        if not source.is_dir():
            raise ValueError("Snapshot non disponibile")
        if remote_root not in target.parents or not remote_root.is_dir():
            raise ValueError("Destinazione remota non valida")
        backup = self.root / RECOVERY_DIR / student / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        if target.exists():
            shutil.copytree(target, backup, dirs_exist_ok=True)
            shutil.rmtree(target)
        shutil.copytree(source, target)
        self.log_event("snapshot_restored", {"student": student, "snapshot": snapshot_id,
                                             "target": str(target), "backup": str(backup)})
        return str(target), str(backup)
