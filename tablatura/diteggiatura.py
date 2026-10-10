"""Da note a posizioni sul manico.

La stessa nota si può prendere su più corde: il Sol2 di un basso sta al 15°
tasto del Mi, al 10° del La, al 5° del Re e a vuoto sul Sol. Scegliere bene
significa non far saltare la mano avanti e indietro sul manico, quindi la
scelta non si fa nota per nota ma sull'intera frase: programmazione dinamica
sulla sequenza, dove ogni passo paga lo spostamento rispetto al passo prima.
"""

from __future__ import annotations

from .strumenti import Nota, NotaSuonata, Posizione, Strumento

# Quanto pesa spostare la mano di un tasto rispetto a cambiare corda.
PESO_SALTO_TASTO = 1.2
PESO_SALTO_CORDA = 0.8
# Una corda a vuoto non muove la mano: lo spostamento intorno a lei conta meno.
SCONTO_CORDA_VUOTA = 0.6
# La corda più grave a vuoto è la nota di pedale dei riff (il Re basso di
# Killing in the Name): lì il premio. Le altre corde a vuoto invece un bassista
# le evita quando ha la mano in posizione, perché suonano diverse e staccano dal
# riff: su Killing in the Name il Re del riff va al 5° del La, non sul Re a vuoto.
PREMIO_CORDA_VUOTA = 1.0
MULTA_CORDA_VUOTA_ALTA = 0.6
PESO_TASTO_ALTO = 0.08
# Oltre il dodicesimo si legge peggio e si suona peggio: si evita se si può.
SOGLIA_TASTO_SCOMODO = 12
PESO_TASTO_SCOMODO = 0.5
# Più tempo passa fra due note, più la mano ha modo di spostarsi con calma.
FRETTA = 4.0


def posizioni_possibili(midi: int, strumento: Strumento) -> list[Posizione]:
    """Tutti i modi di prendere questa nota sullo strumento, dal più grave."""
    return [
        Posizione(corda=i, tasto=midi - corda)
        for i, corda in enumerate(strumento.corde)
        if 0 <= midi - corda <= strumento.tasti
    ]


def _costo_posizione(posizione: Posizione) -> float:
    costo = PESO_TASTO_ALTO * posizione.tasto
    if posizione.tasto == 0:
        costo += -PREMIO_CORDA_VUOTA if posizione.corda == 0 else MULTA_CORDA_VUOTA_ALTA
    if posizione.tasto > SOGLIA_TASTO_SCOMODO:
        costo += PESO_TASTO_SCOMODO * (posizione.tasto - SOGLIA_TASTO_SCOMODO)
    return costo


def _costo_spostamento(prima: Posizione, dopo: Posizione, pausa: float) -> float:
    salto_tasto = abs(prima.tasto - dopo.tasto)
    if prima.tasto == 0 or dopo.tasto == 0:
        salto_tasto *= SCONTO_CORDA_VUOTA
    salto_corda = abs(prima.corda - dopo.corda)
    urgenza = 1.0 / (1.0 + FRETTA * max(0.0, pausa))
    return (PESO_SALTO_TASTO * salto_tasto + PESO_SALTO_CORDA * salto_corda) * urgenza


def fuori_estensione(note: list[Nota], strumento: Strumento) -> list[Nota]:
    """Le note che su questo strumento non esistono proprio."""
    return [n for n in note if not posizioni_possibili(n.midi, strumento)]


def diteggia(note: list[Nota], strumento: Strumento) -> list[NotaSuonata]:
    """Sceglie la posizione di ogni nota tenendo la mano ferma il più possibile.

    Le note fuori estensione vengono scartate: chiedile con `fuori_estensione`
    prima di chiamare qui, se vuoi saperlo.
    """
    suonabili = [n for n in note if posizioni_possibili(n.midi, strumento)]
    suonabili.sort(key=lambda n: (n.inizio, n.midi))
    if not suonabili:
        return []

    # Viterbi: per ogni nota, il costo minimo per arrivarci in ogni posizione.
    percorsi: list[dict[Posizione, tuple[float, Posizione | None]]] = []
    for indice, nota in enumerate(suonabili):
        passo: dict[Posizione, tuple[float, Posizione | None]] = {}
        for posizione in posizioni_possibili(nota.midi, strumento):
            base = _costo_posizione(posizione)
            if indice == 0:
                passo[posizione] = (base, None)
                continue
            pausa = max(0.0, nota.inizio - suonabili[indice - 1].inizio)
            migliore, provenienza = min(
                (
                    (costo + _costo_spostamento(precedente, posizione, pausa), precedente)
                    for precedente, (costo, _) in percorsi[-1].items()
                ),
                key=lambda coppia: coppia[0],
            )
            passo[posizione] = (base + migliore, provenienza)
        percorsi.append(passo)

    # Si torna indietro dal finale più economico.
    finale = min(percorsi[-1].items(), key=lambda voce: voce[1][0])[0]
    scelte = [finale]
    for passo in reversed(percorsi[1:]):
        precedente = passo[scelte[-1]][1]
        assert precedente is not None
        scelte.append(precedente)
    scelte.reverse()

    return [NotaSuonata(nota=n, posizione=p) for n, p in zip(suonabili, scelte)]
