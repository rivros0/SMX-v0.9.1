import os
import shutil
import datetime as dt

import tkinter as tk
from tkinter import filedialog, messagebox, Scrollbar
from tkinter import ttk

import data_handler
import utils

YELLOW_BG = "#fff5cc"
PREPARATION_SCAN_INTERVAL = 30_000


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
    scan_job_id = None

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
            "file_mtimes",
        ),
        show="headings",
    )
    tree_stats.heading("subdirectory", text="Subdirectory")
    tree_stats.heading("num_folders", text="Cartelle")
    tree_stats.heading("num_files", text="File")
    tree_stats.heading("num_extension_files", text="File con estensione")
    tree_stats.heading("extension_files", text="Tutti i file presenti")
    tree_stats.heading("file_mtimes", text="Ultima modifica dei file")

    tree_stats.column("subdirectory", width=120, anchor="w")
    tree_stats.column("num_folders", width=80, anchor="center")
    tree_stats.column("num_files", width=80, anchor="center")
    tree_stats.column("num_extension_files", width=140, anchor="center")
    tree_stats.column("extension_files", width=400, anchor="w")
    tree_stats.column("file_mtimes", width=650, anchor="w")

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
            # Elenco completo dei file, compresi quelli nelle sottocartelle.
            # Conserviamo i percorsi relativi per distinguere nomi duplicati.
            file_details = []
            for current_root, _dirs, files in os.walk(folder_path):
                for file_name in files:
                    full_path = os.path.join(current_root, file_name)
                    relative_path = os.path.relpath(full_path, folder_path)
                    try:
                        modified_at = dt.datetime.fromtimestamp(
                            os.path.getmtime(full_path)
                        ).strftime("%d/%m/%Y %H:%M:%S")
                    except OSError:
                        modified_at = "non disponibile"
                    file_details.append((relative_path, modified_at))

            file_details.sort(key=lambda detail: detail[0].lower())
            all_file_names = [detail[0] for detail in file_details]
            all_file_mtimes = [
                "{}: {}".format(detail[0], detail[1])
                for detail in file_details
            ]

            tree_stats.insert(
                "",
                "end",
                values=(
                    folder_name,
                    num_folders,
                    num_files,
                    num_ext,
                    ", ".join(all_file_names),
                    "  |  ".join(all_file_mtimes),
                ),
            )

    # ======================================================================
    #  RIGA 1: PULSANTI OPERATIVI
    # ======================================================================
    def schedule_next_scan():
        """Programma il prossimo controllo senza accumulare timer duplicati."""
        nonlocal scan_job_id
        if scan_job_id is not None:
            try:
                frame.after_cancel(scan_job_id)
            except tk.TclError:
                pass
        scan_job_id = frame.after(PREPARATION_SCAN_INTERVAL, lambda: do_scan_tests(automatic=True))

    def do_scan_tests(automatic=False):
        """
        Scansiona le cartelle test01..test30 sulla directory remota,
        scrive il risultato nel log e aggiorna la tabella riepilogo.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        if not remote_dir:
            if automatic:
                report_text.insert("end", "Aggiornamento automatico non eseguito: directory remota non impostata.\n")
                report_text.see("end")
            else:
                messagebox.showwarning(
                    "Attenzione",
                    "Imposta prima la directory remota (contente le cartelle testXX).",
                )
            schedule_next_scan()
            return
        data_handler.scan_test_folders(remote_dir, report_text)
        update_remote_stats_table()
        lbl_last_scan.config(text="Ultima scansione: " + dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        report_text.insert(
            "end",
            "\nScansione Preparazione completata: la tabella contiene tutti i file trovati, "
            "mentre il conteggio dedicato usa le estensioni della verifica.\n",
        )
        report_text.see("end")
        schedule_next_scan()

    scan_controls = tk.Frame(frame, bg=YELLOW_BG)
    scan_controls.grid(row=1, column=0, padx=8, pady=4, sticky="w")
    btn_scan = tk.Button(scan_controls, text="Aggiorna", command=do_scan_tests, bg="white", width=11)
    btn_scan.pack(side="left")
    lbl_last_scan = tk.Label(scan_controls, text="Ultima scansione: —", bg=YELLOW_BG, fg="#475569")
    lbl_last_scan.pack(side="left", padx=(8, 0))
    utils.add_tooltip(btn_scan, "Legge solo test01…test30 sul server e aggiorna il riepilogo: non modifica alcun file.")

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
        Raccoglie test01..test30 nella Dir Locale della verifica già aperta.
        Non crea un secondo progetto e non altera mai le cartelle remote.
        """
        remote_dir = global_config["remote_directory"].get().strip()
        local_dir = global_config["local_directory"].get().strip()

        if not remote_dir:
            messagebox.showwarning(
                "Attenzione",
                "Imposta prima la directory remota (contente le cartelle testXX).",
            )
            return

        if not local_dir:
            messagebox.showwarning("Copia locale", "Crea o carica prima una verifica locale.")
            return
        try:
            from project_manager import VerificationProject
            project = VerificationProject(local_dir)
            project.save(remote_directory=remote_dir, file_extensions=global_config["file_extension"].get())
            copied = project.copy_from_remote()
            project.save_session_file()
        except Exception as exc:
            messagebox.showerror("Copia locale", str(exc))
            return

        lbl_local_dir.config(text=f"Dir Locale aggiornata: {local_dir}")
        report_text.insert("end", f"Raccolte {len(copied)} cartelle test nella Dir Locale.\n")
        for refresh_key in ("refresh_correzione", "refresh_export"):
            refresh = global_config.get(refresh_key)
            if callable(refresh):
                refresh()
        report_text.see("end")

    btn_create_copy = tk.Button(
        frame,
        text="Raccogli copia locale",
        command=do_create_local_copy,
        bg="white",
    )
    btn_create_copy.grid(row=1, column=1, padx=8, pady=4, sticky="ew")
    utils.add_tooltip(btn_create_copy, "Copia tutte le cartelle test nella Dir Locale della verifica aperta, senza modificare il server.")

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
    utils.add_tooltip(btn_distribute, "Copia il file scelto nelle sole cartelle test01…test30 del server.")

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
    utils.add_tooltip(btn_clear_remote, "Elimina il contenuto delle cartelle test remote. Usare solo prima della verifica.")

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
    utils.add_tooltip(btn_open_remote, "Apre la directory remota in Esplora file per un controllo manuale.")

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

    # La tabella contiene percorsi e date di molti file: scorrimento orizzontale.
    table_scroll_x = ttk.Scrollbar(
        frame, orient="horizontal", command=tree_stats.xview
    )
    table_scroll_x.grid(row=5, column=0, columnspan=5, sticky="ew", padx=8)
    tree_stats.configure(xscrollcommand=table_scroll_x.set)

    def show_file_details(_event=None):
        """Mostra l'elenco completo dei file e delle date senza troncamenti."""
        selected = tree_stats.selection()
        if not selected:
            return
        selected_item = selected[0]
        folder_name = tree_stats.set(selected_item, "subdirectory")
        details = tree_stats.set(selected_item, "file_mtimes")
        if not details:
            details = "Nessun file presente."

        popup = tk.Toplevel(frame)
        popup.title("File e ultima modifica - " + folder_name)
        popup.geometry("950x520")
        content = tk.Text(popup, wrap="none", font=("Consolas", 10))
        content.pack(side="left", fill="both", expand=True)
        scroll_y = ttk.Scrollbar(popup, orient="vertical", command=content.yview)
        scroll_y.pack(side="right", fill="y")
        content.configure(yscrollcommand=scroll_y.set)
        for item in details.split("  |  "):
            content.insert("end", item + "\\n")
        content.configure(state="disabled")

    tree_stats.bind("<Double-1>", show_file_details)

    # ======================================================================
    #  LOG / REPORT (ORA SOTTO LA TABELLA)
    # ======================================================================
    lbl_report = tk.Label(frame, text="Log / Report:", bg=YELLOW_BG)
    lbl_report.grid(row=6, column=0, sticky="nw", padx=8, pady=4)

    report_text = tk.Text(
        frame,
        width=100,
        height=10,
        bg="#fffbe6",
    )
    report_text.grid(
        row=7,
        column=0,
        columnspan=5,
        sticky="nsew",
        padx=8,
        pady=4,
    )

    scrollbar = Scrollbar(frame, orient="vertical", command=report_text.yview)
    scrollbar.grid(row=7, column=5, sticky="ns", pady=4)
    report_text.config(yscrollcommand=scrollbar.set)
    utils.enable_mousewheel(report_text)

    # ======================================================================
    #  LAYOUT
    # ======================================================================
    frame.rowconfigure(4, weight=1)  # tabella
    frame.rowconfigure(7, weight=1)  # log
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
    # La scansione automatica mantiene il riepilogo aggiornato durante la preparazione.
    schedule_next_scan()

    def cancel_scan_timer(_event=None):
        if scan_job_id is not None:
            try:
                frame.after_cancel(scan_job_id)
            except tk.TclError:
                pass

    frame.bind("<Destroy>", cancel_scan_timer, add="+")

    return frame
