import datetime as dt
import tkinter as tk
from tkinter import ttk
from utils import add_tooltip


class StudentCard(tk.Frame):
    """Riga compatta della dashboard Live, con allarme per forti incrementi."""

    ROW_HEIGHT = 62
    # Larghezza aderente ai contenuti compatti: evita un vuoto dopo il pulsante
    # mantenendo comunque tre colonne nella dashboard Live.
    CARD_WIDTH = 460
    NORMAL_BG = "#ffffff"
    ALERT_COLORS = ("#fff1f2", "#fecdd3")

    def __init__(self, parent, student_name, session_manager, row, col=0, display_name=None):
        super().__init__(parent, bg=self.NORMAL_BG, width=self.CARD_WIDTH, height=self.ROW_HEIGHT,
                         highlightbackground="#cbd5e1", highlightthickness=1)
        self.student_name = student_name
        self.session_manager = session_manager
        self.history = session_manager.get_history(student_name)
        self.alert_active = False
        self.alert_phase = 0
        self._flash_after = None
        self.grid(row=row, column=col, padx=4, pady=3, sticky="w")
        self.grid_propagate(False)
        self.bind("<Destroy>", self._on_destroy, add="+")

        # La colonna della sparkline ha spazio riservato: non può scomparire
        # quando la card mantiene una larghezza fissa.
        # Tutte le colonne, incluso il comando di chiusura alert, devono
        # rientrare nella larghezza fissa della card anche con tre colonne Live.
        self.columnconfigure(3, minsize=100, weight=0)
        self.test_label = tk.Label(self, text=student_name, bg=self.NORMAL_BG, anchor="w",
                                   fg="#475569", font=("Segoe UI", 8, "bold"), width=11)
        self.test_label.grid(row=0, column=0, sticky="sw", padx=(8, 4))
        self.name_label = tk.Label(self, text=display_name or student_name, bg=self.NORMAL_BG, anchor="w",
                                   font=("Segoe UI", 10, "bold"), width=11)
        self.name_label.grid(row=1, column=0, sticky="nw", padx=(8, 4))

        self.lines_label = tk.Label(self, bg=self.NORMAL_BG, anchor="w", width=8,
                                    font=("Segoe UI", 10, "bold"))
        self.lines_label.grid(row=0, column=1, sticky="sw", padx=4)
        self.delta_label = tk.Label(self, bg=self.NORMAL_BG, anchor="w", width=8,
                                    font=("Segoe UI", 9))
        self.delta_label.grid(row=1, column=1, sticky="nw", padx=4)

        self.time_label = tk.Label(self, bg=self.NORMAL_BG, fg="#475569", anchor="w", width=13,
                                   font=("Segoe UI", 8))
        self.time_label.grid(row=0, column=2, rowspan=2, sticky="w", padx=4)

        # Con le card a larghezza fissa il valore Tk predefinito (molto largo)
        # farebbe uscire il canvas dalla riga e nasconderebbe la sparkline.
        self.sparkline = tk.Canvas(self, width=100, height=30, bg="#f8fafc", bd=0,
                                   highlightbackground="#cbd5e1", highlightthickness=1,
                                   cursor="hand2")
        self.sparkline.grid(row=0, column=3, rowspan=2, sticky="ew", padx=4, pady=6)
        self.sparkline.bind("<Configure>", lambda _event: self._draw_sparkline())
        self.sparkline.bind("<Button-1>", self._open_detail)

        self.actions = tk.Frame(self, bg=self.NORMAL_BG)
        self.actions.grid(row=0, column=4, rowspan=2, padx=(0, 4), pady=5, sticky="e")
        self.dismiss_button = ttk.Button(self.actions, text="Chiudi", width=7, command=self.reset_alert)
        add_tooltip(self.dismiss_button, "Chiude l'alert per questa versione dell'elaborato.")
        self._background_widgets = (
            self, self.test_label, self.name_label, self.lines_label, self.delta_label,
            self.time_label, self.sparkline, self.actions,
        )
        self.update_card()

    def update_card(self):
        self.history = self.session_manager.get_history(self.student_name)
        if not self.history:
            self.lines_label.config(text="Nessun dato", fg="#64748b")
            self.delta_label.config(text="In attesa del primo cambiamento", fg="#94a3b8")
            self.time_label.config(text="—")
            self._set_alert(False)
            self._draw_sparkline()
            return

        last = self.history[-1]
        previous = self.history[-2] if len(self.history) > 1 else None
        delta = last["line_count"] - previous["line_count"] if previous else 0
        # Gli snapshot marcati baseline arrivano al primo scan dopo l'apertura
        # di una sessione e non devono colorare la dashboard come un alert.
        suspicious = (previous is not None and not last.get("baseline", False)
                      and delta > self.session_manager.alert_threshold)
        active_alert = suspicious and not self.session_manager.is_alert_dismissed(
            self.student_name, last.get("snapshot_id")
        )
        self.lines_label.config(text=f"{last['line_count']} righe",
                                fg="#b91c1c" if active_alert else "#0f172a")
        if previous is None:
            delta_text, delta_color = "prima versione", "#64748b"
        elif delta > 0:
            delta_text, delta_color = f"+{delta} dall’ultima", "#15803d"
        elif delta < 0:
            delta_text, delta_color = f"{delta} dall’ultima", "#b45309"
        else:
            delta_text, delta_color = "nessuna variazione", "#64748b"
        self.delta_label.config(text=delta_text, fg=delta_color)
        try:
            timestamp = dt.datetime.fromisoformat(last["timestamp"])
            self.time_label.config(text=f"Aggiornato\n{timestamp:%d/%m/%Y %H:%M}")
        except Exception:
            self.time_label.config(text="Ultimo aggiornamento disponibile")
        self.name_label.config(fg="#b91c1c" if active_alert else "#0f172a")
        self._set_alert(active_alert)
        self._draw_sparkline()

    def _set_alert(self, active):
        if active == self.alert_active:
            return
        self.alert_active = active
        if active:
            # È l'unico pulsante nella card: rimane completamente visibile.
            self.dismiss_button.pack(side="left")
            self.alert_phase = 0
            self._flash_background()
        else:
            self.dismiss_button.pack_forget()
            if self._flash_after is not None:
                self.after_cancel(self._flash_after)
                self._flash_after = None
            self._apply_background(self.NORMAL_BG)

    def _open_detail(self, _event=None):
        """Apre lo storico dello studente cliccando sulla sua sparkline."""
        from student_detail_window import StudentDetailWindow
        StudentDetailWindow(self.winfo_toplevel(), self.student_name, self.session_manager)

    def _flash_background(self):
        if not self.alert_active or not self.winfo_exists():
            return
        self._apply_background(self.ALERT_COLORS[self.alert_phase])
        self.alert_phase = 1 - self.alert_phase
        self._flash_after = self.after(450, self._flash_background)

    def _apply_background(self, color):
        for widget in self._background_widgets:
            try:
                widget.configure(bg=color)
            except tk.TclError:
                pass
        self.configure(highlightbackground="#dc2626" if color != self.NORMAL_BG else "#cbd5e1")

    def _on_destroy(self, _event):
        if self._flash_after is not None:
            try:
                self.after_cancel(self._flash_after)
            except tk.TclError:
                pass
            self._flash_after = None

    def _draw_sparkline(self):
        canvas = self.sparkline
        canvas.delete("all")
        width = max(canvas.winfo_width(), 120)
        height = max(canvas.winfo_height(), 30)
        values = [item["line_count"] for item in self.history[-20:]]
        if not values:
            canvas.create_text(width / 2, height / 2, text="nessuno storico",
                               fill="#94a3b8", font=("Segoe UI", 8))
            return
        low, high = min(values), max(values)
        spread = max(high - low, 1)
        if len(values) == 1:
            points = [(width / 2, height / 2)]
        else:
            points = [(5 + index * (width - 10) / (len(values) - 1),
                       height - 5 - (value - low) * (height - 10) / spread)
                      for index, value in enumerate(values)]
        if len(points) > 1:
            canvas.create_line(*[coordinate for point in points for coordinate in point],
                               fill="#04748a", width=2, smooth=True)
        x, y = points[-1]
        canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill="#04748a", outline="")

    def reset_alert(self):
        if not self.history:
            return
        self.session_manager.dismiss_alert(self.student_name, self.history[-1].get("snapshot_id"))
        self._set_alert(False)
