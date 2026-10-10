"""Gli accordi da strimpellare, e come si prendono sulla chitarra.

Si ascolta la traccia «other» che Demucs ha già separato — chitarre e
tastiere, senza batteria e senza voce a sporcare — più un po' del basso, che
dice qual è la nota sotto. Il riconoscimento è il metodo classico: il
cromagramma (quanta energia c'è in ognuna delle dodici note) misurato battito
per battito, confrontato con la sagoma di ogni accordo, e poi una passata di
Viterbi che preferisce restare sullo stesso accordo piuttosto che saltare a
ogni battito per una nota di passaggio.

Maggiori, minori e settime: è quello che serve per strimpellare il pop, il
rock e la canzone d'autore. Gli accordi più ricchi vengono ricondotti al più
vicino di questi tre, e il risultato è una bozza da correggere a orecchio.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

NOMI = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
TIPI = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}
SILENZIO = "N"

# Come si prendono, dalla sesta corda (Mi basso) alla prima; -1 = non suonare.
# Le posizioni aperte dove esistono, altrimenti il barrè a forma di Mi o di La.
DITEGGIATURE = {
    "C": "x32010", "C#": "x46664", "D": "xx0232", "Eb": "x68886", "E": "022100", "F": "133211",
    "F#": "244322", "G": "320003", "Ab": "466544", "A": "x02220", "Bb": "x13331", "B": "x24442",
    "Cm": "x35543", "C#m": "x46654", "Dm": "xx0231", "Ebm": "x68876", "Em": "022000", "Fm": "133111",
    "F#m": "244222", "Gm": "355333", "Abm": "466444", "Am": "x02210", "Bbm": "x13321", "Bm": "x24432",
    "C7": "x32310", "C#7": "x46464", "D7": "xx0212", "Eb7": "x68686", "E7": "020100", "F7": "131211",
    "F#7": "242322", "G7": "320001", "Ab7": "464544", "A7": "x02020", "Bb7": "x13131", "B7": "x21202",
}


@dataclass(frozen=True)
class Accordo:
    """Un accordo, da quando a quando."""

    nome: str
    inizio: float
    fine: float


def sagome() -> tuple[list[str], np.ndarray]:
    """I nomi degli accordi e la loro sagoma sulle dodici note, normalizzata."""
    nomi, righe = [], []
    for tipo, intervalli in TIPI.items():
        for fondamentale in range(12):
            riga = np.zeros(12)
            for i, intervallo in enumerate(intervalli):
                # La fondamentale pesa di più: distingue Am da C, che hanno due note in comune.
                riga[(fondamentale + intervallo) % 12] = 1.5 if i == 0 else 1.0
            nomi.append(NOMI[fondamentale] + tipo)
            righe.append(riga / np.linalg.norm(riga))
    return nomi, np.array(righe)


def dal_croma(
    croma: np.ndarray,
    tempi: np.ndarray,
    restare: float = 0.85,
    nitidezza: float = 12.0,
    soglia: float = 0.08,
    sconto_settima: float = 0.93,
) -> list[Accordo]:
    """Da un cromagramma (12 × battiti) alla sequenza di accordi.

    `tempi` ha un elemento in più delle colonne: l'inizio di ogni battito e la
    fine dell'ultimo. `restare` è la probabilità di non cambiare accordo da un
    battito all'altro: più è alta, meno si inseguono le note di passaggio.
    Un battito con troppo poca energia è silenzio, e non porta nessun accordo.
    """
    nomi, forme = sagome()
    energia = croma.sum(axis=0)
    norme = np.linalg.norm(croma, axis=0)
    somiglianza = forme @ (croma / np.maximum(norme, 1e-9))
    # La settima ha una nota in più e somiglia un po' a tutto: la si sceglie
    # solo quando batte davvero la triade. Su Billie Jean, senza questo
    # sconto, il ritornello D–F#m–Bm–C# diventava una fila di C#7.
    somiglianza[[i for i, nome in enumerate(nomi) if nome.endswith("7")]] *= sconto_settima
    # Il silenzio vale come un accordo in più: alto dove non suona niente.
    zitto = energia < soglia * (np.median(energia[energia > 0]) if (energia > 0).any() else 1)
    somiglianza = np.vstack([somiglianza, np.where(zitto, 1.0, 0.0)])
    nomi = nomi + [SILENZIO]

    probabilita = np.exp(nitidezza * somiglianza)
    probabilita /= probabilita.sum(axis=0, keepdims=True)
    n = len(nomi)
    passaggio = np.full((n, n), (1 - restare) / (n - 1))
    np.fill_diagonal(passaggio, restare)
    percorso = _viterbi(probabilita, passaggio)

    accordi: list[Accordo] = []
    for i, stato in enumerate(percorso):
        nome = nomi[stato]
        if accordi and accordi[-1].nome == nome and abs(accordi[-1].fine - tempi[i]) < 1e-6:
            accordi[-1] = Accordo(nome, accordi[-1].inizio, float(tempi[i + 1]))
        else:
            accordi.append(Accordo(nome, float(tempi[i]), float(tempi[i + 1])))
    return [a for a in accordi if a.nome != SILENZIO]


def _viterbi(probabilita: np.ndarray, passaggio: np.ndarray) -> list[int]:
    """Il percorso più probabile, in logaritmi per non andare a zero."""
    log_p = np.log(probabilita + 1e-12)
    log_t = np.log(passaggio)
    stati, passi = log_p.shape
    punteggio = log_p[:, 0].copy()
    da_dove = np.zeros((stati, passi), dtype=int)
    for t in range(1, passi):
        candidati = punteggio[:, None] + log_t
        da_dove[:, t] = candidati.argmax(axis=0)
        punteggio = candidati.max(axis=0) + log_p[:, t]
    percorso = [int(punteggio.argmax())]
    for t in range(passi - 1, 0, -1):
        percorso.append(int(da_dove[percorso[-1], t]))
    return percorso[::-1]


def ascolta(
    armonia: list[Path], basso: Path | None, bpm: float, partenza: float = 0.0
) -> list[Accordo]:
    """Riconosce gli accordi dalle tracce separate, un battito alla volta.

    `armonia` sono le tracce che portano gli accordi: «other» col modello a
    quattro tracce, chitarra e piano e «other» con quello a sei.
    """
    import librosa

    sr, salto = 22050, 512
    pesi = [(traccia, 1.0) for traccia in armonia] + ([(basso, 0.5)] if basso else [])
    croma, durata = None, 0.0
    for traccia, peso in pesi:
        suono, _ = librosa.load(traccia, sr=sr, mono=True)
        durata = max(durata, len(suono) / sr)
        questo = peso * librosa.feature.chroma_cqt(y=suono, sr=sr, hop_length=salto)
        if croma is None:
            croma = questo
        else:
            lunghezza = min(croma.shape[1], questo.shape[1])
            croma = croma[:, :lunghezza] + questo[:, :lunghezza]
    if croma is None:
        return []

    battito = 60.0 / bpm
    primo = partenza % battito
    tempi = np.arange(primo, durata, battito)
    if len(tempi) < 2:
        return []
    quadri = librosa.time_to_frames(tempi, sr=sr, hop_length=salto)
    per_battito = librosa.util.sync(croma, quadri, aggregate=np.median)[:, 1:]
    # sync aggiunge una colonna prima del primo battito: la si toglie, e i
    # battiti restano quelli fra un tempo e il successivo.
    colonne = min(per_battito.shape[1], len(tempi) - 1)
    return dal_croma(per_battito[:, :colonne], tempi[: colonne + 1])
