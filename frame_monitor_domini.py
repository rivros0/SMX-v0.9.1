"""Interfaccia Tk per il monitor pubblico dei domini Altervista."""
import csv
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from domain_monitor import DomainMonitor, MONITOR_DIR, normalize_url


def create_frame_monitor_domini(root, config):
    frame = tk.Frame(root, bg="#f8fafc")
    students = config.setdefault("domain_students", [])
    events = queue.Queue()
    running = {"value": False}
    status = tk.StringVar(value="Aggiungi gli alunni e avvia l'acquisizione.")

    tk.Label(frame, text="Monitor Domini Altervista", font=("Segoe UI", 16, "bold"), bg="#f8fafc", fg="#0f172a").pack(anchor="w", padx=18, pady=(16, 2))
    tk.Label(frame, text="Lettura pubblica, limitata e rispettosa di robots.txt. Gli snapshot restano nella verifica SMX.", bg="#f8fafc", fg="#475569").pack(anchor="w", padx=18, pady=(0, 12))
    table_box = tk.Frame(frame, bg="#f8fafc")
    table_box.pack(fill="both", expand=True, padx=18)
    columns = ("alunno", "dominio", "stato")
    table = ttk.Treeview(table_box, columns=columns, show="headings", height=13)
    for col, label, width in (("alunno", "Alunno", 220), ("dominio", "Dominio / URL", 520), ("stato", "Ultimo esito", 250)):
        table.heading(col, text=label); table.column(col, width=width, anchor="w")
    table.pack(side="left", fill="both", expand=True)
    scrollbar = ttk.Scrollbar(table_box, orient="vertical", command=table.yview); scrollbar.pack(side="right", fill="y")
    table.configure(yscrollcommand=scrollbar.set)

    log = tk.Text(frame, height=9, state="disabled", bg="#0f172a", fg="#dbeafe", font=("Consolas", 9))
    log.pack(fill="x", padx=18, pady=12)

    def append(message):
        log.configure(state="normal"); log.insert("end", message + "\n"); log.see("end"); log.configure(state="disabled")

    def refresh():
        table.delete(*table.get_children())
        for i, item in enumerate(students):
            table.insert("", "end", iid=str(i), values=(item.get("name", ""), item.get("url", ""), item.get("status", "Mai acquisito")))

    def persist():
        config["domain_students"] = students
        local = config["local_directory"].get().strip()
        if local and (Path(local) / "00_SMXSystem" / "smx_project.json").is_file():
            from project_manager import VerificationProject
            VerificationProject(local).save(domain_students=students)

    def add_student():
        name = simpledialog.askstring("Alunno", "Nome o codice dell'alunno:", parent=frame)
        if not name: return
        url = simpledialog.askstring("Dominio", "Dominio Altervista o URL pubblico:", parent=frame)
        if not url: return
        try: url = normalize_url(url)
        except ValueError as exc: messagebox.showerror("Dominio", str(exc), parent=frame); return
        students.append({"name": name.strip(), "url": url, "status": "Mai acquisito"}); persist(); refresh()

    def remove_student():
        selection = table.selection()
        if not selection: return
        index = int(selection[0]); students.pop(index); persist(); refresh()

    def import_csv():
        path = filedialog.askopenfilename(title="Importa elenco domini", filetypes=[("CSV", "*.csv")])
        if not path: return
        try:
            with open(path, encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                loaded = []
                for row in reader:
                    name = (row.get("alunno") or row.get("nome") or row.get("cognome") or "").strip()
                    url = (row.get("dominio") or row.get("url") or "").strip()
                    if name and url: loaded.append({"name": name, "url": normalize_url(url), "status": "Mai acquisito"})
            students[:] = loaded; persist(); refresh(); append(f"Importati {len(loaded)} domini da CSV.")
        except Exception as exc: messagebox.showerror("Importa CSV", str(exc), parent=frame)

    def scan_all():
        local = config["local_directory"].get().strip()
        if running["value"] or not students: return
        if not local or not os.path.isdir(local):
            messagebox.showwarning("Monitor domini", "Apri o crea prima una verifica SMX con una Dir Locale.", parent=frame); return
        running["value"] = True; status.set("Acquisizione in corso…")
        def worker():
            monitor = DomainMonitor(local)
            for index, item in enumerate(students):
                events.put(("log", f"Acquisizione: {item['name']} — {item['url']}"))
                try:
                    result = monitor.scan(item["name"], item["url"], progress=lambda done, maximum, who: events.put(("progress", f"{who}: {done}/{maximum} pagine")))
                    item["status"] = f"OK: {len(result['files'])} risorse"
                    events.put(("log", f"Report: {result['report_path']}"))
                except Exception as exc:
                    item["status"] = f"Errore: {exc}"; events.put(("log", item["status"]))
            events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def poll():
        try:
            while True:
                kind, value = events.get_nowait()
                if kind in ("log", "progress"): append(value); status.set(value)
                elif kind == "done":
                    running["value"] = False; persist(); refresh(); status.set("Acquisizione completata."); append("Acquisizione completata.")
        except queue.Empty: pass
        frame.after(250, poll)

    buttons = tk.Frame(frame, bg="#f8fafc"); buttons.pack(fill="x", padx=18, pady=(0, 8))
    for text, command in (("Aggiungi alunno", add_student), ("Importa CSV", import_csv), ("Rimuovi selezionato", remove_student), ("Acquisisci e genera report", scan_all)):
        tk.Button(buttons, text=text, command=command, padx=10, pady=5).pack(side="left", padx=(0, 7))
    tk.Label(frame, textvariable=status, bg="#f8fafc", fg="#075985").pack(anchor="w", padx=18, pady=(0, 12))
    refresh(); poll()
    return frame
