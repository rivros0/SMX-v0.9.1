"""
Build Windows/Linux di SMX e launcher. Eseguire nativamente su ciascuna piattaforma.
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import zipfile

from smx_version import APP_VERSION

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
PACKAGES = ROOT / "release-assets"


def run_pyinstaller(arguments):
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"]
    command.extend(arguments)
    subprocess.run(command, cwd=ROOT, check=True)


def compile_application():
    """Pacchetto onedir: dati e moduli sempre inclusi senza dipendere da Python."""
    options = [
        "--windowed", "--onedir", "--name", "SMX",
        "--add-data", "icone/app.png" + os.pathsep + "icone",
        "--hidden-import", "frame_correzione",
        "--hidden-import", "frame_export",
        "--hidden-import", "frame_domini",
        "--hidden-import", "frame_monitor_domini",
        "--hidden-import", "similarity",
        "--hidden-import", "similarity_graph",
    ]
    if sys.platform == "win32":
        options.extend(["--icon", "icone/app.ico"])
        options.extend(["--add-data", "icone/app.ico" + os.pathsep + "icone"])
    options.append("SMX.py")
    run_pyinstaller(options)


def compile_launcher():
    """File unico da distribuire come punto d'ingresso SMX."""
    options = ["--windowed", "--onefile", "--name", "SMX-Launcher"]
    if sys.platform == "win32":
        options.extend(["--icon", "icone/app.ico"])
    options.append("smx_launcher.py")
    run_pyinstaller(options)


def archive_windows():
    path = PACKAGES / "SMX-windows-x64.zip"
    source = DIST / "SMX"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for item in sorted(source.rglob("*")):
            if item.is_file():
                target.write(item, item.relative_to(DIST))
    shutil.copyfile(DIST / "SMX-Launcher.exe", PACKAGES / "SMX-Launcher.exe")


def archive_linux():
    path = PACKAGES / "SMX-linux-x64.tar.gz"
    source = DIST / "SMX"
    with tarfile.open(path, "w:gz") as target:
        target.add(source, arcname="SMX", recursive=True)
    launcher = PACKAGES / "SMX-Launcher"
    shutil.copyfile(DIST / "SMX-Launcher", launcher)
    launcher.chmod(0o755)


def write_checksums():
    """Pubblica checksum per tutti i pacchetti; launcher ne verifica uno prima dell'uso."""
    lines = []
    for file_path in sorted(PACKAGES.iterdir()):
        if not file_path.is_file() or file_path.name == "SHA256SUMS.txt":
            continue
        digest = hashlib.sha256()
        with open(file_path, "rb") as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        lines.append("{}  {}".format(digest.hexdigest(), file_path.name))
    (PACKAGES / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main():
    print("SMX build:", APP_VERSION, "system:", sys.platform)
    PACKAGES.mkdir(parents=True, exist_ok=True)
    compile_application()
    compile_launcher()
    if sys.platform == "win32":
        archive_windows()
    elif sys.platform == "linux":
        archive_linux()
    else:
        raise RuntimeError("Sistema non supportato: " + sys.platform)
    write_checksums()


if __name__ == "__main__":
    main()
