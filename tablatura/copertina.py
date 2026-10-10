"""La copertina dell'album, per la pagina e per l'elenco.

Prima si cerca un'immagine nella cartella dell'album, con i nomi che usano
tutti (front, cover, folder); poi un'immagine qualsiasi, lasciando stare gli
spettrogrammi e le firme di chi ha fatto il rip; per ultima quella che il
file audio si porta dentro, che si tira fuori con ffmpeg.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

IMMAGINI = {".jpg", ".jpeg", ".png", ".webp"}
NOMI_BUONI = ("front", "cover", "folder", "album", "copertina")
NOMI_DA_SCARTARE = ("spek", "spectro", "spettro", "log", "back", "cd", "disc", "inlay", "jolly")


def trova(canzone: Path) -> Path | None:
    """Un'immagine della copertina nella cartella dell'album, se c'è."""
    cartella = canzone.parent
    candidate = [f for f in cartella.iterdir() if f.is_file() and f.suffix.lower() in IMMAGINI]
    for nome in NOMI_BUONI:
        for f in candidate:
            if f.stem.lower().startswith(nome):
                return f
    rimaste = [f for f in candidate if not any(s in f.stem.lower() for s in NOMI_DA_SCARTARE)]
    # Fra le altre, la più grande: le miniature e i loghi pesano poco.
    return max(rimaste, key=lambda f: f.stat().st_size, default=None)


def salva(canzone: Path, album: Path) -> Path | None:
    """Mette la copertina in `album/copertina.<ext>`, se non c'è già."""
    for gia in album.glob("copertina.*"):
        return gia
    album.mkdir(parents=True, exist_ok=True)
    trovata = trova(canzone)
    if trovata is not None:
        destinazione = album / f"copertina{trovata.suffix.lower()}"
        shutil.copyfile(trovata, destinazione)
        return destinazione
    destinazione = album / "copertina.jpg"
    try:
        esito = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", str(canzone), "-an", "-frames:v", "1", str(destinazione)],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if esito.returncode == 0 and destinazione.is_file() and destinazione.stat().st_size > 0:
        return destinazione
    destinazione.unlink(missing_ok=True)
    return None


def di(album: Path) -> Path | None:
    """La copertina già salvata di un album."""
    return next(iter(sorted(album.glob("copertina.*"))), None)
