"""Il formato .t2m (Tab to Music): tutto il lavoro su una canzone in un file solo.

Un file JSON, leggibile e confrontabile, con:

    format, version          «t2m», 1
    song                     artista, titolo, album, durata
    recording                impronta del disco: durata e cromagramma ridotto
                             (dodici note ogni due secondi), per riconoscere su
                             quale registrazione è stata agganciata la tab
    source                   da dove viene la tab (Guitar Pro, tab di testo, Importa)
    score                    la partitura nel JSON di alphaTab: non dipende più
                             da Guitar Pro, e alphaTab la ridisegna com'era
    view                     la traccia preferita
    sync                     per ogni battuta suonata, l'istante nel disco
                             (automatica), più spostamento e correzioni a mano
    lyrics                   le righe del testo con il loro istante, se ci sono
    credits                  Tab to Music — getaweb.it

Il programma lo scrive da solo ogni volta che una canzone viene sincronizzata o
corretta, e lo riapre al posto della tab d'archivio.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np

VERSIONE = 1


def nome_file(artista: str, titolo: str) -> str:
    pulito = lambda s: re.sub(r'[\\/:*?"<>|]+', " ", s).strip()
    return f"{pulito(artista) or 'Unknown'} - {pulito(titolo) or 'Untitled'}.t2m"


def impronta(audio: Path) -> dict:
    """Durata e cromagramma ridotto (un valore 0-9 per nota ogni due secondi)."""
    from .allinea import PASSO, croma_del_disco

    croma = croma_del_disco(audio)
    ogni = max(1, int(round(2.0 / PASSO)))
    pezzi = [croma[:, i:i + ogni].mean(axis=1) for i in range(0, croma.shape[1], ogni)]
    ridotto = np.array(pezzi).T if pezzi else np.zeros((12, 0))
    ridotto = np.round(ridotto / max(float(ridotto.max()), 1e-9) * 9).astype(int)
    return {"duration": round(croma.shape[1] * PASSO, 1), "chroma2s": ["".join(map(str, riga)) for riga in ridotto]}


def somiglianza_impronte(a: dict, b: dict) -> float:
    """0-1: quanto due impronte sembrano la stessa registrazione."""
    if abs(a.get("duration", 0) - b.get("duration", 0)) > 8:
        return 0.0
    x = np.array([[int(c) for c in r] for r in a.get("chroma2s", [])], dtype=float)
    y = np.array([[int(c) for c in r] for r in b.get("chroma2s", [])], dtype=float)
    if x.size == 0 or y.size == 0:
        return 0.0
    n = min(x.shape[1], y.shape[1])
    x, y = x[:, :n].ravel(), y[:, :n].ravel()
    x, y = x - x.mean(), y - y.mean()
    return float(max(0.0, (x @ y) / max(np.linalg.norm(x) * np.linalg.norm(y), 1e-9)))


def scrivi(file: Path, *, voce: dict, audio: Path, sorgente: dict, partitura: str, traccia: int,
           sincronia: dict, righe: list[dict] | None) -> Path:
    vecchio = leggi(file) or {}
    dati = {
        "format": "t2m",
        "version": VERSIONE,
        "song": {k: voce.get(k) for k in ("artista", "titolo", "album", "durata")},
        "recording": vecchio.get("recording") if vecchio.get("recording", {}).get("file") == audio.name else
                     impronta(audio) | {"file": audio.name},
        "source": sorgente,
        "score": json.loads(partitura) if isinstance(partitura, str) else partitura,
        "view": {"track": traccia},
        "sync": sincronia,
        "lyrics": {"source": "lrclib", "lines": righe} if righe else None,
        "credits": "Tab to Music — https://getaweb.it",
        "saved": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    file.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = file.with_suffix(".t2m.tmp")
    temporaneo.write_text(json.dumps(dati, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporaneo.replace(file)
    return file


def leggi(file: Path) -> dict | None:
    try:
        dati = json.loads(Path(file).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dati if dati.get("format") == "t2m" else None
