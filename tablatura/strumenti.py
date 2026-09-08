"""Accordature e note: il vocabolario minimo per parlare di tablature."""

from __future__ import annotations

from dataclasses import dataclass

NOMI_NOTE = ("Do", "Do#", "Re", "Re#", "Mi", "Fa", "Fa#", "Sol", "Sol#", "La", "La#", "Si")


@dataclass(frozen=True)
class Strumento:
    """Uno strumento a corde: le corde a vuoto in note MIDI, dalla più grave."""

    nome: str
    corde: tuple[int, ...]
    tasti: int = 24

    @property
    def nota_piu_grave(self) -> int:
        return min(self.corde)

    @property
    def nota_piu_acuta(self) -> int:
        return max(self.corde) + self.tasti


# Mi1 La1 Re2 Sol2 — il basso normale.
BASSO = Strumento("basso 4 corde", (28, 33, 38, 43))
# Con il Si0 sotto, per chi scende.
BASSO_5 = Strumento("basso 5 corde", (23, 28, 33, 38, 43))
CHITARRA = Strumento("chitarra", (40, 45, 50, 55, 59, 64))
CHITARRA_DROP_D = Strumento("chitarra drop D", (38, 45, 50, 55, 59, 64))

STRUMENTI = {
    "basso": BASSO,
    "basso5": BASSO_5,
    "chitarra": CHITARRA,
    "chitarra-dropd": CHITARRA_DROP_D,
}


@dataclass(frozen=True)
class Nota:
    """Una nota trascritta: altezza MIDI, inizio e durata in secondi."""

    midi: int
    inizio: float
    durata: float
    intensita: float = 0.8

    @property
    def fine(self) -> float:
        return self.inizio + self.durata

    @property
    def nome(self) -> str:
        return f"{NOMI_NOTE[self.midi % 12]}{self.midi // 12 - 1}"


@dataclass(frozen=True)
class Posizione:
    """Dove si preme una nota: indice di corda (0 = la più grave) e tasto."""

    corda: int
    tasto: int


@dataclass(frozen=True)
class NotaSuonata:
    """Una nota con la posizione scelta sul manico."""

    nota: Nota
    posizione: Posizione
