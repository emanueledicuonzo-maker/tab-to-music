"""La tablatura come si legge: corde in orizzontale, numeri sui tasti.

Due modi di disporre il tempo. Se conosci il metronomo del pezzo si usa una
griglia di battute, e viene una tablatura vera. Se non lo conosci si mette lo
spazio in proporzione alle pause: si legge peggio, ma non racconta bugie sul
ritmo.
"""

from __future__ import annotations

from .strumenti import NotaSuonata, Strumento

NOMI_CORDE = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
LARGHEZZA_CELLA = 2
CELLE_PER_RIGA = 32


def _etichette(strumento: Strumento) -> list[str]:
    """Il nome di ogni corda, incolonnato: la più acuta va in cima."""
    nomi = [NOMI_CORDE[nota % 12] for nota in strumento.corde]
    largo = max(len(n) for n in nomi)
    return [n.rjust(largo) for n in nomi]


def _cella(tasto: int | None) -> str:
    if tasto is None:
        return "-" * LARGHEZZA_CELLA
    return str(tasto).ljust(LARGHEZZA_CELLA, "-")


def allinea_partenza(partenza: float, primo: float, bpm: float, movimenti: int = 4) -> float:
    """Arretra il primo movimento di battute intere finché non precede la musica.

    Chi trova il tempo trova un battito qualsiasi, non per forza il primo del
    pezzo: se lo si prende alla lettera, tutto quello che suona prima finisce
    schiacciato nella prima casella. La griglia è periodica, quindi basta
    tornare indietro di battute intere — l'inizio di battuta resta al suo posto.
    """
    battuta = 60.0 / bpm * movimenti
    if battuta <= 0:
        return partenza
    while partenza > primo + 1e-6:
        partenza -= battuta
    return partenza


def in_griglia(
    suonate: list[NotaSuonata],
    bpm: float,
    suddivisione: int = 4,
    movimenti: int = 4,
    partenza: float = 0.0,
) -> list[list[dict[int, int]]]:
    """Incasella le note in battute di celle uguali, quantizzando i tempi.

    `suddivisione` è in quante celle si divide un movimento (4 = sedicesimi),
    `movimenti` quanti movimenti ha una battuta, `partenza` il secondo in cui
    cade il primo movimento del pezzo.
    """
    if bpm <= 0:
        raise ValueError("il metronomo dev'essere un numero positivo")
    cella = 60.0 / bpm / suddivisione
    per_battuta = movimenti * suddivisione
    if suonate:
        partenza = allinea_partenza(partenza, min(s.nota.inizio for s in suonate), bpm, movimenti)

    caselle: dict[int, dict[int, int]] = {}
    for suonata in suonate:
        indice = round((suonata.nota.inizio - partenza) / cella)
        caselle.setdefault(indice, {})[suonata.posizione.corda] = suonata.posizione.tasto

    if not caselle:
        return []
    battute = max(caselle) // per_battuta + 1
    return [
        [caselle.get(b * per_battuta + i, {}) for i in range(per_battuta)]
        for b in range(battute)
    ]


def _posizioni(inizio: int, quante: int, stanghette: set[int], base: int) -> dict[int, int]:
    """A che colonna di caratteri finisce ogni cella, stanghette comprese."""
    x, posizioni = base, {}
    for i in range(inizio, inizio + quante):
        if i in stanghette and i != inizio:
            x += 1
        posizioni[i] = x
        x += LARGHEZZA_CELLA
    return posizioni


def _riga_parole(parole: dict[int, str], posizioni: dict[int, int]) -> str:
    """Le parole incolonnate sotto la cella in cui si cantano.

    Chi non ci sta senza pestare la parola prima slitta a destra: meglio una
    sillaba fuori posto di due parole appiccicate che non si leggono.
    """
    riga = ""
    for cella in sorted(parole):
        if cella not in posizioni:
            continue
        dove = max(posizioni[cella], len(riga) + 1 if riga else 0)
        riga = riga.ljust(dove) + parole[cella]
    return riga


def _disegna_colonne(
    colonne: list[dict[int, int]],
    strumento: Strumento,
    stanghette: set[int],
    celle_per_riga: int,
    parole: dict[int, str] | None = None,
) -> str:
    etichette = _etichette(strumento)
    corde = list(reversed(range(len(strumento.corde))))  # l'acuta in cima
    base = len(etichette[0]) + 1
    righe: list[str] = []

    for inizio in range(0, max(1, len(colonne)), celle_per_riga):
        fetta = colonne[inizio : inizio + celle_per_riga]
        blocco = []
        for corda in corde:
            pezzi = [f"{etichette[corda]}|"]
            for i, colonna in enumerate(fetta, start=inizio):
                if i in stanghette and i != inizio:
                    pezzi.append("|")
                pezzi.append(_cella(colonna.get(corda)))
            pezzi.append("|")
            blocco.append("".join(pezzi))
        if parole:
            posizioni = _posizioni(inizio, len(fetta), stanghette, base)
            dette = {c: p for c, p in parole.items() if c in posizioni}
            if dette:
                blocco.append(_riga_parole(dette, posizioni))
        righe.append("\n".join(blocco))
    return "\n\n".join(righe)


def a_battute(
    suonate: list[NotaSuonata],
    strumento: Strumento,
    bpm: float,
    suddivisione: int = 4,
    movimenti: int = 4,
    partenza: float = 0.0,
    battute_per_riga: int = 4,
    parole: dict[int, str] | None = None,
) -> str:
    """Tablatura in battute, con le stanghette al posto giusto.

    Le `parole` vanno incasellate con la stessa `partenza` di qui, altrimenti
    finiscono sotto la nota sbagliata: `allinea_partenza` dà quella buona.
    """
    battute = in_griglia(suonate, bpm, suddivisione, movimenti, partenza)
    if not battute:
        return "(nessuna nota)"
    per_battuta = movimenti * suddivisione
    colonne = [colonna for battuta in battute for colonna in battuta]
    stanghette = {i * per_battuta for i in range(len(battute))}
    return _disegna_colonne(
        colonne, strumento, stanghette, per_battuta * battute_per_riga, parole
    )


def disegna_battute(
    battute: list[list[dict[int, int]]],
    strumento: Strumento,
    battute_per_riga: int = 4,
    parole: dict[int, str] | None = None,
) -> str:
    """Disegna solo le battute che le si danno, con le loro stanghette."""
    if not battute:
        return "(nessuna nota)"
    per_battuta = len(battute[0])
    colonne = [colonna for battuta in battute for colonna in battuta]
    stanghette = {i * per_battuta for i in range(len(battute))}
    return _disegna_colonne(
        colonne, strumento, stanghette, per_battuta * battute_per_riga, parole
    )


def a_proporzione(
    suonate: list[NotaSuonata],
    strumento: Strumento,
    celle_al_secondo: float = 8.0,
    celle_per_riga: int = CELLE_PER_RIGA,
) -> str:
    """Tablatura senza battute: lo spazio segue il tempo, non il metro."""
    if not suonate:
        return "(nessuna nota)"
    primo = suonate[0].nota.inizio
    caselle: dict[int, dict[int, int]] = {}
    for suonata in suonate:
        indice = max(0, round((suonata.nota.inizio - primo) * celle_al_secondo))
        caselle.setdefault(indice, {})[suonata.posizione.corda] = suonata.posizione.tasto
    colonne = [caselle.get(i, {}) for i in range(max(caselle) + 1)]
    return _disegna_colonne(colonne, strumento, set(), celle_per_riga)
