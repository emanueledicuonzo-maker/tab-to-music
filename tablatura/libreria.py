"""La Libreria: tutta la musica che hai, per artista, senza girare cartella per cartella.

Artista, titolo e album vengono dai tag dei file (tinytag); dove i tag non ci
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
    """Artista, titolo, album, anno, numero e durata dai tag (tinytag, licenza MIT)."""
    try:
        from tinytag import TinyTag

        tag = TinyTag.get(str(file))
    except Exception:
        tag = None
    prendi = lambda k: str(getattr(tag, k, None) or "").strip() if tag else ""
    # L'artista del brano, non quello dell'album: nelle raccolte («Various
    # Artists») l'artista dell'album non dice niente.
    album_artista = prendi("albumartist")
    if re.search(r"various|vari|compilation|^va$", album_artista, re.I):
        album_artista = ""
    numero = re.match(r"\d+", prendi("track"))
    anno = re.search(r"(19|20)\d\d", prendi("year"))
    return {"artista": prendi("artist") or album_artista, "titolo": prendi("title"),
            "album": prendi("album"), "durata": round(float(getattr(tag, "duration", 0) or 0), 1),
            "traccia": int(numero.group()) if numero else None, "anno": anno.group() if anno else ""}


def _dal_nome(file: Path) -> dict:
    """Quando i tag mancano: «Artista - Titolo», poi la cartella dell'album («Artista - Album (anno)»)."""
    nome = re.sub(r"^[\d\s._-]+", "", file.stem.replace("_", " "))
    artista, _, titolo = nome.partition(" - ")
    cartella = file.parent.name
    if not titolo:
        titolo, artista = nome, re.split(r"\s+-\s+", cartella)[0]
    # «1973», «13_ Che Dio ti benedica (1993)», «CD2»: è l'album, non l'artista.
    # L'artista allora è nella cartella sopra («Pino Daniele - Discografia»).
    if re.match(r"^(\d|cd\s*\d|disc|\(|&|\[)", artista.strip(), re.I) or not artista.strip():
        sopra = file.parent.parent.name
        artista = re.split(r"\s+-\s+", re.sub(r"^[\d\s._-]+", "", sopra))[0]
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
            if not voce or voce.get("quando") != quando or voce.get("v") != 4:
                dati = _dai_tag(f)
                ripiego = _dal_nome(f)
                if dati["traccia"] is None:
                    n = re.match(r"\s*(\d{1,3})\b", f.stem)
                    dati["traccia"] = int(n.group(1)) if n else None
                if not dati["anno"]:
                    a = re.search(r"\((19|20)\d\d", f.parent.name)
                    dati["anno"] = a.group()[1:] if a else ""
                voce = {"percorso": percorso, "quando": quando, "v": 4, "traccia": dati["traccia"], "anno": dati["anno"],
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
    return sorted(scelte, key=lambda v: (v.get("anno") or "9999", v["album"].lower(), v.get("traccia") or 999, v["titolo"].lower()))


def cerca(voci: list[dict], testo: str, quante: int = 60) -> list[dict]:
    """Le canzoni il cui titolo, artista o album contiene il testo cercato."""
    t = testo.lower().strip()
    if len(t) < 2:
        return []
    trovate = [v for v in voci if t in v["titolo"].lower() or t in v["artista"].lower() or t in v["album"].lower()]
    trovate.sort(key=lambda v: (t not in v["titolo"].lower(), v["artista"].lower(), v["titolo"].lower()))
    return trovate[:quante]


def copertina_interna(file: Path) -> tuple[bytes, str] | None:
    """La copertina dentro il file audio (FLAC, MP3, M4A), se c'è."""
    try:
        from tinytag import TinyTag

        tag = TinyTag.get(str(file), image=True)
        immagine = tag.images.any
    except Exception:
        return None
    if immagine is None or not immagine.data:
        return None
    return immagine.data, immagine.mime_type or "image/jpeg"
