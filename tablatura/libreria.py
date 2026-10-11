"""La Libreria: tutta la musica che hai, per artista, senza girare cartella per cartella.

Artista, titolo e album vengono dai tag dei file (mutagen); dove i tag non ci
sono, dal nome della cartella e del file. L'elenco si tiene in un file e si
rifà solo per le canzoni nuove o cambiate.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

AUDIO = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}
INDICE = Path.home() / ".config" / "tablatura" / "libreria.json"


def _dai_tag(file: Path) -> dict:
    try:
        import mutagen

        tag = mutagen.File(str(file), easy=True)
    except Exception:
        tag = None
    prendi = lambda k: (tag.get(k) or [""])[0].strip() if tag and tag.tags is not None else ""
    durata = float(getattr(getattr(tag, "info", None), "length", 0) or 0)
    # L'artista del brano, non quello dell'album: nelle raccolte («Various
    # Artists») l'artista dell'album non dice niente.
    album_artista = prendi("albumartist")
    if re.search(r"various|vari|compilation|^va$", album_artista, re.I):
        album_artista = ""
    return {"artista": prendi("artist") or album_artista, "titolo": prendi("title"),
            "album": prendi("album"), "durata": round(durata, 1)}


def _dal_nome(file: Path) -> dict:
    """Quando i tag mancano: «Artista - Titolo», poi la cartella dell'album («Artista - Album (anno)»)."""
    nome = re.sub(r"^[\d\s._-]+", "", file.stem.replace("_", " "))
    artista, _, titolo = nome.partition(" - ")
    cartella = file.parent.name
    if not titolo:
        titolo, artista = nome, re.split(r"\s+-\s+", cartella)[0]
    return {"artista": artista.strip(), "titolo": titolo.strip(), "album": cartella}


def aggiorna(cartelle: list[Path], escludi: list[Path]) -> list[dict]:
    try:
        vecchio = {v["percorso"]: v for v in json.loads(INDICE.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        vecchio = {}
    nuovo = []
    for radice in cartelle:
        if not radice.is_dir():
            continue
        for f in radice.rglob("*"):
            if f.suffix.lower() not in AUDIO or any(e in f.parents for e in escludi):
                continue
            percorso, quando = str(f), f.stat().st_mtime
            voce = vecchio.get(percorso)
            if not voce or voce.get("quando") != quando:
                dati = _dai_tag(f)
                ripiego = _dal_nome(f)
                voce = {"percorso": percorso, "quando": quando,
                        "artista": dati["artista"] or ripiego["artista"] or "Sconosciuto",
                        "titolo": dati["titolo"] or ripiego["titolo"],
                        "album": dati["album"] or ripiego["album"], "durata": dati["durata"]}
            nuovo.append(voce)
    INDICE.parent.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(nuovo, ensure_ascii=False), encoding="utf-8")
    return nuovo


def _chiave_artista(a: str) -> str:
    """«The Police», «Police (The)», «POLICE» sono lo stesso artista."""
    a = re.sub(r"\(the\)|^the\s+|,\s*the$", "", a.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", a.lower()).strip()


def artisti(voci: list[dict]) -> list[dict]:
    gruppi: dict[str, dict] = {}
    for v in voci:
        k = _chiave_artista(v["artista"])
        g = gruppi.setdefault(k, {"artista": v["artista"], "chiave": k, "quante": 0})
        g["quante"] += 1
    return sorted(gruppi.values(), key=lambda g: g["artista"].lower())


def canzoni(voci: list[dict], chiave: str) -> list[dict]:
    scelte = [v for v in voci if _chiave_artista(v["artista"]) == chiave]
    return sorted(scelte, key=lambda v: (v["album"].lower(), v["titolo"].lower()))
