import os
import difflib
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import tkinter as tk
from tkinter import Toplevel, Text, Scrollbar
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


def _resolve_directory_source(directory_source) -> str:
    """
    Accetta:
    - una stringa con il path della directory
    - oppure una Label tkinter con testo tipo 'Directory selezionata: ...'
    - oppure un oggetto con .get() (es. StringVar)

    Restituisce il path pulito (stringa). Se non riesce, restituisce stringa vuota.
    """
    # Caso: Label (o widget simile con .cget)
    if hasattr(directory_source, "cget"):
        try:
            text = directory_source.cget("text")
            path = text.replace("Directory selezionata:", "")
            return path.strip()
        except Exception:
            pass

    # Caso: StringVar o oggetto con .get()
    if hasattr(directory_source, "get"):
        try:
            path = directory_source.get()
            return str(path).strip()
        except Exception:
            pass

    # Caso generico: consideriamo sia già una stringa
    try:
        return str(directory_source).strip()
    except Exception:
        return ""


def calculate_similarity(file1_path, file2_path):
    """
    Calcola la similarità (%) tra due file di testo usando difflib.SequenceMatcher.

    Restituisce:
    - matcher: oggetto SequenceMatcher (o None in caso di errore)
    - similarity: valore percentuale (0-100)
    """
    try:
        # file 1
        try:
            with open(file1_path, "r", encoding="utf-8") as file1:
                content1 = file1.read()
        except UnicodeDecodeError:
            with open(file1_path, "r", encoding="latin-1", errors="replace") as file1:
                content1 = file1.read()

        # file 2
        try:
            with open(file2_path, "r", encoding="utf-8") as file2:
                content2 = file2.read()
        except UnicodeDecodeError:
            with open(file2_path, "r", encoding="latin-1", errors="replace") as file2:
                content2 = file2.read()

        # Normalizza gli a capo
        content1 = content1.replace("\r\n", "\n").replace("\r", "\n")
        content2 = content2.replace("\r\n", "\n").replace("\r", "\n")

        matcher = difflib.SequenceMatcher(None, content1, content2)
        similarity = matcher.ratio() * 100.0
        return matcher, similarity
    except Exception:
        # In caso di errore, restituisce 0 e nessun matcher
        return None, 0.0


def show_similar_fragments(file1, file2, matcher):
    """
    Mostra in una nuova finestra due colonne di testo con i contenuti dei due file,
    a partire dal primo blocco dopo la riga di separazione
    '###############################################################' (se presente).
    """
    top = Toplevel()
    top.title(
        "Somiglianze tra {} e {}".format(
            os.path.basename(file1),
            os.path.basename(file2),
        )
    )
    top.geometry("1200x800")
    top.resizable(True, True)

    frame1 = tk.Frame(top)
    frame1.grid(row=0, column=0, sticky="nsew")

    frame2 = tk.Frame(top)
    frame2.grid(row=0, column=1, sticky="nsew")

    text1 = Text(frame1, wrap="none", width=60, height=30)
    text1.pack(side="left", fill="both", expand=True)

    text2 = Text(frame2, wrap="none", width=60, height=30)
    text2.pack(side="left", fill="both", expand=True)

    scroll_y = Scrollbar(top, orient="vertical")
    scroll_y.grid(row=0, column=2, sticky="ns")

    text1.config(yscrollcommand=scroll_y.set)
    text2.config(yscrollcommand=scroll_y.set)

    def sync_scroll(*args):
        text1.yview(*args)
        text2.yview(*args)

    scroll_y.config(command=sync_scroll)

    # Recupera le stringhe originali dal matcher
    try:
        content1 = matcher.a
        content2 = matcher.b
    except Exception:
        content1 = ""
        content2 = ""

    # Prova a "tagliare" prima del primo blocco vero dopo le ###, se presenti
    marker = "###############################################################"
    try:
        idx1 = content1.find(marker)
        idx2 = content2.find(marker)

        if idx1 != -1:
            next_newline = content1.find("\n", idx1)
            if next_newline != -1:
                content1 = content1[next_newline + 1 :]

        if idx2 != -1:
            next_newline = content2.find("\n", idx2)
            if next_newline != -1:
                content2 = content2[next_newline + 1 :]
    except Exception:
        # in caso di problemi, usiamo comunque le stringhe intere
        pass

    content1_lines = content1.splitlines()
    content2_lines = content2.splitlines()

    # Allinea il numero di righe
    max_line_count = max(len(content1_lines), len(content2_lines))

    while len(content1_lines) < max_line_count:
        content1_lines.append("")

    while len(content2_lines) < max_line_count:
        content2_lines.append("")

    indice = 0
    while indice < max_line_count:
        line1 = content1_lines[indice]
        line2 = content2_lines[indice]
        text1.insert("end", line1 + "\n")
        text2.insert("end", line2 + "\n")
        indice = indice + 1

    top.grid_rowconfigure(0, weight=1)
    top.grid_columnconfigure(0, weight=1)
    top.grid_columnconfigure(1, weight=1)


def plot_similarity_matrix(output_directory, report_text=None):
    """
    Costruisce e mostra una heatmap di similarità tra tutti i file *_mix.txt
    presenti in output_directory.

    - Cliccando su una cella (i, j) diversa dalla diagonale, apre una finestra
      con i frammenti di codice affiancati.

    Restituisce: (files, similarity_matrix)
    - files: lista dei path completi dei file considerati, in ordine
    - similarity_matrix: matrice NxN con i valori percentuali (numpy array) oppure None
    """
    files = []
    for nome in os.listdir(output_directory):
        if nome.endswith("_mix.txt"):
            files.append(os.path.join(output_directory, nome))

    files.sort()
    num_files = len(files)

    if num_files < 2:
        if report_text is not None:
            report_text.insert(
                "end",
                "Per l'analisi delle similarità servono almeno 2 file *_mix.txt.\n",
            )
            report_text.see("end")
        return files, None

    similarity_matrix = np.zeros((num_files, num_files))
    matchers = []

    i_indice = 0
    while i_indice < num_files:
        riga_matcher = []
        j_indice = 0
        while j_indice < num_files:
            riga_matcher.append(None)
            j_indice = j_indice + 1
        matchers.append(riga_matcher)
        i_indice = i_indice + 1

    # Calcolo delle similarità
    i_indice = 0
    while i_indice < num_files:
        j_indice = 0
        while j_indice < num_files:
            if i_indice == j_indice:
                similarity_matrix[i_indice, j_indice] = 100.0
            else:
                matcher, similarity = calculate_similarity(
                    files[i_indice],
                    files[j_indice],
                )
                similarity_matrix[i_indice, j_indice] = similarity
                matchers[i_indice][j_indice] = matcher
            j_indice = j_indice + 1
        i_indice = i_indice + 1

    def on_click(event):
        if event.inaxes is None:
            return

        try:
            x = int(round(event.xdata))
            y = int(round(event.ydata))
        except Exception:
            return

        if x < 0 or y < 0 or x >= num_files or y >= num_files:
            return

        if x == y:
            # diagonale (file con sé stesso), non facciamo nulla
            return

        # attenzione: righe = y, colonne = x
        matcher = matchers[y][x]
        if matcher:
            show_similar_fragments(files[y], files[x], matcher)

    # Plot della matrice
    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        similarity_matrix,
        annot=True,
        fmt=".0f",
        cmap="coolwarm",
        xticklabels=[os.path.basename(f) for f in files],
        yticklabels=[os.path.basename(f) for f in files],
        ax=ax,
    )

    plt.title("Matrice di Similarità tra i file di output")
    plt.xlabel("File di Output")
    plt.ylabel("File di Output")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.canvas.mpl_connect("button_press_event", on_click)
    plt.show()

    if report_text is not None:
        report_text.insert(
            "end",
            "Matrice di similarità calcolata e visualizzata.\n"
            "Clicca su una cella (non diagonale) per vedere i frammenti di codice.\n",
        )
        report_text.see("end")

    return files, similarity_matrix


def analyze_similarities(directory_source, report_text):
    """
    Funzione chiamata dalla GUI (frame_correzione).

    - `directory_source` può essere:
        * una Label con testo 'Directory selezionata: ...'
        * una stringa con il path base
        * una variabile con .get()
    - Usa la sottocartella '00_MixOutput' e analizza i file *_mix.txt.
    """
    base_directory = _resolve_directory_source(directory_source)
    if not base_directory:
        report_text.insert(
            "end",
            "Nessuna directory selezionata per l'analisi delle similarità.\n",
        )
        report_text.see("end")
        return

    output_directory = os.path.join(base_directory, "00_MixOutput")
    if not os.path.exists(output_directory):
        report_text.insert(
            "end",
            "La directory 00_MixOutput non esiste in:\n{}\n".format(base_directory)
            + "Esegui prima la fase di mix per generare i file *_mix.txt.\n",
        )
        report_text.see("end")
        return

    report_text.insert(
        "end",
        "Analisi similarità sui file *_mix.txt in: {}\n".format(output_directory),
    )
    report_text.see("end")

    files, matrix = plot_similarity_matrix(output_directory, report_text)

    if matrix is not None:
        # Piccolo riepilogo su eventuali similarità alte
        try:
            n = len(files)
            sospetti = []

            i_indice = 0
            while i_indice < n:
                j_indice = i_indice + 1
                while j_indice < n:
                    valore = matrix[i_indice, j_indice]
                    if valore >= 80.0:
                        sospetti.append(
                            (
                                os.path.basename(files[i_indice]),
                                os.path.basename(files[j_indice]),
                                valore,
                            )
                        )
                    j_indice = j_indice + 1
                i_indice = i_indice + 1

            if sospetti:
                report_text.insert(
                    "end",
                    "\nCoppie con similarità >= 80% (possibile copia):\n",
                )
                for f1, f2, sim in sospetti:
                    report_text.insert(
                        "end",
                        " - {} <> {}: {:.0f}%\n".format(f1, f2, sim),
                    )
            else:
                report_text.insert(
                    "end",
                    "\nNessuna coppia supera la soglia di similarità del 80%.\n",
                )

            report_text.see("end")
        except Exception:
            # se qualcosa va storto, non blocchiamo l'uso principale
            pass


# ======================================================================
# NUOVE FUNZIONI PER ANALISI VERIFICHE / DOMINI (FRAME DOMINI)
# ======================================================================

def read_text_from_directory(directory_path, allowed_extensions):
    """
    Legge ricorsivamente tutti i file con estensione ammessa in una directory
    e concatena i contenuti in un'unica stringa normalizzata (\n come separatore).

    Ritorna stringa vuota se la directory non esiste o non contiene file validi.
    """
    if not directory_path:
        return ""

    if not os.path.isdir(directory_path):
        return ""

    parti_testo = []

    for radice, _, files in os.walk(directory_path):
        for nome_file in files:
            nome_file_lower = nome_file.lower()
            estensione_valida = False

            for estensione in allowed_extensions:
                if nome_file_lower.endswith(estensione):
                    estensione_valida = True
                    break

            if not estensione_valida:
                continue

            percorso_file = os.path.join(radice, nome_file)

            contenuto = None
            for encoding in ("utf-8", "latin-1"):
                try:
                    with open(
                        percorso_file,
                        "r",
                        encoding=encoding,
                        errors="strict",
                    ) as f:
                        contenuto = f.read()
                    break
                except Exception:
                    contenuto = None

            if contenuto is None:
                try:
                    with open(
                        percorso_file,
                        "r",
                        encoding="latin-1",
                        errors="ignore",
                    ) as f:
                        contenuto = f.read()
                except Exception:
                    contenuto = ""

            if contenuto:
                contenuto = contenuto.replace("\r\n", "\n").replace("\r", "\n")
                parti_testo.append("FILE: " + nome_file + "\n" + contenuto + "\n\n")

    return "\n".join(parti_testo)


def calculate_text_similarity(text1, text2):
    """
    Calcola la somiglianza (0-100) tra due stringhe usando difflib.SequenceMatcher.
    """
    if not text1 and not text2:
        return 100.0

    if not text1 or not text2:
        return 0.0

    matcher = difflib.SequenceMatcher(None, text1, text2)
    ratio = matcher.ratio()
    return ratio * 100.0


def build_texts_from_directories(dirs_by_student, allowed_extensions):
    """
    Converte una mappa {studente: directory} in:
        - lista ordinata di studenti
        - dizionario {studente: testo_concatenato}

    Vengono considerati solo gli studenti con almeno un file valido.
    """
    studenti = []
    testi = {}

    nomi_ordinati = sorted(dirs_by_student.keys())

    for nome in nomi_ordinati:
        directory = dirs_by_student.get(nome)
        testo = read_text_from_directory(directory, allowed_extensions)
        if testo.strip() != "":
            studenti.append(nome)
            testi[nome] = testo

    return studenti, testi


def build_similarity_matrix(student_names, texts_by_student):
    """
    Costruisce una matrice di similarità NxN (lista di liste)
    tra tutti i testi degli studenti indicati.
    """
    dimensione = len(student_names)
    matrice = []

    riga_indice = 0
    while riga_indice < dimensione:
        riga = []
        colonna_indice = 0
        while colonna_indice < dimensione:
            nome_i = student_names[riga_indice]
            nome_j = student_names[colonna_indice]

            testo_i = texts_by_student.get(nome_i, "")
            testo_j = texts_by_student.get(nome_j, "")

            valore = calculate_text_similarity(testo_i, testo_j)
            riga.append(valore)

            colonna_indice = colonna_indice + 1
        matrice.append(riga)
        riga_indice = riga_indice + 1

    return matrice


def build_cross_similarity_matrix(row_names, col_names, row_texts, col_texts):
    """
    Costruisce una matrice di similarità len(row_names) x len(col_names)
    tra due insiemi diversi (es. verifiche e domini).
    """
    num_righe = len(row_names)
    num_colonne = len(col_names)
    matrice = []

    riga_indice = 0
    while riga_indice < num_righe:
        riga = []
        colonna_indice = 0
        while colonna_indice < num_colonne:
            nome_riga = row_names[riga_indice]
            nome_colonna = col_names[colonna_indice]

            testo_riga = row_texts.get(nome_riga, "")
            testo_colonna = col_texts.get(nome_colonna, "")

            valore = calculate_text_similarity(testo_riga, testo_colonna)
            riga.append(valore)

            colonna_indice = colonna_indice + 1
        matrice.append(riga)
        riga_indice = riga_indice + 1

    return matrice


def show_heatmap(parent, titolo, row_labels, col_labels, matrix):
    """
    Mostra una matrice di similarità come heatmap in una nuova finestra Tkinter.

    Pensata per:
    - verifiche vs verifiche
    - domini vs domini
    - verifiche vs domini
    """
    if not row_labels or not col_labels:
        messagebox = tk.messagebox
        messagebox.showwarning(
            "Attenzione",
            "Non ci sono dati sufficienti per costruire la mappa delle similitudini.",
        )
        return

    top = Toplevel(parent)
    top.title(titolo)

    figure_larghezza = 8.0
    figure_altezza = 6.0

    fig, ax = plt.subplots(figsize=(figure_larghezza, figure_altezza))

    # Conversione in float per sicurezza
    dati_numerici = []
    riga_indice = 0
    while riga_indice < len(matrix):
        riga = matrix[riga_indice]
        nuova_riga = []
        colonna_indice = 0
        while colonna_indice < len(riga):
            valore = riga[colonna_indice]
            try:
                nuovo_valore = float(valore)
            except Exception:
                nuovo_valore = 0.0
            nuova_riga.append(nuovo_valore)
            colonna_indice = colonna_indice + 1
        dati_numerici.append(nuova_riga)
        riga_indice = riga_indice + 1

    cax = ax.imshow(dati_numerici, interpolation="nearest", cmap="viridis", vmin=0.0, vmax=100.0)
    barra_colore = fig.colorbar(cax)
    barra_colore.set_label("Similarità (%)")

    num_colonne = len(col_labels)
    num_righe = len(row_labels)

    ax.set_xticks(range(num_colonne))
    ax.set_yticks(range(num_righe))
    ax.set_xticklabels(col_labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(row_labels, fontsize=8)

    ax.set_xlabel("Colonna")
    ax.set_ylabel("Riga")
    ax.set_title(titolo)

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=top)
    canvas.draw()

    widget_canvas = canvas.get_tk_widget()
    widget_canvas.pack(fill="both", expand=True)

    # Mantiene un riferimento alle figure per evitare che vengano distrutte
    # dal garbage collector.
    top._figure = fig
    top._canvas = canvas
