"""Trovare il giro che si ripete, e dire solo quello.

Un basso che tiene lo stesso ostinato per sette minuti riempie duecento
battute identiche: stampate tutte non si leggono, e chi deve impararle vuole
sapere due cose sole — com'è il giro, e dove cambia. Qui si cerca il periodo
con cui le battute si somigliano, si mostra il giro una volta, e si elencano
i punti in cui il bassista ha fatto qualcosa di diverso.

Il confronto è per somiglianza, non per uguaglianza: una nota che il
trascrittore mette un sedicesimo più in là non deve trasformare una
ripetizione in un'eccezione.
"""

from __future__ import annotations

from dataclasses import dataclass

# Due battute sono «la stessa» se questa quota di note coincide.
SOMIGLIANZA = 0.8
# Una nota che il trascrittore mette un sedicesimo più in là resta la stessa
# nota: senza questa tolleranza un ostinato perfetto non si riconosce, perché
# basta un attacco letto storto per far sembrare diverse due battute uguali.
TOLLERANZA_CELLE = 1
# Quanto del pezzo deve tornare, perché si possa parlare di un giro.
QUOTA_MINIMA = 0.6
PERIODI = (1, 2, 4, 8)

Battuta = list[dict[int, int]]


def firma(battuta: Battuta) -> frozenset[tuple[int, int, int]]:
    """Le note di una battuta come insieme di (cella, corda, tasto)."""
    return frozenset(
        (cella, corda, tasto)
        for cella, colonna in enumerate(battuta)
        for corda, tasto in colonna.items()
    )


def somiglianza(prima: Battuta, dopo: Battuta, tolleranza: int = TOLLERANZA_CELLE) -> float:
    """Da 0 a 1: quanta parte delle due battute è la stessa musica.

    Due note sono la stessa se stanno sulla stessa corda allo stesso tasto e
    a non più di `tolleranza` celle di distanza. L'accoppiamento è uno a uno:
    una nota sola non può giustificare due note dell'altra battuta.
    """
    a = sorted(firma(prima))
    b = sorted(firma(dopo))
    if not a and not b:
        return 1.0
    libere = list(b)
    trovate = 0
    for cella, corda, tasto in a:
        for i, (altra_cella, altra_corda, altro_tasto) in enumerate(libere):
            if (corda, tasto) == (altra_corda, altro_tasto) and abs(altra_cella - cella) <= tolleranza:
                libere.pop(i)
                trovate += 1
                break
    return trovate / max(len(a), len(b))


@dataclass(frozen=True)
class Giro:
    """Il giro trovato: quanto è lungo, quante volte torna, dove non torna."""

    periodo: int
    ripetizioni: int
    battute_totali: int
    eccezioni: tuple[int, ...]

    @property
    def quota(self) -> float:
        return self.ripetizioni / max(1, self.battute_totali - self.periodo)


def cerca(
    battute: list[Battuta],
    periodi: tuple[int, ...] = PERIODI,
    soglia: float = SOMIGLIANZA,
    quota_minima: float = QUOTA_MINIMA,
) -> Giro | None:
    """Il giro più corto che regge su abbastanza pezzo, o niente.

    Si prova un periodo alla volta, dal più corto, e si conta quante battute
    somigliano a quella di un giro prima. Il primo che tiene vince: fra un
    giro di una battuta e uno di quattro che spiegano lo stesso pezzo, quello
    da imparare è il primo.
    """
    piene = [i for i, b in enumerate(battute) if firma(b)]
    if len(piene) < 4:
        return None

    for periodo in periodi:
        if len(battute) <= periodo:
            continue
        confronti = range(periodo, len(battute))
        eccezioni = tuple(
            i for i in confronti if somiglianza(battute[i - periodo], battute[i]) < soglia
        )
        ripetizioni = len(confronti) - len(eccezioni)
        giro = Giro(periodo, ripetizioni, len(battute), eccezioni)
        if giro.quota >= quota_minima:
            return giro
    return None


def rappresentativo(battute: list[Battuta], giro: Giro, soglia: float = SOMIGLIANZA) -> int:
    """Da quale battuta prendere il giro da mostrare.

    Non sempre è la prima: un pezzo può cominciare con mezza battuta di
    attacco, e mostrare quella al posto del giro sarebbe fuorviante. Si
    cerca la prima occorrenza che torna identica anche il giro dopo.
    """
    for inizio in range(len(battute) - 2 * giro.periodo + 1):
        if all(
            somiglianza(battute[inizio + k], battute[inizio + giro.periodo + k]) >= soglia
            for k in range(giro.periodo)
        ):
            return inizio
    return 0


def confronta(battute: list[Battuta], periodo: int, inizio: int, soglia: float = SOMIGLIANZA) -> Giro:
    """Misura ogni battuta contro il giro di riferimento, non contro la vicina.

    Confrontando ogni battuta con quella prima, un cambio solo ne segnala due:
    quella diversa, e quella dopo che torna al giro. Contro il riferimento
    invece si segnala quello che è cambiato davvero.
    """
    riferimento = battute[inizio : inizio + periodo]
    eccezioni = tuple(
        i
        for i, battuta in enumerate(battute)
        if somiglianza(riferimento[(i - inizio) % periodo], battuta) < soglia
    )
    return Giro(periodo, len(battute) - len(eccezioni), len(battute), eccezioni)


def analizza(battute: list[Battuta], **opzioni) -> tuple[Giro, int] | None:
    """Il giro, e da dove mostrarlo. Niente, se il pezzo non si ripete."""
    grezzo = cerca(battute, **opzioni)
    if grezzo is None:
        return None
    inizio = rappresentativo(battute, grezzo)
    return confronta(battute, grezzo.periodo, inizio), inizio


def riassunto(giro: Giro | None, movimenti: int = 4) -> str:
    """Una riga in italiano su cosa si è trovato."""
    if giro is None:
        return "Nessun giro che si ripeta: la tablatura va letta tutta."
    battute = "battuta" if giro.periodo == 1 else f"{giro.periodo} battute"
    testo = f"Giro di {battute}, uguale in {giro.ripetizioni} battute su {giro.battute_totali}."
    if not giro.eccezioni:
        return testo + " Non cambia mai."
    quali = ", ".join(str(i + 1) for i in giro.eccezioni[:8])
    if len(giro.eccezioni) > 8:
        quali += f" e altre {len(giro.eccezioni) - 8}"
    return testo + f" Cambia alle battute {quali}."
