import os
from datetime import datetime

import data_handler  # per riutilizzare la logica su test01..test30


# =============================================================================
#  PARSING ESTENSIONI
# =============================================================================

def parse_extensions(ext_string: str):
    """
    Converte una stringa di estensioni in una lista normalizzata.

    Esempi accettati:
      - ".cpp"
      - "cpp"
      - ".php, .html, .css"
      - "php html css"
      - "php,html css"

    Restituisce una lista di estensioni in minuscolo, con il punto iniziale:
      [".php", ".html", ".css"]
    """
    if not ext_string:
        return []

    work = ext_string.replace(";", ",")  # giusto in caso…

    tokens = []
    for chunk in work.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        for part in chunk.split():
            part = part.strip()
            if not part:
                continue
            if not part.startswith("."):
                part = "." + part
            tokens.append(part.lower())

    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def enable_mousewheel(widget):
    """Rende affidabile lo scorrimento con rotella per Text e ScrolledText."""
    def on_enter(_event):
        widget.focus_set()

    def on_wheel(event):
        step = -1 if event.delta > 0 else 1
        widget.yview_scroll(step, "units")
        return "break"

    widget.bind("<Enter>", on_enter, add="+")
    widget.bind("<MouseWheel>", on_wheel, add="+")


# =============================================================================
#  UTILITÀ PER LA SCHEDA "CORREZIONE"
# =============================================================================

def update_directory_listing(directory, entry_extension, report_text):
    """
    Popola la text-area di report con l'elenco dei file trovati nella directory
    (ricerca ricorsiva), filtrando per UNA O PIÙ estensioni.
    """
    report_text.delete("1.0", "end")

    if not directory or not os.path.isdir(directory):
        report_text.insert("end", "Directory non valida o inesistente.\n")
        return

    ext_string = entry_extension.get().strip() if hasattr(entry_extension, "get") else str(entry_extension).strip()
    exts = parse_extensions(ext_string)

    report_text.insert("end", f"Scansione di:\n  {directory}\n")
    if exts:
        report_text.insert("end", f"Filtri estensioni: {', '.join(exts)}\n\n")
    else:
        report_text.insert("end", "Nessun filtro di estensione applicato.\n\n")

    for root, _dirs, files in os.walk(directory):
        for file in files:
            if not exts:
                match = True
            else:
                fname = file.lower()
                match = any(fname.endswith(e) for e in exts)
            if match:
                file_path = os.path.join(root, file)
                report_text.insert("end", f"{file_path}\n")

    report_text.see("end")


def count_directory_content(directory, entry_extension):
    """
    Conta:
      - quante sottocartelle
      - quanti file totali
      - quanti file con le estensioni selezionate
      - l'elenco dei file con quelle estensioni

    Restituisce: (num_folders, num_files, num_extension_files, extension_files)
    """
    num_folders = 0
    num_files = 0
    num_extension_files = 0
    extension_files = []

    ext_string = entry_extension.get().strip() if hasattr(entry_extension, "get") else str(entry_extension).strip()
    exts = parse_extensions(ext_string)

    for _root, dirs, files in os.walk(directory):
        num_folders += len(dirs)
        num_files += len(files)

        if exts:
            current_extension_files = [
                f for f in files if any(f.lower().endswith(e) for e in exts)
            ]
        else:
            current_extension_files = list(files)

        num_extension_files += len(current_extension_files)
        extension_files += current_extension_files

    return num_folders, num_files, num_extension_files, extension_files


def check_directory_content(base_directory, subdir, tree, entry_extension):
    """
    Calcola le statistiche sulla sottocartella `subdir` e inserisce una riga
    nella Treeview (Correzione / Preparazione).
    """
    full_path = os.path.join(base_directory, subdir)
    num_folders, num_files, num_extension_files, extension_files = count_directory_content(
        full_path, entry_extension
    )

    # NOTA: ci aspettiamo che l'albero abbia anche una colonna "mix_file":
    # per le schede che non la usano mettiamo stringa vuota.
    tree.insert(
        "",
        "end",
        values=(
            subdir,
            num_folders,
            num_files,
            num_extension_files,
            ", ".join(extension_files),
            "",
        ),
    )


def update_subdirectories_list(selected_directory, tree, entry_extension):
    """
    Elenca le sottodirectory immediate di `selected_directory`, le ordina
    alfabeticamente e per ciascuna calcola le statistiche inserendole
    nella Treeview.
    """
    if not selected_directory or not os.path.isdir(selected_directory):
        tree.delete(*tree.get_children())
        return

    subdirectories = [
        d for d in os.listdir(selected_directory)
        if os.path.isdir(os.path.join(selected_directory, d))
        and data_handler.is_local_student_folder(d)
    ]
    subdirectories.sort()

    tree.delete(*tree.get_children())
    for subdir in subdirectories:
        check_directory_content(selected_directory, subdir, tree, entry_extension)


# =============================================================================
#  UTILITÀ PER LA SCHEDA "LIVE"
# =============================================================================

def _format_age(last_mod_timestamp: float | None) -> str:
    """
    Converte un timestamp di ultima modifica in una stringa del tipo:
      - "2g 3h"
      - "3h 15m"
      - "12m"
      - "<1m"
    """
    if last_mod_timestamp is None:
        return "-"

    dt = datetime.fromtimestamp(last_mod_timestamp)
    now = datetime.now()
    delta = now - dt

    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}g {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m"
    return "<1m"


def scan_remote_directory(remote_directory, extension, count_lines=False):
    """
    Scansiona in modo sequenziale (mai in parallelo) tutte le sottocartelle di
    ogni test01..test30, così da non sovraccaricare il file server.
    Per ciascun file trovato l'elenco conserva il percorso relativo interno,
    così file con lo stesso nome in cartelle diverse restano distinguibili.

      (nome_cartella,
       num_file_con_estensione,
       num_righe_totali,
       elenco_file,
       ultima_modifica_str,
       eta_str)

    - extension può contenere UNA o PIÙ estensioni (come in parse_extensions)
    """
    results = []

    if not remote_directory or not os.path.isdir(remote_directory):
        return results

    exts = parse_extensions(extension.strip())

    for folder_name, folder_path in data_handler._iter_test_folders(remote_directory):
        if not os.path.isdir(folder_path):
            continue

        files_found = []
        total_lines = 0
        last_mod = None

        for root, _dirs, files in os.walk(folder_path, onerror=lambda _error: None):
            for f in files:
                if not exts:
                    match = True
                else:
                    match = any(f.lower().endswith(e) for e in exts)
                if not match:
                    continue

                file_path = os.path.join(root, f)
                relative_path = os.path.relpath(file_path, folder_path)
                files_found.append(relative_path)

                # aggiorna last_mod
                try:
                    mtime = os.path.getmtime(file_path)
                except OSError:
                    continue
                if last_mod is None or mtime > last_mod:
                    last_mod = mtime

                # conteggio righe opzionale
                if count_lines:
                    try:
                        try:
                            with open(file_path, "r", encoding="utf-8") as fh:
                                total_lines += sum(1 for _line in fh)
                        except UnicodeDecodeError:
                            with open(file_path, "r", encoding="latin-1", errors="replace") as fh:
                                total_lines += sum(1 for _line in fh)
                    except Exception:
                        pass

        num_file = len(files_found)
        files_found.sort()

        if last_mod is not None:
            last_mod_str = datetime.fromtimestamp(last_mod).strftime("%Y-%m-%d %H:%M:%S")
        else:
            last_mod_str = "-"

        age_str = _format_age(last_mod)

        num_lines_value = total_lines if count_lines else None

        results.append(
            (folder_name, num_file, num_lines_value, files_found, last_mod_str, age_str)
        )

    results.sort(key=lambda x: x[0])
    return results


def copy_test_directories(remote_directory, destination_root, nome_verifica):
    """
    Copia SOLO le cartelle test01..test30 esistenti da `remote_directory`
    dentro una nuova cartella creata sotto `destination_root`.
    """
    nome_verifica = (nome_verifica or "").strip()
    if not nome_verifica:
        return "⚠️ Nome verifica mancante."

    if not remote_directory or not os.path.isdir(remote_directory):
        return "⚠️ Directory remota non valida."

    if not destination_root or not os.path.isdir(destination_root):
        return "⚠️ Directory di destinazione non valida."

    from datetime import datetime as _dt

    timestamp = _dt.now().strftime("%Y%m%d_%H-%M")
    dest_base = os.path.join(destination_root, f"{timestamp}_{nome_verifica}")
    os.makedirs(dest_base, exist_ok=True)

    copied = data_handler._copy_test_folders(remote_directory, dest_base, report_text=None)

    if not copied:
        return f"⚠️ Nessuna cartella test01–test30 trovata in {remote_directory}."

    return f"✅ Copiate {len(copied)} cartelle di test in {dest_base}."


# =============================================================================
#  WRAPPER DI COMPATIBILITÀ
# =============================================================================

def choose_directory(lbl_directory, update_directory_listing_func, update_subdirectories_list_func):
    data_handler.choose_directory(lbl_directory, update_directory_listing_func, update_subdirectories_list_func)


def open_selected_directory(selected_directory):
    data_handler.open_selected_directory(selected_directory)
