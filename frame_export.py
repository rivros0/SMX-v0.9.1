# frame_export.py
#
# Modalità EXPORT
# - Visualizza i file *_mix.txt in 00_MixOutput (escludendo voci che iniziano con '00')
# - Crea i PDF individuali in 00_Pdf dai mix (poi rinomina aggiungendo <NomeVerifica>__)
# - Esegue il MEGAmerge in 00_Pdf, includendo TUTTI i PDF (esclusi i '00*'),
#   garantendo pagine pari per ciascun elaborato
# - Mantiene il layout esistente
#
# NOTE DI STILE (coerenti con progetto):
# - niente lambda
# - codice procedurale e commentato
# - massima leggibilità

import os
import tkinter as tk
from tkinter import Scrollbar, messagebox

from PyPDF2 import PdfReader, PdfWriter

import business_logic
import data_handler
import utils

YELLOW_BG = "#ec9109"


def create_frame_export(root, global_config):
    """
    Frame modalità EXPORT.

    Dipendenze da global_config:
      - selected_directory : StringVar con la directory locale di lavoro
      - verifica_name      : StringVar con il nome della verifica
    """
    frame = tk.Frame(root, bg=YELLOW_BG)

    # ======================================================================
    #  UTILITY LOCALI
    # ======================================================================

    def _get_base_dir():
        try:
            base = global_config["selected_directory"].get().strip()
        except Exception:
            base = ""
        return base

    def _get_mix_dir():
        base = _get_base_dir()
        if not base:
            return ""
        return os.path.join(base, "00_MixOutput")

    def _get_pdf_dir():
        base = _get_base_dir()
        if not base:
            return ""
        return os.path.join(base, "00_Pdf")

    def _get_verifica_name_clean():
        """
        Restituisce un nome verifica "sanificato" da usare nei file:
        - rimuove slash e caratteri pericolosi
        - strip spazi
        """
        try:
            vname = global_config["verifica_name"].get()
        except Exception:
            vname = ""
        if vname is None:
            vname = ""
        vname = str(vname).strip()
        bad_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
        idx = 0
        while idx < len(bad_chars):
            vname = vname.replace(bad_chars[idx], "_")
            idx = idx + 1
        return vname

    def _get_class_name_clean():
        try:
            class_name = global_config["class_name"].get()
        except Exception:
            class_name = ""
        class_name = str(class_name or "").strip()
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|', ' ']:
            class_name = class_name.replace(char, "_")
        return class_name.strip("_")

    def _list_mix_files_filtered():
        """
        Elenco di file presenti in 00_MixOutput, esclusi quelli che iniziano con '00'.
        """
        mix_dir = _get_mix_dir()
        files = []
        if os.path.isdir(mix_dir):
            try:
                names = sorted(os.listdir(mix_dir))
            except Exception:
                names = []
            i = 0
            while i < len(names):
                nm = names[i]
                if not nm.startswith("00"):
                    files.append(nm)
                i = i + 1
        return files

    def _list_pdfs_filtered():
        """
        Elenco di PDF presenti in 00_Pdf, esclusi quelli che iniziano con '00'.
        """
        pdf_dir = _get_pdf_dir()
        files = []
        if os.path.isdir(pdf_dir):
            try:
                names = sorted(os.listdir(pdf_dir))
            except Exception:
                names = []
            i = 0
            while i < len(names):
                nm = names[i]
                if nm.lower().endswith(".pdf") and not nm.startswith("00"):
                    files.append(nm)
                i = i + 1
        return files

    def _rename_individual_pdfs_with_verifica():
        """
        Aggiunge il prefisso '<NomeVerifica>__' a tutti i PDF in 00_Pdf
        che NON iniziano con '00' e non hanno già il prefisso.
        """
        pdf_dir = _get_pdf_dir()
        verifica = _get_verifica_name_clean()
        if not os.path.isdir(pdf_dir):
            return

        if verifica == "":
            return

        try:
            names = sorted(os.listdir(pdf_dir))
        except Exception:
            names = []

        i = 0
        while i < len(names):
            nm = names[i]
            # escludo i '00' e i non-PDF
            if nm.startswith("00") or not nm.lower().endswith(".pdf"):
                i = i + 1
                continue

            # se già prefissato, ignoro
            prefix = verifica + "__"
            if nm.startswith(prefix):
                i = i + 1
                continue

            old_path = os.path.join(pdf_dir, nm)
            new_name = prefix + nm
            new_path = os.path.join(pdf_dir, new_name)

            # gestisce possibili collisioni
            if os.path.exists(new_path):
                base = os.path.splitext(new_name)[0]
                ext = ".pdf"
                counter = 2
                candidate = base + "_" + str(counter) + ext
                candidate_path = os.path.join(pdf_dir, candidate)
                while os.path.exists(candidate_path):
                    counter = counter + 1
                    candidate = base + "_" + str(counter) + ext
                    candidate_path = os.path.join(pdf_dir, candidate)
                new_path = candidate_path
                new_name = os.path.basename(new_path)

            try:
                os.rename(old_path, new_path)
            except Exception:
                # se il rename fallisce, proseguo senza interrompere il flusso
                pass

            i = i + 1

    def _open_dir(path):
        if not path:
            return
        if not os.path.exists(path):
            return
        data_handler.open_selected_directory(path)

    # ======================================================================
    #  RIGA 0: DIRECTORY DI OUTPUT (00_MixOutput)
    # ======================================================================

    lbl_output_title = tk.Label(frame, text="Directory di output (00_MixOutput):", bg=YELLOW_BG)
    lbl_output_title.grid(row=0, column=0, sticky="w", padx=8, pady=6)

    lbl_output_path = tk.Label(
        frame,
        text="(nessuna directory selezionata)",
        bg=YELLOW_BG,
        fg="blue",
        cursor="hand2",
        anchor="w",
    )
    lbl_output_path.grid(row=0, column=1, columnspan=2, sticky="ew", padx=8, pady=6)

    def open_output_dir(event=None):
        _open_dir(_get_mix_dir())

    lbl_output_path.bind("<Button-1>", open_output_dir)

    # ======================================================================
    #  RIGA 1: PULSANTI
    # ======================================================================

    def do_create_pdfs():
        """
        1) Crea i PDF individuali in 00_Pdf partendo dai *_mix.txt in 00_MixOutput.
           (business_logic già usa 00_Pdf)
        2) Rinomina i PDF creati aggiungendo '<NomeVerifica>__' come prefisso.
        3) Aggiorna l'elenco.
        """
        base_dir = _get_base_dir()
        if not base_dir:
            messagebox.showwarning("Attenzione", "Seleziona prima una directory di lavoro (Preparazione/Correzione).")
            return

        log_text.insert("end", "Verifica dei file mix prima della creazione PDF...\n")
        business_logic.create_missing_mix_files(
            base_dir,
            global_config["file_extension"].get(),
            global_config["intro_text"].get(),
            log_text,
        )
        business_logic.create_individual_pdfs(base_dir, log_text)
        _rename_individual_pdfs_with_verifica()
        update_file_list()
        log_text.see("end")

    def do_megamerge():
        """
        MEGAmerge locale corretto:
        - usa TUTTI i PDF in 00_Pdf che NON iniziano con '00'
        - aggiunge pagina bianca dove serve per blocchi a pagine pari
        - salva in 00_Pdf come '00_MEGAmerged_output_final__<NomeVerifica>.pdf'
        """
        base_dir = _get_base_dir()
        if not base_dir:
            messagebox.showwarning("Attenzione", "Seleziona prima una directory di lavoro (Preparazione/Correzione).")
            return

        log_text.insert("end", "Verifica dei file mix prima del MEGAmerge...\n")
        business_logic.create_missing_mix_files(
            base_dir,
            global_config["file_extension"].get(),
            global_config["intro_text"].get(),
            log_text,
        )

        pdf_dir = _get_pdf_dir()
        if not os.path.isdir(pdf_dir):
            messagebox.showwarning("Attenzione", "La directory 00_Pdf non esiste ancora. Crea prima i PDF multipli.")
            return

        # elenco pdf da includere (no '00*')
        pdf_files = _list_pdfs_filtered()
        if not pdf_files:
            # provo a generare prima i PDF, poi riprovo
            business_logic.create_individual_pdfs(base_dir, log_text)
            _rename_individual_pdfs_with_verifica()
            pdf_files = _list_pdfs_filtered()

        if not pdf_files:
            messagebox.showwarning("Attenzione", "Nessun PDF individuale trovato in 00_Pdf.")
            return

        # merge
        writer = PdfWriter()
        log_text.insert("end", "Inizio MEGAmerge con pagine pari per ogni elaborato...\n")

        # ordino per stabilità
        pdf_files.sort()

        idx = 0
        while idx < len(pdf_files):
            name = pdf_files[idx]
            path = os.path.join(pdf_dir, name)
            try:
                reader = PdfReader(path)
            except Exception as exc:
                log_text.insert("end", "Errore lettura PDF '" + name + "': " + str(exc) + "\n")
                idx = idx + 1
                continue

            num_pages = len(reader.pages)
            p = 0
            while p < num_pages:
                writer.add_page(reader.pages[p])
                p = p + 1

            if num_pages % 2 == 1 and num_pages > 0:
                # aggiunge una pagina bianca con dimensioni della prima pagina
                first_page = reader.pages[0]
                width = first_page.mediabox.width
                height = first_page.mediabox.height
                writer.add_blank_page(width=width, height=height)
                log_text.insert("end", name + ": " + str(num_pages) + " pagine -> aggiunta 1 pagina bianca (totale blocco: " + str(num_pages + 1) + ").\n")
            else:
                log_text.insert("end", name + ": " + str(num_pages) + " pagine (già pari).\n")

            idx = idx + 1

        # Nome chiaro e portabile per l'invio/stampa finale.
        verifica = _get_verifica_name_clean()
        classe = _get_class_name_clean()
        name_parts = ["MEGAmerge"]
        if classe:
            name_parts.append(classe)
        if verifica:
            name_parts.append(verifica)
        final_name = "_".join(name_parts) + ".pdf"

        final_path = os.path.join(pdf_dir, final_name)
        try:
            with open(final_path, "wb") as fh:
                writer.write(fh)
            log_text.insert("end", "MEGAmerge completato.\nFile PDF finale creato in 00_Pdf:\n" + final_path + "\n")
        except Exception as exc:
            messagebox.showerror("Errore", "Errore durante la scrittura del PDF finale:\n" + str(exc))
            return

        log_text.see("end")
        update_file_list()

    def open_pdf_output_dir():
        """Apre 00_Pdf per passare direttamente alla stampa dei file generati."""
        pdf_dir = _get_pdf_dir()
        if not pdf_dir or not os.path.isdir(pdf_dir):
            messagebox.showwarning(
                "Cartella PDF",
                "La cartella 00_Pdf non esiste ancora. Crea prima i PDF multipli.",
            )
            return
        _open_dir(pdf_dir)

    btn_create_pdfs = tk.Button(frame, text="Crea PDF multipli", command=do_create_pdfs, bg="white")
    btn_create_pdfs.grid(row=1, column=0, sticky="ew", padx=8, pady=4)

    pdf_actions = tk.Frame(frame, bg=YELLOW_BG)
    pdf_actions.grid(row=1, column=1, sticky="w", padx=8, pady=4)
    btn_megamerge = tk.Button(pdf_actions, text="MegaMerge PDF", command=do_megamerge, bg="white", width=15)
    btn_megamerge.pack(side="left")
    btn_open_pdf_dir = tk.Button(
        pdf_actions, text="Apri cartella PDF", command=open_pdf_output_dir, bg="#fffbe6"
    )
    btn_open_pdf_dir.pack(side="left", padx=(6, 0))

    btn_refresh_list = tk.Button(frame, text="Aggiorna elenco", command=lambda: update_file_list(), bg="white")
    btn_refresh_list.grid(row=1, column=2, sticky="ew", padx=8, pady=4)

    # ======================================================================
    #  RIGA 2-3: TEXT AREA ELENCO FILE OUTPUT (00_MixOutput)
    # ======================================================================

    lbl_files = tk.Label(frame, text="File presenti in 00_MixOutput:", bg=YELLOW_BG)
    lbl_files.grid(row=2, column=0, sticky="nw", padx=8, pady=4)

    file_list_text = tk.Text(frame, width=80, height=10, bg="#fffbe6")
    file_list_text.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=8, pady=4)

    scrollbar_files = Scrollbar(frame, orient="vertical", command=file_list_text.yview)
    scrollbar_files.grid(row=3, column=3, sticky="ns", pady=4)
    file_list_text.config(yscrollcommand=scrollbar_files.set)
    utils.enable_mousewheel(file_list_text)

    # ======================================================================
    #  RIGA 4-5: LOG / REPORT
    # ======================================================================

    lbl_log = tk.Label(frame, text="Log / Report:", bg=YELLOW_BG)
    lbl_log.grid(row=4, column=0, sticky="nw", padx=8, pady=4)

    log_text = tk.Text(frame, width=80, height=10, bg="#fffdf0")
    log_text.grid(row=5, column=0, columnspan=3, sticky="nsew", padx=8, pady=4)

    scrollbar_log = Scrollbar(frame, orient="vertical", command=log_text.yview)
    scrollbar_log.grid(row=5, column=3, sticky="ns", pady=4)
    log_text.config(yscrollcommand=scrollbar_log.set)
    utils.enable_mousewheel(log_text)

    # ======================================================================
    #  LAYOUT RESPONSIVE
    # ======================================================================

    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(3, weight=1)
    frame.rowconfigure(5, weight=1)

    # ======================================================================
    #  AGGIORNAMENTO ELENCO (con filtro '00*')
    # ======================================================================

    def update_file_list(*_args):
        """
        Aggiorna la textarea con la lista dei file presenti in 00_MixOutput,
        escludendo qualunque elemento che inizi con '00'.
        """
        mix_dir = _get_mix_dir()
        file_list_text.delete("1.0", "end")

        if not mix_dir:
            file_list_text.insert(
                "end",
                "Nessuna directory di lavoro selezionata.\n"
                "Imposta prima la directory in Preparazione o Correzione.\n",
            )
            lbl_output_path.config(text="(nessuna directory selezionata)")
            return

        lbl_output_path.config(text=mix_dir)

        if not os.path.exists(mix_dir):
            file_list_text.insert(
                "end",
                "La directory di output non esiste ancora:\n" + mix_dir + "\n"
                "Esegui prima la fase di MIX dalla scheda Correzione.\n",
            )
            return

        try:
            all_names = sorted(os.listdir(mix_dir))
        except Exception as e:
            file_list_text.insert("end", "Errore nella lettura di " + mix_dir + ":\n" + str(e) + "\n")
            return

        names = []
        i = 0
        while i < len(all_names):
            nm = all_names[i]
            # filtro '00*'
            if not nm.startswith("00"):
                names.append(nm)
            i = i + 1

        if not names:
            file_list_text.insert("end", "Nessun file (filtrati gli elementi '00*') in:\n" + mix_dir + "\n")
            return

        file_list_text.insert("end", "File presenti in " + mix_dir + ":\n\n")
        j = 0
        while j < len(names):
            file_list_text.insert("end", " - " + names[j] + "\n")
            j = j + 1

    # ======================================================================
    #  REAZIONE AL CAMBIO DIRECTORY SELEZIONATA
    # ======================================================================

    sel_dir_var = global_config.get("selected_directory")
    if sel_dir_var is not None and hasattr(sel_dir_var, "trace_add"):
        sel_dir_var.trace_add("write", lambda *_: update_file_list())
    elif sel_dir_var is not None and hasattr(sel_dir_var, "trace"):
        sel_dir_var.trace("w", lambda *_: update_file_list())

    # Messaggio iniziale nel log
    log_text.insert(
        "end",
        "Modalità Export pronta.\n"
        "- 'Crea PDF multipli' genera i PDF individuali in 00_Pdf.\n"
        "  Dopo la creazione, i PDF vengono rinominati come:\n"
        "  '<NomeVerifica>__<nome_file_mix>.pdf' (se NomeVerifica non è vuoto).\n"
        "- 'MegaMerge PDF' unisce i PDF (escludendo '00*') in un unico file,\n"
        "  aggiungendo una pagina bianca dove necessario (blocchi a pagine pari).\n",
    )
    log_text.see("end")

    # Avvio
    update_file_list()
    global_config["refresh_export"] = update_file_list

    return frame
