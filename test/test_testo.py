"""Prove sull'incolonnamento delle parole sotto la tablatura."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tablatura.disegno import a_battute
from tablatura.diteggiatura import diteggia
from tablatura.strumenti import BASSO, Nota
from tablatura.testo import Parola, in_celle


def test_le_parole_cadono_nella_casella_giusta():
    # A 100 bpm il sedicesimo dura 0.15 s: 0.31 sta nella casella 2.
    parole = [Parola("una", 0.0, 0.2), Parola("due", 0.31, 0.2)]
    assert in_celle(parole, bpm=100) == {0: "una", 2: "due"}


def test_due_parole_nella_stessa_casella_restano_attaccate():
    parole = [Parola("sopra", 0.0, 0.1), Parola("questo", 0.02, 0.1)]
    assert in_celle(parole, bpm=100) == {0: "sopra questo"}


def test_le_parole_prima_dell_inizio_si_scartano():
    assert in_celle([Parola("prima", 0.0, 0.1)], bpm=100, partenza=5.0) == {}


def test_la_riga_di_testo_sta_sotto_la_nota():
    note = [Nota(28, 0.0, 0.5), Nota(33, 0.6, 0.5)]
    parole = in_celle([Parola("qui", 0.0, 0.2), Parola("la", 0.6, 0.2)], bpm=100)
    tab = a_battute(diteggia(note, BASSO), BASSO, bpm=100, parole=parole)
    righe = tab.splitlines()
    assert len(righe) == 5  # quattro corde più il testo
    testo, mi = righe[-1], righe[-2]
    # «qui» comincia esattamente sotto lo zero della prima nota.
    assert testo.index("qui") == mi.index("0")


def test_una_parola_lunga_non_pesta_quella_dopo():
    # Due parole in caselle vicine: la seconda slitta invece di sovrapporsi.
    note = [Nota(28, 0.0, 0.1), Nota(33, 0.15, 0.1)]
    parole = in_celle([Parola("lunghissima", 0.0, 0.1), Parola("poi", 0.15, 0.1)], bpm=100)
    riga = a_battute(diteggia(note, BASSO), BASSO, bpm=100, parole=parole).splitlines()[-1]
    assert "lunghissima poi" in riga
    assert "lunghissimapoi" not in riga


def test_senza_parole_la_tablatura_e_quella_di_prima():
    suonate = diteggia([Nota(28, 0.0, 0.5)], BASSO)
    assert len(a_battute(suonate, BASSO, bpm=100).splitlines()) == 4
