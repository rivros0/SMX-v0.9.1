import os
import datetime
from session_manager import SessionManager
from student_card_widget import StudentCard
from activity_heatmap import ActivityHeatmap
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from utils import enable_mousewheel, scan_remote_directory, add_tooltip

SCAN_INTERVAL = 30000  # 30 seconds

def create_frame_live(root, global_config):
    frame = tk.Frame(root, bg='#046276')
    monitoring_active = True
    
    # === Configurazione Scan === #
    btn_monitoring = tk.Button(
        frame, text='● Monitoraggio attivo', width=23,
        bg='#bbf7d0', fg='#14532d', font=('Segoe UI', 9, 'bold'),
    )
    btn_monitoring.grid(row=0, column=0, padx=(10, 8), pady=5, sticky='w')
    # Il pulsante è anche l'indicatore visivo dello stato del monitoraggio.

    lbl_ext = tk.Label(frame, text='Estensioni:', bg='white')
    lbl_ext.grid(row=0, column=1, sticky='w', padx=5, pady=5)

    entry_ext = tk.Entry(
        frame,
        width=30,
        textvariable=global_config['file_extension'],
    )
    entry_ext.grid(row=0, column=2, padx=5, pady=5, sticky='w')

    lbl_threshold = tk.Label(frame, text='Soglia Alert:', bg='white')
    lbl_threshold.grid(row=0, column=3, sticky='w', padx=5, pady=5)

    threshold_source = global_config.get('alert_threshold', 30)
    threshold_value = threshold_source.get() if hasattr(threshold_source, 'get') else threshold_source
    threshold_var = tk.StringVar(value=str(threshold_value))
    entry_threshold = tk.Entry(
        frame,
        width=10,
        textvariable=threshold_var,
    )
    entry_threshold.grid(row=0, column=4, padx=5, pady=5, sticky='w')

    # === Pulsanti controllo === #
    btn_scan = tk.Button(frame, text='Scan', width=15)
    btn_scan.grid(row=0, column=5, padx=5, pady=5)

    btn_heatmap = tk.Button(frame, text='Heatmap attività', width=17)
    btn_heatmap.grid(row=0, column=6, padx=5, pady=5)

    btn_clear = tk.Button(frame, text='Pulisci Dashboard', width=15)
    btn_clear.grid(row=0, column=7, padx=5, pady=5)

    # === Dashboard Area con Scrollbar === #
    # Contenitore esterno per la scorrimento
    dashboard_outer = tk.Frame(frame, bg='#e1e1e1', bd=2, relief='ridge')
    dashboard_outer.grid(row=1, column=0, columnspan=8, padx=10, pady=10, sticky='nsew')
    frame.grid_rowconfigure(1, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_columnconfigure(1, weight=1)
    frame.grid_columnconfigure(2, weight=1)
    frame.grid_columnconfigure(3, weight=1)
    frame.grid_columnconfigure(4, weight=1)
    frame.grid_columnconfigure(5, weight=1)
    frame.grid_columnconfigure(6, weight=1)
    frame.grid_columnconfigure(7, weight=1)

    canvas = tk.Canvas(dashboard_outer, bg='white', highlightthickness=0)
    scrollbar = ttk.Scrollbar(dashboard_outer, orient="vertical", command=canvas.yview)
    
    # Il contenitore interno dove andremo a mettere le card
    dashboard_container = tk.Frame(canvas, bg='white')
    cards = {}  # {student_name: StudentCard}
    last_results = []
    dashboard_layout_job = None
    
    # Configurazione del canvas
    dashboard_window = canvas.create_window(
        (0, 0), window=dashboard_container, anchor="nw", tags="dashboard_inner"
    )
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def on_canvas_configure(event):
        # Forza la larghezza del contenitore interno a corrispondere alla larghezza del canvas
        canvas.itemconfigure(dashboard_window, width=event.width)
        canvas.configure(scrollregion=canvas.bbox("all"))
        if last_results:
            schedule_dashboard_layout()

    canvas.bind("<Configure>", on_canvas_configure)
    dashboard_container.bind(
        "<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    # === Area Log Live === #
    lbl_log = tk.Label(frame, text='Log di Sistema:', bg='white')
    lbl_log.grid(row=2, column=0, sticky='nw', padx=10, pady=(0, 2))
    
    log_area = scrolledtext.ScrolledText(frame, height=10, font=("Consolas", 9))
    log_area.grid(row=3, column=0, columnspan=8, padx=10, pady=(0, 5), sticky='nsew')
    enable_mousewheel(log_area)

    lbl_esito = tk.Label(frame, text='', fg='green', bg='white')
    lbl_esito.grid(row=4, column=1, columnspan=7, sticky='w', padx=5, pady=5)

    auto_job_id = None

    def build_session_manager():
        local_dir = global_config['local_directory'].get().strip()
        if not local_dir:
            return None
        initial_threshold = 30
        try:
            initial_threshold = int(threshold_var.get())
        except (TypeError, ValueError):
            # Un valore non numerico non blocca la frame: resta la soglia predefinita.
            pass
            
        try:
            return SessionManager(
                local_directory=local_dir,
                verification_name=global_config['verifica_name'].get(),
                alert_threshold=initial_threshold,
                remote_directory=global_config['remote_directory'].get().strip(),
                extensions=global_config['file_extension'].get().strip(),
            )
        except (OSError, ValueError):
            # Può rimanere in memoria un vecchio percorso locale che non è un
            # progetto SMX. Live deve restare apribile e chiedere di crearne/caricarne uno.
            return None

    session_manager = build_session_manager()
    heatmap_window = ActivityHeatmap(frame.winfo_toplevel())
    is_finalized = bool(session_manager and session_manager.project.manifest.get("status") == "finalized")
    if is_finalized:
        monitoring_active = False
        btn_monitoring.config(text="● Verifica terminata", bg="#e2e8f0", fg="#475569", state="disabled")

    def log_to_ui(message):
        log_area.insert(tk.END, f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {message}\n")
        log_area.see(tk.END)

    def render_dashboard(risultati):
        """Ridisegna la griglia senza cambiare la dimensione delle card."""
        cards.clear()
        for widget in dashboard_container.winfo_children():
            widget.destroy()
        if not risultati or session_manager is None:
            return

        # Le card restano larghe 460 px: l'allargamento della finestra aggiunge
        # colonne (fino a tre) invece di dilatare le righe esistenti.
        available_width = max(canvas.winfo_width(), StudentCard.CARD_WIDTH + 12)
        columns = min(3, max(1, available_width // (StudentCard.CARD_WIDTH + 8)))
        for column in range(columns):
            dashboard_container.grid_columnconfigure(column, weight=0,
                                                     minsize=StudentCard.CARD_WIDTH + 8)

        def create_header(column):
            header = tk.Frame(dashboard_container, bg="#e2e8f0", width=StudentCard.CARD_WIDTH, height=30)
            header.grid(row=0, column=column, padx=4, pady=(4, 1), sticky="w")
            header.grid_propagate(False)
            header.columnconfigure(3, weight=1)
            for header_column, text, width in (
                (0, "Test / alunno", 15), (1, "Righe", 12),
                (2, "Aggiornamento", 17), (3, "Andamento", 8), (4, "", 8),
            ):
                tk.Label(header, text=text, bg="#e2e8f0", fg="#334155", anchor="w",
                         width=width, font=("Segoe UI", 8, "bold")).grid(
                    row=0, column=header_column,
                    sticky="ew" if header_column == 3 else "w", padx=5, pady=6
                )

        for column in range(columns):
            create_header(column)
        for index, (nome_dir, _num_file, _num_righe, _files, _ultima_mod, _age_str) in enumerate(risultati):
            column = index % columns
            row = index // columns + 1
            display_name = global_config.get("student_associations", {}).get(nome_dir, nome_dir)
            if "@" in display_name:
                display_name = display_name.split("@", 1)[0]
            cards[nome_dir] = StudentCard(dashboard_container, nome_dir, session_manager, row, column,
                                          display_name=display_name)
        dashboard_container.update_idletasks()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def schedule_dashboard_layout():
        nonlocal dashboard_layout_job
        if dashboard_layout_job is not None:
            frame.after_cancel(dashboard_layout_job)
        dashboard_layout_job = frame.after(120, lambda: render_dashboard(last_results))

    def raccogli_copia_locale():
        """Copia soltanto test01…test30 dal server alla verifica locale."""
        local_dir = global_config['local_directory'].get().strip()
        remote_dir = global_config['remote_directory'].get().strip()
        if not local_dir or not remote_dir:
            lbl_esito.config(text="⚠️ Imposta Dir Remota e carica una verifica locale.", fg="red")
            return
        try:
            from project_manager import VerificationProject
            project = VerificationProject(local_dir)
            project.save(
                remote_directory=remote_dir,
                file_extensions=global_config['file_extension'].get().strip(),
            )
            collection = project.copy_from_remote(return_details=True)
            copied = collection["folders"]
            removed_files = collection["removed_files"]
            session_path = project.save_session_file()
            message = (
                f"✅ Raccolte {len(copied)} cartelle test nella Dir Locale.\n"
                f"Salvate in: {local_dir}"
            )
            lbl_esito.config(text=message, fg="green")
            log_to_ui(message)
            if removed_files:
                log_to_ui(f"Rimossi {len(removed_files)} file locali non più presenti sul server:")
                for removed_file in removed_files:
                    log_to_ui(f"  - {removed_file}")
            else:
                log_to_ui("Nessun file locale obsoleto da rimuovere.")
            log_to_ui(f"Sessione SMX aggiornata: {session_path}")
            for refresh_key in ("refresh_correzione", "refresh_export"):
                refresh = global_config.get(refresh_key)
                if callable(refresh):
                    refresh()
        except Exception as exc:
            message = f"⚠️ Raccolta non riuscita: {exc}"
            lbl_esito.config(text=message, fg="red")
            log_to_ui(message)

    collection_actions = tk.Frame(frame, bg="#046276")
    collection_actions.grid(row=4, column=0, padx=(10, 5), pady=5, sticky="w")
    btn_collect = tk.Button(
        collection_actions, text="Raccogli copia locale", command=raccogli_copia_locale,
        bg="#d9f99d", font=("Segoe UI", 9, "bold"),
    )
    btn_collect.pack(side="left")

    def finalize_delivery():
        """Crea una consegna immutabile e conserva testXX visibili nella Dir Locale."""
        nonlocal monitoring_active, auto_job_id, is_finalized
        local_dir = global_config['local_directory'].get().strip()
        remote_dir = global_config['remote_directory'].get().strip()
        if not local_dir or not remote_dir:
            messagebox.showwarning("Finalizza consegna", "Imposta Dir Remota e apri una verifica locale.")
            return
        confirmed = messagebox.askyesno(
            "Finalizza consegna",
            "SMX eseguirà un'ultima raccolta dal server e creerà una sessione CONSEGNA immutabile.\n\n"
            "Le cartelle testXX resteranno visibili nella Dir Locale anche senza SMX. "
            "Il monitoraggio verrà terminato.\n\nProcedere?",
        )
        if not confirmed:
            return
        try:
            from project_manager import VerificationProject
            project = VerificationProject(local_dir)
            project.save(
                remote_directory=remote_dir,
                file_extensions=global_config['file_extension'].get().strip(),
            )
            collection, delivery_path = project.finalize_delivery()
            removed_files = collection["removed_files"]
            message = (
                "✅ Consegna finalizzata.\n"
                f"Cartelle testXX disponibili in: {local_dir}\n"
                f"Sessione immutabile: {delivery_path}"
            )
            lbl_esito.config(text="✅ Consegna finalizzata: cartelle testXX e sessione CONSEGNA salvate.", fg="green")
            log_to_ui(message)
            if removed_files:
                log_to_ui(f"Rimossi {len(removed_files)} file locali obsoleti durante la raccolta finale.")
                for removed_file in removed_files:
                    log_to_ui(f"  - {removed_file}")

            monitoring_active = False
            is_finalized = True
            if auto_job_id is not None:
                frame.after_cancel(auto_job_id)
            auto_job_id = None
            btn_monitoring.config(text="● Verifica terminata", bg="#e2e8f0", fg="#475569", state="disabled")
            btn_scan.config(state="disabled")
            btn_collect.config(state="disabled")
            btn_finalize.config(text="Consegna finalizzata", state="disabled", bg="#e2e8f0")
            messagebox.showinfo("Consegna finalizzata", message)
        except Exception as exc:
            message = f"⚠️ Finalizzazione non riuscita: {exc}"
            lbl_esito.config(text=message, fg="red")
            log_to_ui(message)

    btn_finalize = tk.Button(
        collection_actions, text="Finalizza consegna e termina verifica", command=finalize_delivery,
        bg="#fef08a", font=("Segoe UI", 9, "bold"),
    )
    btn_finalize.pack(side="left", padx=(8, 0))

    def aggiorna_dashboard():
        nonlocal auto_job_id, session_manager, last_results

        def schedule_next_scan():
            """Mantiene vivo il monitoraggio anche dopo un errore temporaneo del server."""
            nonlocal auto_job_id
            if auto_job_id is not None:
                try:
                    frame.after_cancel(auto_job_id)
                except Exception:
                    pass
            auto_job_id = frame.after(SCAN_INTERVAL, aggiorna_dashboard) if monitoring_active else None

        if is_finalized:
            return

        path = global_config['remote_directory'].get().strip()
        estensioni = global_config['file_extension'].get().strip()

        if not path or not os.path.isdir(path):
            lbl_esito.config(text="⚠️ Percorso non valido o vuoto.", fg="red")
            schedule_next_scan()
            return

        if session_manager is None:
            session_manager = build_session_manager()
        if session_manager is None:
            lbl_esito.config(text="⚠️ Crea o carica una verifica per attivare storico e recupero.", fg="red")
            schedule_next_scan()
            return
        try:
            session_manager.alert_threshold = int(threshold_var.get())
            global_config["alert_threshold"].set(session_manager.alert_threshold)
        except (TypeError, ValueError):
            pass
        try:
            # La scansione resta sequenziale per limitare il carico sul server scolastico.
            risultati = scan_remote_directory(path, estensioni, count_lines=True)
        except OSError as exc:
            log_to_ui(f"Errore durante la scansione remota: {exc}")
            lbl_esito.config(text="⚠️ Scansione non riuscita: verrà ritentata automaticamente.", fg="red")
            schedule_next_scan()
            return

        if session_manager and risultati:
            campioni_per_salvataggio = []
            for nome_dir, num_file, num_righe, files, ultima_mod, age_str in risultati:
                campioni_per_salvataggio.append({
                    'name': nome_dir,
                    'line_count': num_righe,
                    'source_folder': os.path.join(path, nome_dir),
                })
            captured = session_manager.add_sample(campioni_per_salvataggio)
            log_to_ui(f"Scansione sequenziale completata: {len(risultati)} cartelle test rilevate.")
            for entry in captured:
                if entry.get("alert_delta") is not None:
                    log_to_ui(
                        f"⚠️ ALERT {entry['file_name']}: +{entry['alert_delta']} righe "
                        f"(soglia {session_manager.alert_threshold})."
                    )
        else:
            log_to_ui("Scan non eseguita o dati non disponibili.")

        if not risultati:
            lbl_esito.config(text="Nessun dato trovato nella directory.", fg="orange")
            schedule_next_scan()
            return
        associations = global_config.get("student_associations", {})
        # Le cartelle non associate continuano a essere scansionate, salvate
        # nello storico e raccolte localmente; non appesantiscono la dashboard.
        last_results = [result for result in risultati if associations.get(result[0])]
        if not last_results:
            lbl_esito.config(text="Associa gli alunni per visualizzare le card Live.", fg="orange")
        render_dashboard(last_results)
        # La heatmap, se già aperta, segue i nuovi campioni appena salvati.
        heatmap_window.refresh(
            session_manager,
            [result[0] for result in last_results],
            associations,
            session_manager.alert_threshold,
        )
        
        schedule_next_scan()

    def clear_dashboard():
        nonlocal last_results
        last_results = []
        cards.clear()
        for widget in dashboard_container.winfo_children():
            widget.destroy()
        canvas.configure(scrollregion=canvas.bbox("all"))

    def show_activity_heatmap():
        """Apre la vista storica Live senza avviare ulteriori scansioni remote."""
        if session_manager is None:
            messagebox.showwarning(
                "Heatmap attività",
                "Crea o carica una verifica per visualizzare i campioni del monitoraggio.",
            )
            return
        associations = global_config.get("student_associations", {})
        students = [result[0] for result in last_results]
        if not students:
            students = [name for name in associations if associations.get(name)]
        try:
            threshold = int(threshold_var.get())
        except (TypeError, ValueError):
            threshold = session_manager.alert_threshold
        heatmap_window.show(session_manager, students, associations, threshold)
        log_to_ui("Heatmap attività aperta: usa esclusivamente i campioni già registrati.")

    btn_scan.config(command=aggiorna_dashboard)
    btn_clear.config(command=clear_dashboard)
    btn_heatmap.config(command=show_activity_heatmap)

    def toggle_monitoring():
        nonlocal monitoring_active, auto_job_id
        monitoring_active = not monitoring_active
        if monitoring_active:
            btn_monitoring.config(text='● Monitoraggio attivo', bg='#bbf7d0', fg='#14532d')
            log_to_ui("Monitoraggio automatico attivato.")
            aggiorna_dashboard()
        else:
            if auto_job_id is not None:
                try:
                    frame.after_cancel(auto_job_id)
                except Exception:
                    pass
            auto_job_id = None
            btn_monitoring.config(text='○ Monitoraggio sospeso', bg='#fee2e2', fg='#991b1b')
            log_to_ui("Monitoraggio automatico sospeso: è comunque possibile eseguire Scan manuale.")

    btn_monitoring.config(command=toggle_monitoring)

    # Suggerimenti sintetici per le operazioni che incidono sul flusso Live.
    add_tooltip(btn_monitoring, "Attiva o sospende le scansioni automatiche. Scan manuale resta sempre disponibile.")
    add_tooltip(btn_scan, "Esegue subito una scansione sequenziale delle cartelle test; la dashboard mostra solo quelle associate.")
    add_tooltip(btn_heatmap, "Visualizza gli incrementi di righe nel tempo senza eseguire altre letture del server.")
    add_tooltip(btn_clear, "Nasconde le card dalla dashboard; non elimina storico, file o associazioni.")
    add_tooltip(btn_collect, "Copia tutte le cartelle test nella Dir Locale per proseguire correzione ed export.")
    add_tooltip(btn_finalize, "Esegue l'ultima raccolta, crea una sessione CONSEGNA immutabile e ferma il monitoraggio.")

    if is_finalized:
        btn_scan.config(state="disabled")
        btn_collect.config(state="disabled")
        btn_finalize.config(text="Consegna finalizzata", state="disabled", bg="#e2e8f0")

    auto_job_id = frame.after(SCAN_INTERVAL, aggiorna_dashboard) if monitoring_active else None

    global_config["refresh_live"] = aggiorna_dashboard

    return frame
