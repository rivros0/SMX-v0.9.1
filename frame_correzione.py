import tkinter as tk
from tkinter import ttk, messagebox, Scrollbar
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import utils
import business_logic
import similarity
import data_handler


YELLOW_REPORT_BG = "#fdfdfd"


def create_frame_correzione(root, global_config):
    """
    Modalità Correzione.

    Modifiche rispetto alla versione originale:
      - Rimossa la riga con "Scegli Directory" e la label locale "Directory selezionata".
      - La riga sulle estensioni è stata spostata PRIMA dell'INTRO.
      - La directory di lavoro è presa solo da global_config["selected_directory"]
        (la stessa mostrata nella barra superiore).

    Funzionalità preservate:
      - Label con esempio di estensioni multiple.
      - Tabella con colonna "Mix file (clic per copiare)".
      - Click sulla colonna mix per copiare negli appunti.
      - Analisi similarità sui *_mix.txt in 00_MixOutput.
    """

    frame_correzione = tk.Frame(root, bg="#089c52")

    include_prompt_var = tk.BooleanVar(value=True)
    include_subdir_var = tk.BooleanVar(value=True)

    # ======================================================================
    # RIGA 0: ESTENSIONI (spostata PRIMA dell'INTRO)
    # ======================================================================
    lbl_extension = tk.Label(
        frame_correzione,
        text="Estensioni dei file (es: .php,.html,.css):",
        bg="white",
    )
    lbl_extension.grid(row=0, column=0, sticky="w", padx=10, pady=5)

    entry_extension = tk.Entry(
        frame_correzione,
        textvariable=global_config["file_extension"],
        width=25,
    )
    entry_extension.grid(row=0, column=1, sticky="w", padx=10, pady=5)

    # ======================================================================
    # RIGA 1: INTRO / PROMPT
    # ======================================================================
    lbl_prompt = tk.Label(frame_correzione, text="INTRO:", bg="white")
    lbl_prompt.grid(row=1, column=0, sticky="w", padx=10, pady=5)

    entry_prompt = tk.Text(frame_correzione, width=80, height=3)
    entry_prompt.grid(row=1, column=1, columnspan=2, sticky="ew", padx=10, pady=5)

    # Registro il widget dell'INTRO nella configurazione globale
    # in modo da poterlo aggiornare quando viene caricata una configurazione.
    global_config["intro_widget"] = entry_prompt

    def sync_intro_text(_event=None):
        """Mantiene il testo Intro della GUI allineato alla sessione SMX."""
        try:
            value = entry_prompt.get("1.0", "end-1c")
        except tk.TclError:
            return ""
        intro_var = global_config.get("intro_text")
        if hasattr(intro_var, "set"):
            intro_var.set(value)
        else:
            global_config["intro_text"] = value
        return value

    def on_intro_modified(_event=None):
        if entry_prompt.edit_modified():
            sync_intro_text()
            entry_prompt.edit_modified(False)

    global_config["sync_intro_text"] = sync_intro_text

    # Se è già presente un testo di INTRO nella configurazione,
    # lo visualizzo nel widget Text.
    try:
        if "intro_text" in global_config:
            intro_value = global_config["intro_text"].get()
            if intro_value is not None:
                if intro_value != "":
                    entry_prompt.delete("1.0", "end")
                    entry_prompt.insert("1.0", intro_value)
    except Exception:
        # Non blocco la creazione della frame per un eventuale errore
        # (ad esempio se intro_text non è una StringVar).
        pass
    entry_prompt.edit_modified(False)
    entry_prompt.bind("<<Modified>>", on_intro_modified)


    # ======================================================================
    # RIGA 2: CHECKBOX + PULSANTE MIX
    # ======================================================================
    btn_mix = tk.Button(frame_correzione, text="Mixa")
    btn_mix.grid(row=2, column=0, sticky="ew", padx=10, pady=5)

    chk_include_prompt = tk.Checkbutton(
        frame_correzione,
        text="Includi Intro",
        variable=include_prompt_var,
        bg="white",
    )
    chk_include_prompt.grid(row=2, column=1, sticky="w", padx=10, pady=2)

    chk_include_subdir = tk.Checkbutton(
        frame_correzione,
        text="Includi Nome (subdir)",
        variable=include_subdir_var,
        bg="white",
    )
    chk_include_subdir.grid(row=2, column=2, sticky="w", padx=10, pady=2)

    # ======================================================================
    # RIGA 3: TREEVIEW (con colonna Mix file)
    # ======================================================================
    tree = ttk.Treeview(
        frame_correzione,
        columns=(
            "subdirectory",
            "num_folders",
            "num_files",
            "num_extension_files",
            "extension_files",
            "mix_file",
        ),
        show="headings",
    )
    tree.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=10, pady=10)

    tree.heading("subdirectory", text="Subdirectory")
    tree.heading("num_folders", text="Cartelle")
    tree.heading("num_files", text="File")
    tree.heading("num_extension_files", text="File con estensione")
    tree.heading("extension_files", text="Elenco file estensione")
    tree.heading("mix_file", text="Mix file (clic per copiare)")

    tree.column("subdirectory", width=100, anchor="w")
    tree.column("num_folders", width=80, anchor="center")
    tree.column("num_files", width=80, anchor="center")
    tree.column("num_extension_files", width=140, anchor="center")
    tree.column("extension_files", width=350, anchor="w")
    tree.column("mix_file", width=220, anchor="w")

    frame_correzione.columnconfigure(2, weight=1)
    frame_correzione.rowconfigure(3, weight=1)

    # ======================================================================
    # CLICK SULLA COLONNA MIX_FILE -> COPIA IN CLIPBOARD
    # ======================================================================
    def on_tree_click(event):
        region = tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        item_id = tree.identify_row(event.y)
        col_id = tree.identify_column(event.x)  # "#1", "#2", ...

        if not item_id:
            return

        columns = tree["columns"]
        try:
            mix_index = columns.index("mix_file")  # 0-based
        except ValueError:
            return

        # col_id è "#1" per la prima, "#2" per la seconda, ...
        if col_id != "#{}".format(mix_index + 1):
            return

        mix_path = tree.set(item_id, "mix_file")
        if not mix_path:
            messagebox.showinfo(
                "Info",
                "Per questa subdirectory non è ancora stato creato alcun mix.",
            )
            return

        if not os.path.exists(mix_path):
            messagebox.showwarning(
                "Attenzione",
                "Il file di mix non esiste più:\n" + mix_path,
            )
            return

        try:
            try:
                with open(mix_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(
                    mix_path,
                    "r",
                    encoding="latin-1",
                    errors="replace",
                ) as f:
                    content = f.read()
        except Exception as exc:
            messagebox.showerror(
                "Errore",
                "Errore nella lettura del file di mix:\n" + str(exc),
            )
            return

        root_widget = frame_correzione.winfo_toplevel()
        root_widget.clipboard_clear()
        root_widget.clipboard_append(content)

        messagebox.showinfo(
            "Copiato",
            "Contenuto di\n"
            + os.path.basename(mix_path)
            + "\n"
            + "copiato negli appunti.",
        )

    tree.bind("<Button-1>", on_tree_click)

    # ======================================================================
    # RIGA 4: BOTTONI VARI (Apri dir output / Analizza similarità)
    # ======================================================================
    def apri_directory_output():
        base_dir = global_config["selected_directory"].get().strip()
        if not base_dir or base_dir.lower() == "nessuna":
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima una directory di lavoro (dalla barra superiore).",
            )
            return

        output_dir = os.path.join(base_dir, "00_MixOutput")
        data_handler.open_selected_directory(output_dir)

    btn_open_directory = tk.Button(
        frame_correzione,
        text="Apri Directory Output",
        command=apri_directory_output,
    )
    btn_open_directory.grid(row=4, column=0, sticky="ew", padx=10, pady=5)

    def analizza_similarita():
        similarity.analyze_similarities(
            global_config["selected_directory"],  # StringVar gestita da similarity._resolve_directory_source
            report_text,
        )

    btn_analyze = tk.Button(
        frame_correzione,
        text="Analizza Similarità",
        command=analizza_similarita,
    )
    btn_analyze.grid(row=4, column=1, sticky="ew", padx=10, pady=5)

    # ======================================================================
    # RIGHE 5-6: LOG / REPORT
    # ======================================================================
    lbl_report = tk.Label(frame_correzione, text="Log / Report:", bg="white")
    lbl_report.grid(row=5, column=0, sticky="nw", padx=10, pady=5)

    report_text = tk.Text(
        frame_correzione,
        width=100,
        height=10,
        bg=YELLOW_REPORT_BG,
    )
    report_text.grid(
        row=6,
        column=0,
        columnspan=4,
        sticky="nsew",
        padx=10,
        pady=5,
    )

    scrollbar = Scrollbar(
        frame_correzione,
        orient="vertical",
        command=report_text.yview,
    )
    scrollbar.grid(row=6, column=4, sticky="ns", pady=5)

    report_text.config(yscrollcommand=scrollbar.set)
    utils.enable_mousewheel(entry_prompt)
    utils.enable_mousewheel(report_text)
    frame_correzione.rowconfigure(6, weight=1)

    # ======================================================================
    # AGGIORNAMENTO AUTOMATICO SU CAMBIO selected_directory
    # ======================================================================
    def refresh_current_directory_state():
        """
        Aggiorna il log e la tabella in base a global_config["selected_directory"].
        Esclude tutte le subdirectory che iniziano con '00' dalla tabella.
        """
        path = global_config["selected_directory"].get().strip()

        report_text.delete("1.0", "end")
        tree.delete(*tree.get_children())

        if not path or path.lower() == "nessuna":
            report_text.insert(
                "end",
                "Nessuna directory selezionata.\n"
                "Seleziona la directory dalla barra superiore (clic sulla voce blu).\n",
            )
            report_text.see("end")
            return

        if not os.path.isdir(path):
            report_text.insert(
                "end",
                "La directory selezionata non esiste:\n" + path + "\n",
            )
            report_text.see("end")
            return

        # Popola log e tabella con la funzione esistente
        utils.update_directory_listing(path, entry_extension, report_text)
        utils.update_subdirectories_list(path, tree, entry_extension)

        # --- FILTRO post-popolamento: rimuove le subdirectory che iniziano con '00' ---
        # Nota: non modifichiamo utils; filtriamo qui gli item già inseriti nella treeview.
        all_items = tree.get_children()
        idx = 0
        while idx < len(all_items):
            item_id = all_items[idx]
            values = tree.item(item_id, "values")
            if values and len(values) > 0:
                subdir_name = str(values[0]).strip()
                if subdir_name.startswith("00"):
                    tree.delete(item_id)
            idx = idx + 1


    def on_selected_directory_change(*_args):
        refresh_current_directory_state()

    sel_dir_var = global_config.get("selected_directory")
    if sel_dir_var is not None:
        if hasattr(sel_dir_var, "trace_add"):
            sel_dir_var.trace_add("write", on_selected_directory_change)
        elif hasattr(sel_dir_var, "trace"):
            sel_dir_var.trace("w", on_selected_directory_change)

    # possibilità di richiamare il refresh da fuori (bottone "Aggiorna cartella" in header)
    global_config["refresh_correzione"] = refresh_current_directory_state

    # ======================================================================
    # PULSANTE MIX (usa la directory globale)
    # ======================================================================
    def do_mix():
        """
        Esegue il mix dei file nella directory selezionata.

        Prima di procedere:
          - legge il testo dell'INTRO dal widget Text;
          - aggiorna la variabile globale intro_text, così che
            possa essere salvata nel file di configurazione JSON.
        """
        intro_corrente = sync_intro_text().strip()

        business_logic.mix_files(
            global_config["selected_directory"],  # StringVar, gestita da business_logic._resolve_base_directory
            entry_prompt,
            entry_extension,
            tree,
            report_text,
            include_prompt_var.get(),
            include_subdir_var.get(),
        )

    btn_mix.config(command=do_mix)


    # ======================================================================
    # MESSAGGIO INIZIALE
    # ======================================================================
    report_text.insert(
        "end",
        "Modalità Correzione pronta.\n"
        "1) Seleziona la directory dalla barra superiore (clic su 'nessuna' / percorso).\n"
        "2) Imposta le estensioni (es. .php,.html,.css) e l'intro.\n"
        "3) Premi 'Mixa' per generare i file *_mix.txt in 00_MixOutput.\n"
        "   → la colonna 'Mix file' mostrerà il percorso del file di mix.\n"
        "   → cliccando su una cella di quella colonna, il contenuto verrà copiato negli appunti.\n"
        "4) Usa Export / 'Analizza Similarità' per esportare e analizzare.\n",
    )
    report_text.see("end")

    # All'avvio sincronizziamo lo stato attuale, se già presente
    refresh_current_directory_state()

    return frame_correzione
