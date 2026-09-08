"""Prove sul riconoscimento dell'ottava, su segnali costruiti apposta.

Il caso da distinguere è quello vero: una corda di basso la cui fondamentale
è stata mangiata da un diffusore piccolo o dalla compressione. L'orecchio la
sente lo stesso, il trascrittore no e scrive un'ottava sopra.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tablatura.ottava import ci_sta, ottava_giusta, quota_sotto, sposta
from tablatura.strumenti import BASSO, Nota

FC = 44100
DURATA = 1.0


def _corda(midi, armoniche, con_fondamentale=True):
    """Una corda che vibra: fondamentale e multipli, o solo i multipli."""
    f = 440.0 * 2 ** ((midi - 69) / 12)
    t = np.linspace(0, DURATA, int(FC * DURATA), endpoint=False)
    prime = 1 if con_fondamentale else 2
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(prime, armoniche + 1))


def test_una_linea_giusta_resta_dov_e():
    # Mi1 con tutte le sue armoniche, e scritto Mi1: niente da correggere.
    onda = _corda(28, 6)
    note = [Nota(28, 0.0, DURATA)]
    assert quota_sotto(onda, FC, note) < 0.25
    assert ottava_giusta(onda, FC, note, BASSO) == 0


def test_la_fondamentale_mangiata_si_riconosce():
    # La corda vibra a Mi1 ma la fondamentale non c'è: restano 82, 123, 164…
    # Il trascrittore scrive Mi2, un'ottava sopra. Le armoniche lo smentiscono.
    onda = _corda(28, 6, con_fondamentale=False)
    scritte = [Nota(40, 0.0, DURATA)]  # Mi2 invece di Mi1
    assert quota_sotto(onda, FC, scritte) > 0.25
    assert ottava_giusta(onda, FC, scritte, BASSO) == -1


def test_la_fondamentale_debole_si_riconosce():
    # Caso più comune: la fondamentale c'è ma è schiacciata.
    onda = _corda(28, 6, con_fondamentale=False) + 0.1 * _corda(28, 1)
    scritte = [Nota(40, 0.0, DURATA)]
    assert ottava_giusta(onda, FC, scritte, BASSO) == -1


def test_non_si_scende_sotto_la_corda_piu_grave():
    # Un Mi1 è già la nota più bassa del basso: sotto non si può andare,
    # quindi era giusta com'era anche se le armoniche dicessero altro.
    onda = _corda(28, 6, con_fondamentale=False)
    assert not ci_sta([Nota(28, 0.0, DURATA)], BASSO, -1)
    assert ottava_giusta(onda, FC, [Nota(28, 0.0, DURATA)], BASSO) == 0


def test_spostare_non_tocca_i_tempi():
    note = [Nota(40, 1.5, 0.4, 0.7)]
    giu = sposta(note, -1)
    assert giu[0].midi == 28
    assert (giu[0].inizio, giu[0].durata, giu[0].intensita) == (1.5, 0.4, 0.7)


def test_senza_note_non_si_sposta_niente():
    assert ottava_giusta(np.zeros(FC), FC, [], BASSO) == 0
    assert quota_sotto(np.zeros(FC), FC, []) == 0.0
