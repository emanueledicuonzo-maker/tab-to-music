"""I testi veri, da LRCLIB: archivio libero di testi sincronizzati riga per riga.

Gli si chiedono solo artista, titolo e durata (https://lrclib.net). Le righe
arrivano con l'istante in cui cominciano: le parole di ogni riga si spalmano
fra l'inizio della riga e l'inizio della successiva, che basta per vedere
dove si è e per il canzoniere.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
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


# ---------------------------------------------------------------- copertine

COPERTINE = Path.home() / ".config" / "tablatura" / "copertine"


def copertina_online(artista: str, album: str, titolo: str = "") -> bytes | None:
    """La copertina dell'album dalla ricerca di iTunes (gratuita, senza chiave).

    Si salva una volta sola; anche il «non trovata» si ricorda, così non si
    richiede di continuo la stessa cosa.
    """
    import hashlib

    if not album.strip():
        return None
    nome = hashlib.sha1(f"{artista}|{album}".lower().encode()).hexdigest()[:16]
    file, manca = COPERTINE / f"{nome}.jpg", COPERTINE / f"{nome}.manca"
    if file.is_file():
        return file.read_bytes()
    if manca.is_file():
        return None
    COPERTINE.mkdir(parents=True, exist_ok=True)
    pulito = re.sub(r"\(.*?\)|\[.*?\]|\b(cd|disc)\s*\d+\b|flac.*$|\d{2,3}[-_ ]?\d{2,3}", " ", album, flags=re.I)
    pulito = re.sub(r"\s+", " ", pulito).strip(" -_")
    try:
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
            {"term": f"{artista} {pulito}", "entity": "album", "limit": 5})
        richiesta = urllib.request.Request(url, headers={"User-Agent": AGENTE})
        with urllib.request.urlopen(richiesta, timeout=10) as r:
            risultati = json.loads(r.read().decode("utf-8")).get("results", [])
        migliore, punti = None, 0.0
        for x in risultati:
            somiglia = difflib.SequenceMatcher(None, _semplice(pulito), _semplice(x.get("collectionName", ""))).ratio()
            artista_ok = difflib.SequenceMatcher(None, _semplice(artista), _semplice(x.get("artistName", ""))).ratio()
            valore = 0.6 * somiglia + 0.4 * artista_ok
            if valore > punti:
                migliore, punti = x, valore
        if (not migliore or punti < 0.55) and titolo:
            # Le raccolte («Top 500 degli anni 90») su iTunes non ci sono: si cerca
            # la canzone, e si usa la copertina del suo album originale.
            url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
                {"term": f"{artista} {titolo}", "entity": "song", "limit": 5})
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": AGENTE}), timeout=10) as r:
                canzoni = json.loads(r.read().decode("utf-8")).get("results", [])
            migliore, punti = None, 0.0
            for x in canzoni:
                valore = 0.5 * difflib.SequenceMatcher(None, _semplice(titolo), _semplice(x.get("trackName", ""))).ratio() \
                       + 0.5 * difflib.SequenceMatcher(None, _semplice(artista), _semplice(x.get("artistName", ""))).ratio()
                if valore > punti:
                    migliore, punti = x, valore
        if not migliore or punti < 0.55 or not migliore.get("artworkUrl100"):
            manca.touch()
            return None
        grande = migliore["artworkUrl100"].replace("100x100bb", "600x600bb")
        with urllib.request.urlopen(urllib.request.Request(grande, headers={"User-Agent": AGENTE}), timeout=15) as r:
            dati = r.read()
        file.write_bytes(dati)
        return dati
    except Exception:
        return None
