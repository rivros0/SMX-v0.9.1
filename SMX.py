import json
import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

python_dir = os.path.dirname(sys.executable)
for env_name, relative in (("TCL_LIBRARY", ("tcl", "tcl8.6")), ("TK_LIBRARY", ("tcl", "tk8.6"))):
    candidate = os.path.join(python_dir, *relative)
    if os.path.exists(candidate):
        os.environ[env_name] = candidate

import data_handler
from utils import add_tooltip, enable_mousewheel
from frame_associa import create_frame_associa
from frame_live import create_frame_live
from frame_preparazione import create_frame_preparazione
from project_manager import PROJECT_FILE, SESSION_EXTENSION, VerificationProject


def _optional_frame(module_name, function_name):
    try:
        module = __import__(module_name, fromlist=[function_name])
        return getattr(module, function_name), None
    except Exception as exc:
        error = str(exc)
        def unavailable(parent, _config, error=error):
            frame = tk.Frame(parent, bg="white")
            tk.Label(frame, text=f"Modalità non disponibile: {error}", bg="white", fg="red",
                     wraplength=900).pack(padx=30, pady=30)
            return frame
        return unavailable, exc


create_frame_correzione, _ = _optional_frame("frame_correzione", "create_frame_correzione")
create_frame_export, _ = _optional_frame("frame_export", "create_frame_export")
create_frame_domini, _ = _optional_frame("frame_domini", "create_frame_domini")
create_frame_monitor_domini, _ = _optional_frame("frame_monitor_domini", "create_frame_monitor_domini")

APP_STATE = Path.home() / ".smx_state.json"

EXTENSION_PRESETS = {
    "C / C++": ".c .h .cpp",
    "Java": ".java",
    "Python": ".py",
    "Web": ".html .htm .css .js",
    #"C#": ".cs", 
    "SQL": ".sql",
    "Testo": ".txt .md",
}


class SMXApplication:
    def __init__(self, root):
        self.root = root
        root.title("SMX - Gestione elaborati - Versione: 0.9.1")
        root.geometry("1280x800")
        base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        icon_path = base_path / "icone" / "app.ico"
        if icon_path.is_file():
            try:
                root.iconbitmap(str(icon_path))
            except tk.TclError:
                pass
        self.config = {
            "remote_directory": tk.StringVar(value="W:\\"), "local_directory": tk.StringVar(),
            "file_extension": tk.StringVar(value=".cpp"),
            "verifica_name": tk.StringVar(), "class_name": tk.StringVar(), "intro_text": tk.StringVar(),
            "alert_threshold": tk.IntVar(value=30), "current_mode": tk.StringVar(value="Live"),
        }
        # Alias temporaneo: i frame storici vengono migrati senza rompere plugin locali.
        self.config["selected_directory"] = self.config["local_directory"]
        self.config["student_associations"] = {}
        self.config["domain_students"] = []
        self._load_state()
        self._build_menu()
        self._build_header()
        self.content = tk.Frame(root)
        self.content.pack(fill="both", expand=True)
        self.frames = {}
        self.config["show_mode"] = self.show_mode
        self._rebuild_frames()
        # Correzione resta disponibile, ma non compare nella barra delle modalità.
        # Il binding globale funziona anche quando il focus è in un campo di testo.
        self.root.bind_all("<Control-Alt-k>", self._open_hidden_correction)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.show_startup_dialog)

    def _build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Nuova verifica…", command=self.new_project)
        file_menu.add_command(label="Carica sessione .smxSession…", command=self.load_session)
        file_menu.add_command(label="Carica verifica da cartella…", command=self.load_project)
        file_menu.add_command(label="Riprendi ultima verifica", command=self.resume_project)
        file_menu.add_separator()
        file_menu.add_command(label="Salva", command=self.save_session)
        file_menu.add_command(label="Salva con nome…", command=self.save_session_as)
        file_menu.add_separator()
        file_menu.add_command(label="Crea archivio completo…", command=self.archive_project)
        file_menu.add_command(label="Associa alunni alle cartelle…", command=lambda: self.show_mode("Associa"))
        file_menu.add_separator()
        file_menu.add_command(label="Carica configurazione...", command=self.load_configuration)
        file_menu.add_command(label="Salva configurazione...", command=self.save_configuration)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Guida operativa", command=self.show_help)
        help_menu.add_separator()
        help_menu.add_command(label="Informazioni su SMX", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def show_help(self):
        """Mostra una guida breve per il flusso scuola → consegna → casa."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Help – Guida operativa SMX")
        dialog.geometry("760x620")
        dialog.minsize(620, 440)
        dialog.transient(self.root)

        text = tk.Text(dialog, wrap="word", padx=14, pady=12, font=("Segoe UI", 10))
        text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.config(yscrollcommand=scrollbar.set)
        enable_mousewheel(text)
        text.insert("1.0", """SMX – guida operativa

CONCETTI CHIAVE
• Dir Remota: è il server/laboratorio. SMX considera esclusivamente le cartelle test01…test30 e il loro contenuto, comprese le sottocartelle.
• Dir Locale: è il progetto completo sulla postazione del docente. Qui SMX salva raccolte, storico, log, file di correzione, PDF e sessioni.
• Il server non viene modificato durante le normali scansioni: Distribuisci, Pulisci e Recupera sono sempre operazioni esplicite.

1. INIZIARE E PREPARARE LA VERIFICA
Per una nuova verifica indica classe, nome e tipi di file da considerare. La Dir Locale viene identificata con timestamp, classe e nome della verifica.

Nella schermata Preparazione, Aggiorna controlla le cartelle test e mostra tutti i file presenti; il controllo si aggiorna anche automaticamente ogni 30 secondi. Prima di iniziare usa Pulisci solo se sei certo che il server non contenga elaborati da conservare. Distribuisci copia i materiali predisposti nelle cartelle test.

2. ASSOCIARE GLI ALUNNI
Nella schermata Associa collega ogni testXX a un alunno. L'associazione viene salvata nella sessione, è usata nelle card, nei PDF e nelle analisi, ma non rinomina né altera le cartelle del server. Le cartelle senza associazione restano comunque incluse nella raccolta locale per sicurezza.

3. MONITORARE IN LIVE
Il monitoraggio è attivo all'apertura e legge le cartelle in sequenza, per non gravare sul server. Le card mostrano cartella test, alunno, righe rilevate, ultimo aggiornamento e andamento nel tempo. La prima rilevazione è una base di confronto e non genera avvisi; un incremento oltre la soglia evidenzia la card e può essere chiuso manualmente.

4. RACCOGLIERE UNA COPIA LOCALE
Raccogli copia locale crea nella Dir Locale uno specchio aggiornato di tutte le cartelle testXX del server. Se la raccolta viene ripetuta, ogni cartella locale viene sostituita con la versione più recente disponibile sul server: nel log sono indicati anche eventuali file locali rimossi perché non più presenti sul server. La posizione della raccolta viene sempre riportata nel log.

5. FINALIZZARE LA CONSEGNA
Quando gli alunni hanno consegnato, usa Finalizza consegna e termina verifica. SMX esegue un'ultima raccolta, mantiene le cartelle testXX immediatamente accessibili nella Dir Locale e genera un archivio ufficiale immutabile denominato CONSEGNA_timestamp_Classe_Verifica.smxSession. Dopo la finalizzazione, il monitoraggio e le ulteriori raccolte sono disattivati per proteggere lo stato consegnato.

6. CONTINUARE IL LAVORO A CASA
Il file .smxSession ordinario, nella root della Dir Locale, salva il progetto aggiornabile. Il file CONSEGNA_….smxSession è invece la copia ufficiale della consegna da trasferire o archiviare. Entrambi contengono il progetto, lo storico e gli elaborati raccolti; le cartelle testXX restano inoltre consultabili senza SMX.

7. CORREGGERE ED ESPORTARE
La correzione usa l'ultima copia locale per creare i file di testo concatenati, confrontare somiglianze e preparare gli elaborati. Export può generare automaticamente i file mix mancanti prima dei PDF; produce PDF individuali con classe, verifica, cartella test e alunno, oltre al PDF MEGAmerge. Controlla il log di ogni schermata per conoscere esito e percorsi dei file creati.

Buona pratica: conserva il file CONSEGNA_….smxSession e la Dir Locale prima di rimuovere o riutilizzare le cartelle sul server.
""")
        text.config(state="disabled")

    def show_about(self):
        messagebox.showinfo(
            "Informazioni su SMX",
            "SMX – Gestione elaborati\nVersione 0.9.1\n\n"
            "Gestione di verifiche con raccolta, monitoraggio, consegna e correzione locale.",
        )

    def _build_header(self):
        bar = tk.Frame(self.root, bg="#eeeeee")
        bar.pack(fill="x")
        tk.Label(bar, text="Classe:", bg="#eeeeee").pack(side="left", padx=(8, 3), pady=6)
        tk.Entry(bar, textvariable=self.config["class_name"], width=12).pack(side="left")
        tk.Label(bar, text="Verifica:", bg="#eeeeee").pack(side="left", padx=(12, 3))
        tk.Entry(bar, textvariable=self.config["verifica_name"], width=25).pack(side="left")
        tk.Label(bar, text="Dir Remota:", bg="#eeeeee").pack(side="left", padx=(16, 3))
        tk.Label(bar, textvariable=self.config["remote_directory"], bg="#eeeeee", fg="#075985",
                 cursor="hand2", width=35, anchor="w").pack(side="left")
        tk.Label(bar, text="Dir Locale:", bg="#eeeeee").pack(side="left", padx=(16, 3))
        local = tk.Label(bar, textvariable=self.config["local_directory"], bg="#eeeeee", fg="#075985",
                         cursor="hand2", anchor="w")
        local.pack(side="left", fill="x", expand=True, padx=(0, 8))
        local.bind("<Button-1>", lambda _event: self.open_or_choose_local_directory())
        btn_choose_local = tk.Button(bar, text="Scegli Dir Locale…", command=self.choose_local_directory)
        btn_choose_local.pack(
            side="left", padx=(0, 4), pady=4
        )
        btn_refresh = tk.Button(bar, text="Aggiorna", command=self.refresh_current_directory)
        btn_refresh.pack(
            side="left", padx=(0, 8), pady=4
        )
        add_tooltip(btn_choose_local, "Seleziona una cartella-verifica esistente sulla postazione del docente.")
        add_tooltip(btn_refresh, "Rilegge le informazioni della verifica aperta e aggiorna le schermate.")

        modes = tk.Frame(self.root, bg="#e8eef2")
        modes.pack(fill="x")
        tk.Label(modes, text="Modalità:", bg="#e8eef2").pack(side="left", padx=(8, 6), pady=5)
        self.mode_buttons = {}
        # Correzione è una modalità avanzata, raggiungibile con Ctrl+Alt+K.
        # Le modalità Domini restano nel codice per compatibilità, ma non sono esposte nell'interfaccia.
        for mode in ("Preparazione", "Associa", "Live", "Export"):
            button = tk.Button(modes, text=mode, command=lambda value=mode: self.show_mode(value),
                               relief="flat", padx=14, pady=4)
            button.pack(side="left", padx=2, pady=3)
            add_tooltip(button, "Apri la modalità " + mode + ".")
            self.mode_buttons[mode] = button

    def _rebuild_frames(self):
        for frame in self.frames.values():
            frame.destroy()
        self.frames = {
            "Preparazione": create_frame_preparazione(self.content, self.config),
            "Associa": create_frame_associa(self.content, self.config),
            "Live": create_frame_live(self.content, self.config),
            "Correzione": create_frame_correzione(self.content, self.config),
            "Export": create_frame_export(self.content, self.config),
            "Domini": create_frame_domini(self.content, self.config),
            "Monitor Domini": create_frame_monitor_domini(self.content, self.config),
        }
        initial_mode = self.config["current_mode"].get()
        if initial_mode in ("Domini", "Monitor Domini"):
            initial_mode = "Live"
        self.show_mode(initial_mode)

    def show_mode(self, mode):
        if mode not in self.frames:
            mode = "Live"
        for frame in self.frames.values():
            frame.pack_forget()
        self.frames[mode].pack(fill="both", expand=True)
        self.config["current_mode"].set(mode)
        for button_mode, button in self.mode_buttons.items():
            active = button_mode == mode
            button.configure(
                bg="#075985" if active else "#ffffff",
                fg="#ffffff" if active else "#1e293b",
                activebackground="#0c4a6e" if active else "#e2e8f0",
                activeforeground="#ffffff" if active else "#0f172a",
                font=("Segoe UI", 9, "bold" if active else "normal"),
            )

    def _open_hidden_correction(self, _event=None):
        """Apre la modalità Correzione tramite la scorciatoia Ctrl+Alt+K."""
        self.show_mode("Correzione")
        return "break"

    def new_project(self):
        parent = filedialog.askdirectory(title="Dove salvare la nuova verifica?")
        if not parent:
            return
        name = simpledialog.askstring("Nuova verifica", "Nome della verifica:",
                                      initialvalue=self.config["verifica_name"].get(), parent=self.root)
        if not name:
            return
        class_name = simpledialog.askstring("Nuova verifica", "Classe:",
                                            initialvalue=self.config["class_name"].get(), parent=self.root)
        if not class_name:
            return
        extensions = self.choose_extensions_for_new_project()
        if extensions is None:
            return
        remote = filedialog.askdirectory(
            title="Dir Remota (Annulla per configurarla dopo)",
            initialdir=self.config["remote_directory"].get().strip() or "W:\\",
        )
        project = VerificationProject.create_in(parent, name, class_name=class_name, remote_directory=remote,
                                                extensions=extensions,
                                                alert_threshold=self.config["alert_threshold"].get())
        self._apply_project(project)
        project.save_session_file()
        # Una nuova verifica parte sempre dalla Preparazione: qui viene eseguito
        # subito il controllo in sola lettura delle cartelle remote.
        self.config["current_mode"].set("Preparazione")
        self._rebuild_frames()
        if remote:
            self.root.after_idle(lambda: self.config.get("refresh_preparazione", lambda: None)())

    def choose_extensions_for_new_project(self) -> str | None:
        """Mostra preset cumulabili e un campo libero prima di creare una verifica."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Estensioni della verifica")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        # L'annotazione evita il falso positivo di Pylance: inizialmente è None,
        # poi conferma() assegna la stringa scelta dall'utente.
        result: dict[str, str | None] = {"value": None}
        extensions_var = tk.StringVar(value=self.config["file_extension"].get().strip())
        preset_var = tk.StringVar(value="C / C++")

        body = ttk.Frame(dialog, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Quali file deve considerare questa verifica?",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3,
                                                           sticky="w", pady=(0, 6))
        ttk.Label(body, text="Scegli un preset per aggiungere estensioni al campo; il campo rimane modificabile.",
                  wraplength=500).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        ttk.Label(body, text="Preset:").grid(row=2, column=0, sticky="w", pady=4)
        preset_combo = ttk.Combobox(body, textvariable=preset_var, state="readonly",
                                    values=list(EXTENSION_PRESETS), width=22)
        preset_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        def add_preset(_event=None):
            existing = [part.lower() for part in extensions_var.get().replace(",", " ").replace(";", " ").split()]
            additions = EXTENSION_PRESETS[preset_var.get()].split()
            for extension in additions:
                normalized = extension.lower()
                if normalized not in existing:
                    existing.append(normalized)
            extensions_var.set(" ".join(existing))

        ttk.Button(body, text="Aggiungi", command=add_preset).grid(row=2, column=2, pady=4)
        preset_combo.bind("<<ComboboxSelected>>", add_preset)
        ttk.Label(body, text="Estensioni:").grid(row=3, column=0, sticky="w", pady=(10, 4))
        entry = ttk.Entry(body, textvariable=extensions_var, width=52)
        entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(6, 0), pady=(10, 4))
        ttk.Label(body, text="Esempio: .java .txt   (spazio, virgola o punto e virgola)",
                  foreground="#475569").grid(row=4, column=1, columnspan=2, sticky="w")
        body.columnconfigure(1, weight=1)

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=3, sticky="e", pady=(16, 0))

        def confirm():
            value = extensions_var.get().strip()
            if not value:
                messagebox.showwarning("Estensioni", "Indica almeno un'estensione.", parent=dialog)
                return
            result["value"] = value
            self.config["file_extension"].set(value)
            dialog.destroy()

        ttk.Button(buttons, text="Annulla", command=dialog.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Crea verifica", command=confirm).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        entry.focus_set()
        self.root.wait_window(dialog)
        return result["value"]

    def load_project(self):
        directory = filedialog.askdirectory(title=f"Seleziona la verifica ({PROJECT_FILE})")
        if directory:
            self._open_project(directory)

    def resume_project(self):
        directory = self._state_data().get("last_local_directory", "")
        if not directory:
            messagebox.showinfo("Riprendi", "Nessuna verifica recente disponibile.")
            return
        self._open_project(directory)

    def save_session(self):
        local = self.config["local_directory"].get().strip()
        if not local or not (Path(local) / PROJECT_FILE).is_file():
            messagebox.showwarning("Salva", "Apri prima una verifica SMX.")
            return
        try:
            self._sync_project_metadata()
            path = VerificationProject(local).save_session_file()
            messagebox.showinfo("Sessione salvata", f"Sessione aggiornata in:\n{path}")
        except Exception as exc:
            messagebox.showerror("Salva", str(exc))

    def save_session_as(self):
        local = self.config["local_directory"].get().strip()
        if not local or not (Path(local) / PROJECT_FILE).is_file():
            messagebox.showwarning("Salva con nome", "Apri prima una verifica SMX.")
            return
        default = f"{self.config['verifica_name'].get() or 'Verifica'}{SESSION_EXTENSION}"
        destination = filedialog.asksaveasfilename(
            title="Salva sessione completa con nome", defaultextension=SESSION_EXTENSION,
            initialfile=default, filetypes=[("Sessione SMX", f"*{SESSION_EXTENSION}")],
        )
        if not destination:
            return
        try:
            self._sync_project_metadata()
            path = VerificationProject(local).save_session_file(destination)
            messagebox.showinfo("Sessione salvata", f"Sessione completa salvata in:\n{path}")
        except Exception as exc:
            messagebox.showerror("Salva con nome", str(exc))

    def load_session(self):
        source = filedialog.askopenfilename(
            title="Carica sessione", filetypes=[("Sessione SMX", f"*{SESSION_EXTENSION}")]
        )
        if not source:
            return
        parent = filedialog.askdirectory(title="Dove estrarre la sessione caricata?")
        if not parent:
            return
        try:
            project = VerificationProject.load_session_file(source, parent)
            self._apply_project(project)
            self._rebuild_frames()
        except Exception as exc:
            messagebox.showerror("Carica sessione", str(exc))

    def _open_project(self, directory):
        try:
            self._apply_project(VerificationProject(directory))
            self._rebuild_frames()
        except Exception as exc:
            messagebox.showerror("Carica verifica", str(exc))

    def _apply_project(self, project):
        manifest = project.manifest
        self.config["local_directory"].set(str(project.root))
        self.config["remote_directory"].set(manifest.get("remote_directory", ""))
        self.config["verifica_name"].set(manifest.get("name", "Verifica"))
        self.config["class_name"].set(manifest.get("class_name", ""))
        self.config["student_associations"] = dict(manifest.get("student_associations", {}))
        self.config["domain_students"] = list(manifest.get("domain_students", []))
        self.config["file_extension"].set(manifest.get("file_extensions", ".cpp"))
        self.config["alert_threshold"].set(manifest.get("alert_threshold", 30))
        self.config["intro_text"].set(manifest.get("intro_text", ""))
        project.log_event("project_opened", {})
        self._save_state()

    def choose_local_directory(self):
        directory = filedialog.askdirectory(
            title="Seleziona la directory locale di lavoro (cartelle testXX)"
        )
        if directory:
            self.config["local_directory"].set(directory)
            self._save_state()

    def open_or_choose_local_directory(self):
        directory = self.config["local_directory"].get().strip()
        if directory and os.path.isdir(directory):
            data_handler.open_selected_directory(directory)
        else:
            self.choose_local_directory()

    def refresh_current_directory(self):
        mode = self.config["current_mode"].get().lower()
        callback = self.config.get(f"refresh_{mode}")
        if callable(callback):
            callback()
            return
        variable = self.config["remote_directory"] if mode in ("preparazione", "live") else self.config["local_directory"]
        variable.set(variable.get())

    def archive_project(self):
        local = self.config["local_directory"].get()
        if not local:
            messagebox.showwarning("Archivio", "Carica prima una verifica.")
            return
        destination = filedialog.askdirectory(title="Destinazione archivio")
        if destination:
            try:
                self._sync_project_metadata()
                path = VerificationProject(local).archive(destination)
                messagebox.showinfo("Archivio creato", path)
            except Exception as exc:
                messagebox.showerror("Archivio", str(exc))

    def open_association(self):
        self.show_mode("Associa")

    def show_startup_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Apri una verifica")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        tk.Label(dialog, text="Come vuoi procedere?", font=("Segoe UI", 12, "bold")).pack(
            padx=28, pady=(22, 12)
        )
        tk.Label(dialog, text="Puoi iniziare una nuova verifica, riprendere una sessione\n"
                              "oppure entrare direttamente nella correzione.").pack(padx=28, pady=(0, 16))

        def choose(action):
            dialog.destroy()
            action()

        tk.Button(dialog, text="Nuova verifica", width=28,
                  command=lambda: choose(self.new_project)).pack(padx=28, pady=4)
        tk.Button(dialog, text="Continua verifica esistente", width=28,
                  command=lambda: choose(self.resume_or_load_session)).pack(padx=28, pady=4)
        tk.Button(dialog, text="Vai alla correzione", width=28,
                  command=lambda: choose(self.open_correction_directly)).pack(padx=28, pady=4)
        tk.Button(dialog, text="Annulla", width=28, command=dialog.destroy).pack(padx=28, pady=(10, 20))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_height()) // 3
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def resume_or_load_session(self):
        """Permette di scegliere fra l'ultima verifica, un file o una cartella."""
        last_directory = self._state_data().get("last_local_directory", "")
        dialog = tk.Toplevel(self.root)
        dialog.title("Continua verifica esistente")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        body = tk.Frame(dialog, padx=24, pady=20)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="Come vuoi aprire la verifica?", font=("Segoe UI", 11, "bold")).pack(
            anchor="w", pady=(0, 8)
        )

        def choose(action):
            dialog.destroy()
            action()

        if last_directory and Path(last_directory).is_dir():
            tk.Label(body, text="Ultima verifica usata:", anchor="w").pack(fill="x")
            tk.Label(body, text=last_directory, anchor="w", fg="#075985", wraplength=540,
                     justify="left").pack(fill="x", pady=(0, 8))
            tk.Button(body, text="Apri ultima verifica", width=34,
                      command=lambda: choose(lambda: self._open_project(last_directory))).pack(pady=3)
        else:
            tk.Label(body, text="Non è disponibile un'ultima verifica locale valida.",
                     anchor="w", fg="#64748b").pack(fill="x", pady=(0, 8))

        tk.Button(body, text="Cerca file sessione .smxSession…", width=34,
                  command=lambda: choose(self.load_session)).pack(pady=3)
        tk.Button(body, text="Cerca cartella della verifica…", width=34,
                  command=lambda: choose(self.load_project)).pack(pady=3)
        tk.Button(body, text="Annulla", width=34, command=dialog.destroy).pack(pady=(10, 0))
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    def open_correction_directly(self):
        self.choose_local_directory()
        if self.config["local_directory"].get().strip():
            self.show_mode("Correzione")

    def save_configuration(self):
        self._sync_intro_from_widget()
        path = filedialog.asksaveasfilename(
            title="Salva configurazione", defaultextension=".json",
            filetypes=[("Configurazione SMX", "*.json")],
        )
        if not path:
            return
        data = {
            "schema_version": 2,
            "remote_directory": self.config["remote_directory"].get(),
            "local_directory": self.config["local_directory"].get(),
            # Compatibilità con i file della versione stabile.
            "selected_directory": self.config["local_directory"].get(),
            "file_extension": self.config["file_extension"].get(),
            "verifica_name": self.config["verifica_name"].get(),
            "class_name": self.config["class_name"].get(),
            "student_associations": self.config.get("student_associations", {}),
            "domain_students": self.config.get("domain_students", []),
            "alert_threshold": self.config["alert_threshold"].get(),
            "current_mode": self.config["current_mode"].get(),
            "intro_text": self.config["intro_text"].get(),
        }
        try:
            Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("Configurazione", "Configurazione salvata.")
        except OSError as exc:
            messagebox.showerror("Configurazione", f"Impossibile salvare il file:\n{exc}")

    def load_configuration(self):
        path = filedialog.askopenfilename(
            title="Carica configurazione", filetypes=[("Configurazione SMX", "*.json")]
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.config["remote_directory"].set(data.get("remote_directory", ""))
            self.config["local_directory"].set(data.get("local_directory") or data.get("selected_directory", ""))
            self.config["file_extension"].set(data.get("file_extension", ".cpp"))
            self.config["verifica_name"].set(data.get("verifica_name", ""))
            self.config["class_name"].set(data.get("class_name", ""))
            self.config["student_associations"] = dict(data.get("student_associations", {}))
            self.config["domain_students"] = list(data.get("domain_students", []))
            self.config["intro_text"].set(data.get("intro_text", ""))
            try:
                self.config["alert_threshold"].set(int(data.get("alert_threshold", 30)))
            except (TypeError, ValueError):
                self.config["alert_threshold"].set(30)
            mode = data.get("current_mode", "Preparazione")
            self.show_mode(mode if mode in self.frames else "Preparazione")
            intro_widget = self.config.get("intro_widget")
            if intro_widget is not None:
                intro_widget.delete("1.0", "end")
                intro_widget.insert("1.0", self.config["intro_text"].get())
            self._save_state()
            messagebox.showinfo("Configurazione", "Configurazione caricata.")
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Configurazione", f"Impossibile caricare il file:\n{exc}")

    def _sync_project_metadata(self):
        self._sync_intro_from_widget()
        local = self.config["local_directory"].get().strip()
        if not local or not (Path(local) / PROJECT_FILE).is_file():
            return
        VerificationProject(local).save(
            name=self.config["verifica_name"].get(),
            class_name=self.config["class_name"].get(),
            student_associations=self.config.get("student_associations", {}),
            domain_students=self.config.get("domain_students", []),
            remote_directory=self.config["remote_directory"].get(),
            file_extensions=self.config["file_extension"].get(),
            alert_threshold=self.config["alert_threshold"].get(),
            intro_text=self.config["intro_text"].get(),
        )

    def _sync_intro_from_widget(self):
        """Recupera il contenuto del widget Text prima di ogni salvataggio."""
        callback = self.config.get("sync_intro_text")
        if callable(callback):
            try:
                callback()
                return
            except (tk.TclError, RuntimeError):
                pass
        widget = self.config.get("intro_widget")
        if widget is not None:
            try:
                self.config["intro_text"].set(widget.get("1.0", "end-1c"))
            except (tk.TclError, AttributeError):
                pass

    def _state_data(self):
        try:
            return json.loads(APP_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_state(self):
        state = self._state_data()
        for key in ("remote_directory", "local_directory", "file_extension", "verifica_name", "class_name", "intro_text", "current_mode"):
            # Un vecchio stato può contenere una Dir Remota vuota: in quel caso
            # manteniamo il valore operativo predefinito W:\\.
            if key in state and (key != "remote_directory" or str(state[key]).strip()):
                self.config[key].set(state[key])

    def _save_state(self):
        # I frame possono registrare widget e callback nella config per
        # coordinarsi; soltanto questi valori Tk semplici sono impostazioni
        # persistenti dell'applicazione.
        persistent_keys = (
            "remote_directory", "local_directory", "file_extension",
            "verifica_name", "class_name", "intro_text", "alert_threshold", "current_mode",
        )
        state = {key: self.config[key].get() for key in persistent_keys}
        state["last_local_directory"] = self.config["local_directory"].get()
        APP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def close(self):
        local = self.config["local_directory"].get()
        if local and (Path(local) / PROJECT_FILE).is_file():
            try:
                self._sync_project_metadata()
                project = VerificationProject(local)
                project.log_event("application_closed", {})
                project.save_session_file()
            except Exception:
                pass
        self._save_state()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    SMXApplication(root)
    root.mainloop()
