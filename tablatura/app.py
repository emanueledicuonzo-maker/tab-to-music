"""Il programma: la tablatura in una finestra, con Apri e Importa in alto.

Un piccolo server che gira solo su questo computer (127.0.0.1) e una finestra
di Chrome senza barre che gli parla. Il server sa tre cose: quali canzoni sono
già state lavorate (in Musica/tab), cosa c'è nelle cartelle da cui importare,
e la coda delle canzoni da lavorare, che passa una alla volta al programma a
riga di comando. Quando la finestra si chiude e la coda è vuota, si spegne.

    python -m tablatura.app
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import hashlib
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import allinea, copertina, guitarpro, libreria, online
from .strumenti import STRUMENTI
from .visore import pagina

PORTA = 8777
AUDIO = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}
RADICE = Path(__file__).resolve().parent.parent
PWA = Path(__file__).resolve().parent / "pwa"


def cartella_musica() -> Path:
    try:
        uscita = subprocess.run(["xdg-user-dir", "MUSIC"], capture_output=True, text=True).stdout.strip()
    except OSError:
        uscita = ""
    return Path(uscita) if uscita else Path.home() / "Musica"


MUSICA = cartella_musica()
TAB = MUSICA / "tab"
FILE_STATO = Path.home() / ".config" / "tablatura" / "stato.json"


def leggi_stato() -> dict:
    try:
        return json.loads(FILE_STATO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salva_stato(**cambi) -> dict:
    stato = leggi_stato() | cambi
    FILE_STATO.parent.mkdir(parents=True, exist_ok=True)
    FILE_STATO.write_text(json.dumps(stato, ensure_ascii=False, indent=1), encoding="utf-8")
    return stato


# ---------------------------------------------------------------- la coda


@dataclass
class Lavoro:
    canzone: str  # il file audio
    album: str
    titolo: str
    strumento: str
    testo: bool
    lingua: str
    stato: str = "in attesa"  # in attesa · in lavorazione · fatta · errore
    dettaglio: str = ""
    fase: int = -1
    registro: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.album}/{self.titolo}"


# Le fasi del lavoro, riconosciute dalle righe che stampa il programma.
FASI = [
    ("separo", "separo le tracce"),
    ("metronomo", "cerco il metronomo"),
    ("trascrivo il ", "trascrivo le note"),
    ("trascrivo il testo", "trascrivo il testo"),
    ("riconosco gli accordi", "riconosco gli accordi"),
    ("riconosco legati", "legati e bending"),
]
RUMORE = re.compile(r"^\d{4}-\d\d-\d\d|^[EWI]\d{4}|tensorflow|cuda|cudnn|cublas|oneDNN|TF-TRT|AVX|WARNING|rebuild|absl|^\s*warn", re.I)

# Le tablature da collegare a una canzone appena finisce di lavorarla:
# percorso del file audio → (archivio, nome nello zip).
da_collegare: dict[str, tuple[str, str]] = {}
CARTELLE_DISCHI = [MUSICA, Path.home() / "Scaricati"]

TUE = TAB / "_tablature_tue"          # i file Guitar Pro caricati da te
SINCRONIE = FILE_STATO.parent / "sincronie"
_indice = {"quando": 0.0, "voci": []}


def indice_musica() -> list[dict]:
    """L'elenco di tutta la musica, rifatto al massimo una volta al minuto."""
    if time.monotonic() - _indice["quando"] > 60:
        _indice["voci"] = libreria.aggiorna(CARTELLE_DISCHI, [TAB])
        _indice["quando"] = time.monotonic()
    return _indice["voci"]


def disco_permesso(percorso: str) -> Path | None:
    p = Path(percorso).resolve()
    if p.suffix.lower() in libreria.AUDIO and p.is_file() and any(c.resolve() in p.parents for c in CARTELLE_DISCHI):
        return p
    return None


def voce_di(percorso: str) -> dict:
    return next((v for v in indice_musica() if v["percorso"] == percorso), None) or {
        "percorso": percorso, "artista": "", "titolo": Path(percorso).stem, "album": Path(percorso).parent.name, "durata": 0}


def id_fatta(percorso: str) -> str | None:
    p = Path(percorso)
    return f"{p.parent.name}/{p.stem}" if (TAB / p.parent.name / p.stem / "leggio.json").is_file() else None


def tablatura_del_disco(percorso: str) -> dict | None:
    """La tablatura per questo disco: quella scelta da te, o la migliore dell'archivio."""
    scelte = leggi_stato().get("tabPerDisco", {})
    if percorso in scelte:
        return scelte[percorso] | {"scelta": True}
    v = voce_di(percorso)
    candidati = guitarpro.cerca(v["titolo"], v["artista"], MUSICA, quante=1)
    return (candidati[0] | {"scelta": False}) if candidati else None


def chiave_sincronia(percorso: str, tab: dict) -> Path:
    import hashlib

    firma = percorso + "|" + (tab.get("tua") or f"{tab.get('archivio')}|{tab.get('nome')}")
    return SINCRONIE / (hashlib.sha1(firma.encode()).hexdigest()[:16] + ".json")


coda: list[Lavoro] = []
serratura = threading.Lock()
sveglia = threading.Event()


def lavora() -> None:
    """Una canzone alla volta, nell'ordine in cui sono arrivate."""
    while True:
        sveglia.wait()
        with serratura:
            prossimo = next((l for l in coda if l.stato == "in attesa"), None)
            if prossimo is None:
                sveglia.clear()
                continue
            prossimo.stato = "in lavorazione"
        comando = [
            sys.executable, "-m", "tablatura", prossimo.canzone,
            "--strumento", prossimo.strumento,
            "--dove", str(TAB / prossimo.album / prossimo.titolo),
        ]
        if prossimo.testo:
            comando.append("--testo")
            if prossimo.lingua:
                comando += ["--lingua", prossimo.lingua]
        if prossimo.strumento.startswith("chitarra"):
            comando.append("--polifonico")
        # Senza PYTHONUNBUFFERED il programma tiene le righe per sé fino alla
        # fine, e la barra di avanzamento resterebbe ferma per tutto il lavoro.
        processo = subprocess.Popen(
            comando, cwd=RADICE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
            env=os.environ | {"PYTHONUNBUFFERED": "1"},
        )
        for riga in processo.stdout:
            riga = riga.strip()
            if not riga:
                continue
            prossimo.registro.append(riga)
            if RUMORE.search(riga):
                continue
            for i, (inizio, nome) in enumerate(FASI):
                if riga.startswith(inizio) and i > prossimo.fase:
                    prossimo.fase = i
            prossimo.dettaglio = riga[:120]
        esito = processo.wait()
        if esito == 0:
            try:
                copertina.salva(Path(prossimo.canzone), TAB / prossimo.album)
            except OSError:
                pass
            if prossimo.canzone in da_collegare:
                archivio, nome = da_collegare.pop(prossimo.canzone)
                try:
                    guitarpro.estrai(TAB / prossimo.album / prossimo.titolo, MUSICA, archivio, nome)
                except Exception as errore:
                    prossimo.registro.append(f"tablatura non collegata: {errore}")
        prossimo.stato = "fatta" if esito == 0 else "errore"


def accoda(percorsi: list[str], strumento: str, testo: bool, lingua: str) -> int:
    canzoni: list[Path] = []
    for p in map(Path, percorsi):
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() in AUDIO and TAB not in f.parents and not f.parent.name.endswith("-tablatura"):
                    canzoni.append(f)
        elif p.suffix.lower() in AUDIO:
            canzoni.append(p)
    with serratura:
        for f in canzoni:
            coda.append(Lavoro(str(f), f.parent.name, f.stem, strumento, testo, lingua))
    sveglia.set()
    return len(canzoni)


# ---------------------------------------------------------------- le canzoni fatte


def canzoni_fatte() -> list[dict]:
    fatte = []
    if TAB.is_dir():
        for descrizione in sorted(TAB.glob("*/*/leggio.json")):
            cartella = descrizione.parent
            immagine = copertina.di(cartella.parent)
            fatte.append({
                "id": f"{cartella.parent.name}/{cartella.name}",
                "album": cartella.parent.name,
                "canzone": cartella.name,
                "copertina": f"/tab/{urllib.parse.quote(cartella.parent.name)}/{immagine.name}" if immagine else None,
            })
    return fatte


def pagina_di(cartella: Path) -> str:
    """La pagina della canzone, rifatta ogni volta dalla sua descrizione:
    così anche le canzoni lavorate prima hanno la pagina più recente."""
    tab = json.loads((cartella / "leggio.json").read_text(encoding="utf-8"))
    bpm = 60.0 / (tab["durataCella"] * 4)
    # Le canzoni lavorate prima non avevano l'accordatura in numeri: senza, la
    # sincronia con Guitar Pro non sa che nota è ogni tasto.
    if "cordeMidi" not in tab:
        conosciuto = next((s for s in STRUMENTI.values() if s.nome == tab.get("strumento")), None)
        if conosciuto:
            tab["cordeMidi"] = list(conosciuto.corde)
    tracce = [{"nome": f.stem, "file": urllib.parse.quote(f.name)} for f in sorted(cartella.glob("*.wav"))]
    nome = next((s.nome for s in STRUMENTI.values() if s.nome == tab.get("strumento")), tab.get("strumento", ""))
    immagine = copertina.di(cartella.parent)
    gp = guitarpro.di(cartella)
    return pagina(cartella.name.replace("_", " "), nome, round(bpm, 2), tab, tracce,
                  copertina=f"../{urllib.parse.quote(immagine.name)}" if immagine else "",
                  album=cartella.parent.name,
                  guitarpro=urllib.parse.quote(gp.name) if gp else "",
                  id_canzone=f"{cartella.parent.name}/{cartella.name}")


def sfoglia(dove: str | None) -> dict:
    cartella = Path(dove).expanduser() if dove else Path(leggi_stato().get("cartella", MUSICA))
    if not cartella.is_dir():
        cartella = MUSICA if MUSICA.is_dir() else Path.home()
    cartelle, canzoni = [], []
    try:
        for voce in sorted(cartella.iterdir(), key=lambda v: v.name.lower()):
            if voce.name.startswith("."):
                continue
            if voce.is_dir():
                if voce != TAB:
                    cartelle.append(voce.name)
            elif voce.suffix.lower() in AUDIO:
                canzoni.append(voce.name)
    except PermissionError:
        pass
    return {"dove": str(cartella), "su": str(cartella.parent), "cartelle": cartelle, "canzoni": canzoni, "musica": str(MUSICA)}


# ---------------------------------------------------------------- il server

ultimo_contatto = time.monotonic()


class Risponditore(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def manda(self, corpo: bytes, tipo: str, codice: int = 200, altre: dict | None = None):
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (altre or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def json(self, dati, codice: int = 200):
        self.manda(json.dumps(dati, ensure_ascii=False).encode(), "application/json", codice)

    def do_GET(self):
        global ultimo_contatto
        ultimo_contatto = time.monotonic()
        url = urllib.parse.urlsplit(self.path)
        domanda = dict(urllib.parse.parse_qsl(url.query))
        percorso = urllib.parse.unquote(url.path)
        if percorso == "/":
            return self.manda(APP.encode(), "text/html; charset=utf-8")
        if percorso == "/libreria/suona":
            return self.manda(Path(__file__).with_name("suona.html").read_bytes(), "text/html; charset=utf-8")
        if percorso == "/api/canzoni":
            return self.json(canzoni_fatte())
        if percorso == "/api/sfoglia":
            return self.json(sfoglia(domanda.get("dove")))
        if percorso == "/api/stato":
            with serratura:
                lavori = [asdict(l) | {"id": l.id, "registro": l.registro[-15:]} for l in coda]
            return self.json({"coda": lavori, "fasi": [nome for _, nome in FASI], "preferenze": leggi_stato()})
        if percorso.startswith("/tab/"):
            return self.da_tab(percorso[len("/tab/"):])
        if percorso == "/sw.js" or percorso.startswith("/pwa/"):
            relativo = "sw.js" if percorso == "/sw.js" else percorso[len("/pwa/"):]
            file = (PWA / relativo).resolve()
            if PWA.resolve() in file.parents and file.is_file():
                tipo = {".js": "text/javascript", ".mjs": "text/javascript", ".webmanifest": "application/manifest+json", ".png": "image/png",
                        ".woff2": "font/woff2", ".woff": "font/woff", ".sf2": "application/octet-stream",
                        ".txt": "text/plain"}.get(file.suffix, "application/octet-stream")
                altre = {"Service-Worker-Allowed": "/"} if file.name == "sw.js" else {"Cache-Control": "max-age=86400"}
                return self.manda(file.read_bytes(), tipo, altre=altre)
        if percorso == "/api/gp/cerca":
            cartella = self.canzone(domanda.get("id", ""))
            if cartella is None:
                return self.json([], 404)
            tab = json.loads((cartella / "leggio.json").read_text(encoding="utf-8"))
            vuole = "Basso" if "basso" in tab.get("strumento", "basso") else "Chitarra"
            return self.json(guitarpro.cerca(cartella.name, cartella.parent.name, MUSICA, vuole=vuole))
        if percorso == "/api/libreria/artisti":
            return self.json(guitarpro.artisti(MUSICA, domanda.get("q", "")))
        if percorso == "/api/libreria/canzoni":
            return self.json(guitarpro.canzoni_di(MUSICA, domanda.get("artista", "")))
        if percorso == "/api/libreria/strumenti":
            return self.json(guitarpro.strumenti(guitarpro.leggi(MUSICA, domanda["archivio"], domanda["nome"])))
        if percorso == "/api/libreria/file":
            dati = guitarpro.leggi(MUSICA, domanda["archivio"], domanda["nome"])
            return self.manda(dati, "application/octet-stream")
        if percorso == "/api/libreria/disco":
            # Il disco di questa tablatura: già lavorato (in tab) o solo in Musica / Scaricati.
            artista, titolo = domanda.get("artista", ""), domanda.get("titolo", "")
            dischi = [d for c in CARTELLE_DISCHI if c.is_dir() for d in guitarpro.cerca_disco(c, artista, titolo)]
            dischi.sort(key=lambda d: -d["punteggio"])
            fatte = []
            for d in dischi:
                p = Path(d["percorso"])
                cartella = TAB / p.parent.name / p.stem
                if (cartella / "leggio.json").is_file():
                    fatte.append({"id": f"{p.parent.name}/{p.stem}", "percorso": d["percorso"]})
            return self.json({"fatte": fatte, "dischi": dischi})
        if percorso == "/api/musica/artisti":
            return self.json(libreria.artisti(indice_musica()))
        if percorso == "/api/musica/canzoni":
            canzoni = libreria.canzoni(indice_musica(), domanda.get("chiave", ""))
            return self.json([c | {"fatta": id_fatta(c["percorso"])} for c in canzoni])
        if percorso == "/libreria/disco":
            return self.manda(Path(__file__).with_name("disco.html").read_bytes(), "text/html; charset=utf-8")
        if percorso == "/disco/audio":
            p = disco_permesso(domanda.get("percorso", ""))
            return self.file_a_pezzi(p) if p else self.manda(b"no", "text/plain", 403)
        if percorso == "/api/disco/info":
            p = domanda.get("percorso", "")
            if not disco_permesso(p):
                return self.json({"errore": "disco sconosciuto"}, 404)
            v = voce_di(p)
            return self.json({"voce": v, "tablatura": tablatura_del_disco(p), "fatta": id_fatta(p)})
        if percorso == "/api/disco/candidati":
            v = voce_di(domanda.get("percorso", ""))
            return self.json(guitarpro.cerca(v["titolo"], v["artista"], MUSICA))
        if percorso == "/api/disco/gp":
            p = domanda.get("percorso", "")
            tab = tablatura_del_disco(p) if disco_permesso(p) else None
            if not tab:
                return self.manda(b"", "application/octet-stream", 404)
            dati = Path(tab["tua"]).read_bytes() if tab.get("tua") else guitarpro.leggi(MUSICA, tab["archivio"], tab["nome"])
            return self.manda(dati, "application/octet-stream")
        if percorso == "/api/disco/sincronia":
            p = domanda.get("percorso", "")
            tab = tablatura_del_disco(p) if disco_permesso(p) else None
            file = chiave_sincronia(p, tab) if tab else None
            try:
                return self.json(json.loads(file.read_text()) if file else {})
            except (OSError, ValueError):
                return self.json({})
        if percorso == "/api/disco/copertina":
            p = disco_permesso(domanda.get("percorso", ""))
            immagine = copertina.trova(p) if p else None
            if immagine:
                return self.manda(immagine.read_bytes(), mimetypes.guess_type(immagine.name)[0] or "image/jpeg",
                                  altre={"Cache-Control": "max-age=3600"})
            return self.manda(b"", "image/png", 404)
        if percorso == "/api/suoni":
            tuoi = sorted(p for p in MUSICA.glob("*.sf[23]") if p.is_file())
            if tuoi:
                return self.json({"url": "/suoni/" + urllib.parse.quote(tuoi[0].name), "nome": tuoi[0].stem})
            return self.json({"url": "/pwa/alphatab/soundfont/MuseScore_General.sf3", "nome": "MuseScore General"})
        if percorso.startswith("/suoni/"):
            file = MUSICA / Path(percorso).name
            if file.suffix.lower() in (".sf2", ".sf3") and file.is_file():
                return self.file_a_pezzi(file)
        if percorso == "/api/testo":
            return self.json(self.testo_online(domanda.get("id", "")))
        if percorso == "/api/sincronia":
            cartella = self.canzone(domanda.get("id", ""))
            return self.json(guitarpro.leggi_sincronia(cartella) if cartella else {})
        self.manda(b"non c'e'", "text/plain", 404)

    do_HEAD = do_GET

    def do_POST(self):
        global ultimo_contatto
        ultimo_contatto = time.monotonic()
        lunghezza = int(self.headers.get("Content-Length", 0))
        dati_grezzi = self.rfile.read(lunghezza)
        try:
            dati = json.loads(dati_grezzi or b"{}")
        except ValueError:
            dati = {}
        if self.path == "/api/importa":
            salva_stato(strumento=dati["strumento"], testo=dati["testo"], lingua=dati["lingua"])
            quante = accoda(dati["percorsi"], dati["strumento"], dati["testo"], dati["lingua"])
            return self.json({"accodate": quante})
        if self.path == "/api/preferenze":
            return self.json(salva_stato(**dati))
        url = urllib.parse.urlsplit(self.path)
        domanda = dict(urllib.parse.parse_qsl(url.query))
        if url.path == "/api/gp/carica":
            # Il corpo è il file stesso, così si caricano anche file grossi senza moduli.
            cartella = self.canzone(domanda.get("id", ""))
            if cartella is None:
                return self.json({"errore": "canzone sconosciuta"}, 404)
            try:
                guitarpro.metti(cartella, dati_grezzi, Path(domanda.get("nome", "")).suffix)
            except ValueError as errore:
                return self.json({"errore": str(errore)}, 400)
            return self.json({"ok": True})
        if url.path == "/api/gp/scegli":
            cartella = self.canzone(dati.get("id", ""))
            if cartella is None:
                return self.json({"errore": "canzone sconosciuta"}, 404)
            guitarpro.estrai(cartella, MUSICA, dati["archivio"], dati["nome"])
            return self.json({"ok": True})
        if url.path == "/api/disco/scegli":
            # La tablatura giusta per questo disco, scelta da te: vale per sempre.
            stato = leggi_stato()
            scelte = stato.get("tabPerDisco", {})
            scelte[dati["percorso"]] = {"archivio": dati["archivio"], "nome": dati["nome"]}
            salva_stato(tabPerDisco=scelte)
            return self.json({"ok": True})
        if url.path == "/api/disco/carica":
            p = domanda.get("percorso", "")
            estensione = Path(domanda.get("nome", "")).suffix.lower()
            if not disco_permesso(p) or estensione not in guitarpro.ESTENSIONI:
                return self.json({"errore": "file non valido"}, 400)
            TUE.mkdir(parents=True, exist_ok=True)
            file = TUE / (hashlib.sha1(p.encode()).hexdigest()[:12] + "-" + Path(domanda["nome"]).name)
            file.write_bytes(dati_grezzi)
            scelte = leggi_stato().get("tabPerDisco", {})
            scelte[p] = {"tua": str(file), "nome": Path(domanda["nome"]).name}
            salva_stato(tabPerDisco=scelte)
            return self.json({"ok": True})
        if url.path == "/api/allinea":
            p = disco_permesso(dati.get("percorso", ""))
            tab = tablatura_del_disco(str(p)) if p else None
            if not tab:
                return self.json({"errore": "niente da allineare"}, 400)
            ms = allinea.sincronizza(p, dati["eventi"], dati["battute"])
            file = chiave_sincronia(str(p), tab)
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps({"automatica": ms}))
            return self.json({"automatica": ms})
        if url.path == "/api/disco/sincronia":
            p = disco_permesso(dati.get("percorso", ""))
            tab = tablatura_del_disco(str(p)) if p else None
            if not tab:
                return self.json({"errore": "niente"}, 400)
            file = chiave_sincronia(str(p), tab)
            vecchia = {}
            try:
                vecchia = json.loads(file.read_text())
            except (OSError, ValueError):
                pass
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps(vecchia | {"punti": dati["punti"]}))
            return self.json({"ok": True})
        if url.path == "/api/disco/separa":
            # Le tracce separate (mute e solo sul disco vero), con la tablatura già collegata.
            p = disco_permesso(dati.get("percorso", ""))
            if not p:
                return self.json({"errore": "disco sconosciuto"}, 404)
            tab = tablatura_del_disco(str(p))
            if tab and not tab.get("tua"):
                da_collegare[str(p)] = (tab["archivio"], tab["nome"])
            preferenze = leggi_stato()
            accoda([str(p)], dati.get("strumento", "basso"), preferenze.get("testo", True), preferenze.get("lingua", "en"))
            return self.json({"inLavorazione": f"{p.parent.name}/{p.stem}"})
        if url.path == "/api/libreria/usa":
            # Una tablatura dell'archivio sul disco vero: se la canzone è già
            # lavorata la si collega subito, se no si lavora e la si collega dopo.
            if dati.get("id"):
                cartella = self.canzone(dati["id"])
                if cartella is None:
                    return self.json({"errore": "canzone sconosciuta"}, 404)
                guitarpro.estrai(cartella, MUSICA, dati["archivio"], dati["nome"])
                return self.json({"id": dati["id"]})
            canzone = dati["percorso"]
            da_collegare[canzone] = (dati["archivio"], dati["nome"])
            preferenze = leggi_stato()
            accoda([canzone], dati.get("strumento", "basso"), preferenze.get("testo", True), preferenze.get("lingua", "en"))
            p = Path(canzone)
            return self.json({"inLavorazione": f"{p.parent.name}/{p.stem}"})
        if url.path == "/api/sincronia":
            cartella = self.canzone(dati.get("id", ""))
            if cartella is None:
                return self.json({"errore": "canzone sconosciuta"}, 404)
            guitarpro.salva_sincronia(cartella, dati.get("sincronia", {}))
            return self.json({"ok": True})
        if self.path == "/api/svuota":
            with serratura:
                coda[:] = [l for l in coda if l.stato in ("in attesa", "in lavorazione")]
            return self.json({})
        self.manda(b"non c'e'", "text/plain", 404)

    def testo_online(self, id_: str) -> dict:
        """Il testo vero da LRCLIB, al posto di quello di Whisper (una volta sola)."""
        cartella = self.canzone(id_)
        if cartella is None:
            return {"trovato": False}
        file = cartella / "leggio.json"
        tab = json.loads(file.read_text(encoding="utf-8"))
        if tab.get("testoDa") in ("lrclib", "nessuno"):
            return {"trovato": tab["testoDa"] == "lrclib", "gia": True}
        import soundfile

        traccia = next(iter(sorted(cartella.glob("*.wav"))), None)
        durata = soundfile.info(str(traccia)).duration if traccia else 0
        album, canzone = cartella.parent.name, cartella.name.replace("_", " ")
        titoli = guitarpro._titoli_possibili(canzone)
        # L'artista: dal nome della canzone («Rage Against The Machine - Killing…») o dall'album.
        candidati_artista = [p for p in re.split(r"\s+-\s+", re.sub(r"^[\d\s._-]+", "", canzone)) if p not in titoli[-1:]]
        candidati_artista += [re.split(r"\s+-\s+", re.sub(r"^[\d\s._-]+", "", album))[0]]
        trovato = None
        for artista in candidati_artista:
            for titolo in reversed(titoli):
                trovato = online.cerca_testo(artista, titolo, durata)
                if trovato:
                    break
            if trovato:
                break
        if not trovato:
            tab["testoDa"] = "nessuno"
            file.write_text(json.dumps(tab), encoding="utf-8")
            return {"trovato": False}
        tab["paroleWhisper"] = tab.get("parole", [])
        tab["parole"] = online.parole(trovato["syncedLyrics"], durata)
        tab["testoDa"] = "lrclib"
        tab["testoFonte"] = f"{trovato.get('artistName')} — {trovato.get('trackName')}"
        file.write_text(json.dumps(tab), encoding="utf-8")
        return {"trovato": True}

    def canzone(self, id_: str) -> Path | None:
        """La cartella di una canzone dal suo id «album/canzone», solo dentro tab."""
        cartella = (TAB / id_).resolve()
        if TAB.resolve() in cartella.parents and (cartella / "leggio.json").is_file():
            return cartella
        return None

    def da_tab(self, relativo: str):
        file = (TAB / relativo).resolve()
        if TAB.resolve() not in file.parents:
            return self.manda(b"no", "text/plain", 403)
        if file.name == "tablatura.html" and (file.parent / "leggio.json").is_file():
            return self.manda(pagina_di(file.parent).encode(), "text/html; charset=utf-8")
        if not file.is_file():
            return self.manda(b"non c'e'", "text/plain", 404)
        self.file_a_pezzi(file)

    def file_a_pezzi(self, file: Path):
        """Le tracce si mandano a pezzi (Range): senza, il lettore non sa
        saltare in un punto del brano e riparte sempre dall'inizio."""
        totale = file.stat().st_size
        tipo = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        intervallo = self.headers.get("Range")
        inizio, fine, codice = 0, totale - 1, 200
        if intervallo and intervallo.startswith("bytes="):
            a, _, b = intervallo[6:].partition("-")
            if a:
                inizio = int(a)
                fine = int(b) if b else totale - 1
            else:
                inizio = max(0, totale - int(b))
            fine = min(fine, totale - 1)
            codice = 206
        self.send_response(codice)
        self.send_header("Content-Type", tipo)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(fine - inizio + 1))
        if codice == 206:
            self.send_header("Content-Range", f"bytes {inizio}-{fine}/{totale}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with file.open("rb") as f:
            f.seek(inizio)
            resto = fine - inizio + 1
            try:
                while resto > 0:
                    pezzo = f.read(min(1 << 20, resto))
                    if not pezzo:
                        break
                    self.wfile.write(pezzo)
                    resto -= len(pezzo)
            except (BrokenPipeError, ConnectionResetError):
                pass


def guardiano() -> None:
    """Si spegne da solo quando nessuno lo guarda e non ha niente da fare."""
    while True:
        time.sleep(15)
        with serratura:
            occupato = any(l.stato in ("in attesa", "in lavorazione") for l in coda)
        if not occupato and time.monotonic() - ultimo_contatto > 90:
            os._exit(0)


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORTA), Risponditore)
    threading.Thread(target=lavora, daemon=True).start()
    threading.Thread(target=guardiano, daemon=True).start()
    server.serve_forever()
    return 0


APP = (Path(__file__).with_name("app.html")).read_text(encoding="utf-8")

if __name__ == "__main__":
    raise SystemExit(main())
