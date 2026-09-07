import os
import re
import shutil
import sys
from tkinter import filedialog, messagebox
from datetime import datetime, timezone

# Limiti delle cartelle test gestite dall'applicazione
TEST_MIN = 1
TEST_MAX = 30
LOCAL_TEST_FOLDER_RE = re.compile(r"^(?:.+__)?test(?:0[1-9]|[12][0-9]|30)$", re.IGNORECASE)


def _iter_test_folders(base_directory):
    """
    Generatore di coppie (nome_cartella, percorso_assoluto) per test01..test30.
    Serve per essere sicuri di intervenire SOLO su queste cartelle.
    """
    for i in range(TEST_MIN, TEST_MAX + 1):
        folder_name = f"test{str(i).zfill(2)}"
        folder_path = os.path.join(base_directory, folder_name)
        yield folder_name, folder_path


def is_local_student_folder(folder_name):
    """Accetta solo testXX locali, con eventuale prefisso alunno__testXX."""
    return bool(LOCAL_TEST_FOLDER_RE.fullmatch(str(folder_name).strip()))


def _sanitize_verifica_name(nome: str) -> str:
    """
    Ripulisce il nome verifica per usarlo in un nome di cartella:
    - trim spazi
    - sostituisce spazi con underscore
    - tiene solo caratteri alfanumerici, underscore e trattino.
    """
    if not nome:
        return ""
    nome = nome.strip().replace(" ", "_")
    allowed = []
    for ch in nome:
        if ch.isalnum() or ch in ("_", "-"):
            allowed.append(ch)
    return "".join(allowed)


def scan_test_folders(remote_directory, report_text):
    """
    Scansiona le cartelle test01..test30 nella directory remota indicata e
    scrive nel report:
      - quali cartelle sono presenti/mancanti
      - per quelle presenti, elenca i file con la data di creazione.
    """
    report_text.delete("1.0", "end")

    if not os.path.exists(remote_directory):
        messagebox.showerror("Errore", "La directory specificata non esiste.")
        return

    report_text.insert(
        "end",
        f"Scansione Preparazione avviata alle {datetime.now():%H:%M:%S}.\n"
        f"Directory remota: {remote_directory}\n"
        "Modalità: sola lettura, esclusivamente test01..test30.\n"
        "Elenco file: tutti i file presenti, senza filtro di estensione.\n\n",
    )

    present_folders = 0
    found_files = 0
    for folder_name, folder_path in _iter_test_folders(remote_directory):
        if os.path.isdir(folder_path):
            present_folders += 1
            report_text.insert("end", f"[OK] {folder_name}\n")
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    found_files += 1
                    file_path = os.path.join(root, file)
                    creation_time = datetime.fromtimestamp(
                        os.path.getctime(file_path), tz=timezone.utc
                    )
                    report_text.insert(
                        "end",
                        f"  - {file} (Creato il: {creation_time})\n",
                    )
        else:
            report_text.insert("end", f"[MANCANTE] {folder_name}\n")

    report_text.insert(
        "end",
        f"\nScansione completata: {present_folders} cartelle test presenti, "
        f"{found_files} file elencati.\n",
    )
    report_text.see("end")


def _copy_test_folders(remote_directory, target_root, report_text=None):
    """
    Copia tutte le cartelle test01..test30 esistenti da remote_directory
    dentro target_root (mantenendo i nomi delle cartelle).

    Restituisce la lista delle cartelle effettivamente copiate.
    """
    copied = []

    for folder_name, src in _iter_test_folders(remote_directory):
        if os.path.exists(src):
            dest = os.path.join(target_root, folder_name)
            try:
                shutil.copytree(src, dest, dirs_exist_ok=True)
                copied.append(folder_name)
            except Exception as e:
                if report_text is not None:
                    report_text.insert(
                        "end",
                        f"Errore durante la copia di {src} -> {dest}: {e}\n",
                    )

    return copied


def create_local_copy(
    remote_directory,
    report_text,
    lbl_directory,
    update_directory_listing_func,
    update_subdirectories_list_func,
    nome_verifica=None,
):
    """
    Crea una copia locale delle cartelle test01..test30 presenti in remote_directory.

    - La copia viene creata sul Desktop in una nuova cartella con nome:
          YYYYMMDD_HH-MM
      oppure, se nome_verifica è valorizzato:
          YYYYMMDD_HH-MM_<nomeVerificaPulito>

    - Vengono copiate SOLO le cartelle test01..test30.
    - Aggiorna:
        * il report,
        * la label lbl_directory,
        * la tabella/tree tramite le funzioni di update passate.

    Ritorna il percorso della nuova directory creata.
    """
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    timestamp = datetime.now().strftime("%Y%m%d_%H-%M")

    safe_name = _sanitize_verifica_name(nome_verifica or "")
    if safe_name:
        folder_name = f"{timestamp}_{safe_name}"
    else:
        folder_name = timestamp

    new_directory = os.path.join(desktop, folder_name)
    os.makedirs(new_directory, exist_ok=True)

    # Log in stile simile a Correzione/Live
    report_text.delete("1.0", "end")
    report_text.insert(
        "end",
        "Creazione copia locale delle cartelle test.\n"
        f"Directory remota di origine:\n  {remote_directory}\n"
        f"Directory locale di destinazione:\n  {new_directory}\n\n",
    )

    copied = _copy_test_folders(remote_directory, new_directory, report_text)

    if not copied:
        report_text.insert(
            "end",
            "ATTENZIONE: nessuna cartella test01–test30 trovata nella directory remota.\n",
        )
    else:
        report_text.insert(
            "end",
            f"Cartelle test copiate ({len(copied)}):\n  " + ", ".join(copied) + "\n",
        )

    report_text.see("end")

    # Aggiorna la label di quella scheda (vecchio comportamento)
    lbl_directory.config(text=f"Directory selezionata: {new_directory}")

    # Aggiorna eventuali viste (lista file / treeview)
    if update_directory_listing_func is not None:
        update_directory_listing_func(new_directory)

    if update_subdirectories_list_func is not None:
        update_subdirectories_list_func(new_directory)

    return new_directory


def clear_test_folders(selected_directory, report_text):
    """
    Cancella ricorsivamente TUTTI i file e le sottocartelle contenuti in
    test01..test30 sotto selected_directory (ma NON tocca altre cartelle).

    Mostra una tripla conferma "paranoica" prima di procedere.
    """
    confirm = messagebox.askyesno(
        "Conferma",
        "Sei sicuro di voler cancellare i dati nelle sole cartelle test01–test30?\n"
        "Le altre cartelle della Dir Remota non verranno toccate.",
    )
    if not confirm:
        return

    confirm_final = messagebox.askyesno(
        "Conferma finale",
        "Questa azione è irreversibile. Continuare?",
    )
    if not confirm_final:
        return

    confirm_final_final = messagebox.askyesno(
        "Conferma finalissima",
        "Siamo proprio sicuri sicuri??? Continuare?",
    )
    if not confirm_final_final:
        return

    for folder_name, folder_path in _iter_test_folders(selected_directory):
        if os.path.exists(folder_path):
            for root, dirs, files in os.walk(folder_path, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        report_text.insert(
                            "end",
                            f"Errore durante la cancellazione di {file_path}: {e}\n",
                        )
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    try:
                        shutil.rmtree(dir_path)
                    except Exception as e:
                        report_text.insert(
                            "end",
                            f"Errore durante la cancellazione di {dir_path}: {e}\n",
                        )

    report_text.insert("end", "Le cartelle remote test01–test30 sono state pulite.\n")
    report_text.see("end")


def choose_directory(lbl_directory, update_directory_listing_func, update_subdirectories_list_func):
    """
    Dialogo standard "Scegli directory" usato nelle vecchie schede:
    - aggiorna la label passata,
    - chiama le funzioni di update per ricaricare lista file e tree.
    """
    selected_directory = filedialog.askdirectory()
    if selected_directory:
        lbl_directory.config(text=f"Directory selezionata: {selected_directory}")
        update_directory_listing_func(selected_directory)
        update_subdirectories_list_func(selected_directory)


def open_selected_directory(selected_directory):
    """
    Apre nel file browser la directory selezionata.

    Può ricevere:
      - una stringa con il path,
      - una Label tkinter (da cui legge .cget("text")),
      - una StringVar (da cui legge .get()).

    Se il path non è valido, mostra un warning.
    """
    # Normalizza il parametro in una stringa di path
    path = None

    # Caso: Label (o widget simile)
    if hasattr(selected_directory, "cget"):
        try:
            text = selected_directory.cget("text")
            # Gestisce anche il vecchio prefisso "Directory selezionata: ..."
            path = text.replace("Directory selezionata:", "").strip()
        except Exception:
            path = None

    # Caso: StringVar o oggetto con .get()
    if path is None and hasattr(selected_directory, "get"):
        try:
            path = selected_directory.get()
        except Exception:
            path = None

    # Caso generico: già una stringa (o altro oggetto)
    if path is None:
        path = str(selected_directory)

    if not path or not os.path.exists(path):
        messagebox.showwarning("Attenzione", "Nessuna directory valida selezionata.")
        return

    try:
        if os.name == "nt":
            os.startfile(path)
        elif os.name == "posix":
            if sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
    except Exception as e:
        messagebox.showerror(
            "Errore",
            f"Non è stato possibile aprire la directory:\n{str(e)}",
        )
