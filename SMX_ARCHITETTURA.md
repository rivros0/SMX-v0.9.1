# SMX – Architettura

SMX è un'applicazione desktop Tkinter per la gestione delle verifiche di programmazione: prepara, monitora, raccoglie, corregge ed esporta gli elaborati senza modificare automaticamente il server della scuola.

## Principi fondamentali

- La **Dir Remota** è il server/laboratorio. Il valore predefinito è `W:\`.
- SMX considera soltanto le cartelle remote esatte `test01` … `test30`.
- La scansione è ricorsiva nelle sottocartelle di ogni `testXX`, perché gli studenti lavorano al loro interno.
- La **Dir Locale** è il progetto completo della verifica sulla postazione del docente.
- Le operazioni sul server che scrivono dati sono sempre esplicite: distribuzione file, pulizia cartelle e recupero di uno snapshot. Non esistono scritture automatiche sul server.

## Struttura di una verifica locale

```text
20260907_Classe_Verifica/
├── test01/                       # copia locale raccolta dal server
├── test02/
├── …
├── test30/
├── 00_MixOutput/                 # file *_mix.txt
├── 00_Pdf/                       # PDF individuali e MEGAmerge
├── 00_SMXHistory/                # timeline e snapshot per studente
├── 00_SMXRecovery/               # backup creati prima di un recupero remoto
├── 00_SMXSystem/
    ├── smx_project.json          # manifest tecnico della verifica attiva
    └── events.jsonl              # audit log degli eventi SMX
├── 20260907_Classe_Verifica.smxSession
└── CONSEGNA_20260907_16-30-00_Classe_Verifica.smxSession
```

Le verifiche create con versioni precedenti, che avevano `smx_project.json` nella radice, vengono migrate automaticamente alla prima apertura.

## Persistenza e salvataggio

### `00_SMXSystem/smx_project.json`

È il manifest leggero necessario per riaprire immediatamente una Dir Locale. Contiene nome e stato della verifica, Dir Remota associata, estensioni, soglia alert, testo Intro e date di aggiornamento.

### `*.smxSession` nella root

È un archivio ZIP con estensione `.smxSession` contenente l'intero progetto: manifest, copie locali, storico, snapshot, recuperi, mix, PDF e log. Serve per trasferire una verifica su un'altra postazione o recuperarla dopo un guasto.

Il salvataggio ordinario viene mantenuto nella **root della Dir Locale**, in modo che sia subito identificabile e copiabile. I file `.smxSession` non vengono annidati l'uno nell'altro.

### Consegna ufficiale immutabile

Alla fine della verifica, **Finalizza consegna e termina verifica** crea nella root un file distinto:

```text
CONSEGNA_YYYYMMDD_HH-MM-SS_Classe_NomeVerifica.smxSession
```

Prima della creazione SMX effettua un'ultima raccolta dal server. Il file contiene lo stato completo e definitivo della verifica; non viene sovrascritto dai successivi salvataggi ordinari. Le cartelle `testXX` restano anche visibili nella Dir Locale e consultabili anche senza SMX.

Nel menu **File**:

- **Salva** aggiorna la sessione contenuta nella Dir Locale;
- **Salva con nome…** esporta una copia `.smxSession` nel percorso scelto;
- **Carica sessione .smxSession…** estrae una sessione in una nuova Dir Locale;
- **Carica verifica da cartella…** apre direttamente una verifica locale.

Alla chiusura dell'applicazione SMX sincronizza il manifest e salva la sessione. Anche il testo **Intro** viene sincronizzato durante l'editing e prima di ogni salvataggio.

## Flusso operativo

```text
Nuova verifica
    ↓
Preparazione (scansione remota automatica)
    ↓
Live (monitoraggio, timeline e alert)
    ↓
Raccogli copia locale
    ↓
Finalizza consegna e termina verifica
    ↓
Correzione (mix e similarità)
    ↓
Export (PDF e MEGAmerge)
```

All'avvio l'utente può scegliere:

1. **Nuova verifica**;
2. **Continua verifica esistente**, scegliendo ultima verifica, file `.smxSession` o cartella locale;
3. **Vai alla correzione**.

## Moduli principali

| Modulo | Responsabilità |
|---|---|
| `SMX.py` | Finestra principale, menu File, avvio, configurazione e caricamento/salvataggio progetti. |
| `project_manager.py` | Manifest, `.smxSession`, archivio completo, raccolta locale e recupero snapshot. |
| `session_manager.py` | Cattura snapshot, timeline, eventi e gestione degli alert chiusi. |
| `data_handler.py` | Operazioni mirate sulle sole `test01`–`test30`, scansione, copia, distribuzione e pulizia. |
| `utils.py` | Parsing estensioni, scansione sequenziale Live, conteggi e utilità GUI. |
| `frame_preparazione.py` | Scansione iniziale, elenco completo dei file, copia locale, distribuzione e pulizia remota. |
| `frame_live.py` | Monitoraggio sequenziale, dashboard, raccolta locale, finalizzazione della consegna e log. |
| `student_card_widget.py` | Card Live, sparkline cliccabile, lampeggiamento e chiusura alert. |
| `student_detail_window.py` | Grafico cronologico, confronto diff affiancato e recupero dello snapshot. |
| `frame_associa.py` | Associazione fra cartelle `testXX` e alunni. |
| `frame_correzione.py` | Intro, mix degli elaborati e similarità. |
| `frame_export.py` | PDF individuali, MEGAmerge e apertura rapida di `00_Pdf`. |

## Preparazione

La frame Preparazione viene mostrata dopo l'inizializzazione di una nuova verifica ed esegue subito una scansione in sola lettura della Dir Remota.

- La tabella elenca tutte le cartelle test trovate e **tutti i nomi dei file**, senza filtrare la colonna dell'elenco.
- Il conteggio “File con estensione” usa invece il set di estensioni configurato per la verifica.
- **Raccogli copia locale** aggiorna nella Dir Locale già aperta solo le cartelle test ammesse.
- **Distribuisci file** copia un file scelto nelle cartelle remote `test01`–`test30` esistenti.
- **Pulisci cartelle test remote** svuota solo il contenuto delle cartelle test e richiede tre conferme.

## Estensioni dei file

Durante la creazione di una verifica si possono scegliere preset cumulabili:

- C / C++: `.c .h .cpp .hpp`
- Java: `.java`
- Python: `.py`
- Web: `.html .htm .css .js`
- C#: `.cs`
- SQL: `.sql`
- Testo: `.txt .md`

Il campo delle estensioni resta sempre modificabile manualmente. Il valore viene memorizzato nel progetto e condiviso da Live, Correzione ed Export.

## Monitoraggio Live

La modalità Live legge una cartella test alla volta, in modo sequenziale e mai in parallelo, per ridurre il carico sul file server.

- La dashboard usa card a larghezza fissa; quando la finestra offre spazio sufficiente, dispone fino a tre colonne senza ingrandire le card.
- Ogni card mostra righe, variazione, ultima modifica e sparkline degli ultimi campioni.
- Cliccando la sparkline si apre il dettaglio dello studente.
- Il pulsante **Heatmap attività** apre una finestra con righe `testXX`/alunno e colonne corrispondenti agli intervalli di scansione più recenti. Bianco indica nessuna variazione, verde un incremento entro soglia, rosso un incremento oltre soglia e arancione una diminuzione. La finestra usa esclusivamente gli snapshot già salvati in `00_SMXHistory`, si aggiorna al termine di ogni scansione Live senza ulteriori accessi al server e non modifica né server né elaborati. Il clic su una cella apre il dettaglio dell'alunno corrispondente.
- Un incremento superiore alla soglia genera un alert, registra l'evento nel log e fa lampeggiare la card. Il pulsante **Chiudi alert** resta disponibile fino alla chiusura manuale.
- Il primo rilevamento dopo l'apertura di una sessione è una **baseline**: non genera alert retroattivi per dati storici.
- **Raccogli copia locale** crea una copia specchio: ogni `testXX` locale viene sostituita con la versione più recente del server. I file locali non più presenti sul server vengono rimossi e annotati nel log Live e nell'audit log della sessione.
- **Finalizza consegna e termina verifica** esegue l'ultima raccolta, crea una sessione `CONSEGNA_…smxSession`, mantiene `testXX` leggibili nella root e disabilita monitoraggio, scansione e raccolte successive per quella verifica.

## Interfaccia e Help

- La frame **Correzione** è disponibile nella barra delle modalità per creare i mix e analizzare le somiglianze. I controlli avanzati dell'**Intro** (etichetta, testo e relativa inclusione nel mix) restano nascosti all'apertura per mantenere essenziale la schermata ordinaria.
- Le modalità **Domini** e **Monitor Domini** non sono esposte nell'interfaccia corrente.
- Il menu **Help** contiene guida operativa e informazioni sull'applicazione.
- I principali comandi dell'interfaccia hanno tooltip al passaggio del mouse.

## Storico, diff e recupero

Quando il contenuto di uno studente cambia, `SessionManager` registra un campione e conserva lo snapshot in `00_SMXHistory`.

La finestra Dettaglio permette di:

- visualizzare l'incremento delle righe nel tempo;
- scegliere indipendentemente una versione a sinistra e una a destra;
- confrontare il contenuto in una vista diff affiancata e sincronizzata;
- leggere righe rimosse/precedenti in rosso e righe aggiunte/nuove in verde;
- ripristinare lo snapshot scelto nella Dir Remota.

Il recupero remoto è l'eccezione controllata alla regola di sola lettura: prima salva il contenuto remoto in `00_SMXRecovery`, richiede conferma e registra l'operazione nell'audit log.

## Correzione ed Export

In Correzione SMX usa le cartelle locali degli studenti (`testXX` o `alunno__testXX`) ed esclude cartelle di sistema o verifiche annidate.

1. Le estensioni e, se scelta, l'Intro generano i file `_mix.txt` in `00_MixOutput`. Il nome della cartella non viene inserito nel corpo del mix, perché è già riportato nell'intestazione dei PDF insieme all'alunno.
2. L'analisi di similarità confronta i file di mix effettivi; le cartelle spurie non entrano nella matrice.
3. Export crea PDF individuali in `00_Pdf`, applica il prefisso della verifica e può creare un unico PDF MEGAmerge con pagine pari per elaborato.
4. Il pulsante **Apri cartella PDF** apre direttamente `00_Pdf`, pronta per controllo e stampa.

## Dipendenze principali

- Python 3.12+
- Tkinter
- Matplotlib
- PyPDF2
- NumPy, Pandas e Seaborn per le analisi di similarità

## Note di sicurezza

- Non usare mai la pulizia remota senza una raccolta locale verificata.
- Il recupero di uno snapshot sovrascrive l'elaborato remoto solo dopo conferma esplicita.
- I file `.smxSession` contengono gli elaborati: trattarli come dati scolastici riservati.
