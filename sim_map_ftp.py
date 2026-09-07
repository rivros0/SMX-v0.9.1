"""
sim_map_ftp.py

Gestione della finestra "Mappa similitudini" per i confronti
VERIFICA ↔ MERGE dominio (FTP).

Tutto il calcolo delle metriche è delegato a similarity_ftp.
Questo modulo si occupa di:

  - mostrare la tabella riassuntiva per studente;
  - colorare le righe in base al livello di riuso;
  - fornire un "report riuso" testuale per ogni studente;
  - permettere un doppio clic su una riga per aprire le
    comparazioni avanzate (dettaglio testi).
"""

import tkinter as tk
from tkinter import ttk, messagebox

import similarity_ftp


YELLOW_BG = "#85187c"


def _build_reuse_report(metrics):
    """
    Costruisce un breve report testuale a partire dalle metriche
    calcolate da similarity_ftp.compute_merge_metrics.

    Metriche utilizzate:
      - percent_shared_chars_on_test
      - percent_shared_chars_on_domain
      - similarity_percent
      - shared_lines_count
      - total_lines_test
      - total_chars_test
      - full_inclusion_flag
    """
    pezzi = []

    if metrics is None:
        return ""

    percent_on_test = float(metrics.get("percent_shared_chars_on_test", 0.0))
    percent_on_domain = float(metrics.get("percent_shared_chars_on_domain", 0.0))
    similarity_percent = float(metrics.get("similarity_percent", 0.0))
    shared_lines = int(metrics.get("shared_lines_count", 0))
    total_lines_test = int(metrics.get("total_lines_test", 0))
    total_chars_test = int(metrics.get("total_chars_test", 0))
    full_inclusion_flag = bool(metrics.get("full_inclusion_flag", False))

    # ------------------------------------------------------------------
    # 1) Caso speciale: test integralmente (o quasi) presente nel dominio
    # ------------------------------------------------------------------
    if full_inclusion_flag:
        if percent_on_test >= 80.0 and percent_on_domain >= 80.0:
            pezzi.append(
                "Il codice del dominio risulta sostanzialmente coincidente con quello del test: "
                "il sito sembra contenere principalmente la verifica consegnata."
            )
        elif percent_on_test >= 60.0:
            pezzi.append(
                "Il codice del test è contenuto quasi integralmente nel dominio, ma rappresenta "
                "solo una parte del sito, che include anche altro codice."
            )

    # ------------------------------------------------------------------
    # 2) Valutazione in base a percentuale di caratteri condivisi sul test
    # ------------------------------------------------------------------
    if percent_on_test < 5.0:
        pezzi.append("Riuso trascurabile (meno del 5% del testo del test).")
    elif percent_on_test < 15.0:
        pezzi.append("Riuso lieve (tra 5% e 15% del testo del test).")
    elif percent_on_test < 30.0:
        pezzi.append(
            "Riuso significativo (tra il 15% e il 30% del testo del test): opportuno un controllo puntuale."
        )
    elif percent_on_test < 60.0:
        pezzi.append(
            "Riuso elevato (tra il 30% e il 60% del testo del test): forte sospetto di copia dal dominio."
        )
    else:
        pezzi.append(
            "Riuso molto elevato (oltre il 60% del testo del test): verosimile copia quasi integrale dal dominio."
        )

    # ------------------------------------------------------------------
    # 3) Contesto basato sulla similarità globale
    # ------------------------------------------------------------------
    if similarity_percent < 20.0:
        pezzi.append("La similarita complessiva tra test e dominio e bassa (meno del 20%).")
    elif similarity_percent < 40.0:
        pezzi.append("La similarita complessiva tra test e dominio e moderata (tra 20% e 40%).")
    elif similarity_percent < 70.0:
        pezzi.append("La similarita complessiva tra test e dominio e alta (tra 40% e 70%).")
    else:
        pezzi.append("La similarita complessiva tra test e dominio e molto alta (oltre il 70%).")

    if percent_on_test >= 30.0 and similarity_percent >= 50.0:
        pezzi.append(
            "Percentuale di caratteri condivisi e similarita globale risultano entrambe elevate."
        )

    # ------------------------------------------------------------------
    # 4) Analisi delle righe condivise
    # ------------------------------------------------------------------
    ratio_righe = 0.0
    if total_lines_test > 0:
        ratio_righe = (float(shared_lines) * 100.0) / float(total_lines_test)

    if shared_lines == 0:
        pezzi.append("Non risultano righe significative in comune.")
    else:
        if ratio_righe < 10.0:
            pezzi.append(
                "Poche righe significative in comune (meno del 10% delle righe del test)."
            )
        elif ratio_righe < 30.0:
            pezzi.append(
                "Numero non trascurabile di righe in comune (tra il 10% e il 30% delle righe del test)."
            )
        elif ratio_righe < 60.0:
            pezzi.append(
                "Molte righe in comune (tra il 30% e il 60% delle righe del test): possibile riuso strutturale del codice."
            )
        else:
            pezzi.append(
                "La maggior parte delle righe del test coincide con il codice sul dominio (oltre il 60% delle righe)."
            )

    # ------------------------------------------------------------------
    # 5) Affidabilita in funzione della dimensione del test
    # ------------------------------------------------------------------
    if total_chars_test < 400 or total_lines_test < 15:
        pezzi.append(
            "Attenzione: il test e di dimensioni ridotte; le percentuali di riuso potrebbero essere meno significative."
        )

    report = " ".join(pezzi)
    return report


def open_similarity_map(
    parent_frame,
    metrics_by_student,
    texts_test,
    merged_domain_texts,
    students_in_test,
    students_in_domain,
):
    """
    Apre la finestra con la mappa delle similitudini Test ↔ Dominio.

    Parametri:
      - parent_frame: frame Tkinter padre (frame domini)
      - metrics_by_student: dict {studente: metriche}
      - texts_test: dict {studente: testo_verifica}
      - merged_domain_texts: dict {studente: testo_merge_dominio}
      - students_in_test: lista studenti presenti nei test
      - students_in_domain: lista studenti presenti nei domini
    """
    if not metrics_by_student:
        messagebox.showwarning(
            "Attenzione",
            "Nessuna analisi disponibile. Esegui prima 'Analizza somiglianze'.",
        )
        return

    top = tk.Toplevel(parent_frame)
    top.title("Riepilogo similitudini (verifica ↔ MERGE dominio)")
    top.configure(bg="white")

    colonne = (
        "Studente",
        "Simil. Test/Dominio (%)",
        "Righe riutilizzate",
        "Caratteri riutilizzati",
        "% char su test",
        "Righe test",
        "Caratteri test",
        "Report riuso",
    )

    tree = ttk.Treeview(
        top,
        columns=colonne,
        show="headings",
        height=18,
    )

    indice = 0
    while indice < len(colonne):
        col = colonne[indice]
        tree.heading(col, text=col)

        if col == "Studente":
            tree.column(col, width=200, anchor="w")
        elif col == "Report riuso":
            tree.column(col, width=600, anchor="w")
        else:
            tree.column(col, width=130, anchor="center")

        indice = indice + 1

    tree.grid(row=0, column=0, columnspan=3, padx=10, pady=10, sticky="nsew")

    scrollbar_vert = ttk.Scrollbar(
        top,
        orient="vertical",
        command=tree.yview,
    )
    tree.configure(yscrollcommand=scrollbar_vert.set)
    scrollbar_vert.grid(row=0, column=3, sticky="ns", pady=10)

    top.grid_rowconfigure(0, weight=1)
    top.grid_columnconfigure(0, weight=1)

    tree.tag_configure("low", foreground="blue")
    tree.tag_configure("mid", foreground="orange")
    tree.tag_configure("high", foreground="red")

    studenti = sorted(metrics_by_student.keys())

    indice = 0
    while indice < len(studenti):
        studente = studenti[indice]
        m = metrics_by_student[studente]

        simil = float(m.get("similarity_percent", 0.0))
        righe_comuni = int(m.get("shared_lines_count", 0))
        chars_comuni = int(m.get("shared_chars_len", 0))
        perc_chars_test = float(m.get("percent_shared_chars_on_test", 0.0))
        righe_test = int(m.get("total_lines_test", 0))
        chars_test = int(m.get("total_chars_test", 0))

        report = _build_reuse_report(m)

        valori = (
            studente,
            "{:.1f}".format(simil),
            str(righe_comuni),
            str(chars_comuni),
            "{:.1f}".format(perc_chars_test),
            str(righe_test),
            str(chars_test),
            report,
        )

        if perc_chars_test < 15.0:
            tag = "low"
        elif perc_chars_test < 40.0:
            tag = "mid"
        else:
            tag = "high"

        tree.insert("", "end", values=valori, tags=(tag,))

        indice = indice + 1

    legenda = (
        "Legenda: blu = bassa similarita, arancio = media, rosso = alta. "
        "Doppio clic su uno studente per aprire le comparazioni avanzate."
    )

    lbl_legenda = tk.Label(
        top,
        text=legenda,
        anchor="w",
        justify="left",
        bg="white",
    )
    lbl_legenda.grid(row=1, column=0, columnspan=3, padx=10, pady=(0, 8), sticky="we")

    def apri_comparazioni_avanzate(evento):
        """
        Su doppio clic apre una finestra con i due testi a confronto
        (test e merge dominio) per lo studente selezionato.
        """
        item_id = tree.focus()
        if not item_id:
            return

        valori = tree.item(item_id, "values")
        if not valori:
            return

        studente = valori[0]

        testo_test = texts_test.get(studente, "")
        testo_dom = merged_domain_texts.get(studente, "")

        if testo_test == "" and testo_dom == "":
            messagebox.showinfo(
                "Informazione",
                "Non sono disponibili testi per lo studente selezionato.",
            )
            return

        win = tk.Toplevel(top)
        win.title("Dettaglio similitudini per: " + studente)
        win.geometry("1200x700")

        frame_sx = tk.Frame(win)
        frame_dx = tk.Frame(win)

        frame_sx.pack(side="left", fill="both", expand=True)
        frame_dx.pack(side="right", fill="both", expand=True)

        lbl_sx = tk.Label(frame_sx, text="TEST locale", anchor="w")
        lbl_sx.pack(fill="x")

        txt_sx = tk.Text(frame_sx, wrap="none")
        txt_sx.pack(fill="both", expand=True)

        scroll_y_sx = tk.Scrollbar(frame_sx, orient="vertical", command=txt_sx.yview)
        scroll_y_sx.pack(side="right", fill="y")
        txt_sx.configure(yscrollcommand=scroll_y_sx.set)

        scroll_x_sx = tk.Scrollbar(frame_sx, orient="horizontal", command=txt_sx.xview)
        scroll_x_sx.pack(side="bottom", fill="x")
        txt_sx.configure(xscrollcommand=scroll_x_sx.set)

        lbl_dx = tk.Label(frame_dx, text="MERGE dominio", anchor="w")
        lbl_dx.pack(fill="x")

        txt_dx = tk.Text(frame_dx, wrap="none")
        txt_dx.pack(fill="both", expand=True)

        scroll_y_dx = tk.Scrollbar(frame_dx, orient="vertical", command=txt_dx.yview)
        scroll_y_dx.pack(side="right", fill="y")
        txt_dx.configure(yscrollcommand=scroll_y_dx.set)

        scroll_x_dx = tk.Scrollbar(frame_dx, orient="horizontal", command=txt_dx.xview)
        scroll_x_dx.pack(side="bottom", fill="x")
        txt_dx.configure(xscrollcommand=scroll_x_dx.set)

        txt_sx.insert("1.0", testo_test)
        txt_dx.insert("1.0", testo_dom)

        txt_sx.config(state="disabled")
        txt_dx.config(state="disabled")

    tree.bind("<Double-1>", apri_comparazioni_avanzate)
