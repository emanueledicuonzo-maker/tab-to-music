"""I testi veri, da LRCLIB: archivio libero di testi sincronizzati riga per riga.

Gli si chiedono solo artista, titolo e durata (https://lrclib.net). Le righe
arrivano con l'istante in cui cominciano: le parole di ogni riga si spalmano
fra l'inizio della riga e l'inizio della successiva, che basta per vedere
dove si è e per il canzoniere.
"""

from __future__ import annotations

import difflib
import json
import re
import urllib.parse
import urllib.request

AGENTE = "Tablatura/1.0 (uso personale)"
RIGA = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")


def _chiedi(percorso: str, **domanda) -> object:
    url = "https://lrclib.net/api/" + percorso + "?" + urllib.parse.urlencode(domanda)
    richiesta = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    with urllib.request.urlopen(richiesta, timeout=15) as risposta:
        return json.loads(risposta.read().decode("utf-8"))


def _semplice(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\(.*?\)|\[.*?\]", " ", s.lower())).strip()


def cerca_testo(artista: str, titolo: str, durata: float) -> dict | None:
    """Il testo sincronizzato più adatto, o None."""
    candidati = []
    try:
        candidati = _chiedi("search", track_name=titolo, artist_name=artista) or []
        if not candidati:
            candidati = _chiedi("search", q=f"{artista} {titolo}") or []
    except Exception:
        return None
    migliore, punti = None, 0.0
    for c in candidati:
        if not c.get("syncedLyrics"):
            continue
        somiglia = difflib.SequenceMatcher(None, _semplice(titolo), _semplice(c.get("trackName", ""))).ratio()
        artista_ok = difflib.SequenceMatcher(None, _semplice(artista), _semplice(c.get("artistName", ""))).ratio()
        scarto = abs((c.get("duration") or 0) - durata)
        valore = somiglia * 0.6 + artista_ok * 0.3 + (0.1 if scarto < 4 else 0) - (0.5 if scarto > 20 else 0)
        if valore > punti:
            migliore, punti = c, valore
    return migliore if punti >= 0.6 else None


def parole(sincronizzato: str, durata: float) -> list[dict]:
    """Dalle righe [mm:ss.xx] alle parole con il loro istante."""
    righe = []
    for r in sincronizzato.splitlines():
        m = RIGA.match(r.strip())
        if m:
            righe.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
    fuori = []
    for i, (inizio, testo) in enumerate(righe):
        if not testo:
            continue
        fine = righe[i + 1][0] if i + 1 < len(righe) else min(durata, inizio + 6)
        # Le parole occupano al massimo l'80% della riga: la pausa sta in fondo.
        spazio = max(0.5, (fine - inizio) * 0.8)
        pezzi = testo.split()
        for k, p in enumerate(pezzi):
            fuori.append({"testo": p, "quando": round(inizio + spazio * k / len(pezzi), 3), "riga": i})
    return fuori
