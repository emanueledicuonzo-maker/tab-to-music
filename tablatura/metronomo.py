"""Trovare il metronomo del pezzo, per poter scrivere battute vere.

Senza il tempo non esiste tablatura leggibile: i numeri ci sono ma non si sa
quando cadono. Librosa arriva già con Basic Pitch, e per la musica con una
batteria in quattro il suo battito è quasi sempre giusto. Su un pezzo senza
polso stabile può sbagliare, e in quel caso conviene dirglielo a mano.
"""

from __future__ import annotations

from pathlib import Path


def metronomo(audio: Path) -> tuple[float, float]:
    """Battiti al minuto e secondo del primo battito trovato.

    Da usare come `bpm` e `partenza` del disegno. Attenzione: trova i battiti,
    non gli inizi di battuta, quindi la prima stanghetta può cadere sul
    movimento sbagliato — se la tablatura «sfasa», sposta `--partenza` di un
    movimento.
    """
    try:
        import librosa
    except ImportError as errore:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError("Librosa non è installata: pip install -r requirements.txt") from errore

    onda, campionamento = librosa.load(str(audio), mono=True)
    battiti_al_minuto, battiti = librosa.beat.beat_track(y=onda, sr=campionamento, units="time")
    bpm = float(battiti_al_minuto if not hasattr(battiti_al_minuto, "item") else battiti_al_minuto.item())
    primo = float(battiti[0]) if len(battiti) else 0.0
    return round(bpm, 2), round(primo, 3)


# I livelli metrici su cui un rilevatore di battito sbaglia di solito: sente
# il doppio, la metà, o il movimento puntato invece di quello semplice.
RAPPORTI = (1 / 3, 1 / 2, 2 / 3, 3 / 4, 1, 4 / 3, 3 / 2, 2, 3)
BPM_MINIMO, BPM_MASSIMO = 40, 240
# Una nota è «sulla griglia» entro un quarto di cella, e comunque entro 40 ms:
# più o meno il tremolio di un musicista che tiene bene il tempo.
QUOTA_CELLA = 0.25
TOLLERANZA_MASSIMA = 0.04
# Il livello metrico si scavalca solo con una prova netta: coperture più
# vicine di così sono un pareggio, e il pareggio lo vince il tempo rilevato.
# Stretto di proposito — un tempo sbagliato di un terzo può coprire il 98%
# delle note, perché a quel tempo la battuta fa quasi un numero intero di
# celle e le posizioni ci ricascano dentro per caso.
PAREGGIO = 0.01


def _copertura(inizi: list[float], bpm: float, fase: float, suddivisione: int) -> float:
    """Che quota di note cade sulla griglia di questo tempo.

    La tolleranza è legata alla cella, non fissa: con una tolleranza fissa un
    tempo doppio vince sempre, perché le sue celle diventano più corte della
    tolleranza stessa e qualunque nota risulta «in griglia».
    """
    cella = 60.0 / bpm / suddivisione
    tolleranza = min(TOLLERANZA_MASSIMA, cella * QUOTA_CELLA)
    dentro = sum(
        1 for i in inizi if abs(i - fase - round((i - fase) / cella) * cella) <= tolleranza
    )
    return dentro / len(inizi)


def affina(
    inizi: list[float],
    bpm: float,
    partenza: float,
    suddivisione: int = 4,
    scarto: float = 0.05,
    passi_bpm: int = 20,
    passi_fase: int = 24,
) -> tuple[float, float]:
    """Ritocca tempo e fase finché la griglia non passa per le note vere.

    Due errori diversi, e vanno corretti insieme. Il primo è di precisione:
    il battito viene trovato a 99.4 invece di 100, e mezzo punto dopo dieci
    secondi è mezza casella. Il secondo è di livello: su un ostinato sincopato
    il rilevatore sente 136 bpm dove ce ne sono 100, e nessun ritocco fine può
    salvare una griglia sbagliata di un terzo. Quindi si provano anche i
    livelli metrici vicini — metà, doppio, puntato — e si tiene quello su cui
    cadono più note. A parità, vince il tempo più vicino a quello rilevato:
    il livello si scavalca solo con una prova chiara.
    """
    if not inizi or bpm <= 0:
        return bpm, partenza

    candidati: list[tuple[float, float, float]] = []
    for rapporto in RAPPORTI:
        base = bpm * rapporto
        if not BPM_MINIMO <= base <= BPM_MASSIMO:
            continue
        cella = 60.0 / base / suddivisione
        candidati.append(
            max(
                (
                    _copertura(inizi, candidato, fase, suddivisione),
                    candidato,
                    fase,
                )
                for i in range(passi_bpm + 1)
                for candidato in [base * (1 - scarto + 2 * scarto * i / passi_bpm)]
                for j in range(passi_fase)
                for fase in [inizi[0] + cella * j / passi_fase]
            )
        )

    if not candidati:
        return bpm, partenza
    massima = max(copertura for copertura, _, _ in candidati)
    ammessi = [c for c in candidati if c[0] >= massima - PAREGGIO]
    _, scelto, fase = min(ammessi, key=lambda c: abs(c[1] - bpm))
    return round(scelto, 2), round(fase, 3)
