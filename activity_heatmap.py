"""Heatmap dell'attività Live costruita esclusivamente dai campioni già salvati."""

import datetime as dt

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.figure import Figure


def _short_student_name(value):
    """Riduce un'email alla parte utile per mantenere leggibili le righe."""
    value = str(value or "").strip()
    return value.split("@", 1)[0] if "@" in value else value


def build_activity_matrix(session_manager, students, interval_seconds=30, max_columns=24):
    """Restituisce delta di righe per alunno e intervallo di monitoraggio.

    Non interroga il server: usa solo le timeline presenti in ``00_SMXHistory``.
    I timestamp vengono raccolti in intervalli di 30 secondi, coerenti con lo
    scan Live, affinché gli studenti restino allineati pur essendo letti uno
    alla volta nella scansione sequenziale.
    """
    interval_seconds = max(1, int(interval_seconds))
    changes = {}
    all_buckets = set()

    for student in students:
        previous_lines = None
        student_changes = {}
        for sample in session_manager.get_history(student):
            try:
                timestamp = dt.datetime.fromisoformat(sample["timestamp"])
                bucket = int(timestamp.timestamp() // interval_seconds) * interval_seconds
                line_count = int(sample.get("line_count", 0))
            except (KeyError, TypeError, ValueError):
                continue
            delta = 0 if previous_lines is None or sample.get("baseline") else line_count - previous_lines
            previous_lines = line_count
            # Una cartella produce al massimo uno snapshot per intervallo; se
            # accade più volte, il valore più recente è quello significativo.
            student_changes[bucket] = delta
            all_buckets.add(bucket)
        changes[student] = student_changes

    buckets = sorted(all_buckets)[-max_columns:]
    matrix = [[changes.get(student, {}).get(bucket, 0) for bucket in buckets] for student in students]
    return matrix, buckets


class ActivityHeatmap:
    """Finestra aggiornata dal Live per visualizzare incrementi e alert."""

    def __init__(self, master):
        self.master = master
        self.dialog = None
        self.figure = None
        self.axes = None
        self.canvas = None
        self.session_manager = None
        self.students = []
        self.associations = {}
        self.threshold = 30
        self._rows = []
        self._buckets = []

    def show(self, session_manager, students, associations, threshold):
        self.refresh(session_manager, students, associations, threshold)
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.deiconify()
            self.dialog.lift()
            self.dialog.focus_force()
            return

        self.dialog = tk.Toplevel(self.master)
        self.dialog.title("SMX – Heatmap attività Live")
        self.dialog.geometry("980x600")
        self.dialog.minsize(680, 420)
        self.dialog.protocol("WM_DELETE_WINDOW", self._close)

        legend = tk.Label(
            self.dialog,
            text="Attività per intervallo di scansione: bianco = invariato, verde = incremento, rosso = oltre soglia, arancione = diminuzione. Clicca una cella per il dettaglio.",
            anchor="w", justify="left", padx=12, pady=8,
        )
        legend.pack(fill="x")

        self.figure = Figure(figsize=(9, 5), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.20, right=0.98, bottom=0.18, top=0.92)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.dialog)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect("button_press_event", self._on_click)
        self._draw()

    def refresh(self, session_manager, students, associations, threshold):
        """Riceve lo stato più recente senza creare nuove letture del server."""
        self.session_manager = session_manager
        self.students = list(students)
        self.associations = dict(associations or {})
        try:
            self.threshold = max(1, int(threshold))
        except (TypeError, ValueError):
            self.threshold = 30
        if self.dialog is not None and self.dialog.winfo_exists() and self.canvas is not None:
            self._draw()

    def _draw(self):
        if self.axes is None:
            return
        self.axes.set_axis_on()
        self.axes.clear()
        self._rows = list(self.students)
        matrix, self._buckets = build_activity_matrix(self.session_manager, self._rows)
        if not self._rows:
            self.axes.text(0.5, 0.5, "Associa almeno un alunno per visualizzare la heatmap.",
                           ha="center", va="center", transform=self.axes.transAxes)
            self.axes.set_axis_off()
            self.canvas.draw_idle()
            return
        if not self._buckets:
            self.axes.text(0.5, 0.5, "In attesa dei primi campioni del monitoraggio.",
                           ha="center", va="center", transform=self.axes.transAxes)
            self.axes.set_axis_off()
            self.canvas.draw_idle()
            return

        # Codici discreti: la tonalità comunica immediatamente stato e soglia.
        coded = []
        for row in matrix:
            coded.append([
                -1 if delta < 0 else 3 if delta > self.threshold else 2 if delta > 0 else 0
                for delta in row
            ])
        colors = ["#fed7aa", "#ffffff", "#bbf7d0", "#22c55e", "#fecaca"]
        cmap = ListedColormap(colors)
        norm = BoundaryNorm([-1.5, -0.5, 0.5, 1.5, 2.5, 3.5], cmap.N)
        image = self.axes.imshow(coded, aspect="auto", interpolation="nearest", cmap=cmap, norm=norm)
        del image  # La variabile rende esplicita la creazione dell'immagine per il canvas.

        self.axes.set_title("Incremento righe per scansione")
        self.axes.set_yticks(range(len(self._rows)))
        self.axes.set_yticklabels([
            f"{student} — {_short_student_name(self.associations.get(student, student))}"
            for student in self._rows
        ], fontsize=8)
        self.axes.set_xticks(range(len(self._buckets)))
        self.axes.set_xticklabels([
            dt.datetime.fromtimestamp(bucket).strftime("%H:%M:%S") for bucket in self._buckets
        ], rotation=45, ha="right", fontsize=8)
        self.axes.set_xlabel("Ora della scansione")
        self.axes.set_ylabel("Test / alunno")
        self.axes.set_xticks([index - 0.5 for index in range(1, len(self._buckets))], minor=True)
        self.axes.set_yticks([index - 0.5 for index in range(1, len(self._rows))], minor=True)
        self.axes.grid(which="minor", color="#cbd5e1", linewidth=0.5)
        self.axes.tick_params(which="minor", bottom=False, left=False)
        self.canvas.draw_idle()

    def _on_click(self, event):
        if event.inaxes is not self.axes or event.xdata is None or event.ydata is None:
            return
        column, row = int(round(event.xdata)), int(round(event.ydata))
        if not (0 <= row < len(self._rows) and 0 <= column < len(self._buckets)):
            return
        from student_detail_window import StudentDetailWindow
        StudentDetailWindow(self.master, self._rows[row], self.session_manager)

    def _close(self):
        if self.dialog is not None and self.dialog.winfo_exists():
            self.dialog.destroy()
        self.dialog = None
        self.figure = None
        self.axes = None
        self.canvas = None
