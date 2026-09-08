"""Da audio a note, con Basic Pitch.

Il modello di Spotify lavora bene su uno strumento alla volta, ed è per
questo che qui arriva dopo la separazione e non prima. Il trucco che conta
davvero è restringergli la finestra di frequenze: a un basso non serve
cercare note sopra il Sol4, e non cercandole smette di inventarsele.
"""

from __future__ import annotations

from pathlib import Path

from .strumenti import Nota, Strumento

# Un margine sotto la corda più grave e sopra l'ultimo tasto, in semitoni.
MARGINE = 3


def _hertz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def finestra(strumento: Strumento) -> tuple[float, float]:
    """Le frequenze in cui questo strumento può davvero suonare."""
    return (
        _hertz(strumento.nota_piu_grave - MARGINE),
        _hertz(strumento.nota_piu_acuta + MARGINE),
    )


def trascrivi(
    audio: Path,
    strumento: Strumento,
    soglia_attacco: float = 0.5,
    soglia_nota: float = 0.3,
    durata_minima_ms: float = 60.0,
) -> list[Nota]:
    """Ascolta un file audio e ne tira fuori le note.

    Alza `soglia_attacco` se escono note che nel pezzo non ci sono, abbassala
    se ne mancano.
    """
    try:
        from basic_pitch import ICASSP_2022_MODEL_PATH
        from basic_pitch.inference import predict
    except ImportError as errore:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError(
            "Basic Pitch non è installato: pip install -r requirements.txt"
        ) from errore

    grave, acuta = finestra(strumento)
    _, _, eventi = predict(
        str(audio),
        ICASSP_2022_MODEL_PATH,
        onset_threshold=soglia_attacco,
        frame_threshold=soglia_nota,
        minimum_note_length=durata_minima_ms,
        minimum_frequency=grave,
        maximum_frequency=acuta,
    )

    return [
        Nota(midi=int(altezza), inizio=float(inizio), durata=float(fine - inizio), intensita=float(ampiezza))
        for inizio, fine, altezza, ampiezza, *_ in eventi
        if fine > inizio
    ]
