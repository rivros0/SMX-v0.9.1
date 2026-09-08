import datetime
import difflib
import tkinter as tk
from tkinter import messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from utils import add_tooltip


class StudentDetailWindow(tk.Toplevel):
    """Storico studente con confronto affiancato fra due snapshot."""

    def __init__(self, parent, student_name, session_manager):
        super().__init__(parent)
        self.title(f"Dettaglio: {student_name}")
        self.geometry("1180x900")
        self.minsize(900, 700)
        self.session_manager = session_manager
        self.student_name = student_name
        self.history = session_manager.get_history(student_name)
        self.snapshots = list(reversed(self.history))

        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        graph_frame = ttk.LabelFrame(main, text="Incremento righe nel tempo")
        graph_frame.pack(fill="both", expand=True, pady=(0, 5))
        self.fig = Figure(figsize=(7, 2.4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self._draw_graph()

        controls = ttk.LabelFrame(main, text="Confronta due snapshot")
        controls.pack(fill="x", pady=5)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)
        tk.Label(controls, text="Versione a sinistra:").grid(row=0, column=0, padx=(8, 4), pady=7, sticky="w")
        tk.Label(controls, text="Versione a destra:").grid(row=0, column=2, padx=(12, 4), pady=7, sticky="w")
        values = [self._snapshot_label(item) for item in self.snapshots]
        self.left_combo = ttk.Combobox(controls, values=values, state="readonly")
        self.right_combo = ttk.Combobox(controls, values=values, state="readonly")
        self.left_combo.grid(row=0, column=1, padx=4, pady=7, sticky="ew")
        self.right_combo.grid(row=0, column=3, padx=4, pady=7, sticky="ew")
        if values:
            self.left_combo.current(1 if len(values) > 1 else 0)
            self.right_combo.current(0)
        btn_compare = ttk.Button(controls, text="Confronta", command=self._render_comparison)
        btn_compare.grid(
            row=0, column=4, padx=(8, 4), pady=7
        )
        btn_restore = ttk.Button(controls, text="Ripristina versione destra", command=self._restore)
        btn_restore.grid(
            row=0, column=5, padx=(4, 8), pady=7
        )
        add_tooltip(btn_compare, "Confronta i due snapshot selezionati affiancando le differenze.")
        add_tooltip(btn_restore, "Scrive lo snapshot di destra nella cartella remota dell'alunno dopo conferma.")
        self.left_combo.bind("<<ComboboxSelected>>", lambda _event: self._render_comparison())
        self.right_combo.bind("<<ComboboxSelected>>", lambda _event: self._render_comparison())

        diff_frame = ttk.LabelFrame(main, text="Differenze affiancate")
        diff_frame.pack(fill="both", expand=True, pady=5)
        diff_frame.columnconfigure(0, weight=1)
        diff_frame.columnconfigure(1, weight=1)
        diff_frame.rowconfigure(1, weight=1)
        self.left_title = ttk.Label(diff_frame, text="Versione a sinistra")
        self.right_title = ttk.Label(diff_frame, text="Versione a destra")
        self.left_title.grid(row=0, column=0, padx=6, pady=(6, 2), sticky="w")
        self.right_title.grid(row=0, column=1, padx=6, pady=(6, 2), sticky="w")

        left_frame = tk.Frame(diff_frame)
        right_frame = tk.Frame(diff_frame)
        left_frame.grid(row=1, column=0, padx=(6, 2), pady=(0, 6), sticky="nsew")
        right_frame.grid(row=1, column=1, padx=(2, 6), pady=(0, 6), sticky="nsew")
        left_frame.rowconfigure(0, weight=1)
        left_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(0, weight=1)
        right_frame.columnconfigure(0, weight=1)
        self.left_text = tk.Text(left_frame, wrap="none", font=("Consolas", 10), undo=False)
        self.right_text = tk.Text(right_frame, wrap="none", font=("Consolas", 10), undo=False)
        self.left_text.grid(row=0, column=0, sticky="nsew")
        self.right_text.grid(row=0, column=0, sticky="nsew")
        self.diff_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self._scroll_both)
        self.diff_scrollbar.grid(row=0, column=1, sticky="ns")
        self.left_text.configure(yscrollcommand=self._set_scrollbar)
        self.right_text.configure(yscrollcommand=self._set_scrollbar)
        for text in (self.left_text, self.right_text):
            text.tag_configure("changed", background="#fee2e2", foreground="#b91c1c")
            text.tag_configure("added", background="#dcfce7", foreground="#15803d")
            text.tag_configure("removed", background="#fee2e2", foreground="#b91c1c")
            text.bind("<MouseWheel>", self._scroll_with_wheel, add="+")

        self._render_comparison()

    @staticmethod
    def _snapshot_label(item):
        return f"{item['timestamp']} | {item['line_count']} righe | {item['snapshot_id']}"

    def _selected_snapshot(self, combo):
        index = combo.current()
        if index < 0 or index >= len(self.snapshots):
            return None
        return self.snapshots[index]

    def _draw_graph(self):
        self.ax.clear()
        if not self.history:
            self.ax.set_title("Nessun dato disponibile")
        else:
            times = [datetime.datetime.fromisoformat(item["timestamp"]) for item in self.history]
            lines = [item["line_count"] for item in self.history]
            self.ax.plot(times, lines, marker="o", color="#046276")
            self.ax.set_ylabel("Righe")
            self.ax.grid(True, alpha=.3)
            self.fig.autofmt_xdate()
        self.canvas.draw()

    def _clear_comparison(self):
        for text in (self.left_text, self.right_text):
            text.delete("1.0", "end")

    @staticmethod
    def _line_or_empty(lines, index):
        return lines[index] if index < len(lines) else ""

    def _insert_pair(self, left_line, right_line, left_tag=None, right_tag=None):
        if left_tag:
            self.left_text.insert("end", left_line + "\n", left_tag)
        else:
            self.left_text.insert("end", left_line + "\n")
        if right_tag:
            self.right_text.insert("end", right_line + "\n", right_tag)
        else:
            self.right_text.insert("end", right_line + "\n")

    def _render_comparison(self):
        self._clear_comparison()
        left = self._selected_snapshot(self.left_combo)
        right = self._selected_snapshot(self.right_combo)
        if left is None or right is None:
            self._insert_pair("Nessuno snapshot selezionato.", "")
            return
        self.left_title.config(text="Sinistra: " + self._snapshot_label(left))
        self.right_title.config(text="Destra: " + self._snapshot_label(right))
        left_lines = left.get("content", "").splitlines()
        right_lines = right.get("content", "").splitlines()
        matcher = difflib.SequenceMatcher(None, left_lines, right_lines)
        for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            left_chunk = left_lines[left_start:left_end]
            right_chunk = right_lines[right_start:right_end]
            if tag == "equal":
                for left_line, right_line in zip(left_chunk, right_chunk):
                    self._insert_pair(left_line, right_line)
                continue
            max_lines = max(len(left_chunk), len(right_chunk))
            for index in range(max_lines):
                left_line = self._line_or_empty(left_chunk, index)
                right_line = self._line_or_empty(right_chunk, index)
                if tag == "replace":
                    # Come nel diff a colonne: la vecchia riga è rossa, la nuova verde.
                    self._insert_pair(left_line, right_line, "removed", "added")
                elif tag == "delete":
                    self._insert_pair(left_line, "", "removed", "removed")
                else:  # insert
                    self._insert_pair("", right_line, "added", "added")
        for text in (self.left_text, self.right_text):
            text.yview_moveto(0)

    def _scroll_both(self, *args):
        self.left_text.yview(*args)
        self.right_text.yview(*args)

    def _set_scrollbar(self, first, last):
        self.diff_scrollbar.set(first, last)

    def _scroll_with_wheel(self, event):
        amount = -1 if event.delta > 0 else 1
        self.left_text.yview_scroll(amount, "units")
        self.right_text.yview_scroll(amount, "units")
        return "break"

    def _restore(self):
        item = self._selected_snapshot(self.right_combo)
        if item is None:
            messagebox.showwarning("Recupero", "Seleziona la versione a destra.", parent=self)
            return
        remote = self.session_manager.remote_directory
        if not remote:
            messagebox.showwarning("Recupero", "La Dir Remota non è collegata a questa verifica.", parent=self)
            return
        question = (f"Scrivere la versione del {item['timestamp']} nella cartella remota\n"
                    f"{remote} / {self.student_name}?\n\n"
                    "Il contenuto remoto attuale verrà prima salvato in 00_SMXRecovery.")
        if not messagebox.askyesno("Conferma recupero", question, parent=self):
            return
        try:
            target, backup = self.session_manager.restore(self.student_name, item["snapshot_id"])
            messagebox.showinfo("Recupero completato", f"Ripristinato in:\n{target}\n\nBackup:\n{backup}", parent=self)
        except Exception as exc:
            messagebox.showerror("Recupero non riuscito", str(exc), parent=self)
