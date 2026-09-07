import os
import shutil

import tkinter as tk
from tkinter import filedialog, messagebox, Scrollbar
from tkinter import ttk

import data_handler
import utils

YELLOW_BG = "#fff5cc"


def create_frame_preparazione(root, global_config):
    """
    Frame modalità PREPARAZIONE.

    - Usa la directory remota indicata nell'intestazione principale (test01..test30)
    - Scansiona cartelle test e mostra riepilogo in tabella (sopra)
    - Crea copia locale sul Desktop (timestamp + nome verifica)
    - Distribuisce un file in tutte le cartelle test
    - Cancella il contenuto delle cartelle test remote (pulsante rosso)
    """
    frame = tk.Frame(root, bg=YELLOW_BG)

    # ======================================================================
    #  TABELLA RIEPILOGO CARTELLE TEST REMOTE (creata qui, usata più sotto)
    # ======================================================================
    tree_stats = ttk.Treeview(
        frame,
        columns=(
            "subdirectory",
            "num_folders",
            "num_files",
            "num_extension_files",
            "extension_files",
        ),
        show="headings",
    )
    tree_stats.heading("subdirectory", text="Subdirectory")
    tree_stats.heading("num_folders", text="Cartelle")
    tree_stats.heading("num_files", text="File")
    tree_stats.heading("num_extension_files", text="File con estensione")
    tree_stats.heading("extension_files", text="Tutti i file presenti")

    tree_stats.column("subdirectory", width=120, anchor="w")
    tree_stats.column("num_folders", width=80, anchor="center")
    tree_stats.column("num_files", width=80, anchor="center")
    tree_stats.column("num_extension_files", width=140, anchor="center")
    tree_stats.column("extension_files", width=560, anchor="w")

    def update_remote_stats_table():
        """
        Aggiorna la tabella con le informazioni sulle cartelle test01..test30
        presenti nella directory remota. La colonna finale elenca sempre tutti i file,
        senza applicare il filtro delle estensioni della verifica.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        entry_extension = global_config["file_extension"]  # StringVar

        tree_stats.delete(*tree_stats.get_children())

        if not remote_dir or not os.path.isdir(remote_dir):
            return

        for folder_name, folder_path in data_handler._iter_test_folders(remote_dir):
            if not os.path.isdir(folder_path):
                continue

            num_folders, num_files, num_ext, ext_files = utils.count_directory_content(
                folder_path, entry_extension
            )
            all_file_names = sorted(
                file_name
                for _root, _dirs, files in os.walk(folder_path)
                for file_name in files
            )

            tree_stats.insert(
                "",
                "end",
                values=(
                    folder_name,
                    num_folders,
                    num_files,
                    num_ext,
                    ", ".join(all_file_names),
                ),
            )

    # ======================================================================
    #  RIGA 1: PULSANTI OPERATIVI
    # ======================================================================
    def do_scan_tests():
        """
        Scansiona le cartelle test01..test30 sulla directory remota,
        scrive il risultato nel log e aggiorna la tabella riepilogo.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota (contente le cartelle testXX).",
            )
            return
        data_handler.scan_test_folders(remote_dir, report_text)
        update_remote_stats_table()
        report_text.insert(
            "end",
            "\nScansione Preparazione completata: la tabella contiene tutti i file trovati, "
            "mentre il conteggio dedicato usa le estensioni della verifica.\n",
        )
        report_text.see("end")

    btn_scan = tk.Button(
        frame,
        text="Scansiona cartelle test",
        command=do_scan_tests,
        bg="white",
    )
    btn_scan.grid(row=1, column=0, padx=8, pady=4, sticky="ew")

    # Label per mostrare l'ultima directory locale creata
    lbl_local_dir = tk.Label(
        frame,
        text="Ultima directory locale creata: (nessuna)",
        anchor="w",
        bg=YELLOW_BG,
    )
    lbl_local_dir.grid(row=2, column=0, columnspan=5, sticky="ew", padx=8, pady=4)

    def do_create_local_copy():
        """
        Crea una copia locale di test01..test30 sul Desktop in una cartella
        timestampata + nome verifica, aggiorna il log e imposta selected_directory.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        nome_verifica = global_config["verifica_name"].get().strip()

        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota (contente le cartelle testXX).",
            )
            return

        destination = filedialog.askdirectory(title="Scegli dove creare la Dir Locale della verifica")
        if not destination:
            return
        try:
            from project_manager import VerificationProject
            project = VerificationProject.create_in(
                destination, nome_verifica or "Verifica", remote_directory=remote_dir,
                extensions=global_config["file_extension"].get(),
                alert_threshold=global_config["alert_threshold"].get(),
            )
            project.copy_from_remote()
            new_dir = str(project.root)
        except Exception as exc:
            messagebox.showerror("Copia locale", str(exc))
            return

        if new_dir:
            global_config["local_directory"].set(new_dir)
            lbl_local_dir.config(
                text=f"Ultima directory locale creata: {new_dir}"
            )
            report_text.insert(
                "end",
                "Directory locale impostata per la correzione/export.\n",
            )
            report_text.see("end")

    btn_create_copy = tk.Button(
        frame,
        text="Crea copia locale (Desktop)",
        command=do_create_local_copy,
        bg="white",
    )
    btn_create_copy.grid(row=1, column=1, padx=8, pady=4, sticky="ew")

    def do_distribute_file():
        """
        Chiede un file e lo copia in tutte le cartelle test01..test30
        presenti nella directory remota.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota (contente le cartelle testXX).",
            )
            return

        file_path = filedialog.askopenfilename(
            title="Seleziona il file da distribuire nelle cartelle test"
        )
        if not file_path:
            return

        file_name = os.path.basename(file_path)
        copied_count = 0

        report_text.insert(
            "end",
            f"Distribuzione del file '{file_name}' nelle cartelle test...\n",
        )

        for folder_name, folder_path in data_handler._iter_test_folders(remote_dir):
            if os.path.isdir(folder_path):
                dest_path = os.path.join(folder_path, file_name)
                try:
                    shutil.copy2(file_path, dest_path)
                    copied_count += 1
                except Exception as e:
                    report_text.insert(
                        "end",
                        f"Errore nel copiare {file_name} in {folder_name}: {e}\n",
                    )

        if copied_count == 0:
            msg = (
                "Nessuna cartella test01–test30 trovata nella directory remota.\n"
                "File NON distribuito."
            )
        else:
            msg = f"File '{file_name}' distribuito in {copied_count} cartelle test.\n"

        report_text.insert("end", msg + "\n")
        report_text.see("end")

    btn_distribute = tk.Button(
        frame,
        text="Distribuisci file",
        command=do_distribute_file,
        bg="white",
    )
    btn_distribute.grid(row=1, column=2, padx=8, pady=4, sticky="ew")

    def do_clear_remote():
        remote_dir = global_config["remote_directory"].get().strip()
        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota (contente le cartelle testXX).",
            )
            return

        data_handler.clear_test_folders(remote_dir, report_text)

    btn_clear_remote = tk.Button(
        frame,
        text="Pulisci cartelle test remote",
        command=do_clear_remote,
        bg="#fca5a5",
    )
    btn_clear_remote.grid(row=1, column=3, padx=8, pady=4, sticky="ew")

    def open_remote_dir():
        remote_dir = global_config["remote_directory"].get().strip()
        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota.",
            )
            return
        data_handler.open_selected_directory(remote_dir)

    btn_open_remote = tk.Button(
        frame,
        text="Apri directory remota",
        command=open_remote_dir,
        bg="white",
    )
    btn_open_remote.grid(row=1, column=4, padx=8, pady=4, sticky="ew")

    # ======================================================================
    #  TABELLA RIEPILOGO (ORA SOPRA AL LOG)
    # ======================================================================
    lbl_table = tk.Label(
        frame,
        text="Riepilogo cartelle test (directory remota + estensioni selezionate):",
        bg=YELLOW_BG,
    )
    lbl_table.grid(row=3, column=0, sticky="nw", padx=8, pady=4)

    tree_stats.grid(row=4, column=0, columnspan=5, sticky="nsew", padx=8, pady=4)

    # ======================================================================
    #  LOG / REPORT (ORA SOTTO LA TABELLA)
    # ======================================================================
    lbl_report = tk.Label(frame, text="Log / Report:", bg=YELLOW_BG)
    lbl_report.grid(row=5, column=0, sticky="nw", padx=8, pady=4)

    report_text = tk.Text(
        frame,
        width=100,
        height=10,
        bg="#fffbe6",
    )
    report_text.grid(
        row=6,
        column=0,
        columnspan=5,
        sticky="nsew",
        padx=8,
        pady=4,
    )

    scrollbar = Scrollbar(frame, orient="vertical", command=report_text.yview)
    scrollbar.grid(row=6, column=5, sticky="ns", pady=4)
    report_text.config(yscrollcommand=scrollbar.set)
    utils.enable_mousewheel(report_text)

    # ======================================================================
    #  LAYOUT
    # ======================================================================
    frame.rowconfigure(4, weight=1)  # tabella
    frame.rowconfigure(6, weight=1)  # log
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(2, weight=1)
    frame.columnconfigure(3, weight=1)

    # Messaggio iniziale nel log (ora sotto)
    report_text.insert(
        "end",
        "Modalità Preparazione pronta.\n"
        "- La Dir Remota viene letta esclusivamente nelle cartelle test01..test30.\n"
        "- La scansione elenca tutti i file; il filtro delle estensioni influenza solo il relativo conteggio.\n"
        "- Crea una copia locale prima di pulire le cartelle remote.\n"
        "- Distribuzione e pulizia sono operazioni esplicite sulle sole cartelle test.\n",
    )
    report_text.see("end")

    # Stato iniziale
    if global_config["selected_directory"].get().strip():
        lbl_local_dir.config(
            text=f"Ultima directory locale creata: {global_config['selected_directory'].get().strip()}"
        )

    global_config["refresh_preparazione"] = do_scan_tests

    return frame
