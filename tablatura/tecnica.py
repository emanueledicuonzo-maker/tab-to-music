"""Come si suona una nota, oltre a dove: legati, glissati, bending, vibrato, trilli.

I segni sono quelli di ogni tablatura:

    5h7   legato in salita (hammer-on): la seconda nota senza pennata
    7p5   legato in discesa (pull-off)
    5/7   glissato in salita, 7\\5 in discesa (slide)
    7b    bending: la nota sale senza un nuovo attacco
    7~    vibrato: l'altezza oscilla su una nota tenuta
    tr    trillo: due note vicine alternate velocissime

Per riconoscerli servono due cose della traccia separata: l'altezza istante
per istante (pYIN), e quanto è forte l'attacco all'inizio di ogni nota. Una
nota che parte senza attacco, mentre la corda sta ancora suonando, è stata
presa con la mano sinistra: legato, o glissato se in mezzo l'altezza è
passata per tutte le note intermedie.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 22050
SALTO = 256


@dataclass(frozen=True)
class Evento:
    """Una nota già messa sul manico: quando parte, quale nota, su che corda."""

    inizio: float
    midi: int
    corda: int
    fine: float | None = None


def semitoni(f0: np.ndarray) -> np.ndarray:
    """Da hertz a note MIDI con i decimali; NaN dove non suona niente."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return 69 + 12 * np.log2(f0 / 440.0)


def _sempre_suona(altezza: np.ndarray, a: int, b: int) -> bool:
    """Fra due istanti la corda non si è mai fermata: la nota non è stata ripresa."""
    return b > a and not np.isnan(altezza[a:b]).any()


def dalle_curve(
    eventi: list[Evento],
    altezza: np.ndarray,
    attacchi: np.ndarray,
    passo: float,
    legato_max: float = 0.4,
    soglia_attacco: float = 0.35,
) -> list[str]:
    """Il segno di ogni nota ("" se suonata normale), nello stesso ordine.

    `altezza` è la curva in semitoni (NaN = silenzio), `attacchi` la forza
    dell'attacco nello stesso passo di tempo, `passo` i secondi fra due punti.
    """
    segni = [""] * len(eventi)
    if not eventi:
        return segni
    quadro = lambda t: int(np.clip(round(t / passo), 0, len(altezza) - 1))

    # Quanto è forte l'attacco di ogni nota, rispetto a quello tipico del pezzo.
    def forza(t: float) -> float:
        a, b = quadro(t - 0.04), quadro(t + 0.05)
        return float(attacchi[a : b + 1].max()) if b >= a else 0.0

    forze = np.array([forza(e.inizio) for e in eventi])
    tipica = float(np.median(forze[forze > 0])) if (forze > 0).any() else 1.0

    for i, e in enumerate(eventi):
        fine = e.fine
        if fine is None:
            fine = eventi[i + 1].inizio if i + 1 < len(eventi) else e.inizio + 0.5
        a, b = quadro(e.inizio + 0.03), quadro(fine - 0.05)
        tratto = altezza[a : b + 1] - e.midi if b > a else np.array([])
        # Via i buchi e i salti d'ottava del riconoscitore: non sono tecnica, sono errori.
        tratto = tratto[~np.isnan(tratto)]
        tratto = tratto[np.abs(tratto) < 3]
        liscio = len(tratto) < 2 or np.abs(np.diff(tratto)).max() < 0.6

        # Legato e glissato: stessa corda, la nota prima ancora viva, niente pennata.
        prima = eventi[i - 1] if i else None
        if (
            prima is not None
            and prima.corda == e.corda
            and prima.midi != e.midi
            and 0 < e.inizio - prima.inizio <= legato_max + 0.6
            and _sempre_suona(altezza, quadro(prima.inizio + 0.03), quadro(e.inizio - 0.01))
            and forze[i] < soglia_attacco * tipica
        ):
            a, b = quadro(e.inizio - 0.12), quadro(e.inizio + 0.02)
            ponte = altezza[a : b + 1]
            continuo = ponte[~np.isnan(ponte)]
            basso, alto = sorted((prima.midi, e.midi))
            # Glissato se l'altezza è passata in mezzo per almeno metà dell'intervallo.
            dentro = ((continuo > basso + 0.4) & (continuo < alto - 0.4)).sum() if alto - basso >= 2 else 0
            if dentro >= max(2, 0.5 * (alto - basso - 1)):
                segni[i] = "/" if e.midi > prima.midi else "\\"
            elif abs(e.midi - prima.midi) <= 5:
                segni[i] = "h" if e.midi > prima.midi else "p"

        dopo = eventi[i + 1] if i + 1 < len(eventi) else None
        if len(tratto) >= 6 and not segni[i] and liscio:
            # Bending: la nota parte giusta, sale di almeno tre quarti di tono senza
            # salti e ci resta per un po'. Se la nota dopo, sulla stessa corda, è
            # proprio quella d'arrivo, era un legato o un glissato, non un bending.
            salita = np.percentile(tratto, 85)
            arrivo_uguale = dopo is not None and dopo.corda == e.corda and abs(dopo.midi - e.midi - salita) < 0.6
            in_alto = (tratto > 0.6).sum() * passo
            if 0.75 <= salita <= 2.5 and tratto[: max(2, len(tratto) // 5)].mean() < 0.3 and in_alto >= 0.08 and not arrivo_uguale:
                segni[i] = "b"
                continue
        if len(tratto) * passo >= 0.35 and not segni[i] and liscio:
            # Vibrato: l'altezza attraversa la sua media più volte, poco ma con regolarità.
            # Il tremolio del riconoscitore è disordinato; il vibrato vero è un'onda
            # regolare fra 4 e 8 oscillazioni al secondo, e si vede nello spettro.
            centrato = tratto - np.median(tratto)
            ampiezza = np.percentile(np.abs(centrato), 80)
            spettro = np.abs(np.fft.rfft(centrato * np.hanning(len(centrato)))) ** 2
            frequenze = np.fft.rfftfreq(len(centrato), passo)
            banda = (frequenze >= 4) & (frequenze <= 8)
            quota = spettro[banda].sum() / max(spettro[1:].sum(), 1e-12)
            if 0.15 <= ampiezza <= 1.0 and quota >= 0.5:
                segni[i] = "~"

    # Trillo: almeno quattro note di fila che alternano due altezze vicine, veloci.
    i = 0
    while i < len(eventi):
        j = i
        while (
            j + 1 < len(eventi)
            and eventi[j + 1].inizio - eventi[j].inizio < 0.13
            and 1 <= abs(eventi[j + 1].midi - eventi[j].midi) <= 2
            and (j == i or eventi[j + 1].midi == eventi[j - 1].midi)
        ):
            j += 1
        if j - i + 1 >= 4:
            segni[i] = "tr"
            for k in range(i + 1, j + 1):
                segni[k] = "h" if eventi[k].midi > eventi[k - 1].midi else "p"
            i = j + 1
        else:
            i += 1
    return segni


@lru_cache(maxsize=2)
def curve(traccia: Path, grave: float, acuta: float) -> tuple[np.ndarray, np.ndarray]:
    """L'altezza in semitoni e la forza degli attacchi, a passi di SALTO.

    È il conto lungo (un minuto a canzone): lo usano sia i segni sia le note
    ritrovate dai colpi, quindi si fa una volta sola.
    """
    import librosa

    suono, _ = librosa.load(traccia, sr=SR, mono=True)
    f0, _, _ = librosa.pyin(suono, fmin=grave, fmax=acuta, sr=SR, frame_length=2048, hop_length=SALTO)
    attacchi = librosa.onset.onset_strength(y=suono, sr=SR, hop_length=SALTO)
    lunghezza = min(len(f0), len(attacchi))
    return semitoni(f0[:lunghezza]), attacchi[:lunghezza]


def ascolta(traccia: Path, eventi: list[Evento], grave: float = 35.0, acuta: float = 1200.0) -> list[str]:
    """Riconosce le tecniche sulla traccia separata dello strumento."""
    altezza, attacchi = curve(Path(traccia), grave, acuta)
    ordine = sorted(range(len(eventi)), key=lambda i: eventi[i].inizio)
    segni = dalle_curve([eventi[i] for i in ordine], altezza, attacchi, SALTO / SR)
    # Si restituiscono nell'ordine in cui sono arrivati.
    fuori = [""] * len(eventi)
    for posto, i in enumerate(ordine):
        fuori[i] = segni[posto]
    return fuori


def note_dai_colpi(
    note: list,
    altezza: np.ndarray,
    attacchi: np.ndarray,
    passo: float,
    grave: int,
    acuta: int,
    percentile: float = 60,
    vicino: float = 0.07,
) -> list:
    """Le note che il trascrittore non ha scritto, ritrovate dagli attacchi.

    Sul basso distorto di Killing in the Name il trascrittore si perdeva un Re
    ribattuto su quattro: l'attacco nella traccia c'è, la nota no. Dove c'è un
    colpo chiaro (fra i più forti del pezzo) e nessuna nota parte lì vicino, si
    aggiunge la nota con l'altezza che si sente subito dopo. Provato contro
    BigBassTabs: 107 note in più, quasi tutte Re ribattuti, e nessuna nota
    sbagliata in più.
    """
    from .strumenti import Nota

    picchi = [
        i for i in range(1, len(attacchi) - 1)
        if attacchi[i] >= attacchi[i - 1] and attacchi[i] > attacchi[i + 1]
    ]
    if not picchi:
        return list(note)
    forti = np.array([attacchi[i] for i in picchi])
    soglia = np.percentile(forti, percentile)
    inizi = np.array(sorted(n.inizio for n in note)) if note else np.array([])
    nuove = []
    for i in picchi:
        if attacchi[i] < soglia:
            continue
        t = i * passo
        if len(inizi) and np.min(np.abs(inizi - t)) < vicino:
            continue
        tratto = altezza[i + 1 : i + 8]
        tratto = tratto[~np.isnan(tratto)]
        if len(tratto) < 4:
            continue
        midi = int(round(float(np.median(tratto))))
        if grave <= midi <= acuta:
            nuove.append(Nota(midi=midi, inizio=float(t), durata=0.12, intensita=0.6))
    return sorted(list(note) + nuove, key=lambda n: n.inizio)
