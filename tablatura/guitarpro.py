"""Le tablature Guitar Pro: trovarle nell'archivio, metterle accanto alla canzone.

L'archivio è uno zip con decine di migliaia di file, ordinati per lettera e
artista («P/Police (The)/Police (The) - Roxanne.gp3»). Non si estrae tutto:
si legge l'elenco una volta, si cercano i titoli simili alla canzone, e si
estrae solo il file scelto, nella cartella della canzone.
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
import subprocess
from functools import lru_cache
from pathlib import Path

ESTENSIONI = (".gp3", ".gp4", ".gp5", ".gpx", ".gp", ".gtp")
NOME_FILE = "tablatura"          # tablatura.gp3, tablatura.gp5…
SINCRONIA = "sincronia.json"


def archivi(musica: Path) -> list[Path]:
    """Gli zip di tablature nella cartella della musica."""
    return sorted(p for p in musica.glob("*.zip") if re.search(r"guitar.?pro|tab", p.name, re.I))


def _semplice(testo: str) -> str:
    testo = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    testo = re.sub(r"\(.*?\)|\[.*?\]", " ", testo.lower())
    testo = re.sub(r"\b(the|feat|ft|live|remaster(ed)?|version|mono|stereo)\b", " ", testo)
    return re.sub(r"[^a-z0-9]+", " ", testo).strip()


@lru_cache(maxsize=4)
def elenco(archivio: Path) -> list[tuple[str, str, str]]:
    """(percorso nello zip, artista semplificato, titolo semplificato) di ogni tablatura."""
    # Si usa unzip e non il modulo zipfile: l'archivio da 55.000 tablature ha
    # un'intestazione che zipfile rifiuta («not a zip file»), unzip no.
    nomi = subprocess.run(["unzip", "-Z1", str(archivio)], capture_output=True, text=True, errors="replace").stdout
    voci = []
    if True:
        for nome in nomi.splitlines():
            if not nome.lower().endswith(ESTENSIONI):
                continue
            base = Path(nome).stem
            artista, _, titolo = base.partition(" - ")
            if not titolo:
                artista, titolo = Path(nome).parent.name, base
            voci.append((nome, _semplice(artista), _semplice(titolo)))
    return voci


def _titoli_possibili(canzone: str) -> list[str]:
    """Dal nome del file, i pezzi che possono essere il titolo.

    «01 - Roxanne», «02. Rage Against The Machine - Killing In the Name (Live)»,
    «01-01-Michael_Jackson-Billie_Jean-SMR»: non c'è una regola sola, quindi
    si provano tutti i pezzi fra i trattini e vince quello che somiglia di più.
    """
    nome = re.sub(r"^[\d\s._-]+", "", canzone.replace("_", " "))
    pezzi = [p.strip() for p in re.split(r"\s*-\s*", nome) if len(p.strip()) > 2]
    return pezzi or [nome]


FAMIGLIE = ["Pianoforte", "Percussioni", "Organo", "Chitarra", "Basso", "Archi", "Archi", "Ottoni",
            "Fiati", "Flauti", "Synth", "Synth", "Effetti", "Etnici", "Percussioni", "Effetti"]


def strumenti(dati: bytes) -> list[str]:
    """Gli strumenti di un file Guitar Pro 3-5, dal suono di ogni traccia."""
    import io

    import guitarpro

    try:
        canzone = guitarpro.parse(io.BytesIO(dati))
    except Exception:
        return []
    fuori = []
    for t in canzone.tracks:
        if t.isPercussionTrack:
            fuori.append("Batteria")
        elif re.search(r"voc|voz|voix|voice|vox|sing|canto|coro|choir", t.name or "", re.I):
            fuori.append("Voce")
        elif len(t.strings) in (4, 5) and min(s.value for s in t.strings) < 35:
            fuori.append("Basso")
        else:
            fuori.append(FAMIGLIE[(t.channel.instrument or 0) // 8])
    return fuori


def _leggi(archivio: Path, nome: str) -> bytes:
    return subprocess.run(["unzip", "-p", str(archivio), nome], capture_output=True).stdout


def cerca(canzone: str, album: str, musica: Path, quante: int = 12, vuole: str = "Basso") -> list[dict]:
    """Le tablature più somiglianti a questa canzone, con un punteggio da 0 a 1."""
    titoli = [_semplice(t) for t in _titoli_possibili(canzone)]
    contesto = set(_semplice(f"{album} {canzone.replace('_', ' ')}").split())
    contesto_unito = "".join(_semplice(f"{album} {canzone.replace('_', ' ')}").split())
    risultati = []
    for archivio in archivi(musica):
        for nome, artista, t in elenco(archivio):
            if not t:
                continue
            somiglia = max(difflib.SequenceMatcher(None, titolo, t).ratio() for titolo in titoli if titolo)
            if somiglia < 0.6:
                continue
            parole_artista = set(artista.split())
            artista_ok = len(parole_artista & contesto) / max(1, len(parole_artista))
            # «AC/DC» nella tua musica, «ACDC» nell'archivio: si confrontano anche senza spazi.
            if artista_ok < 1 and artista.replace(" ", "") and artista.replace(" ", "") in contesto_unito:
                artista_ok = 1.0
            punteggio = 0.7 * somiglia + 0.3 * artista_ok
            risultati.append({"archivio": archivio.name, "nome": nome, "punteggio": round(punteggio, 3)})
    risultati.sort(key=lambda r: -r["punteggio"])
    # Delle migliori si guarda dentro: quali strumenti ha ogni file. Quelle con
    # lo strumento che serve (di solito il basso) vanno in cima.
    migliori = risultati[: quante * 2]
    per_nome = {a.name: a for a in archivi(musica)}
    for r in migliori:
        r["strumenti"] = strumenti(_leggi(per_nome[r["archivio"]], r["nome"]))
        r["ha"] = vuole in r["strumenti"]
    migliori.sort(key=lambda r: (not r["ha"], -r["punteggio"], -len(r["strumenti"])))
    # Lo stesso file sta spesso in più cartelle dell'archivio: uno solo.
    visti, unici = set(), []
    for r in migliori:
        chiave = (Path(r["nome"]).name.lower(), tuple(r["strumenti"]))
        if chiave not in visti:
            visti.add(chiave)
            unici.append(r)
    return unici[:quante]


def di(cartella: Path) -> Path | None:
    """La tablatura Guitar Pro già messa accanto a questa canzone."""
    return next((p for p in sorted(cartella.glob(f"{NOME_FILE}.*")) if p.suffix.lower() in ESTENSIONI), None)


def metti(cartella: Path, dati: bytes, estensione: str) -> Path:
    """Salva la tablatura accanto alla canzone, al posto di quella che c'era."""
    estensione = estensione.lower()
    if estensione not in ESTENSIONI:
        raise ValueError(f"non è un file Guitar Pro: {estensione}")
    for vecchia in cartella.glob(f"{NOME_FILE}.*"):
        if vecchia.suffix.lower() in ESTENSIONI:
            vecchia.unlink()
    (cartella / SINCRONIA).unlink(missing_ok=True)
    destinazione = cartella / f"{NOME_FILE}{estensione}"
    destinazione.write_bytes(dati)
    return destinazione


def estrai(cartella: Path, musica: Path, archivio: str, nome: str) -> Path:
    """Tira fuori dallo zip solo la tablatura scelta."""
    zip_ = next(a for a in archivi(musica) if a.name == archivio)
    esito = subprocess.run(["unzip", "-p", str(zip_), nome], capture_output=True)
    if esito.returncode != 0 or not esito.stdout:
        raise OSError(f"non riesco a estrarre {nome}")
    dati = esito.stdout
    return metti(cartella, dati, Path(nome).suffix)


def leggi_sincronia(cartella: Path) -> dict:
    try:
        return json.loads((cartella / SINCRONIA).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salva_sincronia(cartella: Path, dati: dict) -> None:
    (cartella / SINCRONIA).write_text(json.dumps(dati), encoding="utf-8")


# ---------------------------------------------------------------- la libreria


def _artista_di(nome: str) -> str:
    """L'artista come sta scritto nella cartella dell'archivio («Jackson, Michael»)."""
    cartella = Path(nome).parent.name
    return cartella or Path(nome).stem.partition(" - ")[0]


@lru_cache(maxsize=2)
def _per_artista(musica: Path) -> dict[str, list[tuple[str, str]]]:
    """artista → [(archivio, nome nello zip)]"""
    gruppi: dict[str, list[tuple[str, str]]] = {}
    for archivio in archivi(musica):
        for nome, _, _ in elenco(archivio):
            gruppi.setdefault(_artista_di(nome), []).append((archivio.name, nome))
    return gruppi


def artisti(musica: Path, filtro: str = "", quanti: int = 400) -> list[dict]:
    f = _semplice(filtro)
    fuori = [
        {"artista": a, "quante": len(v)}
        for a, v in _per_artista(musica).items()
        if not f or f in _semplice(a)
    ]
    fuori.sort(key=lambda x: x["artista"].lower())
    return fuori[:quanti]


def canzoni_di(musica: Path, artista: str) -> list[dict]:
    """Le canzoni di un artista, ognuna con le sue versioni («(2)», «Live»…)."""
    per_titolo: dict[str, dict] = {}
    for archivio, nome in _per_artista(musica).get(artista, []):
        base = Path(nome).stem.partition(" - ")[2] or Path(nome).stem
        titolo = re.sub(r"\s*\(\d+\)\s*$", "", base).strip()
        chiave = _semplice(titolo)
        voce = per_titolo.setdefault(chiave, {"titolo": titolo, "versioni": []})
        if all(Path(v["nome"]).name != Path(nome).name for v in voce["versioni"]):
            voce["versioni"].append({"archivio": archivio, "nome": nome, "etichetta": base})
    return sorted(per_titolo.values(), key=lambda v: v["titolo"].lower())


@lru_cache(maxsize=2)
def _per_titolo(musica: Path) -> dict[str, list[set[str]]]:
    """titolo semplificato → le parole degli artisti che lo hanno: per sapere al volo se c'è una tab."""
    indice: dict[str, list[set[str]]] = {}
    for archivio in archivi(musica):
        for nome, artista, titolo in elenco(archivio):
            t = re.sub(r"\s+\d+$", "", titolo)
            indice.setdefault(t, []).append(set(artista.split()))
    return indice


def ha_tablatura(musica: Path, artista: str, titolo: str) -> bool:
    """Veloce: c'è negli archivi una tablatura con questo titolo e un artista compatibile?"""
    indice = _per_titolo(musica)
    in_ordine = _semplice(artista.replace(",", " ")).split()
    parole, unito = set(in_ordine), "".join(in_ordine)
    for t in {_semplice(titolo)} | {_semplice(x) for x in _titoli_possibili(titolo)}:
        for artisti_di in indice.get(t, []):
            if not parole or parole & artisti_di or any(unito == a or (len(a) > 2 and a in unito) for a in artisti_di):
                return True
    return False


def leggi(musica: Path, archivio: str, nome: str) -> bytes:
    zip_ = next(a for a in archivi(musica) if a.name == archivio)
    return _leggi(zip_, nome)


AUDIO = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}


@lru_cache(maxsize=1)
def _dischi(musica: Path, _giro: int) -> list[tuple[str, set[str], list[str]]]:
    """(percorso, parole del percorso, titoli possibili) di ogni canzone in Musica."""
    fuori = []
    for f in musica.rglob("*"):
        if f.suffix.lower() in AUDIO and "tab" not in f.relative_to(musica).parts[:1]:
            parole = set(_semplice(" ".join(f.relative_to(musica).parts).replace("_", " ")).split())
            fuori.append((str(f), parole, [_semplice(t) for t in _titoli_possibili(f.stem)]))
    return fuori


def cerca_disco(musica: Path, artista: str, titolo: str, quanti: int = 8) -> list[dict]:
    """I file audio in Musica che sembrano questa canzone."""
    import time

    t = _semplice(titolo)
    nomi_artista = set(_semplice(artista.replace(",", " ")).split())
    fuori = []
    for percorso, parole, titoli in _dischi(musica, int(time.time() // 300)):
        somiglia = max((difflib.SequenceMatcher(None, t, x).ratio() for x in titoli if x), default=0)
        if somiglia < 0.75:
            continue
        artista_ok = len(nomi_artista & parole) / max(1, len(nomi_artista))
        if artista_ok < 0.5:
            continue
        fuori.append({"percorso": percorso, "punteggio": round(0.7 * somiglia + 0.3 * artista_ok, 3)})
    fuori.sort(key=lambda r: -r["punteggio"])
    return fuori[:quanti]


def eventi(dati: bytes) -> tuple[list[dict], list[float]]:
    """Le note di tutti gli strumenti (non la batteria) e gli inizi di battuta, al
    tempo scritto, da un file Guitar Pro 3-5. Serve a confrontare le versioni
    col disco senza aprirle nel browser (i ritornelli non si ripetono: basta
    per scegliere, non per sincronizzare)."""
    import io

    import guitarpro

    try:
        canzone = guitarpro.parse(io.BytesIO(dati))
    except Exception:
        return [], []
    tempo = canzone.tempo or 120
    fuori, battute, t_ms = [], [], 0.0
    for i, testa in enumerate(canzone.measureHeaders):
        battute.append(t_ms)
        durata = testa.timeSignature.numerator * (4 / testa.timeSignature.denominator.value) * 60000 / tempo
        for traccia in canzone.tracks:
            if traccia.isPercussionTrack or i >= len(traccia.measures):
                continue
            for voce in traccia.measures[i].voices:
                for beat in voce.beats:
                    inizio = t_ms + (beat.start - testa.start) / 960 * 60000 / tempo
                    for nota in beat.notes:
                        if 0 < nota.string <= len(traccia.strings):
                            fuori.append({"inizio": inizio, "durata": beat.duration.time / 960 * 60000 / tempo,
                                          "midi": traccia.strings[nota.string - 1].value + nota.value})
        t_ms += durata
    return fuori, battute


def versione_piu_vicina(audio: Path, candidati: list[dict], musica: Path, quante: int = 6) -> list[dict]:
    """Prova le versioni candidate sul disco e le mette in ordine di somiglianza."""
    from . import allinea

    import math

    import soundfile

    durata_disco = soundfile.info(str(audio)).duration * 1000
    per_nome = {a.name: a for a in archivi(musica)}
    provate = []
    for c in candidati[:quante]:
        ev, bt = eventi(_leggi(per_nome[c["archivio"]], c["nome"]))
        if not ev:
            provate.append(c | {"costo": 9.0})
            continue
        # Due cose: quanto le note combaciano, e quanto va stirata la tablatura
        # per coprire il disco. Un arrangiamento diverso o un pezzo solo (l'assolo
        # di Beat It) combacia a tratti ma è lungo la metà: lo si penalizza.
        lunghezza = max(e["inizio"] + e["durata"] for e in ev)
        stiro = abs(math.log(max(lunghezza, 1) / max(durata_disco, 1)))
        provate.append(c | {"costo": round(allinea.somiglianza(audio, ev, bt) + 0.4 * stiro, 4)})
    provate.sort(key=lambda c: (c["costo"], -c["punteggio"]))
    return provate
