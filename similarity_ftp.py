"""
similarity_ftp.py
Analisi del riuso tra VERIFICHE LOCALI e DOMINI (FTP) con merge per dominio.

Supporta un callback di progresso opzionale:
    progress_cb(phase: str, current: int, total: int, name: str)

Fasi:
- "read_tests"     : lettura e normalizzazione verifiche locali
- "merge_domains"  : generazione testi merged dei domini (e salvataggio __MERGED__.txt)
- "compare"        : confronto verifica vs merge dominio (metriche)

Le altre funzionalità restano invariate (heatmap coerente con similarity.py).
"""

import os
import difflib

import tkinter as tk
from tkinter import Toplevel, messagebox

try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    HAS_MATPLOTLIB = True
except Exception:
    plt = None
    FigureCanvasTkAgg = None
    HAS_MATPLOTLIB = False


# ======================================================================
# LETTURA E NORMALIZZAZIONE TESTO
# ======================================================================

def _safe_read_text(file_path):
    """
    Legge un file di testo provando alcune codifiche comuni.
    Restituisce stringa vuota in caso di problemi.
    """
    if not os.path.isfile(file_path):
        return ""

    contenuto = ""

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            contenuto = f.read()
        return contenuto
    except Exception:
        pass

    try:
        with open(file_path, "r", encoding="latin-1") as f:
            contenuto = f.read()
        return contenuto
    except Exception:
        pass

    try:
        with open(file_path, "r", encoding="latin-1", errors="ignore") as f:
            contenuto = f.read()
        return contenuto
    except Exception:
        return ""


def _normalize_text_for_code(text):
    """
    Normalizza il testo pensando a codice sorgente:

      - normalizza i fine riga
      - rimuove righe vuote
      - rimuove commenti molto semplici (//, #, blocchi tipo /*, *, */)

    L'obiettivo è ridurre il "rumore" nei confronti.
    """
    if text is None:
        return ""

    testo = text.replace("\r\n", "\n").replace("\r", "\n")
    righe = testo.split("\n")

    righe_pulite = []

    i = 0
    while i < len(righe):
        r = righe[i].strip()

        if r == "":
            i = i + 1
            continue

        if r.startswith("//"):
            i = i + 1
            continue

        if r.startswith("#"):
            i = i + 1
            continue

        if r.startswith("/*"):
            i = i + 1
            continue

        if r.startswith("*"):
            i = i + 1
            continue

        if r.startswith("*/"):
            i = i + 1
            continue

        righe_pulite.append(r)
        i = i + 1

    return "\n".join(righe_pulite)


def _text_to_line_set(text, min_len):
    """
    Converte il testo in un insieme di righe di lunghezza almeno min_len.
    Utile per contare le righe condivise tra due testi.
    """
    insieme = set()

    if text is None:
        return insieme

    righe = text.split("\n")
    i = 0
    while i < len(righe):
        r = righe[i].strip()
        if len(r) >= int(min_len):
            insieme.add(r)
        i = i + 1

    return insieme


def read_text_from_directory(directory_path, allowed_extensions):
    """
    Scorre ricorsivamente una directory e concatena il contenuto di tutti i file
    con estensione in allowed_extensions.

    Ogni blocco è preceduto dalla riga:
        FILE: relativo/percorso/file.ext
    """
    if not directory_path or not os.path.isdir(directory_path):
        return ""

    blocchi = []

    for radice, _, files in os.walk(directory_path):
        j = 0
        while j < len(files):
            nome = files[j]
            nome_lower = nome.lower()

            estensione_valida = False
            k = 0
            while k < len(allowed_extensions):
                est = allowed_extensions[k]
                if nome_lower.endswith(est):
                    estensione_valida = True
                    break
                k = k + 1

            if estensione_valida:
                percorso = os.path.join(radice, nome)
                contenuto = _safe_read_text(percorso)

                if contenuto is None:
                    contenuto = ""

                if contenuto != "":
                    blocchi.append(
                        "FILE: "
                        + os.path.relpath(percorso, directory_path)
                        + "\n"
                        + contenuto
                        + "\n"
                    )

            j = j + 1

    testo = "\n".join(blocchi)
    return _normalize_text_for_code(testo)


# ======================================================================
# MERGE PER DOMINIO
# ======================================================================

def _write_text(path, text):
    """
    Scrive un testo su file provando utf-8 e, in fallback, latin-1.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        try:
            with open(path, "w", encoding="latin-1", errors="ignore") as f:
                f.write(text)
        except Exception:
            pass


def generate_domain_merges(domini_dirs, allowed_extensions, progress_cb=None):
    """
    Crea __MERGED__.txt in ogni cartella dominio e restituisce i testi merged.

    progress_cb("merge_domains", indice_corrente, totale, nome_studente)
    """
    merged_texts_by_student = {}
    merged_paths_by_student = {}

    nomi = sorted(list(domini_dirs.keys()))
    tot = len(nomi)

    i = 0
    while i < tot:
        stud = nomi[i]

        if progress_cb is not None:
            try:
                progress_cb("merge_domains", i + 1, tot, stud)
            except Exception:
                pass

        dom_dir = domini_dirs.get(stud)

        if dom_dir and os.path.isdir(dom_dir):
            testo_merged = read_text_from_directory(dom_dir, allowed_extensions)
            merged_texts_by_student[stud] = testo_merged

            merged_path = os.path.join(dom_dir, "__MERGED__.txt")
            _write_text(merged_path, testo_merged)
            merged_paths_by_student[stud] = merged_path

        i = i + 1

    return merged_texts_by_student, merged_paths_by_student


# ======================================================================
# METRICHE DI CONFRONTO
# ======================================================================

def _sum_matching_block_chars(a_text, b_text, min_block_chars):
    """
    Somma la lunghezza dei blocchi coincidenti con dimensione >= min_block_chars.
    Usa difflib.SequenceMatcher sui due testi.
    """
    if not a_text or not b_text:
        return 0

    matcher = difflib.SequenceMatcher(None, a_text, b_text)
    blocks = matcher.get_matching_blocks()

    totale = 0
    i = 0
    while i < len(blocks):
        size = blocks[i].size
        if size >= int(min_block_chars):
            totale = totale + int(size)
        i = i + 1

    return totale


def calculate_text_similarity_percent(text1, text2):
    """
    Similarità globale tra due testi (0–100) basata su SequenceMatcher.ratio().
    """
    if not text1 and not text2:
        return 100.0

    if not text1 or not text2:
        return 0.0

    matcher = difflib.SequenceMatcher(None, text1, text2)
    ratio = matcher.ratio()
    return ratio * 100.0


def _normalize_for_inclusion(text):
    """
    Normalizza il testo per verificare se un contenuto è integralmente
    incluso in un altro. Riduce tutte le sequenze di whitespace a singoli
    spazi e rimuove spazi iniziali/finali.
    """
    if text is None:
        return ""

    s = text.replace("\r\n", "\n").replace("\r", "\n")

    righe = s.split("\n")
    righe_norm = []

    i = 0
    while i < len(righe):
        riga = righe[i].rstrip()
        righe_norm.append(riga)
        i = i + 1

    s = "\n".join(righe_norm)

    parti = s.split()
    s = " ".join(parti)

    s = s.strip()
    return s


def compute_merge_metrics(test_text, merged_domain_text, min_line_len=4, min_block_chars=8):
    """
    Calcola le metriche di confronto tra:
      - test_text  (verifica locale)
      - merged_domain_text  (codice complessivo sul dominio)

    Restituisce un dizionario con:
      - similarity_percent
      - shared_lines_count
      - shared_chars_len
      - percent_shared_chars_on_test
      - percent_shared_chars_on_domain
      - total_lines_test
      - total_chars_test
      - total_chars_domain
      - full_inclusion_flag
    """
    risultato = {}

    testo_test = test_text
    if testo_test is None:
        testo_test = ""

    testo_dom = merged_domain_text
    if testo_dom is None:
        testo_dom = ""

    similarity_percent = calculate_text_similarity_percent(testo_test, testo_dom)

    set_test = _text_to_line_set(testo_test, min_line_len)
    set_dom = _text_to_line_set(testo_dom, min_line_len)

    shared_lines = 0
    if len(set_test) > 0 and len(set_dom) > 0:
        shared_lines = len(set_test.intersection(set_dom))

    shared_chars_len = _sum_matching_block_chars(
        testo_test,
        testo_dom,
        min_block_chars,
    )

    total_chars_test = len(testo_test)
    total_chars_domain = len(testo_dom)

    percent_shared_chars_on_test = 0.0
    if total_chars_test > 0:
        percent_shared_chars_on_test = (shared_chars_len * 100.0) / float(total_chars_test)

    percent_shared_chars_on_domain = 0.0
    if total_chars_domain > 0:
        percent_shared_chars_on_domain = (shared_chars_len * 100.0) / float(total_chars_domain)

    norm_test = _normalize_for_inclusion(testo_test)
    norm_dom = _normalize_for_inclusion(testo_dom)

    full_inclusion_flag = False
    if norm_test != "" and norm_dom != "":
        if norm_test in norm_dom:
            full_inclusion_flag = True
        else:
            if percent_shared_chars_on_test >= 95.0 and percent_shared_chars_on_domain >= 95.0:
                full_inclusion_flag = True

    risultato["similarity_percent"] = similarity_percent
    risultato["shared_lines_count"] = shared_lines
    risultato["shared_chars_len"] = shared_chars_len
    risultato["percent_shared_chars_on_test"] = percent_shared_chars_on_test
    risultato["percent_shared_chars_on_domain"] = percent_shared_chars_on_domain
    risultato["total_lines_test"] = len(set_test)
    risultato["total_chars_test"] = total_chars_test
    risultato["total_chars_domain"] = total_chars_domain
    risultato["full_inclusion_flag"] = full_inclusion_flag

    return risultato


# ======================================================================
# PIPELINE PRINCIPALE
# ======================================================================

def analyze_reuse_by_student(tests_dirs, domini_dirs, allowed_extensions, progress_cb=None):
    """
    Esegue tutta la pipeline di analisi del riuso per studente.

    Parametri:
      - tests_dirs:   dict {studente: path_verifica_locale}
      - domini_dirs:  dict {studente: path_cartella_dominio}
      - allowed_extensions: lista/tupla di estensioni (".php", ".html", ...)

    Restituisce:
      metrics_by_student, students_in_test, students_in_domain,
      texts_test, merged_domain_texts
    """
    texts_test = {}
    merged_domain_texts = {}
    metrics_by_student = {}

    nomi_test = sorted(list(tests_dirs.keys()))
    tot_tests = len(nomi_test)

    i = 0
    while i < tot_tests:
        nome = nomi_test[i]

        if progress_cb is not None:
            try:
                progress_cb("read_tests", i + 1, tot_tests, nome)
            except Exception:
                pass

        d = tests_dirs.get(nome)
        testo = read_text_from_directory(d, allowed_extensions)

        if testo.strip() != "":
            texts_test[nome] = testo

        i = i + 1

    merged_domain_texts, _merged_paths = generate_domain_merges(
        domini_dirs,
        allowed_extensions,
        progress_cb,
    )

    studenti = sorted(
        list(
            set(texts_test.keys()).intersection(
                set(merged_domain_texts.keys()),
            )
        )
    )

    tot_cmp = len(studenti)
    j = 0
    while j < tot_cmp:
        nome = studenti[j]

        if progress_cb is not None:
            try:
                progress_cb("compare", j + 1, tot_cmp, nome)
            except Exception:
                pass

        m = compute_merge_metrics(
            texts_test.get(nome, ""),
            merged_domain_texts.get(nome, ""),
        )
        metrics_by_student[nome] = m

        j = j + 1

    students_in_test = sorted(list(texts_test.keys()))
    students_in_domain = sorted(list(merged_domain_texts.keys()))

    return metrics_by_student, students_in_test, students_in_domain, texts_test, merged_domain_texts


# ======================================================================
# MATRICI E HEATMAP
# ======================================================================

def build_similarity_matrix(student_names, texts_by_student):
    """
    Matrice NxN di similarità tra studenti,
    basata sulla percentuale di similarità tra i rispettivi testi.
    """
    n = len(student_names)
    matrice = []

    r = 0
    while r < n:
        row = []
        c = 0
        while c < n:
            nome_i = student_names[r]
            nome_j = student_names[c]

            t_i = texts_by_student.get(nome_i, "")
            t_j = texts_by_student.get(nome_j, "")

            val = calculate_text_similarity_percent(t_i, t_j)
            row.append(val)

            c = c + 1
        matrice.append(row)
        r = r + 1

    return matrice


def build_cross_similarity_matrix(row_names, col_names, row_texts, col_texts):
    """
    Matrice len(row_names) x len(col_names) per confrontare due insiemi
    diversi (es. verifiche vs domini).
    """
    nr = len(row_names)
    nc = len(col_names)
    matrice = []

    r = 0
    while r < nr:
        row = []
        c = 0
        while c < nc:
            nome_r = row_names[r]
            nome_c = col_names[c]

            t_r = row_texts.get(nome_r, "")
            t_c = col_texts.get(nome_c, "")

            val = calculate_text_similarity_percent(t_r, t_c)
            row.append(val)

            c = c + 1
        matrice.append(row)
        r = r + 1

    return matrice


def show_heatmap(parent, titolo, row_labels, col_labels, matrix):
    """
    Mostra una heatmap di similarità (0–100%) in una nuova finestra Tkinter.
    Gestisce:
      - verifiche vs verifiche
      - domini vs domini
      - verifiche vs domini
    """
    if not HAS_MATPLOTLIB:
        messagebox.showerror(
            "Errore",
            "Matplotlib non è disponibile. Installalo per visualizzare la mappa delle similitudini.",
        )
        return

    if not row_labels or not col_labels:
        messagebox.showwarning(
            "Attenzione",
            "Dati insufficienti per costruire la mappa delle similitudini.",
        )
        return

    top = Toplevel(parent)
    top.title(titolo)

    fig_width = 8.0
    fig_height = 6.0

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    dati_numerici = []
    riga_indice = 0
    while riga_indice < len(matrix):
        riga_valori = matrix[riga_indice]
        nuova_riga = []

        colonna_indice = 0
        while colonna_indice < len(riga_valori):
            valore = riga_valori[colonna_indice]
            try:
                nuovo_valore = float(valore)
            except Exception:
                nuovo_valore = 0.0
            nuova_riga.append(nuovo_valore)
            colonna_indice = colonna_indice + 1

        dati_numerici.append(nuova_riga)
        riga_indice = riga_indice + 1

    cax = ax.imshow(
        dati_numerici,
        interpolation="nearest",
        cmap="viridis",
        vmin=0.0,
        vmax=100.0,
    )

    barra = fig.colorbar(cax)
    barra.set_label("Similarita (%)")

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
    widget = canvas.get_tk_widget()
    widget.pack(fill="both", expand=True)

    top._figure = fig
    top._canvas = canvas
