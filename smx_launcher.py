"""
SMX Launcher - controlla automaticamente GitHub Releases, aggiorna solo su richiesta.

- Nessuna credenziale: richiede release pubbliche.
- Installazione in una directory dell'utente, separata dai dati delle verifiche.
- Verifica SHA-256 e percorsi dei file prima di attivare un aggiornamento.
- L'ultima versione funzionante rimane disponibile anche senza rete.
"""

import hashlib
import json
import os
import pathlib
import platform
import queue
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox
import urllib.error
import urllib.request
import zipfile

from launcher_config import CHECKSUM_ASSET, GITHUB_API_URL, GITHUB_REPOSITORY, RELEASE_ASSETS


def user_application_directory():
    """Cartella persistente del programma, mai dentro alle cartelle delle verifiche."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            base = os.path.join(pathlib.Path.home(), "AppData", "Local")
        return pathlib.Path(base) / "SMX" / "Launcher"

    base = os.environ.get("XDG_DATA_HOME")
    if not base:
        base = os.path.join(pathlib.Path.home(), ".local", "share")
    return pathlib.Path(base) / "smx" / "launcher"


def platform_asset():
    """Seleziona unicamente archivi x86-64 per Windows o Linux."""
    if sys.platform not in RELEASE_ASSETS:
        raise RuntimeError("Piattaforma non supportata: " + sys.platform)

    architecture = platform.machine().lower()
    if architecture not in ("amd64", "x86_64"):
        raise RuntimeError("Architettura non supportata: " + architecture)

    return RELEASE_ASSETS[sys.platform]


def request_bytes(url, timeout=30):
    """Recupera dati pubblici via HTTPS, evitando redirect verso HTTP."""
    if not url.startswith("https://"):
        raise RuntimeError("Il download deve utilizzare HTTPS.")
    req = urllib.request.Request(
        url, headers={"User-Agent": "SMX-Launcher/1.0", "Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        if not response.geturl().startswith("https://"):
            raise RuntimeError("Redirect non sicuro.")
        return response.read()


def latest_release():
    """Legge una sola volta i metadati dell'ultima release pubblicata."""
    url = "{}/repos/{}/releases/latest".format(GITHUB_API_URL, GITHUB_REPOSITORY)
    info = json.loads(request_bytes(url).decode("utf-8"))
    version = str(info.get("tag_name", "")).strip()
    if not version or not version.startswith("v"):
        raise RuntimeError("La release non contiene un tag versione valido.")

    assets = {}
    for item in info.get("assets", []):
        name = item.get("name")
        address = item.get("browser_download_url")
        if name and address:
            assets[name] = address

    return {"version": version, "assets": assets}


def version_sort_key(tag):
    """Confronto numerico dei tag vMAJOR.MINOR.PATCH (senza espressioni contratte)."""
    cleaned = tag.lstrip("v").split("-")[0]
    parts = cleaned.split(".")
    if len(parts) != 3:
        raise ValueError("Versione non valida: " + tag)
    numbers = []
    for part in parts:
        numbers.append(int(part))
    return tuple(numbers)


def current_version(base):
    marker = base / "current.json"
    if not marker.is_file():
        return ""
    try:
        content = json.loads(marker.read_text(encoding="utf-8"))
        return str(content.get("version", ""))
    except (OSError, ValueError, TypeError):
        return ""


def previous_version(base):
    """Versione avviabile disponibile per un ripristino manuale."""
    manifest = base / "current.json"
    if not manifest.is_file():
        return ""
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        candidate = str(data.get("previous", ""))
        if candidate and binary_for_version(base, candidate).is_file():
            return candidate
    except (OSError, ValueError, TypeError):
        pass
    return ""


def restore_previous(base):
    """Ripristina il puntatore senza cancellare né modificare i dati utente."""
    previous = previous_version(base)
    if not previous:
        raise RuntimeError("Non è disponibile una versione precedente valida.")
    current = current_version(base)
    temporary = base / "current.json.tmp"
    temporary.write_text(
        json.dumps({"version": previous, "previous": current}, indent=2),
        encoding="utf-8"
    )
    os.replace(temporary, base / "current.json")
    return previous


def binary_for_version(base, version):
    spec = platform_asset()
    return base / "versions" / version / pathlib.Path(spec["binary"])


def local_executable(base):
    """Non avvia un file assente, anche se la manifestazione locale è corrotta."""
    version = current_version(base)
    if not version:
        return None
    executable = binary_for_version(base, version)
    if executable.is_file():
        return executable
    return None


def expected_sha256(checksums_text, filename):
    """SHA256SUMS.txt utilizza il formato standard sha256sum."""
    for line in checksums_text.splitlines():
        fields = line.strip().split()
        if len(fields) < 2:
            continue
        expected = fields[0]
        listed_name = fields[1].lstrip("*")
        if listed_name == filename:
            if len(expected) == 64:
                return expected.lower()
    raise RuntimeError("Checksum non trovato per " + filename)


def download_archive(address, destination):
    """Scrive l'archivio in streaming senza caricarlo tutto in RAM."""
    if not address.startswith("https://"):
        raise RuntimeError("URL di download non sicuro.")
    request = urllib.request.Request(address, headers={"User-Agent": "SMX-Launcher/1.0"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response:
        if not response.geturl().startswith("https://"):
            raise RuntimeError("Redirect non sicuro.")
        with open(destination, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                output.write(chunk)
    return digest.hexdigest()


def safe_member_path(root, member_name):
    """Blocca directory traversal e path assoluti negli archivi."""
    normalized = member_name.replace("\\", "/")
    item = pathlib.PurePosixPath(normalized)
    if item.is_absolute() or ".." in item.parts:
        raise RuntimeError("Percorso non consentito nell'archivio.")
    if ":" in normalized:
        raise RuntimeError("Percorso non consentito nell'archivio.")
    return root.joinpath(*item.parts)


def unpack_archive(archive_path, destination):
    """Estrae file regolari, senza seguire symlink o hardlink."""
    destination.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                output = safe_member_path(destination, member.filename)
                mode = (member.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    raise RuntimeError("Link simbolici non ammessi.")
                if member.is_dir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source:
                    with open(output, "wb") as target:
                        shutil.copyfileobj(source, target)
    else:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise RuntimeError("Elemento non consentito nell'archivio.")
                output = safe_member_path(destination, member.name)
                if member.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                    continue
                output.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise RuntimeError("Archivio incompleto.")
                with source:
                    with open(output, "wb") as target:
                        shutil.copyfileobj(source, target)
                if sys.platform == "linux":
                    os.chmod(output, member.mode & 0o755)


def install_release(base, release):
    """
    Installa in una directory nuova, verifica l'avviabile e cambia il puntatore
    current.json soltanto a installazione completata. La vecchia release resta.
    """
    version = release["version"]
    version_sort_key(version)
    specification = platform_asset()
    archive_name = specification["archive"]
    assets = release["assets"]
    if archive_name not in assets or CHECKSUM_ASSET not in assets:
        raise RuntimeError("La release non contiene i file previsti per questa piattaforma.")

    checksum_text = request_bytes(assets[CHECKSUM_ASSET]).decode("utf-8")
    expected = expected_sha256(checksum_text, archive_name)

    versions_directory = base / "versions"
    versions_directory.mkdir(parents=True, exist_ok=True)
    destination = versions_directory / version
    if destination.exists():
        executable = binary_for_version(base, version)
        if not executable.is_file():
            raise RuntimeError("Versione già presente ma incompleta: " + str(destination))
    else:
        with tempfile.TemporaryDirectory(prefix="smx-update-", dir=base) as temp:
            working = pathlib.Path(temp)
            archive_path = working / archive_name
            actual = download_archive(assets[archive_name], archive_path)
            if actual != expected:
                raise RuntimeError("SHA-256 non corrispondente: download rifiutato.")

            staged = working / "staged"
            unpack_archive(archive_path, staged)
            executable = staged / pathlib.Path(specification["binary"])
            if not executable.is_file():
                raise RuntimeError("Eseguibile SMX assente nel pacchetto scaricato.")
            os.replace(staged, destination)

    previous = current_version(base)
    if previous == version:
        previous = previous_version(base)

    manifest = base / "current.json"
    temporary_manifest = base / "current.json.tmp"
    temporary_manifest.write_text(
        json.dumps({"version": version, "previous": previous}, indent=2),
        encoding="utf-8"
    )
    os.replace(temporary_manifest, manifest)
    return binary_for_version(base, version)


def launch_application(executable):
    """Avvia SMX come processo indipendente, senza intervenire sui suoi dati."""
    if sys.platform == "linux":
        executable.chmod(executable.stat().st_mode | 0o100)
    subprocess.Popen([str(executable)], cwd=str(executable.parent))


def main():
    base = user_application_directory()
    base.mkdir(parents=True, exist_ok=True)
    events = queue.Queue()
    state = {"release": None, "busy": False}

    root = tk.Tk()
    root.title("SMX - Avvio e aggiornamenti")
    root.geometry("680x295")
    root.resizable(False, False)
    root.configure(bg="#f7f9fc")

    heading = tk.Label(
        root, text="SMX - Gestione elaborati", font=("Arial", 16, "bold"),
        bg="#f7f9fc", fg="#223456"
    )
    heading.pack(pady=(22, 8))

    current = current_version(base)
    description = "Versione installata: " + current
    if not current:
        description = "SMX non ancora installato."

    version_label = tk.Label(root, text=description, bg="#f7f9fc")
    version_label.pack(pady=4)

    status = tk.Label(root, text="Controllo aggiornamenti in corso...", bg="#f7f9fc")
    status.pack(pady=8)

    controls = tk.Frame(root, bg="#f7f9fc")
    controls.pack(pady=12)
    launch_button = tk.Button(controls, text="Avvia SMX", width=17)
    launch_button.pack(side="left", padx=7)
    update_button = tk.Button(
        controls, text="Aggiorna / Installa", width=20, state="disabled"
    )
    update_button.pack(side="left", padx=7)
    rollback_button = tk.Button(
        controls, text="Versione precedente", width=19, state="disabled"
    )
    rollback_button.pack(side="left", padx=7)

    def refresh_restore_control():
        if previous_version(base):
            rollback_button.configure(state="normal")
        else:
            rollback_button.configure(state="disabled")

    def on_restore():
        if state["busy"]:
            return
        candidate = previous_version(base)
        if not candidate:
            return
        if not messagebox.askyesno(
            "Ripristina SMX",
            "Ripristinare la versione {}? I dati delle verifiche resteranno invariati.".format(
                candidate
            ),
        ):
            return
        try:
            restored = restore_previous(base)
            version_label.configure(text="Versione installata: " + restored)
            status.configure(text="Ripristinata la versione " + restored)
            refresh_restore_control()
        except (OSError, ValueError, RuntimeError) as error:
            messagebox.showerror("Ripristino SMX", str(error))

    def on_launch():
        executable = local_executable(base)
        if executable is None:
            messagebox.showwarning(
                "SMX", "Nessuna versione locale disponibile: effettuare l'installazione."
            )
            return
        try:
            launch_application(executable)
            root.destroy()
        except OSError as error:
            messagebox.showerror("Avvio SMX", str(error))

    def install_worker(release):
        try:
            executable = install_release(base, release)
            events.put(("installed", str(executable)))
        except Exception as error:
            events.put(("install_error", str(error)))

    def on_update():
        if state["busy"] or state["release"] is None:
            return
        release = state["release"]
        confirmation = messagebox.askyesno(
            "Aggiornamento SMX",
            "Installare la versione {}?\nI dati delle verifiche non saranno modificati.".format(
                release["version"]
            ),
        )
        if not confirmation:
            return
        state["busy"] = True
        update_button.configure(state="disabled")
        status.configure(text="Download e verifica dell'aggiornamento in corso...")
        threading.Thread(target=install_worker, args=(release,), daemon=True).start()

    def check_worker():
        try:
            release = latest_release()
            events.put(("checked", release))
        except Exception as error:
            events.put(("check_error", str(error)))

    def poll_events():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind == "checked":
                    state["release"] = value
                    local = current_version(base)
                    newer = True
                    if local:
                        try:
                            newer = version_sort_key(value["version"]) > version_sort_key(local)
                        except ValueError:
                            newer = value["version"] != local
                    if newer:
                        status.configure(text="Disponibile la versione " + value["version"])
                        update_button.configure(state="normal")
                    else:
                        status.configure(text="SMX è aggiornato.")
                elif kind == "check_error":
                    status.configure(text="Controllo online non disponibile. Avvio offline possibile.")
                elif kind == "installed":
                    state["busy"] = False
                    new_version = current_version(base)
                    version_label.configure(text="Versione installata: " + new_version)
                    status.configure(text="Aggiornamento completato. SMX pronto all'avvio.")
                    launch_button.configure(state="normal")
                    update_button.configure(state="disabled")
                    refresh_restore_control()
                elif kind == "install_error":
                    state["busy"] = False
                    status.configure(text="Aggiornamento non riuscito; versione precedente conservata.")
                    update_button.configure(state="normal")
                    messagebox.showerror("Aggiornamento SMX", value)
        except queue.Empty:
            pass

        root.after(150, poll_events)

    launch_button.configure(command=on_launch)
    update_button.configure(command=on_update)
    rollback_button.configure(command=on_restore)
    refresh_restore_control()
    if local_executable(base) is None:
        launch_button.configure(state="disabled")
    root.after(150, poll_events)
    threading.Thread(target=check_worker, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
