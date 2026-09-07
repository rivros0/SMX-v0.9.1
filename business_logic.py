import os
import io
import textwrap
from tkinter import messagebox

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Preformatted
from reportlab.pdfgen import canvas

from PyPDF2 import PdfReader, PdfWriter


# =============================================================================
#  COSTANTI GLOBALI PER I FILE DI MIX
# =============================================================================

FLAG_END_INTRO = "###__END_INTRO__###"


# =============================================================================
#  FUNZIONI DI SUPPORTO
# =============================================================================


def _extract_directory(lbl_or_var_directory):
    """
    Estrae il percorso stringa dalla label o dalla StringVar.
    Restituisce sempre una stringa (eventualmente vuota).
    """
    if lbl_or_var_directory is None:
        return ""
    # Può essere una Label (con .cget) o una StringVar (con .get)
    if hasattr(lbl_or_var_directory, "cget"):
        return str(lbl_or_var_directory.cget("text")).strip()
    if hasattr(lbl_or_var_directory, "get"):
        return str(lbl_or_var_directory.get()).strip()
    return str(lbl_or_var_directory).strip()


def _normalize_text(text):
    """
    Normalizza il testo per evitare problemi di encoding e a capo.
    """
    if text is None:
        return ""
    text = str(text)
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    text = text.replace("\t", "    ")
    text = text.replace("\u00a0", " ")
    return text


def _parse_extensions(ext_value):
    """
    Converte il contenuto del campo estensioni in una lista normalizzata.

    Esempi accettati:
      ".php"
      "php html css"
      ".php, .html, .css"

    Restituisce sempre un elenco del tipo: [".php", ".html", ".css"]
    """
    if ext_value is None:
        return []

    if isinstance(ext_value, list) or isinstance(ext_value, tuple):
        raw_items = []
        i = 0
        while i < len(ext_value):
            raw_items.append(str(ext_value[i]))
            i = i + 1
        joined = " ".join(raw_items)
    else:
        joined = str(ext_value)

    separators = [",", ";"]
    i = 0
    while i < len(separators):
        sep = separators[i]
        joined = joined.replace(sep, " ")
        i = i + 1

    parts = joined.split()

    extensions = []
    i = 0
    while i < len(parts):
        part = parts[i].strip()
        if part != "":
            if not part.startswith("."):
                part = "." + part
            extensions.append(part.lower())
        i = i + 1

    return extensions


def wrap_preserve_indent(text, width):
    """
    Esegue il wrapping del testo preservando l'indentazione di ogni riga.
    Usato per rendere più leggibile il codice nei PDF.
    """
    if text is None:
        return ""

    lines = str(text).splitlines()
    wrapped_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        leading_spaces = len(line) - len(line.lstrip(" "))
        indent = " " * leading_spaces
        stripped = line.lstrip(" ")
        if stripped == "":
            wrapped_lines.append("")
        else:
            wrapped = textwrap.wrap(stripped, width=width - leading_spaces) or [""]
            j = 0
            while j < len(wrapped):
                wrapped_lines.append(indent + wrapped[j])
                j = j + 1
        i = i + 1

    return "\n".join(wrapped_lines)


def estrai_contenuto_per_pdf_da_mix(mix_text):
    """
    Restituisce la parte di testo di un file di mix che deve essere
    inclusa nel PDF finale.

    Logica:
      - se trova una riga che corrisponde esattamente a FLAG_END_INTRO
        (ignorando spazi all'inizio e alla fine), restituisce tutto ciò
        che viene DOPO quella riga;
      - se la flag non è presente, restituisce il testo originale
        (retrocompatibilità con vecchi file di mix).

    In questo modo l'introduzione (intro di correzione, eventuali
    commenti sui dominii, note, ecc.) può essere scritta prima della
    flag e NON verrà inclusa nel PDF, mentre il corpo conterrà il nome
    della subdirectory (es. test01) e tutti i file della verifica, che
    verranno preservati nel PDF.
    """
    if mix_text is None:
        return ""

    text = str(mix_text)

    if "\r\n" in text:
        separator = "\r\n"
        lines = text.split("\r\n")
    else:
        separator = "\n"
        lines = text.split("\n")

    start_index = 0
    index = 0
    found_flag = False

    while index < len(lines):
        current_line = lines[index]
        if current_line.strip() == FLAG_END_INTRO:
            found_flag = True
            start_index = index + 1
            break
        index = index + 1

    if not found_flag:
        return text

    body_lines = []
    index = start_index
    while index < len(lines):
        body_lines.append(lines[index])
        index = index + 1

    body_text = separator.join(body_lines)

    return body_text.lstrip("\r\n")

def _add_header_to_page(page, header_text):
    """
    Aggiunge un'intestazione testuale (header_text) nella parte alta
    della pagina PDF passata come argomento, SENZA aggiungere nuove pagine.

    Utilizza un overlay generato con reportlab e lo fonde con la pagina
    originale tramite PyPDF2.
    """
    if page is None:
        return

    try:
        media_box = page.mediabox
        width = float(media_box.width)
        height = float(media_box.height)
    except Exception:
        width = A4[0]
        height = A4[1]

    buffer_stream = io.BytesIO()
    c = canvas.Canvas(buffer_stream, pagesize=(width, height))

    try:
        c.setFont("Helvetica-Bold", 12)
    except Exception:
        c.setFont("Helvetica", 12)

    margin_x = 40.0
    margin_y = height - 30.0

    testo = str(header_text)
    c.drawString(margin_x, margin_y, testo)

    c.save()
    buffer_stream.seek(0)

    try:
        overlay_reader = PdfReader(buffer_stream)
        overlay_page = overlay_reader.pages[0]
        page.merge_page(overlay_page)
    except Exception:
        pass


# =============================================================================
#  CREAZIONE FILE MIX
# =============================================================================


def mix_files(lbl_or_var_directory,
              entry_prompt,
              entry_extension,
              tree,
              report_text,
              include_prompt,
              include_subdir):
    """
    Funzione principale richiamata dalla scheda di Correzione per creare
    tutti i file di mix all'interno della directory 00_MixOutput.

    Parametri:
      - lbl_or_var_directory : Label o StringVar con la directory selezionata
      - entry_prompt         : widget Text contenente il prompt/intro
      - entry_extension      : widget Entry con le estensioni
      - tree                 : Treeview con elenco subdirectory (testXX)
      - report_text          : widget Text per il log
      - include_prompt       : bool, include o meno l'intro nel mix
      - include_subdir       : bool, include o meno il nome della subdir nel mix
    """
    base_dir = _extract_directory(lbl_or_var_directory)

    report_text.delete("1.0", "end")

    if base_dir == "" or not os.path.isdir(base_dir):
        messagebox.showwarning(
            "Attenzione",
            "Directory di lavoro non valida.\nSeleziona una directory dalla GUI."
        )
        return

    prompt_string = entry_prompt.get("1.0", "end").strip()
    extensions_text = entry_extension.get()

    if extensions_text.strip() == "":
        messagebox.showwarning(
            "Attenzione",
            "Specificare almeno una estensione per i file da mixare."
        )
        return

    extensions = _parse_extensions(extensions_text)

    output_directory = os.path.join(base_dir, "00_MixOutput")
    try:
        os.makedirs(output_directory, exist_ok=True)
    except Exception as exc:
        messagebox.showerror(
            "Errore",
            "Impossibile creare la directory 00_MixOutput:\n" + str(exc)
        )
        return

        report_text.insert("end", "Inizio creazione dei file di mix...\n")

    # Azzeriamo prima la colonna "mix_file" per tutte le righe
    items = tree.get_children()
    idx = 0
    while idx < len(items):
        item_id = items[idx]
        try:
            tree.set(item_id, "mix_file", "")
        except Exception:
            # In caso di problemi non blocchiamo l'esecuzione
            pass
        idx = idx + 1

    # Ora creiamo i file di mix e aggiorniamo la tabella
    items = tree.get_children()
    idx = 0
    while idx < len(items):
        item_id = items[idx]
        values = tree.item(item_id, "values")
        if values and len(values) > 0:
            subdir = str(values[0]).strip()
            if subdir != "" and not subdir.startswith("00"):
                msg, mix_path = create_mix_file(
                    base_directory=base_dir,
                    subdir=subdir,
                    prompt_string=prompt_string,
                    extensions=extensions,
                    output_directory=output_directory,
                    include_prompt=include_prompt,
                    include_subdir=include_subdir,
                )

                # Log dell'operazione
                report_text.insert("end", msg)

                # Se il file di mix è stato creato correttamente,
                # aggiorniamo la colonna "mix_file" della riga corrispondente
                if mix_path is not None and mix_path != "":
                    try:
                        tree.set(item_id, "mix_file", mix_path)
                    except Exception:
                        # Non blocchiamo in caso di errore sulla Treeview
                        pass

        idx = idx + 1

    report_text.insert("end", "Creazione dei file di mix completata.\n")

    report_text.see("end")


def create_mix_file(base_directory,
                    subdir,
                    prompt_string,
                    extensions,
                    output_directory,
                    include_prompt,
                    include_subdir):
    """
    Crea il file di mix per una specifica subdirectory (es. test01).

    - Cerca ricorsivamente tutti i file con le estensioni indicate;
    - Ignora qualunque sottocartella che inizi con '00';
    - Scrive un file '<subdir>_mix.txt' nella directory 00_MixOutput.
    - ESCLUDE SEMPRE i file PDF dal mix, anche se l'estensione '.pdf'
      è presente in 'extensions', per evitare di scrivere contenuto
      binario nel file di testo.
    """
    if not isinstance(extensions, list) and not isinstance(extensions, tuple):
        extensions = _parse_extensions(extensions)

    normalized_exts = []
    i = 0
    while i < len(extensions):
        ext = str(extensions[i]).strip().lower()
        if ext != "":
            if not ext.startswith("."):
                ext = "." + ext
            normalized_exts.append(ext)
        i = i + 1

    full_path = os.path.join(base_directory, subdir)
    mix_file_path = os.path.join(output_directory, subdir + "_mix.txt")

    try:
        files_to_mix = []

        for root, dirs, files in os.walk(full_path):
            # esclude sottocartelle che iniziano con '00'
            safe_dirs = []
            j = 0
            while j < len(dirs):
                dname = str(dirs[j])
                if not dname.startswith("00"):
                    safe_dirs.append(dname)
                j = j + 1
            dirs[:] = safe_dirs

            k = 0
            while k < len(files):
                file_name = files[k]
                k = k + 1

                lower_name = str(file_name).lower()

                # ESCLUSIONE FORZATA DEI PDF DAL MIX DI TESTO
                if lower_name.endswith(".pdf"):
                    continue

                match = False
                m = 0
                while m < len(normalized_exts):
                    ext = normalized_exts[m]
                    if lower_name.endswith(ext):
                        match = True
                        break
                    m = m + 1

                if match:
                    files_to_mix.append(os.path.join(root, file_name))

        if len(files_to_mix) == 0:
            message = (
                "Nessun file con estensioni "
                + ", ".join(normalized_exts)
                + " (esclusi i PDF) trovato nella subdirectory "
                + subdir
                + " (sottocartelle '00*' escluse). File di mix NON creato.\n"
            )
            return message, None

        with open(mix_file_path, "w", encoding="utf-8") as mix_file:
            # -------------------------------------------------------------
            # INTRO: solo prompt (se richiesto)
            # Questa parte non verrà inclusa nel PDF, perché si trova
            # prima della flag FLAG_END_INTRO.
            # -------------------------------------------------------------
            if include_prompt and prompt_string:
                intro_text = _normalize_text(prompt_string)
                mix_file.write(intro_text + "\n\n")

            # -------------------------------------------------------------
            # FLAG DI FINE INTRO
            # Tutto ciò che si trova sopra questa riga potrà essere
            # scartato in fase di creazione del PDF.
            # -------------------------------------------------------------
            mix_file.write(FLAG_END_INTRO + "\n\n")

            # -------------------------------------------------------------
            # DA QUI IN POI IL CONTENUTO VIENE PRESERVATO NEL PDF
            # -------------------------------------------------------------
            if include_subdir:
                mix_file.write(subdir + "\n\n")

            z = 0
            while z < len(files_to_mix):
                file_path = files_to_mix[z]
                z = z + 1

                try:
                    with open(file_path, "r", encoding="utf-8") as current_file:
                        content = current_file.read()
                except UnicodeDecodeError:
                    with open(
                        file_path,
                        "r",
                        encoding="latin-1",
                        errors="replace",
                    ) as current_file:
                        content = current_file.read()

                content = _normalize_text(content)

                # Separatore visivo tra i file, come nel tuo esempio
                mix_file.write("###############################################################\n\n")
                mix_file.write(os.path.basename(file_path) + "\n")
                mix_file.write(content + "\n\n")

        message = (
            "File di mix creato per "
            + subdir
            + ": "
            + mix_file_path
            + "\n"
        )
        return message, mix_file_path

    except Exception as exc:
        message = "Errore durante il mix per " + subdir + ": " + str(exc) + "\n"
        return message, None

def _add_header_to_page(page, header_text):
    """
    Aggiunge un'intestazione testuale (header_text) in alto alla pagina PDF
    passata come argomento, SENZA aggiungere nuove pagine.

    Usa un overlay generato con reportlab e lo fonde con la pagina
    originale tramite PyPDF2.
    """
    if page is None:
        return

    try:
        media_box = page.mediabox
        width = float(media_box.width)
        height = float(media_box.height)
    except Exception:
        width = A4[0]
        height = A4[1]

    buffer_stream = io.BytesIO()
    c = canvas.Canvas(buffer_stream, pagesize=(width, height))

    try:
        c.setFont("Helvetica-Bold", 12)
    except Exception:
        c.setFont("Helvetica", 12)

    margin_x = 40.0
    margin_y = height - 30.0

    testo = str(header_text)
    c.drawString(margin_x, margin_y, testo)

    c.save()
    buffer_stream.seek(0)

    try:
        overlay_reader = PdfReader(buffer_stream)
        overlay_page = overlay_reader.pages[0]
        page.merge_page(overlay_page)
    except Exception:
        # Se qualcosa va storto nel merge, non blocchiamo l'esecuzione
        pass


# =============================================================================
#  CREAZIONE PDF INDIVIDUALI DA *_mix.txt
# =============================================================================


def create_individual_pdfs(base_directory, report_text):
    """
    Crea PDF individuali nella directory 00_Pdf.

    1) PDF da file *_mix.txt in 00_MixOutput:
       - usa font monospaziato (Courier);
       - ignora file che iniziano per '00';
       - SALTA i mix relativi a cartelle che possiedono già PDF originali
         (per evitare duplicati rispetto ai *_pdfmix.pdf).

    2) PDF da file .pdf originali nelle cartelle testXX:
       - cerca ricorsivamente tutti i .pdf;
       - crea un unico PDF per cartella;
       - applica su OGNI pagina un'intestazione con il nome della cartella
         (es. 'accogli.joele__test01');
       - salva in 00_Pdf come '<cartella>_pdfmix.pdf'.

    La logica delle pagine pari per la stampa fronte/retro è gestita
    successivamente dal MEGAmerge nella scheda Export.
    """
    base_dir = _extract_directory(base_directory)
    if base_dir == "" or not os.path.isdir(base_dir):
        messagebox.showwarning(
            "Attenzione",
            "Directory di lavoro non valida per la creazione dei PDF."
        )
        return

    mix_output_directory = os.path.join(base_dir, "00_MixOutput")
    pdf_output_directory = os.path.join(base_dir, "00_Pdf")

    try:
        os.makedirs(pdf_output_directory, exist_ok=True)
    except Exception as exc:
        messagebox.showerror(
            "Errore",
            "Impossibile creare la directory 00_Pdf:\n" + str(exc)
        )
        return

    styles = getSampleStyleSheet()
    monospace_style = ParagraphStyle(
        "Monospace",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=9,
        leading=11,
    )

    max_char_width = 95

    report_text.insert("end", "Inizio creazione dei PDF individuali...\n")
    report_text.see("end")

    created_count = 0

    # ============================================================
    # 0) Prima passo: verifico quali cartelle contengono PDF originali
    #    → costruisco un set di nomi cartella (es. 'accogli.joele__test01')
    # ============================================================
    subdirs_con_pdf = set()

    try:
        entries = sorted(os.listdir(base_dir))
    except Exception:
        entries = []

    idx_entry = 0
    while idx_entry < len(entries):
        entry_name = entries[idx_entry]
        idx_entry = idx_entry + 1

        if entry_name.startswith("00"):
            continue

        subdir_path = os.path.join(base_dir, entry_name)
        if not os.path.isdir(subdir_path):
            continue

        # scandisco la cartella per vedere se esiste almeno un .pdf
        found_pdf = False

        for root, dirs, files in os.walk(subdir_path):
            # escludo eventuali sottocartelle "00*"
            safe_dirs = []
            d_idx = 0
            while d_idx < len(dirs):
                dname = str(dirs[d_idx])
                if not dname.startswith("00"):
                    safe_dirs.append(dname)
                d_idx = d_idx + 1
            dirs[:] = safe_dirs

            f_idx = 0
            while f_idx < len(files):
                fn = files[f_idx]
                f_idx = f_idx + 1

                if fn.lower().endswith(".pdf"):
                    found_pdf = True
                    break

            if found_pdf:
                break

        if found_pdf:
            subdirs_con_pdf.add(entry_name)

    # ============================================================
    # 1) PDF dai file *_mix.txt (comportamento originario,
    #    ma saltando le cartelle che hanno PDF originali)
    # ============================================================
    if os.path.isdir(mix_output_directory):
        try:
            names = sorted(os.listdir(mix_output_directory))
        except Exception:
            names = []
    else:
        names = []

    i = 0
    while i < len(names):
        file_name = names[i]
        i = i + 1

        if file_name.startswith("00"):
            continue

        if not file_name.endswith("_mix.txt"):
            continue

        # ricavo il "nome cartella" dal nome del mix:
        # es. 'accogli.joele__test01_mix.txt' -> 'accogli.joele__test01'
        base_name = file_name[:-len("_mix.txt")]

        # se per questa cartella esistono già PDF originali,
        # NON creo il PDF dal mix per evitare duplicati
        if base_name in subdirs_con_pdf:
            continue

        mix_path = os.path.join(mix_output_directory, file_name)

        try:
            with open(mix_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(
                    mix_path,
                    "r",
                    encoding="latin-1",
                    errors="replace",
                ) as f:
                    content = f.read()
            except Exception as exc:
                report_text.insert(
                    "end",
                    "Errore nella lettura di "
                    + file_name
                    + ": "
                    + str(exc)
                    + "\n",
                )
                report_text.see("end")
                continue
        except Exception as exc:
            report_text.insert(
                "end",
                "Errore nella lettura di "
                + file_name
                + ": "
                + str(exc)
                + "\n",
            )
            report_text.see("end")
            continue

        content = _normalize_text(content)
        content_for_pdf = estrai_contenuto_per_pdf_da_mix(content)
        wrapped = wrap_preserve_indent(content_for_pdf, max_char_width)

        pdf_name = os.path.splitext(file_name)[0] + ".pdf"
        pdf_path = os.path.join(pdf_output_directory, pdf_name)

        try:
            doc = SimpleDocTemplate(pdf_path, pagesize=A4)
            story = [Preformatted(wrapped, monospace_style)]
            doc.build(story)
            created_count = created_count + 1
            report_text.insert("end", "Creato PDF da mix: " + pdf_name + "\n")
            report_text.see("end")
        except Exception as exc:
            report_text.insert(
                "end",
                "Errore nella creazione del PDF da "
                + file_name
                + ": "
                + str(exc)
                + "\n",
            )
            report_text.see("end")

    # ============================================================
    # 2) PDF originali per cartella (solo da .pdf)
    #    → un PDF per cartella, header con nome cartella su ogni pagina
    # ============================================================
    # riutilizzo 'entries' già letti sopra
    idx_entry = 0
    while idx_entry < len(entries):
        entry_name = entries[idx_entry]
        idx_entry = idx_entry + 1

        if entry_name.startswith("00"):
            continue

        subdir_path = os.path.join(base_dir, entry_name)
        if not os.path.isdir(subdir_path):
            continue

        writer = PdfWriter()
        pages_found = 0

        for root, dirs, files in os.walk(subdir_path):
            # escludo eventuali sottocartelle "00*"
            safe_dirs = []
            d_idx = 0
            while d_idx < len(dirs):
                dname = str(dirs[d_idx])
                if not dname.startswith("00"):
                    safe_dirs.append(dname)
                d_idx = d_idx + 1
            dirs[:] = safe_dirs

            f_idx = 0
            while f_idx < len(files):
                fn = files[f_idx]
                f_idx = f_idx + 1

                if not fn.lower().endswith(".pdf"):
                    continue

                pdf_input_path = os.path.join(root, fn)

                try:
                    reader = PdfReader(pdf_input_path)
                except Exception as exc:
                    report_text.insert(
                        "end",
                        "Errore nella lettura del PDF '"
                        + fn
                        + "' in "
                        + entry_name
                        + ": "
                        + str(exc)
                        + "\n",
                    )
                    report_text.see("end")
                    continue

                p_index = 0
                while p_index < len(reader.pages):
                    page = reader.pages[p_index]
                    _add_header_to_page(page, entry_name)
                    writer.add_page(page)
                    pages_found = pages_found + 1
                    p_index = p_index + 1

        if pages_found == 0:
            # nessun PDF trovato in questa cartella, passo alla successiva
            continue

        out_name = entry_name + "_pdfmix.pdf"
        out_path = os.path.join(pdf_output_directory, out_name)

        try:
            with open(out_path, "wb") as out_f:
                writer.write(out_f)
            created_count = created_count + 1
            report_text.insert(
                "end",
                "Creato PDF da PDF originali per cartella "
                + entry_name
                + ": "
                + out_name
                + " (pagine: "
                + str(pages_found)
                + ")\n",
            )
            report_text.see("end")
        except Exception as exc:
            report_text.insert(
                "end",
                "Errore nella scrittura del PDF di gruppo per "
                + entry_name
                + ": "
                + str(exc)
                + "\n",
            )
            report_text.see("end")

    report_text.insert(
        "end",
        "Creazione dei PDF individuali completata. Totale PDF creati: "
        + str(created_count)
        + "\n",
    )
    report_text.see("end")





# =============================================================================
#  MEGAMERGE PDF (BACKWARD COMPATIBLE)
# =============================================================================


def merge_all_files(base_directory, report_text,  verifica_name=None):
    """
    Esegue il merge di tutti i PDF presenti in 00_Pdf in un unico file:

      - usa solo i PDF che NON iniziano con '00';
      - per ogni elaborato, assicura un numero PARI di pagine
        aggiungendo una pagina bianca se necessario;
      - salva il risultato come 00_MEGAmerged_output_final.pdf
        all'interno di 00_Pdf.

    Nota: questa funzione viene mantenuta per compatibilità con versioni
    precedenti. La logica è coerente con quella usata nella scheda Export.
    """
    base_dir = _extract_directory(base_directory)
    if base_dir == "" or not os.path.isdir(base_dir):
        messagebox.showwarning(
            "Attenzione",
            "Directory di lavoro non valida per il MEGAmerge."
        )
        return

    pdf_output_directory = os.path.join(base_dir, "00_Pdf")
    if not os.path.isdir(pdf_output_directory):
        messagebox.showwarning(
            "Attenzione",
            "La directory 00_Pdf non esiste. Crea prima i PDF multipli."
        )
        return

    report_text.insert("end", "Inizio MEGAmerge dei PDF...\n")
    report_text.see("end")

    pdf_files = sorted(os.listdir(pdf_output_directory))
    writer = PdfWriter()

    i = 0
    while i < len(pdf_files):
        pdf_name = pdf_files[i]
        i = i + 1

        if pdf_name.startswith("00"):
            continue

        if not pdf_name.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_output_directory, pdf_name)
        try:
            reader = PdfReader(pdf_path)
        except Exception as exc:
            report_text.insert(
                "end",
                "Errore nella lettura del PDF "
                + pdf_name
                + ": "
                + str(exc)
                + "\n",
            )
            report_text.see("end")
            continue

        num_pages = len(reader.pages)
        j = 0
        while j < num_pages:
            page = reader.pages[j]
            writer.add_page(page)
            j = j + 1

        if num_pages % 2 != 0:
            blank_page = writer.add_blank_page()
            blank_page.mediabox.upper_right = (A4[0], A4[1])

    if verifica_name is None or str(verifica_name).strip() == "":
        final_pdf_name = "00_MEGAmerged_output_final.pdf"
    else:
        safe_name = str(verifica_name).strip()
        final_pdf_name = "00_MEGAmerged_output_final_" + safe_name + ".pdf"

    final_pdf_path = os.path.join(pdf_output_directory, final_pdf_name)

    try:
        with open(final_pdf_path, "wb") as out_file:
            writer.write(out_file)
        report_text.insert(
            "end",
            "MEGAmerge completato. File PDF finale creato:\n"
            + final_pdf_path
            + "\n",
        )
        report_text.see("end")
    except Exception as exc:
        report_text.insert(
            "end",
            "Errore durante la scrittura del PDF finale: "
            + str(exc)
            + "\n",
        )
        report_text.see("end")
