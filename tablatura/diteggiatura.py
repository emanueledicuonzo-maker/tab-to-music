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
PESO_TASTO_ALTO = 0.03
# Oltre il dodicesimo si legge peggio e si suona peggio: si evita se si può.
SOGLIA_TASTO_SCOMODO = 12
PESO_TASTO_SCOMODO = 0.5
# Saltare una corda (dal Re basso al Re, scavalcando il La) costa più che passare
# a quella accanto: su Killing in the Name il Mi bemolle dopo il Re basso a
# vuoto va al 6° del La, la corda vicina, non al 1° del Re.
PESO_SCAVALCO = 0.5
# La mano copre quattro tasti, un dito per tasto: dentro quella finestra non si muove.
DITA = 4
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


def _sposta_mano(mano: int | None, tasto: int) -> tuple[int, int | None]:
    """Di quanti tasti si sposta la mano per prendere `tasto`, e dove finisce.

    `mano` è il tasto sotto l'indice: la mano copre da lì ai tre tasti dopo.
    """
    if tasto == 0:
        return 0, mano
    if mano is None:
        return 0, tasto
    if mano <= tasto <= mano + DITA - 1:
        return 0, mano
    if tasto > mano + DITA - 1:
        return tasto - (mano + DITA - 1), tasto - (DITA - 1)
    return mano - tasto, tasto


def _costo_mano(mano: int | None, dopo: Posizione, corda_prima: int, pausa: float) -> float:
    """Quanto costa arrivare a `dopo` con la mano ferma al tasto `mano`.

    La corda a vuoto non sposta la mano: dopo il Re basso a vuoto di Killing
    in the Name la mano è ancora al 5° tasto, e il Mi bemolle che segue si
    prende al 6° del La, non al 1° del Re. Per questo la mano si ricorda
    dell'ultima nota tastata, e lo spostamento si misura da lì.
    """
    urgenza = 1.0 / (1.0 + FRETTA * max(0.0, pausa))
    salto_corda = abs(corda_prima - dopo.corda)
    salto_tasto, _ = _sposta_mano(mano, dopo.tasto)
    # Lo spostamento della mano si fa con calma se c'è tempo; la scelta della
    # corda no, quella dipende da come si suona il giro.
    return PESO_SALTO_TASTO * salto_tasto * urgenza + PESO_SALTO_CORDA * salto_corda + PESO_SCAVALCO * max(0, salto_corda - 1)


def diteggia(note: list[Nota], strumento: Strumento) -> list[NotaSuonata]:
    """Sceglie la posizione di ogni nota tenendo la mano ferma il più possibile.

    Le note fuori estensione vengono scartate: chiedile con `fuori_estensione`
    prima di chiamare qui, se vuoi saperlo. Lo stato di ogni passo è la
    posizione della nota più il tasto dove sta la mano (che una corda a vuoto
    non cambia).
    """
    suonabili = [n for n in note if posizioni_possibili(n.midi, strumento)]
    suonabili.sort(key=lambda n: (n.inizio, n.midi))
    if not suonabili:
        return []

    Stato = tuple[Posizione, "int | None"]
    percorsi: list[dict[Stato, tuple[float, Stato | None]]] = []
    for indice, nota in enumerate(suonabili):
        passo: dict[Stato, tuple[float, Stato | None]] = {}
        for posizione in posizioni_possibili(nota.midi, strumento):
            base = _costo_posizione(posizione)
            if indice == 0:
                stato = (posizione, posizione.tasto or None)
                passo[stato] = (base, None)
                continue
            pausa = max(0.0, nota.inizio - suonabili[indice - 1].inizio)
            for precedente, (costo, _) in percorsi[-1].items():
                pos_prima, mano = precedente
                totale = costo + base + _costo_mano(mano, posizione, pos_prima.corda, pausa)
                stato = (posizione, _sposta_mano(mano, posizione.tasto)[1])
                if stato not in passo or totale < passo[stato][0]:
                    passo[stato] = (totale, precedente)
        percorsi.append(passo)

    # Si torna indietro dal finale più economico.
    finale = min(percorsi[-1].items(), key=lambda voce: voce[1][0])[0]
    scelte = [finale]
    for passo in reversed(percorsi[1:]):
        precedente = passo[scelte[-1]][1]
        assert precedente is not None
        scelte.append(precedente)
    scelte.reverse()

    return [NotaSuonata(nota=n, posizione=stato[0]) for n, stato in zip(suonabili, scelte)]
