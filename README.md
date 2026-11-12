# SMX — Gestione elaborati

Applicazione desktop per la gestione delle verifiche scolastiche. Il progetto include
un **launcher** per Windows e Linux, indipendente dall'installazione di Python.

## Modalità di distribuzione

La repository è pubblica. Il launcher controlla automaticamente l'ultima release
pubblica di GitHub e visualizza la disponibilità di un aggiornamento.
**Non installa nulla senza il consenso esplicito** dell'utente.

| Piattaforma | File da distribuire | Pacchetto scaricato dal launcher |
|---|---|---|
| Windows 10/11 x64 | `SMX-Launcher.exe` | `SMX-windows-x64.zip` |
| Linux x86-64 | `SMX-Launcher` (eseguibile ELF) | `SMX-linux-x64.tar.gz` |

Su Linux il launcher ELF è compilato su Ubuntu 22.04: è consigliato
utilizzare una distribuzione x86-64 con glibc compatibile e interfaccia grafica.
Non è un'AppImage; non richiede Python ma può richiedere librerie GUI di sistema.

## Primo avvio

1. Scaricare il launcher dalla pagina **Releases**.
2. Avviarlo (su Linux: `chmod +x SMX-Launcher && ./SMX-Launcher`).
3. Alla prima esecuzione premere **Aggiorna / Installa**.
4. Attendere il termine del download e poi selezionare **Avvia SMX**.

Ai successivi avvii l'aggiornamento viene **controllato**, non installato.
Il pulsante **Versione precedente** permette il ripristino manuale dopo
l'installazione di almeno due versioni. Senza connessione Internet si può
continuare a utilizzare l'ultima versione locale.

Le installazioni risiedono in:
- Windows: `%LOCALAPPDATA%\\SMX\\Launcher\\versions\\`
- Linux: `~/.local/share/smx/launcher/versions/`

Le directory dei progetti e degli elaborati sono **esterne** a questa area.
Il launcher non le apre, cancella o migra. Evitare di salvare le verifiche
nella directory di installazione del launcher.

## Pubblicazione di una release

I commit su `master` **non** producono aggiornamenti per gli utenti.
Si pubblicano solo versioni esplicite con tag `vMAJOR.MINOR.PATCH`.
Aggiornare prima `smx_version.APP_VERSION`.

Da una copia locale aggiornata:

```bash
git switch master
git pull origin master
git tag v0.9.1
git push origin v0.9.1
```

> Usare questo tag soltanto se non esiste già. Per le release successive
> aggiornare la versione, ad esempio `0.9.2`, e pubblicare `v0.9.2`.

Il workflow `.github/workflows/smx-release.yml` costruisce i pacchetti
su runner Windows e Linux distinti. In caso di esito positivo crea
automaticamente una GitHub Release con:
- `SMX-Launcher.exe` e `SMX-Launcher`
- `SMX-windows-x64.zip` e `SMX-linux-x64.tar.gz`
- `SHA256SUMS.txt`

I pacchetti degli utenti vengono scaricati tramite HTTPS e verificati con
SHA-256 prima dell'installazione. Per evitare il rischio di aggiornamenti
sbagliati è consigliato non modificare gli asset di una release già pubblicata.
Il launcher non offre una firma crittografica indipendente da GitHub.

### Build locale (per collaudo)

```bash
python -m pip install -r requirements-build.txt
python build_release.py
```

Eseguire il comando nel sistema operativo per cui si desidera compilare.
Il file `SMX.spec` preesistente è conservato per le build manuali storiche.

### Test automatici

```bash
python -m unittest -v test_smx_launcher.py
```

## Sicurezza della repository pubblica

Non versionare credenziali FTP, rubriche studenti, verifiche, file di sessione
o copie locali del laboratorio. `.gitignore` esclude i principali percorsi
generati e gli artefatti di compilazione. Le credenziali FTP vengono richieste
all'utente durante l'uso, non devono essere inserite nei sorgenti.

**Attenzione:** il vecchio contenuto di `build/` e `__pycache__/` rimane
recuperabile dalla cronologia Git precedente; la loro rimozione dal ramo
corrente non riscrive la cronologia. La verifica dei binari storici resta
un'attività separata prima di dichiarare completato un audit di sicurezza.
