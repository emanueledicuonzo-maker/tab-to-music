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
