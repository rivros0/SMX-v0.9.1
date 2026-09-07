# associa.py
# Finestra per associare EMAIL ↔ cartelle test*, con:
# - logica di Smixer_v6 (liste filtrate, dissocia, associa in ordine, ecc.)
# - directory di lavoro presa da local_directory,
#   con fallback di compatibilità a selected_directory
# - tabella associazioni con colonne: EMAIL | CARTELLA (invertite)
# - rinomina cartelle con schema: "email test"
#   -> local_part(email) + "__" + base_name_cartella

import os
import tkinter as tk
from tkinter import messagebox, Scrollbar, ttk
import utils
import data_handler


def _email_local_part(email: str) -> str:
    """
    Restituisce solo la parte locale dell'email (prima della @).
    Esempio: 'nome.cognome@pantanelli-monnet.edu.it' -> 'nome.cognome'
    Se non c'è '@', restituisce la stringa così com'è.
    """
    email = email.strip()
    if "@" in email:
        parts = email.split("@", 1)
        return parts[0]
    return email


def open_associa_window(root, global_config):
    """
    Finestra per associare gli indirizzi email degli alunni alle cartelle di test
    della directory locale selezionata.

    Struttura (come Smixer_v6):
    - Riga 0: label con directory di lavoro.
    - Riga 1: label "Incolla qui le email..."
    - Riga 2: Text per incollare email (3 righe) + pulsante "Aggiorna lista email".
    - Riga 3: label sopra le due liste (Cartelle a sinistra, Email a destra).
    - Riga 4: tre colonne:
        colonna 0: Listbox cartelle test
        colonna 1: pulsanti (refresh, associa, associa in ordine, dissocia, applica)
        colonna 2: Listbox email (senza dominio)
    - Riga 5: label "Associazioni"
    - Riga 6: tabella con associazioni (EMAIL | CARTELLA).

    Le liste mostrano solo gli elementi NON ancora associati.
    Le cartelle già associate (e le email già associate) restano solo nella tabella.
    Quando si dissocia, cartella ed email tornano disponibili nelle liste.
    """

    window = tk.Toplevel(root)
    window.title("Associa email a cartelle di test")
    window.geometry("1100x650")
    window.configure(bg="white")

    # ======================================================================
    # VARIABILI DI STATO
    # ======================================================================
    base_dir_var = tk.StringVar()

    # Tutte le email presenti nel Text (forma completa con dominio)
    all_emails_full = []

    # Tutte le cartelle trovate nella directory di lavoro (esclusa 00_MixOutput)
    all_folders = []

    # Associazioni correnti: { "nome_cartella": "email_completa" }
    associations = {}

    # ======================================================================
    # FUNZIONI DI SUPPORTO
    # ======================================================================
    def get_current_base_dir():
        """
        Restituisce la directory locale selezionata:
        - prima prova con local_directory
        - poi usa selected_directory solo per compatibilità con versioni precedenti
        """
        selected_var = global_config.get("local_directory") or global_config.get("selected_directory")
        path = ""

        if selected_var is not None:
            path = selected_var.get().strip()
        else:
            remote_var = global_config.get("remote_directory")
            if remote_var is not None:
                path = remote_var.get().strip()

        if not path:
            return ""

        lower_path = path.lower()
        if lower_path == "nessuna":
            return ""

        return path

    def update_base_dir_label():
        """
        Aggiorna la label che mostra la directory di lavoro corrente.
        """
        base_dir = get_current_base_dir()
        if not base_dir:
            base_dir_var.set("Directory di lavoro: (nessuna)")
        else:
            base_dir_var.set("Directory di lavoro: " + base_dir)

    def parse_emails_from_text():
        """
        Legge il contenuto dell'area di testo e aggiorna all_emails_full
        con le email (righe non vuote).
        """
        nonlocal all_emails_full

        raw = text_emails.get("1.0", "end")
        lines = raw.splitlines()
        emails = []
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if line:
                emails.append(line)
            index = index + 1

        all_emails_full = emails

    def discover_all_folders():
        """
        Scansiona la directory di lavoro e aggiorna all_folders con le
        sottocartelle trovate, escludendo 00_MixOutput.
        """
        nonlocal all_folders

        all_folders = []

        base_dir = get_current_base_dir()
        if not base_dir:
            return
        if not os.path.isdir(base_dir):
            return

        entries = os.listdir(base_dir)
        for entry in entries:
            full_path = os.path.join(base_dir, entry)
            if os.path.isdir(full_path) and data_handler.is_local_student_folder(entry):
                all_folders.append(entry)
        all_folders.sort()

    def get_remaining_emails():
        """
        Restituisce la lista di email (forma completa) che non sono ancora
        assegnate in 'associations'.
        """
        remaining = []
        associated = set(associations.values())

        index = 0
        while index < len(all_emails_full):
            email_value = all_emails_full[index]
            if email_value not in associated:
                remaining.append(email_value)
            index = index + 1

        return remaining

    def get_remaining_folders():
        """
        Restituisce la lista di cartelle non ancora presenti in 'associations'.
        """
        remaining = []
        associated = set(associations.keys())

        index = 0
        while index < len(all_folders):
            folder_name = all_folders[index]
            if folder_name not in associated:
                remaining.append(folder_name)
            index = index + 1

        return remaining

    def refresh_email_list_from_state():
        """
        Aggiorna la Listbox delle email mostrando solo quelle non associate,
        e solo la parte prima di '@'.
        """
        listbox_emails.delete(0, "end")
        remaining = get_remaining_emails()

        if not all_emails_full:
            listbox_emails.insert("end", "(Nessuna email)")
            return

        if not remaining:
            listbox_emails.insert("end", "(Nessuna email disponibile)")
            return

        index = 0
        while index < len(remaining):
            full_email = remaining[index]
            local_part = _email_local_part(full_email)
            listbox_emails.insert("end", local_part)
            index = index + 1

    def refresh_folder_list_from_state():
        """
        Aggiorna la Listbox delle cartelle test mostrando solo quelle non associate.
        """
        listbox_folders.delete(0, "end")
        remaining = get_remaining_folders()

        if not all_folders:
            listbox_folders.insert("end", "(Nessuna sottocartella trovata)")
            return

        if not remaining:
            listbox_folders.insert("end", "(Nessuna cartella disponibile)")
            return

        index = 0
        while index < len(remaining):
            folder_name = remaining[index]
            listbox_folders.insert("end", folder_name)
            index = index + 1

    def refresh_mapping_tree():
        """
        Aggiorna la tabella delle associazioni.
        Colonne invertite: EMAIL | CARTELLA
        Nella colonna email viene mostrata solo la parte prima di '@'.
        """
        tree_mapping.delete(*tree_mapping.get_children())
        cartelle = list(associations.keys())
        cartelle.sort()

        index = 0
        while index < len(cartelle):
            folder_name = cartelle[index]
            email_value = associations[folder_name]
            local_part = _email_local_part(email_value)
            # Colonne: EMAIL (0), CARTELLA (1)
            tree_mapping.insert(
                "",
                "end",
                values=(local_part, folder_name),
            )
            index = index + 1

    def on_refresh_dir():
        """
        Aggiorna la directory di lavoro mostrata, rilegge le cartelle
        e rinfresca le liste in base alle associazioni correnti.
        """
        update_base_dir_label()
        discover_all_folders()
        refresh_folder_list_from_state()

    def on_update_email_list():
        """
        Aggiorna l'elenco delle email partendo dal testo incollato sopra,
        quindi rinfresca la Listbox in base alle associazioni correnti.
        """
        parse_emails_from_text()
        refresh_email_list_from_state()

    def on_associate_selected():
        """
        Associa l'email selezionata (Lista a destra) alla cartella selezionata
        (Lista a sinistra). Aggiorna 'associations' e rinfresca liste e tabella.
        """
        # selezione cartella test (a sinistra)
        selection_folder = listbox_folders.curselection()
        if not selection_folder:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima una cartella di test nella lista a sinistra.",
            )
            return

        folder_index = selection_folder[0]
        remaining_folders = get_remaining_folders()
        if folder_index < 0 or folder_index >= len(remaining_folders):
            messagebox.showwarning(
                "Attenzione",
                "La selezione nella lista cartelle non è valida.",
            )
            return

        folder_name = remaining_folders[folder_index]

        # selezione email (a destra)
        selection_email = listbox_emails.curselection()
        if not selection_email:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima un'email nella lista a destra.",
            )
            return

        email_index = selection_email[0]
        remaining_emails = get_remaining_emails()
        if email_index < 0 or email_index >= len(remaining_emails):
            messagebox.showwarning(
                "Attenzione",
                "La selezione nella lista email non è valida.",
            )
            return

        full_email = remaining_emails[email_index]

        # aggiorna associazioni
        associations[folder_name] = full_email

        # aggiorna viste
        refresh_folder_list_from_state()
        refresh_email_list_from_state()
        refresh_mapping_tree()

    def on_associate_sequential():
        """
        Associazione automatica in ordine:
        1ª cartella disponibile -> 1ª email disponibile
        2ª cartella disponibile -> 2ª email disponibile
        e così via.

        NON chiude la finestra.
        """
        base_dir = get_current_base_dir()
        if not base_dir or not os.path.isdir(base_dir):
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima una directory locale valida.",
            )
            return

        if not all_emails_full:
            messagebox.showwarning(
                "Attenzione",
                "Inserisci prima almeno una email nel campo di testo e aggiorna la lista.",
            )
            return

        remaining_folders = get_remaining_folders()
        remaining_emails = get_remaining_emails()
        if not remaining_folders or not remaining_emails:
            messagebox.showwarning(
                "Attenzione",
                "Non ci sono cartelle o email disponibili per l'associazione automatica.",
            )
            return

        max_count = len(remaining_folders)
        if len(remaining_emails) < max_count:
            max_count = len(remaining_emails)

        index = 0
        while index < max_count:
            folder_name = remaining_folders[index]
            full_email = remaining_emails[index]
            associations[folder_name] = full_email
            index = index + 1

        refresh_folder_list_from_state()
        refresh_email_list_from_state()
        refresh_mapping_tree()

        messagebox.showinfo(
            "Associazione in ordine",
            "Create " + str(max_count) + " associazioni in ordine.",
        )
        # la finestra resta aperta

    def on_dissociate():
        """
        Dissocia la coppia selezionata nella tabella delle associazioni.
        La cartella e l'email tornano disponibili nelle rispettive liste.
        """
        selected_items = tree_mapping.selection()
        if not selected_items:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima una riga nella tabella delle associazioni.",
            )
            return

        item_id = selected_items[0]
        values = tree_mapping.item(item_id, "values")
        if not values or len(values) < 2:
            messagebox.showwarning(
                "Attenzione",
                "Selezione non valida nella tabella delle associazioni.",
            )
            return

        # Colonne: EMAIL (0), CARTELLA (1)
        folder_name = values[1]

        if folder_name in associations:
            del associations[folder_name]

        refresh_mapping_tree()
        refresh_folder_list_from_state()
        refresh_email_list_from_state()

    def on_apply_and_rename():
        """
        Applica le associazioni rinominando fisicamente le cartelle.
        Nel nome della cartella viene usata solo la parte prima della '@'.

        Nuovo schema di concatenazione:
        - email test  -> local_part(email) + "__" + base_name_cartella
        """
        base_dir = get_current_base_dir()
        if not base_dir:
            messagebox.showwarning(
                "Attenzione",
                "Seleziona prima una directory locale (copiata dal server).",
            )
            return

        if not os.path.isdir(base_dir):
            messagebox.showwarning(
                "Attenzione",
                "La directory selezionata non esiste:\n" + base_dir,
            )
            return

        if not associations:
            messagebox.showwarning(
                "Attenzione",
                "Non ci sono associazioni da applicare.\n"
                "Usa 'Associa selezionati' o 'Associa automaticamente (in ordine)'.",
            )
            return

        cartelle = list(associations.keys())
        cartelle.sort()

        lines = []
        index = 0
        while index < len(cartelle):
            folder_name = cartelle[index]
            email_value = associations[folder_name]
            line = folder_name + " -> " + email_value
            lines.append(line)
            index = index + 1

        riepilogo = "\n".join(lines)

        conferma = messagebox.askyesno(
            "Conferma rinomina cartelle",
            "Verranno rinominate le seguenti cartelle:\n\n"
            + riepilogo
            + "\n\nNel nome cartella verrà usata SOLO la parte prima di '@'.\n\n"
            + "Schema: email test (es. nome.cognome__test01)\n\n"
            + "Procedere?",
        )
        if not conferma:
            return

        rinominate = 0
        errori = 0

        index = 0
        while index < len(cartelle):
            old_name = cartelle[index]
            email_value = associations[old_name]

            if "__" in old_name:
                parts = old_name.split("__", 1)
                base_name = parts[0]
            else:
                base_name = old_name

            local_part = _email_local_part(email_value)

            # NUOVO NOME: email test -> local_part__base_name
            new_name = local_part + "__" + base_name

            old_path = os.path.join(base_dir, old_name)
            new_path = os.path.join(base_dir, new_name)

            if not os.path.exists(old_path):
                errori = errori + 1
                index = index + 1
                continue

            if os.path.exists(new_path) and old_path != new_path:
                errori = errori + 1
                index = index + 1
                continue

            try:
                os.rename(old_path, new_path)
                rinominate = rinominate + 1
            except Exception as exc:
                errori = errori + 1
                messagebox.showerror(
                    "Errore",
                    "Errore nel rinominare '"
                    + old_name
                    + "' in '"
                    + new_name
                    + "':\n"
                    + str(exc),
                )

            index = index + 1

        associations.clear()
        refresh_mapping_tree()
        discover_all_folders()
        refresh_folder_list_from_state()
        refresh_email_list_from_state()

        messagebox.showinfo(
            "Operazione completata",
            "Cartelle rinominate: " + str(rinominate)
            + "\nEventuali errori: " + str(errori),
        )

    # ======================================================================
    # LAYOUT: RIGA 0 - Directory di lavoro
    # ======================================================================
    update_base_dir_label()
    lbl_base_dir = tk.Label(
        window,
        textvariable=base_dir_var,
        bg="white",
        anchor="w",
    )
    lbl_base_dir.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=10)

    # ======================================================================
    # LAYOUT: RIGA 1-2 - Text email (3 righe) + pulsante "Aggiorna lista email"
    # ======================================================================
    lbl_emails_text = tk.Label(
        window,
        text="Incolla qui le email (una per riga):",
        bg="white",
        anchor="w",
    )
    lbl_emails_text.grid(row=1, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 2))

    text_emails = tk.Text(
        window,
        width=60,
        height=3,  # altezza ridotta a 3 righe
    )
    text_emails.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)
    utils.enable_mousewheel(text_emails)

    btn_update_email_list = tk.Button(
        window,
        text="Aggiorna lista email",
        command=on_update_email_list,
        bg="white",
    )
    btn_update_email_list.grid(row=2, column=2, sticky="n", padx=10, pady=5)

    # ======================================================================
    # LAYOUT: RIGA 3-4 - Cartelle (sx) | pulsanti | Email (dx)
    # ======================================================================
    lbl_folders = tk.Label(
        window,
        text="Cartelle test nella directory di lavoro:",
        bg="white",
        anchor="w",
    )
    lbl_folders.grid(row=3, column=0, sticky="w", padx=10, pady=(10, 2))

    lbl_emails_list = tk.Label(
        window,
        text="Email (parte prima di '@' - seleziona per associare):",
        bg="white",
        anchor="w",
    )
    lbl_emails_list.grid(row=3, column=2, sticky="w", padx=10, pady=(10, 2))

    # Listbox cartelle test (sinistra)
    frame_folders_list = tk.Frame(window, bg="white")
    frame_folders_list.grid(row=4, column=0, sticky="nsew", padx=10, pady=5)

    listbox_folders = tk.Listbox(
        frame_folders_list,
        width=40,
        height=14,
        exportselection=False,
    )
    listbox_folders.pack(side="left", fill="both", expand=True)

    scroll_folders = Scrollbar(
        frame_folders_list,
        orient="vertical",
        command=listbox_folders.yview,
    )
    scroll_folders.pack(side="right", fill="y")
    listbox_folders.config(yscrollcommand=scroll_folders.set)

    # Colonna centrale: pulsanti
    center_buttons_frame = tk.Frame(window, bg="white")
    center_buttons_frame.grid(row=4, column=1, sticky="n", padx=10, pady=5)

    btn_refresh_dir = tk.Button(
        center_buttons_frame,
        text="Aggiorna directory / cartelle",
        command=on_refresh_dir,
        bg="white",
        width=28,
    )
    btn_refresh_dir.pack(pady=5)

    btn_associate_selected = tk.Button(
        center_buttons_frame,
        text="Associa selezionati →",
        command=on_associate_selected,
        bg="white",
        width=28,
    )
    btn_associate_selected.pack(pady=5)

    btn_associate_seq = tk.Button(
        center_buttons_frame,
        text="Associa automaticamente (in ordine)",
        command=on_associate_sequential,
        bg="white",
        width=28,
    )
    btn_associate_seq.pack(pady=5)

    btn_dissociate = tk.Button(
        center_buttons_frame,
        text="Dissocia selezionato",
        command=on_dissociate,
        bg="#ffe0e0",
        width=28,
    )
    btn_dissociate.pack(pady=5)

    btn_apply = tk.Button(
        center_buttons_frame,
        text="Applica e rinomina cartelle",
        command=on_apply_and_rename,
        bg="#d0ffd0",
        width=28,
    )
    btn_apply.pack(pady=15)

    # Listbox email (destra, mostra solo parte prima di '@')
    frame_emails_list = tk.Frame(window, bg="white")
    frame_emails_list.grid(row=4, column=2, sticky="nsew", padx=10, pady=5)

    listbox_emails = tk.Listbox(
        frame_emails_list,
        width=40,
        height=14,
        exportselection=False,
    )
    listbox_emails.pack(side="left", fill="both", expand=True)

    scroll_emails = Scrollbar(
        frame_emails_list,
        orient="vertical",
        command=listbox_emails.yview,
    )
    scroll_emails.pack(side="right", fill="y")
    listbox_emails.config(yscrollcommand=scroll_emails.set)

    # ======================================================================
    # LAYOUT: RIGA 5-6 - Tabella associazioni (EMAIL | CARTELLA)
    # ======================================================================
    lbl_mapping = tk.Label(
        window,
        text="Associazioni (email ↔ cartella):",
        bg="white",
        anchor="w",
    )
    lbl_mapping.grid(row=5, column=0, columnspan=3, sticky="w", padx=10, pady=(15, 2))

    mapping_frame = tk.Frame(window, bg="white")
    mapping_frame.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)

    # Colonne invertite: EMAIL, CARTELLA
    tree_mapping = ttk.Treeview(
        mapping_frame,
        columns=("email", "cartella"),
        show="headings",
        height=6,
    )
    tree_mapping.heading("email", text="Email (prima di '@')")
    tree_mapping.heading("cartella", text="Cartella")
    tree_mapping.column("email", width=600, anchor="w")
    tree_mapping.column("cartella", width=200, anchor="w")
    tree_mapping.pack(side="left", fill="both", expand=True)

    scroll_mapping = Scrollbar(mapping_frame, orient="vertical", command=tree_mapping.yview)
    scroll_mapping.pack(side="right", fill="y")
    tree_mapping.config(yscrollcommand=scroll_mapping.set)

    # ======================================================================
    # CONFIGURAZIONE PESI (ridimensionamento finestra)
    # ======================================================================
    window.grid_rowconfigure(2, weight=0)
    window.grid_rowconfigure(4, weight=1)
    window.grid_rowconfigure(6, weight=1)
    window.grid_columnconfigure(0, weight=1)
    window.grid_columnconfigure(1, weight=0)
    window.grid_columnconfigure(2, weight=1)

    # Stato iniziale
    update_base_dir_label()
    discover_all_folders()
    refresh_folder_list_from_state()
    parse_emails_from_text()
    refresh_email_list_from_state()
    refresh_mapping_tree()
