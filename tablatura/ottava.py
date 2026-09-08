"""Riconoscere una linea scritta un'ottava sopra quella vera.

È il modo classico in cui sbaglia un trascrittore di altezze, e sul basso è
il peggiore di tutti: la fondamentale di un Mi grave sta a 41 Hz, è debole,
e la compressione e i diffusori piccoli se la mangiano. Il modello allora si
aggancia alla seconda armonica — che sta esattamente un'ottava sopra — e
scrive quella.

Guardare i numeri non serve: una linea spostata di un'ottava resta
perfettamente suonabile, solo più su sul manico, e nessuna statistica sulle
altezze sa dire quale delle due sia quella vera. Il segnale sta nell'audio.
Una corda che vibra a 41 Hz produce energia a 41, 82, 123, 164 Hz: la sua
fondamentale e i suoi multipli. Se il modello scrive 82, allora esiste
energia a 123 Hz — che è una volta e mezza la nota scritta, e per una nota
vera a 82 Hz è una frequenza impossibile: lì non ci va nessuna armonica.

Il controllo è tutto lì, e conviene farlo così invece che cercare la
fondamentale a metà frequenza: nel caso che interessa davvero la
fondamentale è proprio quella che manca, mangiata dalla compressione o da
un diffusore piccolo, e cercandola non si troverebbe niente. Le armoniche
dispari a metà passo invece ci sono sempre.
"""

from __future__ import annotations

from .diteggiatura import posizioni_possibili
from .strumenti import Nota, Strumento

# Finestra lunga: per distinguere 41 Hz da 20 servono bin di pochi hertz.
FINESTRA = 0.5
# Si salta l'attacco, dove il transiente sporca tutto lo spettro.
DOPO_ATTACCO = 0.03
# La banda intorno a una frequenza, e comunque mai meno di tre bin.
BANDA = 0.03
BIN_MINIMI = 3
# Dove ci sarebbe energia se la nota vera fosse un'ottava sotto, e dove c'è
# comunque: sono multipli della nota scritta. A mezzo passo (0.5, 1.5, 2.5)
# per una nota vera non ci va niente.
MEZZI = (0.5, 1.5, 2.5)
INTERI = (1.0, 2.0, 3.0)
# Sopra questo rapporto fra le due pettinate, la nota vera è quella sotto.
SOGLIA = 0.25
# Non serve misurarle tutte: la domanda è sulla linea, non sulla singola nota.
NOTE_CAMPIONE = 40


def _hertz(midi: int) -> float:
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def _ampiezza(spettro, frequenze, frequenza: float) -> float:
    """L'ampiezza massima in una banda stretta intorno a una frequenza."""
    risoluzione = float(frequenze[1] - frequenze[0])
    larghezza = max(frequenza * BANDA, BIN_MINIMI * risoluzione)
    banda = (frequenze >= frequenza - larghezza) & (frequenze <= frequenza + larghezza)
    return float(spettro[banda].max()) if banda.any() else 0.0


def quota_sotto(
    onda,
    campionamento: int,
    note: list[Nota],
    finestra: float = FINESTRA,
    campione: int = NOTE_CAMPIONE,
) -> float:
    """Quanto le armoniche dicono che la nota vera sta un'ottava più giù.

    Si misurano due pettinate di frequenze: quella che una nota a
    quest'altezza deve avere (la nota e i suoi multipli) e quella che
    avrebbe solo se l'altezza vera fosse la metà (i multipli dispari di
    mezza frequenza). Vicino a zero le note sono dove devono stare; sopra
    la soglia vanno abbassate tutte di un'ottava.
    """
    import numpy as np

    lunghe = sorted(note, key=lambda n: -n.durata)[:campione]
    rapporti = []
    for nota in lunghe:
        inizio = int((nota.inizio + DOPO_ATTACCO) * campionamento)
        segmento = onda[inizio : inizio + int(finestra * campionamento)]
        if len(segmento) < finestra * campionamento / 2:
            continue
        spettro = np.abs(np.fft.rfft(segmento * np.hanning(len(segmento))))
        frequenze = np.fft.rfftfreq(len(segmento), 1.0 / campionamento)
        scritta = _hertz(nota.midi)
        interi = sum(_ampiezza(spettro, frequenze, scritta * m) for m in INTERI)
        if interi <= 0:
            continue
        mezzi = sum(_ampiezza(spettro, frequenze, scritta * m) for m in MEZZI)
        rapporti.append(mezzi / interi)

    if not rapporti:
        return 0.0
    rapporti.sort()
    meta = len(rapporti) // 2
    return rapporti[meta] if len(rapporti) % 2 else (rapporti[meta - 1] + rapporti[meta]) / 2


def sposta(note: list[Nota], ottave: int) -> list[Nota]:
    """La stessa linea, spostata di ottave intere."""
    return [
        Nota(midi=n.midi + 12 * ottave, inizio=n.inizio, durata=n.durata, intensita=n.intensita)
        for n in note
    ]


def ci_sta(note: list[Nota], strumento: Strumento, ottave: int) -> bool:
    """Se spostata così, la linea resta suonabile su questo strumento."""
    return all(posizioni_possibili(n.midi, strumento) for n in sposta(note, ottave))


def ottava_giusta(
    onda,
    campionamento: int,
    note: list[Nota],
    strumento: Strumento,
    soglia: float = SOGLIA,
) -> int:
    """Di quante ottave va spostata la linea: 0 o -1.

    Si abbassa solo se le armoniche lo dicono e se la linea abbassata
    resta suonabile: se scende sotto la corda più grave, allora era già
    giusta com'era — è il controllo che distingue i due casi.
    """
    if not note or not ci_sta(note, strumento, -1):
        return 0
    return -1 if quota_sotto(onda, campionamento, note) > soglia else 0


def da_file(percorso, note: list[Nota], strumento: Strumento) -> int:
    """Come `ottava_giusta`, ma leggendo l'audio da un file."""
    import soundfile

    onda, campionamento = soundfile.read(str(percorso), always_2d=True)
    return ottava_giusta(onda.mean(axis=1), campionamento, note, strumento)
