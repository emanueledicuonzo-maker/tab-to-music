"""Ripulire quello che sputa fuori un trascrittore automatico.

Un modello audio→MIDI sbaglia sempre nello stesso modo: schegge di note da
trenta millisecondi, la stessa nota spezzata in due, e il fantasma un'ottava
sopra o sotto quella giusta. Su una linea di basso, che è quasi sempre una
nota alla volta, queste tre pulizie da sole cambiano la faccia al risultato.
"""

from __future__ import annotations

from .strumenti import Nota

DURATA_MINIMA = 0.06
BUCO_TRASCURABILE = 0.05
# Un pezzo più corto di così non è una nota: è la coda di quella prima.
FRAMMENTO = 0.15
# Sotto questa distanza due attacchi sono lo stesso attacco, non due note.
STESSO_ATTACCO = 0.06
# Quanti semitoni sopra la fondamentale cadono le sue prime armoniche.
ARMONICHE = (12, 19, 24, 28, 31, 34, 36)
TOLLERANZA_ARMONICA = 1


def scarta_briciole(note: list[Nota], durata_minima: float = DURATA_MINIMA) -> list[Nota]:
    """Via le note troppo corte per essere state suonate davvero."""
    return [n for n in note if n.durata >= durata_minima]


def unisci_ripetizioni(
    note: list[Nota], buco: float = BUCO_TRASCURABILE, frammento: float = FRAMMENTO
) -> list[Nota]:
    """Riattacca la stessa nota spezzata in due dal trascrittore.

    Attenzione a non esagerare: due Mi uguali suonati uno dopo l'altro sono
    due note, e fonderli vuol dire perdere una pulsazione del pezzo. Si
    riattacca solo quando uno dei due pezzi è troppo corto per essere una
    nota vera, cioè quando è chiaramente la coda dell'altro.
    """
    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    unite: list[Nota] = []
    for nota in ordinate:
        gemella = next(
            (
                i
                for i, precedente in enumerate(unite)
                if precedente.midi == nota.midi
                and 0 <= nota.inizio - precedente.fine <= buco
                and min(precedente.durata, nota.durata) < frammento
            ),
            None,
        )
        if gemella is None:
            unite.append(nota)
            continue
        precedente = unite[gemella]
        unite[gemella] = Nota(
            midi=precedente.midi,
            inizio=precedente.inizio,
            durata=max(precedente.fine, nota.fine) - precedente.inizio,
            intensita=max(precedente.intensita, nota.intensita),
        )
    return unite


def _e_armonica(sopra: int, sotto: int) -> bool:
    intervallo = sopra - sotto
    return any(abs(intervallo - a) <= TOLLERANZA_ARMONICA for a in ARMONICHE)


def scarta_armonici(note: list[Nota]) -> list[Nota]:
    """Toglie i fantasmi che il modello sente sopra la nota vera.

    Una corda di basso non produce solo la sua nota: produce anche l'ottava,
    la dodicesima, la doppia ottava. Il trascrittore le sente e le scrive come
    note a sé. Si riconoscono da tre cose insieme: partono mentre la nota
    grave sta ancora suonando, stanno a un intervallo di armonica esatto sopra
    di lei, e sono più deboli. Tutte e tre, o non si tocca niente: un salto
    d'ottava suonato davvero non ha nessuna di queste caratteristiche.
    """
    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    tenute: list[Nota] = []
    for nota in ordinate:
        fondamentale = next(
            (
                f
                for f in reversed(tenute)
                if f.midi < nota.midi
                and f.inizio <= nota.inizio < f.fine
                and _e_armonica(nota.midi, f.midi)
                and _peso(nota) < _peso(f)
            ),
            None,
        )
        if fondamentale is None:
            tenute.append(nota)
    return tenute


def _peso(nota: Nota) -> float:
    """Quanto una nota «pesa»: il fantasma di ottava è corto e debole."""
    return nota.durata * nota.intensita


def monofonico(note: list[Nota]) -> list[Nota]:
    """Tiene una nota alla volta, senza mangiarsi le note lunghe.

    Due note che partono insieme sono lo stesso attacco: una delle due è il
    fantasma di ottava del modello, e vince quella che pesa di più. Una nota
    che parte mentre la precedente sta ancora suonando, invece, è una nota
    nuova: si tiene, e si accorcia quella prima fino al suo attacco.
    """
    ordinate = sorted(note, key=lambda n: (n.inizio, n.midi))
    tenute: list[Nota] = []
    for nota in ordinate:
        if tenute and nota.inizio - tenute[-1].inizio <= STESSO_ATTACCO:
            ultima = tenute[-1]
            if (_peso(nota), -nota.midi) > (_peso(ultima), -ultima.midi):
                tenute[-1] = nota
            continue
        tenute.append(nota)

    # Nessuna nota deve sconfinare nella successiva: la si accorcia.
    for i in range(len(tenute) - 1):
        if tenute[i].fine > tenute[i + 1].inizio:
            tenute[i] = Nota(
                midi=tenute[i].midi,
                inizio=tenute[i].inizio,
                durata=tenute[i + 1].inizio - tenute[i].inizio,
                intensita=tenute[i].intensita,
            )
    return tenute


def ripulisci(note: list[Nota], una_nota_alla_volta: bool = True) -> list[Nota]:
    """Le tre pulizie in fila, nell'ordine che fa meno danni."""
    pulite = scarta_armonici(unisci_ripetizioni(scarta_briciole(note)))
    return monofonico(pulite) if una_nota_alla_volta else sorted(pulite, key=lambda n: n.inizio)
