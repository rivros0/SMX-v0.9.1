# Proposta — Monitor Domini Altervista

## Obiettivo

Integrare in SMX un controllo **periodico e non invasivo** dei siti pubblici
degli alunni. Il sistema misura l'evoluzione di ciò che è effettivamente
pubblicato: pagine, CSS, JavaScript e altri file testuali raggiungibili dalla
home page.

## Flusso docente

1. Aprire o creare una verifica SMX e selezionare **Monitor Domini**.
2. Aggiungere manualmente gli alunni oppure importare un CSV UTF-8 con colonne
   `alunno,dominio` (sono accettati anche `nome`/`cognome` e `url`).
3. Premere **Acquisisci e genera report**. La prima esecuzione crea una
   baseline; le successive producono un confronto rispetto allo snapshot
   precedente dello stesso alunno.
4. Aprire i file Markdown in `00_DomainMonitor/reports/`. Il report elenca i
   file aggiunti, modificati e rimossi e, per i primi dieci file modificati,
   un diff unificato stile Git.

## Dati e metriche

Per ogni risorsa sono salvati URL, tipo MIME, hash SHA-256, righe e contenuto
testuale pubblico. Il riepilogo del report indica il numero di risorse e il
delta di righe. Questo è un indicatore di avanzamento, non una valutazione
automatica della qualità del lavoro.

```text
00_DomainMonitor/
├── snapshots/<alunno>/YYYYMMDD_HHMMSS.json
└── reports/YYYYMMDD_HHMMSS_<alunno>.md
```

## Garanzie operative

- Solo richieste HTTP GET senza credenziali: il programma non può modificare
  il sito dell'alunno.
- Crawling limitato allo stesso host, massimo 60 risorse per sito e una breve
  pausa tra le richieste.
- Rispetto di `robots.txt` quando disponibile.
- Nessuna scansione di directory, area amministrativa o risorse di terze
  parti; vengono seguiti soltanto link pubblici raggiungibili dalla home.
- I dati sono locali alla verifica SMX e quindi entrano nella sua sessione
  portabile. Trattare gli snapshot come dati scolastici riservati.

## Limiti dichiarati

Un dominio pubblico non espone necessariamente tutti i file sorgenti: PHP e
altri contenuti server-side non sono osservabili. Il sistema controlla quindi
la versione pubblicata, non il repository privato. Per una verifica puntuale
del sorgente resta preferibile affiancare GitHub Classroom, GitLab o consegna
diretta del progetto.
