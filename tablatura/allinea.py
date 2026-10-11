"""Sincronizzare una tablatura Guitar Pro col disco intero, senza separare niente.

È il metodo classico per allineare una partitura a una registrazione: da una
parte il cromagramma del disco (quanta energia c'è in ognuna delle dodici
note, istante per istante), dall'altra lo stesso cromagramma «suonato» dalla
partitura al suo tempo scritto, con le note di tutti gli strumenti. Un
allineamento dinamico (DTW) trova la corrispondenza fra i due tempi, e da lì
si legge a che istante del disco comincia ogni battuta.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SR = 22050
SALTO = 2048           # ~93 ms: abbastanza fine per le battute, veloce da allineare
PASSO = SALTO / SR


from functools import lru_cache


def croma_del_disco(audio: Path) -> np.ndarray:
    """Il cromagramma di un disco; se è la cartella di una canzone lavorata,
    quello delle sue tracce separate sommate (batteria esclusa)."""
    audio = Path(audio)
    if audio.is_dir():
        tracce = [t for t in sorted(audio.glob("*.wav")) if t.stem != "drums"]
        somma = None
        for t in tracce:
            c = _croma(str(t), t.stat().st_mtime)
            somma = c if somma is None else somma[:, : min(somma.shape[1], c.shape[1])] + c[:, : min(somma.shape[1], c.shape[1])]
        return somma / np.maximum(np.linalg.norm(somma, axis=0, keepdims=True), 1e-9)
    return _croma(str(audio), audio.stat().st_mtime)


@lru_cache(maxsize=8)
def _croma(audio: str, _quando: float) -> np.ndarray:
    """Calcolata una volta per disco: la usano sia la sincronia sia il confronto fra versioni."""
    import librosa

    suono, _ = librosa.load(audio, sr=SR, mono=True)
    croma = librosa.feature.chroma_cqt(y=suono, sr=SR, hop_length=SALTO)
    return croma / np.maximum(np.linalg.norm(croma, axis=0, keepdims=True), 1e-9)


def croma_della_partitura(eventi: list[dict], fine_ms: float) -> np.ndarray:
    """eventi: {inizio, durata} in millisecondi al tempo scritto, e midi."""
    quadri = int(np.ceil(fine_ms / 1000 / PASSO)) + 1
    croma = np.zeros((12, quadri))
    for e in eventi:
        da = int(e["inizio"] / 1000 / PASSO)
        a = max(da + 1, int((e["inizio"] + e["durata"]) / 1000 / PASSO))
        # Le note gravi pesano di più: sono il basso e le fondamentali degli accordi.
        peso = 1.5 if e["midi"] < 48 else 1.0
        croma[e["midi"] % 12, da:min(a, quadri)] += peso
    return croma / np.maximum(np.linalg.norm(croma, axis=0, keepdims=True), 1e-9)


def _allinea(audio: Path, eventi: list[dict], battute: list[float]):
    import librosa

    disco = croma_del_disco(audio)
    fine = max([e["inizio"] + e["durata"] for e in eventi] + battute + [0])
    partitura = croma_della_partitura(eventi, fine)
    # Costo coseno; i passi non diagonali costano un po' di più, così il
    # tempo non si contrae e dilata a scatti per una nota sbagliata.
    costo = 1 - partitura.T @ disco
    totale, percorso = librosa.sequence.dtw(C=costo, step_sizes_sigma=np.array([[1, 1], [0, 1], [1, 0]]),
                                            weights_add=np.array([0, 0.1, 0.1]), subseq=False, backtrack=True)
    return totale[-1, -1], percorso[::-1], partitura


def somiglianza(audio: Path, eventi: list[dict], battute: list[float]) -> float:
    """Quanto una tablatura combacia col disco: il costo medio lungo l'allineamento (più basso = meglio)."""
    if not eventi:
        return 9.0
    totale, percorso, _ = _allinea(audio, eventi, battute)
    return float(totale / len(percorso))


def sincronizza(audio: Path, eventi: list[dict], battute: list[float]) -> list[float]:
    """Per ogni inizio di battuta (ms al tempo scritto), l'istante nel disco (ms)."""
    _, percorso, partitura = _allinea(audio, eventi, battute)
    # Per ogni quadro della partitura, il primo quadro del disco che gli corrisponde.
    verso = np.full(partitura.shape[1], -1)
    for i, j in percorso:
        if verso[i] < 0:
            verso[i] = j
    for i in range(1, len(verso)):
        if verso[i] < 0:
            verso[i] = verso[i - 1]
    fuori = []
    for b in battute:
        q = min(len(verso) - 1, int(round(b / 1000 / PASSO)))
        fuori.append(round(float(verso[q] * PASSO * 1000)))
    # Mai all'indietro.
    for k in range(1, len(fuori)):
        fuori[k] = max(fuori[k], fuori[k - 1])
    return fuori
