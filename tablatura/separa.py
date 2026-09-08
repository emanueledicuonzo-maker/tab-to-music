"""Da canzone a strumenti separati, con Demucs.

Quattro tracce (voce, basso, batteria, resto) col modello normale; con
`htdemucs_6s` si staccano anche chitarra e piano, ma quelle due escono più
sporche delle altre — è il modello che le ha imparate peggio.
"""

from __future__ import annotations

from pathlib import Path

MODELLO_4 = "htdemucs"
MODELLO_6 = "htdemucs_6s"
# Che traccia serve a ogni strumento, e con che modello si ottiene.
TRACCIA = {
    "basso": ("bass", MODELLO_4),
    "basso5": ("bass", MODELLO_4),
    "chitarra": ("guitar", MODELLO_6),
    "chitarra-dropd": ("guitar", MODELLO_6),
}


def separa(canzone: Path, dove: Path, modello: str = MODELLO_4) -> dict[str, Path]:
    """Spacca la canzone nei suoi strumenti e restituisce i file scritti.

    La prima volta scarica i pesi del modello (qualche centinaio di mega),
    poi resta tutto in locale.
    """
    try:
        import torch
        from demucs.api import Separator, save_audio
    except ImportError as errore:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError(
            "Demucs non è installato: pip install -r requirements.txt"
        ) from errore

    dove.mkdir(parents=True, exist_ok=True)
    separatore = Separator(model=modello)
    _, tracce = separatore.separate_audio_file(canzone)

    scritte: dict[str, Path] = {}
    for nome, onda in tracce.items():
        percorso = dove / f"{nome}.wav"
        save_audio(onda.to(torch.float32), str(percorso), separatore.samplerate)
        scritte[nome] = percorso
    return scritte
