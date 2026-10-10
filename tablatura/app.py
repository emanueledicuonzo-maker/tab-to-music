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
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import copertina
from .strumenti import STRUMENTI
from .visore import pagina

PORTA = 8777
AUDIO = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}
RADICE = Path(__file__).resolve().parent.parent


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
        processo = subprocess.Popen(
            comando, cwd=RADICE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
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
    tracce = [{"nome": f.stem, "file": urllib.parse.quote(f.name)} for f in sorted(cartella.glob("*.wav"))]
    nome = next((s.nome for s in STRUMENTI.values() if s.nome == tab.get("strumento")), tab.get("strumento", ""))
    immagine = copertina.di(cartella.parent)
    return pagina(cartella.name.replace("_", " "), nome, round(bpm, 2), tab, tracce,
                  copertina=f"../{urllib.parse.quote(immagine.name)}" if immagine else "",
                  album=cartella.parent.name)


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
        self.manda(b"non c'e'", "text/plain", 404)

    do_HEAD = do_GET

    def do_POST(self):
        global ultimo_contatto
        ultimo_contatto = time.monotonic()
        lunghezza = int(self.headers.get("Content-Length", 0))
        dati = json.loads(self.rfile.read(lunghezza) or b"{}")
        if self.path == "/api/importa":
            salva_stato(strumento=dati["strumento"], testo=dati["testo"], lingua=dati["lingua"])
            quante = accoda(dati["percorsi"], dati["strumento"], dati["testo"], dati["lingua"])
            return self.json({"accodate": quante})
        if self.path == "/api/preferenze":
            return self.json(salva_stato(**dati))
        if self.path == "/api/svuota":
            with serratura:
                coda[:] = [l for l in coda if l.stato in ("in attesa", "in lavorazione")]
            return self.json({})
        self.manda(b"non c'e'", "text/plain", 404)

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
