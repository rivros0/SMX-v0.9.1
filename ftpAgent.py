"""
ftpAgent.py
Modulo procedurale per la gestione dei download FTP dei domini Altervista.

Responsabilità:
- Connessione FTP (latin-1 per gestire risposte non UTF-8)
- Traversal ricorsivo (MLSD se disponibile, altrimenti NLST)
- Download file con versionamento incrementale locale
- Aggiornamento progressi verso la GUI tramite 'update_queue'
- Esecuzione parallela (un thread per dominio)
- Segnale di completamento batch ("fine_download")

Interfaccia pubblica:
- start_batch_download(jobs, base_dir, update_queue)

Il chiamante si occupa di costruire 'jobs' e di passare 'base_dir' (cartella radice
che contiene le cartelle test; qui verrà creata/aggiornata la sottocartella '00_DominiFTP').
"""

import os
from ftplib import FTP
from datetime import datetime
import threading


# ======================================================================
# UTILITY LOCALI
# ======================================================================

def _format_bytes(num_bytes):
    """
    Converte byte in stringa leggibile.
    """
    unita = ["B", "KB", "MB", "GB", "TB"]
    valore = float(num_bytes)
    indice = 0
    while valore >= 1024.0 and indice < len(unita) - 1:
        valore = valore / 1024.0
        indice = indice + 1
    if indice == 0:
        return str(int(valore)) + " " + unita[indice]
    return "{:.1f} {}".format(valore, unita[indice])


def _get_versioned_path(percorso_base):
    """
    Ritorna un percorso libero applicando versionamento:
    file.ext -> file_v01.ext -> file_v02.ext ...
    """
    if not os.path.exists(percorso_base):
        return percorso_base
    base, ext = os.path.splitext(percorso_base)
    contatore = 1
    while True:
        candidato = "{}_v{:02d}{}".format(base, contatore, ext)
        if not os.path.exists(candidato):
            return candidato
        contatore = contatore + 1


# ======================================================================
# WORKER PER SINGOLO DOMINIO
# ======================================================================

def _worker_job(job, dir_ftp_base, update_queue):
    """
    Esegue il download per un singolo dominio.
    'job' deve contenere:
        item_id, alunno, dominio, stato_base, ftp_user, ftp_pass
    """
    item_id = job["item_id"]
    alunno = job["alunno"]
    dominio = job["dominio"]
    stato_base = job["stato_base"]
    ftp_user = job["ftp_user"]
    ftp_pass = job["ftp_pass"]

    # reset campi nella tabella
    update_queue.put(("set", item_id, "Stato", stato_base + " / Connessione FTP..."))
    update_queue.put(("set", item_id, "Avanzamento", "0%"))
    update_queue.put(("set", item_id, "N. file", "0"))
    update_queue.put(("set", item_id, "Elenco file", ""))
    update_queue.put(("set", item_id, "Peso cartella", "0 B"))
    update_queue.put(("set", item_id, "Ultima modifica", ""))

    if not dominio:
        update_queue.put(("log", "❌ Nessun dominio specificato per '{}'.".format(alunno)))
        update_queue.put(("set", item_id, "Stato", "Errore: dominio mancante"))
        return

    if not ftp_user or not ftp_pass:
        update_queue.put(("log", "❌ Credenziali mancanti per '{}' ({}).".format(alunno, dominio)))
        update_queue.put(("set", item_id, "Stato", "Errore: credenziali mancanti"))
        return

    host = dominio
    if host and not host.startswith("ftp."):
        host = "ftp." + host

    update_queue.put(("log", "Connessione a {} per '{}'...".format(host, alunno)))

    # Connessione (latin-1 per evitare errori di decode)
    try:
        ftp = FTP(host, timeout=30, encoding="latin-1")
        ftp.login(user=ftp_user, passwd=ftp_pass)
        update_queue.put(("set", item_id, "Stato", stato_base + " / Login OK"))
        update_queue.put(("log", "✅ Login riuscito su {} per '{}'".format(host, alunno)))
    except Exception as e:
        update_queue.put(("set", item_id, "Stato", "Errore login FTP"))
        update_queue.put(("log", "❌ Errore di connessione/login {} per '{}': {}".format(host, alunno, e)))
        return

    # Cartella locale del singolo alunno
    nome_cartella_alunno = alunno if alunno else "sconosciuto"
    dir_locale_alunno = os.path.join(dir_ftp_base, nome_cartella_alunno)
    if not os.path.isdir(dir_locale_alunno):
        try:
            os.makedirs(dir_locale_alunno, exist_ok=True)
        except Exception:
            pass

    # Raccolta lista file remoti (mlsd se disponibile, fallback nlst)
    lista_file_remoti = []
    ultima_modifica = None

    def collect_files(percorso_remoto):
        nonlocal ultima_modifica
        try:
            entries = list(ftp.mlsd(percorso_remoto))
        except Exception:
            # fallback NLST
            try:
                ftp.cwd(percorso_remoto)
                nomi = ftp.nlst()
            except Exception:
                return
            j = 0
            while j < len(nomi):
                nome = nomi[j]
                if nome not in (".", ".."):
                    if percorso_remoto in (".", ""):
                        remoto = nome
                    else:
                        remoto = percorso_remoto + "/" + nome
                    lista_file_remoti.append(remoto)
                j = j + 1
            return

        k = 0
        while k < len(entries):
            nome, facts = entries[k]
            if nome in (".", ".."):
                k = k + 1
                continue
            tipo = facts.get("type", "")
            if percorso_remoto in (".", ""):
                remoto = nome
            else:
                remoto = percorso_remoto + "/" + nome
            if tipo == "dir":
                collect_files(remoto)
            else:
                lista_file_remoti.append(remoto)
                modify = facts.get("modify")
                if modify:
                    try:
                        data = datetime.strptime(modify, "%Y%m%d%H%M%S")
                        if ultima_modifica is None or data > ultima_modifica:
                            ultima_modifica = data
                    except Exception:
                        pass
            k = k + 1

    collect_files(".")

    totale_file = len(lista_file_remoti)
    if totale_file == 0:
        update_queue.put(("set", item_id, "Stato", stato_base + " / Nessun file remoto"))
        update_queue.put(("log", "ℹ Nessun file trovato su {} per '{}'".format(dominio, alunno)))
        try:
            ftp.quit()
        except Exception:
            pass
        return

    conteggio_file = 0
    peso_totale_alunno = 0
    elenco_file_preview = []

    m = 0
    while m < len(lista_file_remoti):
        remoto = lista_file_remoti[m]
        # crea cartelle locali intermedie
        parti = remoto.split("/")
        cartella_locale_corrente = dir_locale_alunno

        n = 0
        while n < len(parti) - 1:
            nome_dir = parti[n]
            cartella_locale_corrente = os.path.join(cartella_locale_corrente, nome_dir)
            if not os.path.isdir(cartella_locale_corrente):
                try:
                    os.makedirs(cartella_locale_corrente, exist_ok=True)
                except Exception:
                    pass
            n = n + 1

        nome_file = parti[-1]
        percorso_locale_base = os.path.join(cartella_locale_corrente, nome_file)
        percorso_locale = _get_versioned_path(percorso_locale_base)

        # download
        try:
            with open(percorso_locale, "wb") as f_locale:
                ftp.retrbinary("RETR " + remoto, f_locale.write)
        except Exception:
            # file saltato
            m = m + 1
            continue

        try:
            dimensione = os.path.getsize(percorso_locale)
            peso_totale_alunno = peso_totale_alunno + dimensione
        except Exception:
            pass

        conteggio_file = conteggio_file + 1

        # preview elenco file (max 10)
        if len(elenco_file_preview) < 10:
            elenco_file_preview.append(os.path.basename(percorso_locale))
        elif len(elenco_file_preview) == 10:
            elenco_file_preview.append("...")

        # avanzamento (forzando max 99% finché non termina)
        percentuale = int(round((conteggio_file * 100.0) / float(totale_file)))
        if percentuale > 99 and conteggio_file < totale_file:
            percentuale = 99

        update_queue.put(("set", item_id, "Avanzamento", str(percentuale) + "%"))
        update_queue.put(("set", item_id, "N. file", str(conteggio_file)))
        update_queue.put(("set", item_id, "Peso cartella", _format_bytes(peso_totale_alunno)))
        update_queue.put(("set", item_id, "Elenco file", ", ".join(elenco_file_preview)))

        m = m + 1

    try:
        ftp.quit()
    except Exception:
        pass

    if ultima_modifica is not None:
        testo_data = ultima_modifica.strftime("%Y-%m-%d %H:%M")
    else:
        testo_data = "n.d."

    # fine job: porta al 100%
    update_queue.put(("set", item_id, "Avanzamento", "100%"))
    update_queue.put(("set", item_id, "Ultima modifica", testo_data))
    update_queue.put(("set", item_id, "Stato", stato_base + " / Download OK"))
    update_queue.put(("log", "✅ Download completato per '{}' ({}). Ultima modifica remota: {}".format(alunno, dominio, testo_data)))


# ======================================================================
# AVVIO BATCH PARALLELO
# ======================================================================

def start_batch_download(jobs, base_dir, update_queue):
    """
    Avvia i download per tutti i 'jobs' in parallelo.
    Crea (se necessario) la cartella '00_DominiFTP' sotto 'base_dir'.
    Al termine invia update_queue.put(("fine_download", None)).
    """
    if not base_dir or not os.path.isdir(base_dir):
        update_queue.put(("log", "❌ base_dir non valida per il download FTP."))
        return

    dir_ftp_base = os.path.join(base_dir, "00_DominiFTP")
    if not os.path.isdir(dir_ftp_base):
        os.makedirs(dir_ftp_base, exist_ok=True)

    update_queue.put(("log", "=== Inizio download FTP in {} ===".format(dir_ftp_base)))

    # avvio thread
    threads = []
    i = 0
    while i < len(jobs):
        t = threading.Thread(target=_worker_job, args=(jobs[i], dir_ftp_base, update_queue))
        t.daemon = True
        t.start()
        threads.append(t)
        i = i + 1

    # monitor in thread separato
    def _monitor():
        j = 0
        while j < len(threads):
            threads[j].join()
            j = j + 1
        update_queue.put(("fine_download", None))

    m = threading.Thread(target=_monitor, daemon=True)
    m.start()
