"""Le parole cantate, con il momento in cui cadono.

Vale lo stesso trucco del basso: si ascolta la traccia della voce già
separata, non il disco intero. Whisper è addestrato sul parlato e il cantato
lo mette in difficoltà — note tenute, sillabe spalmate, cori sovrapposti —
ma su una voce isolata e in primo piano se la cava.

Per chi suona il basso il valore non è leggere il testo: è sapere dove si
è. Ventisei battute identiche di ostinato diventano navigabili se sotto
c'è la parola che il cantante sta dicendo in quel momento.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MODELLO = "small"


@dataclass(frozen=True)
class Parola:
    """Una parola cantata, e quando."""

    testo: str
    inizio: float
    durata: float

    @property
    def fine(self) -> float:
        return self.inizio + self.durata


def ascolta(
    voce: Path, lingua: str | None = None, modello: str = MODELLO
) -> list[Parola]:
    """Trascrive la traccia della voce, parola per parola.

    `lingua` in codice ISO («it», «en»): darla evita che il modello la
    indovini male su un ritornello corto. La prima volta scarica il modello.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError as errore:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError(
            "faster-whisper non è installato: pip install -r requirements.txt"
        ) from errore

    trascrittore = WhisperModel(modello, device="cpu", compute_type="int8")
    # Senza «condition_on_previous_text» il modello non si porta dietro la
    # frase prima: sui ritornelli ripetuti (il finale di Killing in the Name,
    # sedici volte la stessa riga) altrimenti ne salta la maggior parte.
    segmenti, _ = trascrittore.transcribe(
        str(voce), word_timestamps=True, language=lingua, condition_on_previous_text=False
    )
    return [
        Parola(testo=parola.word.strip(), inizio=float(parola.start), durata=float(parola.end - parola.start))
        for segmento in segmenti
        for parola in (segmento.words or [])
        if parola.word.strip()
    ]


def in_celle(
    parole: list[Parola],
    bpm: float,
    suddivisione: int = 4,
    movimenti: int = 4,
    partenza: float = 0.0,
) -> dict[int, str]:
    """Ogni parola nella casella in cui viene cantata.

    Stessa griglia delle note: le parole non hanno un tempo loro, hanno
    quello del pezzo. Se due parole cadono nella stessa casella si tengono
    attaccate, che è come si cantano.
    """
    cella = 60.0 / bpm / suddivisione
    caselle: dict[int, str] = {}
    for parola in parole:
        indice = round((parola.inizio - partenza) / cella)
        if indice < 0:
            continue
        caselle[indice] = f"{caselle[indice]} {parola.testo}" if indice in caselle else parola.testo
    return caselle
